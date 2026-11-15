from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.models import DoseLog, DoseStatus, Medication


@dataclass(frozen=True)
class DoseSlotInfo:
    """Consolidated representation of a scheduled dose slot and its adherence state."""

    slot_id: str  # {medication_id}_{date}_{time}
    medication_id: str
    medication_name: str
    dosage: str
    is_private: bool
    scheduled_date: str  # YYYY-MM-DD
    scheduled_time: str  # HH:MM
    slot_datetime: datetime  # Timezone-aware in profile tz
    status: str  # TAKEN, SKIPPED, PENDING, MISSED
    status_text: str  # Accessible, senior-friendly text label
    logged_by_name: str | None = None
    logged_at: datetime | None = None


def format_time_12h(time_24h: str) -> str:
    """Convert 'HH:MM' (24-hour) string to 'H:MM AM/PM'."""
    try:
        parts = time_24h.split(":")
        h, m = int(parts[0]), int(parts[1])
        suffix = "PM" if h >= 12 else "AM"
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{m:02d} {suffix}"
    except Exception:
        return time_24h


def compute_slot_status(
    medication: Medication,
    scheduled_date: str,
    scheduled_time: str,
    log: DoseLog | None,
    now: datetime,
    tz: ZoneInfo,
) -> tuple[str, str]:
    """Pure evaluation of slot adherence status.

    Status rules:
    - If log exists: TAKEN or SKIPPED with actor and timestamp.
    - If no log:
      - If now >= slot_datetime + 60 mins -> MISSED (Overdue)
      - If now < slot_datetime + 60 mins -> PENDING
    - Slots scheduled before medication.created_at or for inactive meds are never MISSED.

    Returns:
        (status_code, accessible_status_text)
    """
    if log:
        if log.status == DoseStatus.TAKEN:
            log_time_str = log.logged_at.astimezone(tz).strftime("%I:%M %p").lstrip("0")
            return "TAKEN", f"Taken at {log_time_str} by {log.logged_by_name}"
        if log.status == DoseStatus.SKIPPED:
            return "SKIPPED", f"Skipped by {log.logged_by_name}"

    # No log exists
    parts = scheduled_time.split(":")
    slot_t = time(int(parts[0]), int(parts[1]))
    d_parts = [int(p) for p in scheduled_date.split("-")]
    d_obj = date(d_parts[0], d_parts[1], d_parts[2])
    slot_dt = datetime.combine(d_obj, slot_t, tzinfo=tz)

    time_12h = format_time_12h(scheduled_time)

    # Inactive medications or slots before creation are not counted as missed
    if not medication.is_active or slot_dt < medication.created_at.astimezone(tz):
        return "PENDING", f"Scheduled for {time_12h}"

    # Overdue threshold: exactly 60 minutes past slot time
    overdue_threshold = slot_dt + timedelta(minutes=60)
    now_tz = now.astimezone(tz)

    if now_tz >= overdue_threshold:
        return "MISSED", f"Missed - overdue (was due at {time_12h})"

    return "PENDING", f"Due at {time_12h}"


def get_today_slots(
    medications: list[Medication],
    logs: list[DoseLog],
    now: datetime,
    tz: ZoneInfo,
) -> list[DoseSlotInfo]:
    """Generate all scheduled slots for today, merged with dose logs."""
    today_date_str = now.astimezone(tz).strftime("%Y-%m-%d")
    logs_by_slot: dict[str, DoseLog] = {log.id: log for log in logs}

    slots: list[DoseSlotInfo] = []
    for med in medications:
        if not med.is_active:
            continue

        for scheduled_t in med.scheduled_times:
            slot_id = f"{med.id}_{today_date_str}_{scheduled_t}"
            log = logs_by_slot.get(slot_id)

            status_code, status_label = compute_slot_status(
                medication=med,
                scheduled_date=today_date_str,
                scheduled_time=scheduled_t,
                log=log,
                now=now,
                tz=tz,
            )

            parts = scheduled_t.split(":")
            slot_dt = datetime.combine(
                now.astimezone(tz).date(),
                time(int(parts[0]), int(parts[1])),
                tzinfo=tz,
            )

            slots.append(
                DoseSlotInfo(
                    slot_id=slot_id,
                    medication_id=med.id,
                    medication_name=med.name,
                    dosage=med.dosage,
                    is_private=med.is_private,
                    scheduled_date=today_date_str,
                    scheduled_time=scheduled_t,
                    slot_datetime=slot_dt,
                    status=status_code,
                    status_text=status_label,
                    logged_by_name=log.logged_by_name if log else None,
                    logged_at=log.logged_at if log else None,
                )
            )

    return sorted(slots, key=lambda s: (s.scheduled_time, s.medication_name.lower()))


def derived_misses(
    medications: list[Medication],
    logs: list[DoseLog],
    start_date: date,
    end_date: date,
    now: datetime,
    tz: ZoneInfo,
) -> list[dict[str, Any]]:
    """Identify all derived missed doses across a date range [start_date, end_date].

    Used by escalation engine and adherence analytics.
    """
    logs_by_slot: dict[str, DoseLog] = {log.id: log for log in logs}
    missed: list[dict[str, Any]] = []

    curr_date = start_date
    while curr_date <= end_date:
        date_str = curr_date.strftime("%Y-%m-%d")
        for med in medications:
            if not med.is_active:
                continue

            for t_str in med.scheduled_times:
                slot_id = f"{med.id}_{date_str}_{t_str}"
                log = logs_by_slot.get(slot_id)

                status_code, _ = compute_slot_status(
                    medication=med,
                    scheduled_date=date_str,
                    scheduled_time=t_str,
                    log=log,
                    now=now,
                    tz=tz,
                )

                if status_code == "MISSED":
                    missed.append(
                        {
                            "slot_id": slot_id,
                            "medication_id": med.id,
                            "medication_name": med.name,
                            "is_private": med.is_private,
                            "scheduled_date": date_str,
                            "scheduled_time": t_str,
                        }
                    )
        curr_date += timedelta(days=1)

    return missed
