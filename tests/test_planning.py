"""Packing and summary rules used by plan_trip (pure functions, no MCP)."""

import datetime as dt

from trip_mcp.models import DayForecast, Forecast
from trip_mcp.planning import build_packing_list, summarize


def forecast(*days: tuple[str, float, float, int]) -> Forecast:
    start = dt.date(2026, 10, 24)
    return Forecast(
        city="Beirut", country="Lebanon", latitude=33.9, longitude=35.5, timezone="Asia/Beirut",
        days=[
            DayForecast(date=start + dt.timedelta(days=i), condition=c, temp_max_c=hi, temp_min_c=lo,
                        precip_probability_pct=p)
            for i, (c, hi, lo, p) in enumerate(days)
        ],
    )


def test_hot_dry_trip():
    items = build_packing_list(forecast(("Clear sky", 31, 22, 0), ("Mainly clear", 30, 21, 5)))
    assert "Sunscreen and sunglasses" in items
    assert "Umbrella or rain jacket" not in items


def test_rain_by_probability_or_condition():
    assert "Umbrella or rain jacket" in build_packing_list(forecast(("Overcast", 20, 15, 60)))
    assert "Umbrella or rain jacket" in build_packing_list(forecast(("Slight rain showers", 20, 15, 10)))


def test_cold_and_snow():
    assert "Warm jacket for the evenings" in build_packing_list(forecast(("Overcast", 14, 8, 0)))
    assert "Winter coat, gloves and hat" in build_packing_list(forecast(("Slight snowfall", 2, -3, 70)))


def test_summary_names_best_and_wettest_day():
    text = summarize(forecast(("Overcast", 25, 18, 10), ("Moderate rain", 21, 16, 90), ("Clear sky", 27, 18, 0)))
    assert text.startswith("Beirut, Lebanon, 2026-10-24 to 2026-10-26 (3 day(s)): 16-27 °C.")
    assert "Best day for outdoor plans: 2026-10-26 (clear sky)" in text
    assert "Wettest day: 2026-10-25 (90% chance of precipitation)" in text
