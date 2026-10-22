"""Pure helpers the Orchestration tool uses to combine the forecast into a plan.

No I/O here, so the rules are easy to unit-test.
"""

from trip_mcp.models import Forecast

RAIN_WORDS = ("drizzle", "rain", "shower", "thunder")
SNOW_WORDS = ("snow",)


def build_packing_list(forecast: Forecast) -> list[str]:
    days = forecast.days
    hottest = max(d.temp_max_c for d in days)
    coldest = min(d.temp_min_c for d in days)
    conditions = " ".join(d.condition.casefold() for d in days)
    wet = any((d.precip_probability_pct or 0) >= 50 for d in days) or any(w in conditions for w in RAIN_WORDS)

    items = ["Comfortable walking shoes"]
    if wet:
        items.append("Umbrella or rain jacket")
    if any(w in conditions for w in SNOW_WORDS) or coldest <= 3:
        items.append("Winter coat, gloves and hat")
    elif coldest <= 12:
        items.append("Warm jacket for the evenings")
    if hottest >= 28:
        items += ["Sunscreen and sunglasses", "Light, breathable clothes"]
    elif hottest >= 18:
        items.append("Light layers")
    if "thunder" in conditions:
        items.append("Indoor backup plans for stormy hours")
    return items


def summarize(forecast: Forecast) -> str:
    days = forecast.days
    place = ", ".join(p for p in (forecast.city, forecast.country) if p)
    low = min(d.temp_min_c for d in days)
    high = max(d.temp_max_c for d in days)
    wettest = max(days, key=lambda d: d.precip_probability_pct or 0)
    driest = min(days, key=lambda d: (d.precip_probability_pct or 0, -d.temp_max_c))
    text = (
        f"{place}, {days[0].date} to {days[-1].date} ({len(days)} day(s)): "
        f"{low:.0f}-{high:.0f} °C. Best day for outdoor plans: {driest.date} ({driest.condition.lower()})."
    )
    if (wettest.precip_probability_pct or 0) >= 30:
        text += f" Wettest day: {wettest.date} ({wettest.precip_probability_pct}% chance of precipitation)."
    return text
