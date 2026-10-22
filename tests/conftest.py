"""Shared fixtures: an isolated trip store and a fake Open-Meteo, so tests never touch the network."""

import datetime as dt

import httpx2
import pytest
from fastmcp import Client

from trip_mcp import weather

TODAY = dt.date.today()
SOON = TODAY + dt.timedelta(days=2)

PLACES = {
    "beirut": [
        {"name": "Beirut", "latitude": 33.89, "longitude": 35.5, "country": "Lebanon", "country_code": "LB",
         "admin1": "Beirut", "timezone": "Asia/Beirut"},
    ],
    "tripoli": [
        {"name": "Tripoli", "latitude": 32.89, "longitude": 13.19, "country": "Libya", "country_code": "LY",
         "admin1": "Tripoli", "timezone": "Africa/Tripoli"},
        {"name": "Tripoli", "latitude": 34.43, "longitude": 35.84, "country": "Lebanon", "country_code": "LB",
         "admin1": "North Lebanon", "timezone": "Asia/Beirut"},
    ],
}


class FakeOpenMeteo:
    """Answers geocoding and forecast requests like Open-Meteo. Set `fail_with` to simulate outages."""

    def __init__(self):
        self.requests: list[httpx2.Request] = []
        self.fail_with: Exception | int | None = None

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if isinstance(self.fail_with, Exception):
            raise self.fail_with
        if isinstance(self.fail_with, int):
            return httpx2.Response(self.fail_with, text="upstream error")
        params = request.url.params
        if request.url.host == "geocoding-api.open-meteo.com":
            results = PLACES.get(params["name"].casefold())
            return httpx2.Response(200, json={"results": results} if results else {"generationtime_ms": 0.1})

        start = dt.date.fromisoformat(params["start_date"])
        end = dt.date.fromisoformat(params["end_date"])
        n = (end - start).days + 1
        # Day 2 is rainy so the packing rules have something to react to.
        return httpx2.Response(200, json={
            "timezone": "Asia/Beirut",
            "daily": {
                "time": [(start + dt.timedelta(days=i)).isoformat() for i in range(n)],
                "weather_code": [61 if i == 1 else 3 for i in range(n)],
                "temperature_2m_max": [29.0 - i for i in range(n)],
                "temperature_2m_min": [18.0 - i for i in range(n)],
                "precipitation_probability_max": [80 if i == 1 else 5 for i in range(n)],
            },
        })


@pytest.fixture(autouse=True)
def trips_file(tmp_path, monkeypatch):
    path = tmp_path / "trips.json"
    monkeypatch.setenv("TRIPS_FILE", str(path))
    return path


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    fake = FakeOpenMeteo()
    monkeypatch.setattr(weather, "_transport", httpx2.MockTransport(fake))
    monkeypatch.setattr(weather, "RETRY_DELAY_S", 0)
    return fake


@pytest.fixture
async def client():
    from trip_mcp.server import mcp

    async with Client(mcp) as c:
        yield c


async def call_error(client: Client, tool: str, args: dict) -> str:
    """Call a tool that is expected to fail; return the error text the agent would see."""
    result = await client.call_tool(tool, args, raise_on_error=False)
    assert result.is_error, f"{tool} unexpectedly succeeded: {result.structured_content}"
    return result.content[0].text
