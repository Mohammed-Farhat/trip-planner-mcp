"""Each tool's happy path and its predictable failure cases, through an in-memory MCP client."""

import datetime as dt
import json

import httpx2

from conftest import SOON, TODAY, call_error
from trip_mcp import weather

# ---------- the toolkit as a whole ----------


async def test_server_exposes_exactly_three_tools(client):
    tools = {t.name: t for t in await client.list_tools()}
    assert set(tools) == {"get_weather_forecast", "save_trip", "plan_trip"}

    assert tools["get_weather_forecast"].annotations.read_only_hint is True  # Data
    assert tools["save_trip"].annotations.read_only_hint is False  # Action
    assert tools["save_trip"].annotations.destructive_hint is False
    assert tools["plan_trip"].annotations.read_only_hint is False  # Orchestration


async def test_every_tool_is_documented_and_typed(client):
    for tool in await client.list_tools():
        assert tool.description and len(tool.description) > 40, tool.name
        assert tool.output_schema, f"{tool.name} has no typed output"
        for name, prop in tool.input_schema["properties"].items():
            assert prop.get("description"), f"{tool.name}.{name} has no description"


# ---------- Data tool: get_weather_forecast ----------


async def test_forecast_returns_typed_days(client):
    result = await client.call_tool("get_weather_forecast", {"city": "Beirut", "start_date": str(SOON), "days": 3})
    data = result.structured_content
    assert (data["city"], data["country"]) == ("Beirut", "Lebanon")
    assert [d["date"] for d in data["days"]] == [str(SOON + dt.timedelta(days=i)) for i in range(3)]
    assert data["days"][1]["condition"] == "Slight rain"
    assert data["days"][1]["precip_probability_pct"] == 80


async def test_forecast_defaults_to_today(client):
    result = await client.call_tool("get_weather_forecast", {"city": "Beirut", "days": 1})
    assert result.structured_content["days"][0]["date"] == str(TODAY)


async def test_forecast_country_qualifier_picks_the_right_city(client):
    result = await client.call_tool("get_weather_forecast", {"city": "Tripoli, Lebanon", "days": 1})
    assert result.structured_content["country"] == "Lebanon"


async def test_forecast_unknown_city_is_a_clear_error(client):
    error = await call_error(client, "get_weather_forecast", {"city": "Xyzzyville"})
    assert "No city named 'Xyzzyville' was found" in error


async def test_forecast_rejects_dates_beyond_the_window(client, fake_api):
    error = await call_error(client, "get_weather_forecast", {"city": "Beirut", "start_date": str(TODAY + dt.timedelta(days=40))})
    assert "The forecast only reaches" in error
    assert fake_api.requests == []  # rejected before any network call


async def test_forecast_rejects_past_dates(client):
    error = await call_error(client, "get_weather_forecast", {"city": "Beirut", "start_date": str(TODAY - dt.timedelta(days=1))})
    assert "is in the past" in error


async def test_forecast_rejects_out_of_range_days(client):
    error = await call_error(client, "get_weather_forecast", {"city": "Beirut", "days": 99})
    assert "less than or equal to 7" in error


async def test_forecast_timeout_is_retried_then_reported(client, fake_api):
    fake_api.fail_with = httpx2.ReadTimeout("timed out")
    error = await call_error(client, "get_weather_forecast", {"city": "Beirut"})
    assert "Weather service unavailable" in error and f"tried {weather.ATTEMPTS} times" in error
    assert len(fake_api.requests) == weather.ATTEMPTS


async def test_forecast_server_error_is_reported(client, fake_api):
    fake_api.fail_with = 503
    error = await call_error(client, "get_weather_forecast", {"city": "Beirut"})
    assert "HTTP 503" in error


async def test_forecast_never_writes_the_trip_store(client, trips_file):
    await client.call_tool("get_weather_forecast", {"city": "Beirut"})
    assert not trips_file.exists()


# ---------- Action tool: save_trip ----------


def trip_args(**overrides):
    return {"city": "Byblos", "start_date": str(SOON), "end_date": str(SOON + dt.timedelta(days=1)),
            "notes": "Citadel", **overrides}


