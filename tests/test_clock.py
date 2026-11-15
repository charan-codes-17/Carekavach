from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.clock import FixedClock, SystemClock


def test_system_clock_returns_utc() -> None:
    clock = SystemClock()
    now_utc = clock.now_utc()
    assert now_utc.tzinfo is not None
    assert now_utc.tzinfo == UTC

    # Test conversion to specified timezone
    ist_tz = ZoneInfo("Asia/Kolkata")
    now_ist = clock.now(ist_tz)
    assert now_ist.tzinfo == ist_tz
    assert abs((now_ist.astimezone(UTC) - now_utc).total_seconds()) < 1.0


def test_fixed_clock_deterministic_time() -> None:
    fixed_time = datetime(2026, 11, 15, 10, 0, 0, tzinfo=UTC)
    clock = FixedClock(fixed_time)

    assert clock.now_utc() == fixed_time

    # Timezone conversion
    ist_tz = ZoneInfo("Asia/Kolkata")
    ist_time = clock.now(ist_tz)
    assert ist_time.hour == 15
    assert ist_time.minute == 30

    # Advancing time
    new_time = fixed_time + timedelta(hours=2)
    clock.set_time(new_time)
    assert clock.now_utc() == new_time
