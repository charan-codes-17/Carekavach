from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.models import DoseLog, Medication, Member, MemberRole
from app.services.adherence import derived_misses


@dataclass(frozen=True)
class RuleAMiss:
    """Represents a single scheduled dose slot that is 60+ minutes overdue with no log."""

    slot_id: str
    medication_id: str
    medication_name: str
    dosage: str
    is_private: bool
    scheduled_date: str
    scheduled_time: str
    slot_datetime: datetime


@dataclass(frozen=True)
class RuleBEscalation:
    """Represents Rule B escalation (2 or more derived misses in the last 72 hours)."""

    count: int
    missed_items: list[dict[str, Any]]
    latest_miss: dict[str, Any]


def evaluate_rule_a(
    medications: list[Medication],
    logs: list[DoseLog],
    now: datetime,
    tz: ZoneInfo,
    lookback_hours: int = 24,
) -> list[RuleAMiss]:
    """Identify slots currently MISSED under Rule A (60+ min overdue, no log).

    Reuses adherence.derived_misses to ensure identical overdue logic.
    """
    now_tz = now.astimezone(tz)
    start_dt = now_tz - timedelta(hours=lookback_hours)
    start_date = start_dt.date()
    end_date = now_tz.date()

    all_misses = derived_misses(
        medications=medications,
        logs=logs,
        start_date=start_date,
        end_date=end_date,
        now=now,
        tz=tz,
    )

    rule_a_misses: list[RuleAMiss] = []
    for item in all_misses:
        d = date.fromisoformat(item["scheduled_date"])
        parts = [int(p) for p in item["scheduled_time"].split(":")]
        slot_dt = datetime.combine(d, time(parts[0], parts[1]), tzinfo=tz)

        # Slot must be within the lookback window up to now
        if start_dt <= slot_dt <= now_tz:
            rule_a_misses.append(
                RuleAMiss(
                    slot_id=item["slot_id"],
                    medication_id=item["medication_id"],
                    medication_name=item["medication_name"],
                    dosage=item.get("dosage", ""),
                    is_private=item.get("is_private", False),
                    scheduled_date=item["scheduled_date"],
                    scheduled_time=item["scheduled_time"],
                    slot_datetime=slot_dt,
                )
            )

    return sorted(rule_a_misses, key=lambda m: m.slot_datetime)


def evaluate_rule_b(
    medications: list[Medication],
    logs: list[DoseLog],
    now: datetime,
    tz: ZoneInfo,
) -> RuleBEscalation | None:
    """Identify whether Rule B applies (2 or more derived misses within the last 72 hours).

    Reuses adherence.derived_misses.
    """
    now_tz = now.astimezone(tz)
    cutoff_72h = now_tz - timedelta(hours=72)
    start_date = cutoff_72h.date()
    end_date = now_tz.date()

    all_misses = derived_misses(
        medications=medications,
        logs=logs,
        start_date=start_date,
        end_date=end_date,
        now=now,
        tz=tz,
    )

    # Filter to misses strictly within the 72-hour window
    recent_misses: list[dict[str, Any]] = []
    for item in all_misses:
        d = date.fromisoformat(item["scheduled_date"])
        parts = [int(p) for p in item["scheduled_time"].split(":")]
        slot_dt = datetime.combine(d, time(parts[0], parts[1]), tzinfo=tz)
        if cutoff_72h <= slot_dt <= now_tz:
            recent_misses.append(item)

    if len(recent_misses) < 2:
        return None

    # Sort chronological so latest miss is at the end
    sorted_misses = sorted(
        recent_misses,
        key=lambda it: (it["scheduled_date"], it["scheduled_time"]),
    )

    return RuleBEscalation(
        count=len(sorted_misses),
        missed_items=sorted_misses,
        latest_miss=sorted_misses[-1],
    )


def filter_escalation_for_member(
    member: Member,
    missed_items: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Filter missed items based on member role and privacy settings.

    Rules:
    - Inactive members or members without an email get None.
    - Active SENIOR and CARETAKER get full details (including is_private meds).
    - Active FAMILY members have is_private meds excluded.
    - If only private items would be listed for family, return None (no email).
    """
    if not member.is_active or not member.email or not member.email.strip():
        return None

    if member.role in (MemberRole.CARETAKER, MemberRole.SENIOR):
        return missed_items if missed_items else None

    if member.role == MemberRole.FAMILY:
        visible = [item for item in missed_items if not item.get("is_private", False)]
        if not visible:
            return None
        return visible

    return None