async def test_save_trip_persists_and_returns_id(client, trips_file):
    result = await client.call_tool("save_trip", trip_args())
    assert result.structured_content["id"] == "trip-0001"
    stored = json.loads(trips_file.read_text(encoding="utf-8"))
    assert [(t["id"], t["city"], t["notes"]) for t in stored] == [("trip-0001", "Byblos", "Citadel")]


async def test_save_trip_assigns_increasing_ids(client):
    await client.call_tool("save_trip", trip_args())
    result = await client.call_tool("save_trip", trip_args(city="Tyre"))
    assert result.structured_content["id"] == "trip-0002"


async def test_save_trip_rejects_end_before_start(client, trips_file):
    error = await call_error(client, "save_trip", trip_args(end_date=str(SOON - dt.timedelta(days=1))))
    assert "is before start_date" in error
    assert not trips_file.exists()


async def test_save_trip_rejects_duplicates(client, trips_file):
    await client.call_tool("save_trip", trip_args())
    error = await call_error(client, "save_trip", trip_args(city="  byblos "))
    assert "already saved as trip-0001" in error
    assert len(json.loads(trips_file.read_text(encoding="utf-8"))) == 1


async def test_save_trip_leaves_a_corrupt_store_untouched(client, trips_file):
    trips_file.write_text("{ not json", encoding="utf-8")
    error = await call_error(client, "save_trip", trip_args())
    assert "is corrupt" in error
    assert trips_file.read_text(encoding="utf-8") == "{ not json"


# ---------- Orchestration tool: plan_trip ----------


async def test_plan_trip_calls_data_then_action_tool(client, trips_file):
    result = await client.call_tool("plan_trip", {"city": "Beirut", "start_date": str(SOON), "days": 3})
    plan = result.structured_content

    assert [s.split(":")[0] for s in plan["steps"]] == [
        "1. get_weather_forecast", "2. combined the forecast into a summary and 4 packing item(s)", "3. save_trip"]
    assert plan["trip"]["id"] == "trip-0001"
    assert (plan["trip"]["start_date"], plan["trip"]["end_date"]) == (str(SOON), str(SOON + dt.timedelta(days=2)))
    assert "Umbrella or rain jacket" in plan["packing_list"]  # day 2 of the fake forecast is rainy
    stored = json.loads(trips_file.read_text(encoding="utf-8"))
    assert stored[0]["notes"].startswith(plan["summary"])


async def test_plan_trip_saves_nothing_when_the_forecast_fails(client, trips_file):
    error = await call_error(client, "plan_trip", {"city": "Xyzzyville", "start_date": str(SOON)})
    assert error.startswith("plan_trip stopped at step 1 (get_weather_forecast)")
    assert "No city named 'Xyzzyville'" in error and "Nothing was saved" in error
    assert not trips_file.exists()


async def test_plan_trip_reports_a_failed_save_step(client, trips_file):
    await client.call_tool("plan_trip", {"city": "Beirut", "start_date": str(SOON), "days": 2})
    error = await call_error(client, "plan_trip", {"city": "Beirut", "start_date": str(SOON), "days": 2})
    assert "step 3 (save_trip) failed" in error and "already saved as trip-0001" in error
    assert len(json.loads(trips_file.read_text(encoding="utf-8"))) == 1


async def test_plan_trip_validates_its_own_arguments(client):
    error = await call_error(client, "plan_trip", {"city": "Beirut", "start_date": str(SOON), "days": 0})
    assert "greater than or equal to 1" in error


# ---------- Resources ----------


async def test_resources_list_saved_trips(client):
    assert [str(r.uri) for r in await client.list_resources()] == ["trips://saved"]
    assert [t.uri_template for t in await client.list_resource_templates()] == ["trips://{trip_id}"]

    assert json.loads((await client.read_resource("trips://saved"))[0].text) == []
    await client.call_tool("save_trip", trip_args())
    trips = json.loads((await client.read_resource("trips://saved"))[0].text)
    assert [t["id"] for t in trips] == ["trip-0001"]
    one = json.loads((await client.read_resource("trips://trip-0001"))[0].text)
    assert one["city"] == "Byblos"


async def test_resource_unknown_trip_is_a_clear_error(client):
    try:
        await client.read_resource("trips://trip-9999")
    except Exception as e:  # noqa: BLE001 - the client wraps the server's ResourceError
        assert "No saved trip has id 'trip-9999'" in str(e)
    else:
        raise AssertionError("reading a missing trip should fail")
