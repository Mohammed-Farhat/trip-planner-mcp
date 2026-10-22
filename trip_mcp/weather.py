"""Open-Meteo client used by the Data tool.

No API key is needed. Data: Open-Meteo.com, licensed CC BY 4.0 (https://open-meteo.com/en/terms).
Every predictable failure is raised as WeatherError with a message that is safe to show to the user.
"""

import asyncio
import datetime as dt

import httpx2

from trip_mcp.models import DayForecast, Forecast

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 10.0
ATTEMPTS = 2
RETRY_DELAY_S = 1.0
FORECAST_HORIZON_DAYS = 16  # Open-Meteo serves today + 15 days
USER_AGENT = "trip-planner-mcp/0.1 (EECE 503P coursework)"

# Tests swap this for an httpx2.MockTransport so the suite never touches the network.
_transport: httpx2.AsyncBaseTransport | None = None

# WMO weather interpretation codes, as documented at https://open-meteo.com/en/docs
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherError(Exception):
    """A predictable failure whose message is meant for the user."""


class _TransientError(WeatherError):
    """Timeouts, connection failures and 5xx responses: worth one more try."""


def forecast_window(today: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """First and last date the forecast service can answer for."""
    today = today or dt.date.today()
    return today, today + dt.timedelta(days=FORECAST_HORIZON_DAYS - 1)


async def _get_json_once(url: str, params: dict) -> dict:
    try:
        async with httpx2.AsyncClient(
            timeout=TIMEOUT_S, transport=_transport, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(url, params=params)
    except httpx2.TimeoutException as e:
        raise _TransientError(f"Weather service unavailable (no response within {TIMEOUT_S:g} s)") from e
    except httpx2.RequestError as e:
        raise _TransientError(f"Weather service unreachable ({type(e).__name__})") from e

    try:
        data = resp.json()
    except ValueError:
        data = None
    if resp.status_code >= 400 or not isinstance(data, dict):
        reason = data.get("reason") if isinstance(data, dict) else None
        if resp.status_code < 500 and reason:
            raise WeatherError(f"Weather service rejected the request: {reason}")
        raise _TransientError(f"Weather service error (HTTP {resp.status_code})")
    return data


async def _get_json(url: str, params: dict) -> dict:
    # GET requests are read-only, so retrying a transient failure is safe.
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return await _get_json_once(url, params)
        except _TransientError as e:
            if attempt == ATTEMPTS:
                raise WeatherError(f"{e}; tried {ATTEMPTS} times. Try again in a minute.") from e
            await asyncio.sleep(RETRY_DELAY_S)
    raise AssertionError("unreachable")


async def geocode(city: str) -> dict:
    """Resolve 'City' or 'City, Country/Region' to the most populous matching place."""
    name, _, qualifier = (part.strip() for part in city.partition(","))
    if len(name) < 2:
        raise WeatherError(f"'{city}' is not a usable city name. Give at least two letters, e.g. 'Beirut'.")
    data = await _get_json(GEOCODE_URL, {"name": name, "count": 10, "language": "en", "format": "json"})
    results = data.get("results") or []
    if qualifier:
        q = qualifier.casefold()
        results = [
            r
            for r in results
            if q in (str(r.get(k, "")).casefold() for k in ("country", "country_code", "admin1"))
        ]
    if not results:
        raise WeatherError(
            f"No city named '{city}' was found. Check the spelling, or add the country "
            "(e.g. 'Tripoli, Lebanon')."
        )
    return results[0]


async def get_forecast(city: str, start_date: dt.date, days: int) -> Forecast:
    """Daily forecast for `days` consecutive days starting at `start_date`."""
    first, last = forecast_window()
    end_date = start_date + dt.timedelta(days=days - 1)
    if start_date < first:
        raise WeatherError(
            f"start_date {start_date} is in the past. Forecasts are available from {first} to {last}."
        )
    if end_date > last:
        raise WeatherError(
            f"The forecast only reaches {last} ({FORECAST_HORIZON_DAYS} days ahead), but {days} day(s) from "
            f"{start_date} ends on {end_date}. Choose an earlier start date or fewer days."
        )

    place = await geocode(city)
    data = await _get_json(
        FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    try:
        daily = data["daily"]
        out = []
        for i, day in enumerate(daily["time"]):
            code = daily["weather_code"][i]
            precip = daily.get("precipitation_probability_max", [None] * len(daily["time"]))[i]
            out.append(
                DayForecast(
                    date=day,
                    condition=WMO_CODES.get(code, f"Unknown (WMO code {code})"),
                    temp_max_c=daily["temperature_2m_max"][i],
                    temp_min_c=daily["temperature_2m_min"][i],
                    precip_probability_pct=precip,
                )
            )
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise WeatherError("Weather service returned data in an unexpected format. Try again later.") from e
    if not out:
        raise WeatherError("Weather service returned no days for that date range. Try again later.")

    return Forecast(
        city=place["name"],
        country=place.get("country"),
        region=place.get("admin1"),
        latitude=place["latitude"],
        longitude=place["longitude"],
        timezone=data.get("timezone") or place.get("timezone") or "UTC",
        days=out,
    )
