"""Typed inputs/outputs shared by the three tools.

These Pydantic models become the tools' MCP output schemas, so every field carries a description.
"""

import datetime as dt

from pydantic import BaseModel, Field


class DayForecast(BaseModel):
    """Weather for one calendar day."""

    date: dt.date = Field(description="Calendar day (YYYY-MM-DD), local to the city.")
    condition: str = Field(description="Human-readable condition, e.g. 'Overcast' or 'Light rain'.")
    temp_max_c: float = Field(description="Daily maximum temperature in degrees Celsius.")
    temp_min_c: float = Field(description="Daily minimum temperature in degrees Celsius.")
    precip_probability_pct: int | None = Field(
        default=None, description="Highest chance of precipitation that day, 0-100 (null if unavailable)."
    )


class Forecast(BaseModel):
    """Result of the Data tool (get_weather_forecast)."""

    city: str = Field(description="Resolved city name.")
    country: str | None = Field(default=None, description="Country of the resolved city.")
    region: str | None = Field(default=None, description="Region/state of the resolved city.")
    latitude: float = Field(description="Latitude of the resolved city.")
    longitude: float = Field(description="Longitude of the resolved city.")
    timezone: str = Field(description="IANA time zone used for the daily values.")
    days: list[DayForecast] = Field(description="One entry per requested day, in date order.")
    source: str = Field(default="Open-Meteo.com (CC BY 4.0)", description="Data source and licence.")


class SavedTrip(BaseModel):
    """Result of the Action tool (save_trip): one stored trip."""

    id: str = Field(description="Stable trip id, e.g. 'trip-0001'.")
    city: str = Field(description="Destination city.")
    start_date: dt.date = Field(description="First day of the trip.")
    end_date: dt.date = Field(description="Last day of the trip (inclusive).")
    notes: str = Field(default="", description="Free-text notes saved with the trip.")
    created_at: dt.datetime = Field(description="When the trip was saved (UTC).")


class TripPlan(BaseModel):
    """Result of the Orchestration tool (plan_trip)."""

    trip: SavedTrip = Field(description="The trip as saved by save_trip.")
    forecast: Forecast = Field(description="The forecast returned by get_weather_forecast.")
    packing_list: list[str] = Field(description="Weather-based packing suggestions.")
    summary: str = Field(description="One-paragraph weather summary of the trip.")
    steps: list[str] = Field(description="Audit trail of the tool calls plan_trip made, in order.")
