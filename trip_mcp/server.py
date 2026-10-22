"""Weather & Trip Planner MCP server (FastMCP).

Exactly three tools, one per category:
  * get_weather_forecast  - DATA tool: reads a forecast, changes nothing.
  * save_trip             - ACTION tool: persists a trip to the trip store.
  * plan_trip             - ORCHESTRATION tool: calls the two tools above and combines their results.
Plus two read-only resources: trips://saved and trips://{trip_id}.

Run over stdio (default, used by the agent):  python -m trip_mcp.server
Run over Streamable HTTP:                     python -m trip_mcp.server --http --port 8000
"""

import argparse
import datetime as dt
import json
import logging
import sys
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError, ValidationError
from pydantic import Field

from trip_mcp import weather
from trip_mcp.models import Forecast, SavedTrip, TripPlan
from trip_mcp.planning import build_packing_list, summarize
from trip_mcp.storage import StorageError, TripStore

NOTES_MAX = 2000

# Server-side logs go to stderr: the stdio transport owns stdout, and the host's terminal shows stderr.
log = logging.getLogger("trip_mcp")

mcp = FastMCP(
    name="trip-planner",
    instructions=(
        "Weather-aware trip planning. Use get_weather_forecast to look up weather, save_trip to store a "
        "trip the user has fully specified, and plan_trip to produce a saved plan in one step."
    ),
)

City = Annotated[
    str,
    Field(
        min_length=2,
        max_length=100,
        description="City name, optionally followed by a comma and the country or region, "
        "e.g. 'Beirut' or 'Tripoli, Lebanon'.",
    ),
]
Days = Annotated[int, Field(ge=1, le=7, description="Number of consecutive days, from 1 to 7.")]


@mcp.tool(
    annotations={
        "title": "Get weather forecast",
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def get_weather_forecast(
    city: City,
    start_date: Annotated[
        dt.date | None,
        Field(description="First day to forecast (YYYY-MM-DD). Defaults to today."),
    ] = None,
    days: Days = 3,
) -> Forecast:
    """Look up the daily weather forecast for a city.

    DATA tool: read-only, it never saves or changes anything. Use it for any question about the weather.
    The forecast covers today through the next 15 days. Fails with a clear error when the city cannot be
    found, the dates fall outside the forecast window, or the weather service is unavailable.
    """
    start_date = start_date or dt.date.today()
    log.info("get_weather_forecast(city=%r, start_date=%s, days=%d)", city, start_date, days)
    try:
        forecast = await weather.get_forecast(city, start_date, days)
    except weather.WeatherError as e:
        log.info("  get_weather_forecast -> ERROR: %s", e)
        raise ToolError(str(e)) from e
    log.info("  get_weather_forecast -> %d day(s) for %s, %s", len(forecast.days), forecast.city, forecast.country)
    return forecast


@mcp.tool(
    annotations={
        "title": "Save trip",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
def save_trip(
    city: City,
    start_date: Annotated[dt.date, Field(description="First day of the trip (YYYY-MM-DD).")],
    end_date: Annotated[dt.date, Field(description="Last day of the trip, inclusive (YYYY-MM-DD).")],
    notes: Annotated[str, Field(max_length=NOTES_MAX, description="Optional free-text notes.")] = "",
) -> SavedTrip:
    """Save one trip to the user's trip list.

    ACTION tool: it writes to the trip store and returns the saved trip with its new id. It does not look
    up weather. Fails with a clear error when end_date is before start_date, the same trip (city and
    dates) is already saved, or the trip store cannot be read or written.
    """
    log.info("save_trip(city=%r, start_date=%s, end_date=%s)", city, start_date, end_date)
    try:
        trip = TripStore().add(city, start_date, end_date, notes)
    except StorageError as e:
        log.info("  save_trip -> ERROR: %s", e)
        raise ToolError(str(e)) from e
    log.info("  save_trip -> saved %s", trip.id)
    return trip


@mcp.tool(
    annotations={
        "title": "Plan trip",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def plan_trip(
    city: City,
    start_date: Annotated[dt.date, Field(description="First day of the trip (YYYY-MM-DD).")],
    days: Days = 3,
) -> TripPlan:
    """Create a saved, weather-aware trip plan for a city.

    ORCHESTRATION tool: step 1 calls get_weather_forecast, step 2 turns the forecast into a summary and a
    packing list, step 3 calls save_trip. Use it when the user wants a trip planned; there is no need to
    call the other two tools first. If step 1 fails, nothing is saved.
    """
    log.info("plan_trip(city=%r, start_date=%s, days=%d)", city, start_date, days)
    steps: list[str] = []

    try:
        result = await mcp.call_tool(
            "get_weather_forecast", {"city": city, "start_date": start_date.isoformat(), "days": days}
        )
    except (ToolError, ValidationError) as e:
        log.info("  plan_trip -> stopped at step 1")
        raise ToolError(f"plan_trip stopped at step 1 (get_weather_forecast): {e} Nothing was saved.") from e
    forecast = Forecast.model_validate(result.structured_content)
    steps.append(f"1. get_weather_forecast: {len(forecast.days)} day(s) for {forecast.city}, {forecast.country}")

    packing = build_packing_list(forecast)
    summary = summarize(forecast)
    steps.append(f"2. combined the forecast into a summary and {len(packing)} packing item(s)")

    notes = f"{summary} Pack: {', '.join(packing)}."[:NOTES_MAX]
    try:
        result = await mcp.call_tool(
            "save_trip",
            {
                "city": forecast.city,
                "start_date": forecast.days[0].date.isoformat(),
                "end_date": forecast.days[-1].date.isoformat(),
                "notes": notes,
            },
        )
    except (ToolError, ValidationError) as e:
        log.info("  plan_trip -> stopped at step 3")
        raise ToolError(
            f"plan_trip got the forecast, but step 3 (save_trip) failed: {e} The plan was not saved."
        ) from e
    trip = SavedTrip.model_validate(result.structured_content)
    steps.append(f"3. save_trip: saved as {trip.id}")

    log.info("  plan_trip -> done (%s)", trip.id)
    return TripPlan(trip=trip, forecast=forecast, packing_list=packing, summary=summary, steps=steps)


@mcp.resource(
    "trips://saved",
    name="saved_trips",
    description="All saved trips as a JSON list (read-only).",
    mime_type="application/json",
)
def saved_trips() -> str:
    try:
        trips = TripStore().load()
    except StorageError as e:
        raise ResourceError(str(e)) from e
    return json.dumps([t.model_dump(mode="json") for t in trips], indent=2, ensure_ascii=False)


@mcp.resource(
    "trips://{trip_id}",
    name="saved_trip",
    description="One saved trip by id, e.g. trips://trip-0001 (read-only).",
    mime_type="application/json",
)
def saved_trip(trip_id: str) -> str:
    try:
        trip = TripStore().get(trip_id)
    except StorageError as e:
        raise ResourceError(str(e)) from e
    return trip.model_dump_json(indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weather & Trip Planner MCP server")
    parser.add_argument("--http", action="store_true", help="serve Streamable HTTP instead of stdio")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("    [server] %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False

    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=args.port, show_banner=False)
    else:
        mcp.run(show_banner=False)


if __name__ == "__main__":
    main()
