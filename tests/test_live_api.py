"""Opt-in checks against the real Open-Meteo API:  uv run pytest -m live"""

import pytest

from conftest import call_error
from trip_mcp import weather

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def real_network(monkeypatch):
    monkeypatch.setattr(weather, "_transport", None)


async def test_live_forecast_for_beirut(client):
    result = await client.call_tool("get_weather_forecast", {"city": "Beirut", "days": 2})
    data = result.structured_content
    assert data["country"] == "Lebanon" and len(data["days"]) == 2


async def test_live_unknown_city(client):
    error = await call_error(client, "get_weather_forecast", {"city": "Xyzzyville"})
    assert "No city named" in error
