import os
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TleSet:
    name: str
    line1: str
    line2: str
    epoch: datetime
    source: str = "manual"
    saved_at: datetime = None

    def age_days(self, now):
        return (now - self.epoch).total_seconds() / 86400


@dataclass
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str
    elevation_m: float = 0.0
    id: int = None
    is_default: bool = False
    is_favorite: bool = False


@dataclass
class Pass:
    rise: datetime
    set: datetime
    max_elevation: float
    visible: bool
    shown_start: datetime = None
    shown_end: datetime = None
    start_azimuth: float = 0.0
    end_azimuth: float = 0.0
    start_elevation: float = 0.0
    end_elevation: float = 0.0
    peak_time: datetime = None
    peak_azimuth: float = 0.0
    sun_altitude: float = 0.0
    reason: str = None
    path: list = field(default_factory=list)

    def duration_minutes(self):
        return (self.shown_end - self.shown_start).total_seconds() / 60


_real_start = datetime.now(timezone.utc)
_sim = os.environ.get("ISSPASS_NOW")
_sim_start = datetime.fromisoformat(_sim.replace("Z", "+00:00")) if _sim else None


def now():
    real = datetime.now(timezone.utc)
    if _sim_start is None:
        return real
    return _sim_start + (real - _real_start)
