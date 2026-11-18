"""Fechas en la zona horaria de presentación (America/Lima). En la base todo se guarda en UTC."""

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings


@lru_cache
def display_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz_display)


def today_local() -> date:
    return datetime.now(display_tz()).date()


def day_start_utc(d: date) -> datetime:
    """Inicio del día `d` en Lima, expresado en UTC."""
    return datetime.combine(d, time.min, tzinfo=display_tz()).astimezone(UTC)


def day_end_utc(d: date) -> datetime:
    """Inicio del día siguiente a `d` en Lima (límite exclusivo), en UTC."""
    return day_start_utc(d + timedelta(days=1))


def to_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(display_tz())


def fmt_datetime(dt: datetime | None, seconds: bool = False) -> str:
    local = to_local(dt)
    if local is None:
        return "—"
    return local.strftime("%d/%m/%Y %H:%M:%S" if seconds else "%d/%m/%Y %H:%M")


def fmt_date(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"
