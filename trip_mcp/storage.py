"""JSON-file trip store used by the Action tool.

Writes are atomic (temp file + os.replace) and a corrupt file is never overwritten.
"""

import datetime as dt
import json
import os
import re
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from trip_mcp.models import SavedTrip

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "trips.json"
_TRIPS = TypeAdapter(list[SavedTrip])


class StorageError(Exception):
    """A predictable failure whose message is meant for the user."""


def trips_path() -> Path:
    """Store location: $TRIPS_FILE if set, else data/trips.json in the project."""
    return Path(os.environ.get("TRIPS_FILE") or DEFAULT_PATH)


class TripStore:
    def __init__(self, path: Path | None = None):
        self.path = path or trips_path()

    def load(self) -> list[SavedTrip]:
        if not self.path.exists():
            return []
        try:
            return _TRIPS.validate_json(self.path.read_bytes())
        except ValidationError as e:
            raise StorageError(
                f"The trip store {self.path} is corrupt ({e.error_count()} problem(s), first: "
                f"{e.errors()[0]['msg']}). It was left untouched; fix or move the file and retry."
            ) from e
        except OSError as e:
            raise StorageError(f"Cannot read the trip store {self.path}: {e.strerror}.") from e

    def get(self, trip_id: str) -> SavedTrip:
        for trip in self.load():
            if trip.id == trip_id:
                return trip
        raise StorageError(f"No saved trip has id '{trip_id}'.")

    def add(self, city: str, start_date: dt.date, end_date: dt.date, notes: str = "") -> SavedTrip:
        city = " ".join(city.split())
        if end_date < start_date:
            raise StorageError(f"end_date {end_date} is before start_date {start_date}.")
        trips = self.load()
        for t in trips:
            if t.city.casefold() == city.casefold() and (t.start_date, t.end_date) == (start_date, end_date):
                raise StorageError(
                    f"A trip to {t.city} from {start_date} to {end_date} is already saved as {t.id}."
                )

        numbers = [int(m.group(1)) for t in trips if (m := re.fullmatch(r"trip-(\d+)", t.id))]
        trip = SavedTrip(
            id=f"trip-{max(numbers, default=0) + 1:04d}",
            city=city,
            start_date=start_date,
            end_date=end_date,
            notes=notes.strip(),
            created_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0),
        )
        self._write([*trips, trip])
        return trip

    def _write(self, trips: list[SavedTrip]) -> None:
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(_TRIPS.dump_json(trips, indent=2))
            os.replace(tmp, self.path)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            raise StorageError(f"Could not write the trip store {self.path}: {e.strerror}.") from e
