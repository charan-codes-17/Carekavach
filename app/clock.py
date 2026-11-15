from datetime import UTC, datetime
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    """Protocol for time retrieval across the application."""

    def now_utc(self) -> datetime:
        """Return the current time in UTC with timezone info."""
        ...

    def now(self, tz: ZoneInfo | None = None) -> datetime:
        """Return current time in specified timezone (defaults to UTC)."""
        ...


class SystemClock:
    """Production clock using system wall-clock time."""

    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def now(self, tz: ZoneInfo | None = None) -> datetime:
        current = self.now_utc()
        if tz is not None:
            return current.astimezone(tz)
        return current


class FixedClock:
    """Test clock with deterministic time that can be frozen or advanced."""

    def __init__(self, current_time: datetime | None = None) -> None:
        if current_time is None:
            self._current_time = datetime(2026, 11, 15, 8, 0, 0, tzinfo=UTC)
        elif current_time.tzinfo is None:
            self._current_time = current_time.replace(tzinfo=UTC)
        else:
            self._current_time = current_time.astimezone(UTC)

    def now_utc(self) -> datetime:
        return self._current_time

    def now(self, tz: ZoneInfo | None = None) -> datetime:
        if tz is not None:
            return self._current_time.astimezone(tz)
        return self._current_time

    def set_time(self, new_time: datetime) -> None:
        if new_time.tzinfo is None:
            self._current_time = new_time.replace(tzinfo=UTC)
        else:
            self._current_time = new_time.astimezone(UTC)
