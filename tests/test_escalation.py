from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models import DoseLog, DoseStatus, Medication, Member, MemberRole
from app.services.escalation import (
    evaluate_rule_a,
    evaluate_rule_b,
    filter_escalation_for_member,
)

TZ = ZoneInfo("Asia/Kolkata")


def make_med(
    med_id: str,
    name: str = "Metformin",
    scheduled_times: list[str] | None = None,
    is_private: bool = False,
    is_active: bool = True,
    created_at: datetime | None = None,
) -> Medication:
    now_utc = datetime.now(UTC)
    return Medication(
        id=med_id,
        profile_id="default_profile",
        name=name,
        dosage="500mg",
        frequency="Daily",
        scheduled_times=scheduled_times or ["08:00"],
        instructions="After meals",
        is_private=is_private,
        is_active=is_active,
        created_by="mem_1",
        created_at=created_at or (now_utc - timedelta(days=10)),
        updated_at=now_utc,
    )


def make_member(
    mem_id: str,
    role: MemberRole,
    email: str | None = "test@example.com",
    is_active: bool = True,
) -> Member:
    return Member(
        id=mem_id,
        profile_id="default_profile",
        name=f"Member {mem_id}",
        email=email,
        role=role,
        can_edit=True,
        passcode_salt="salt",
        passcode_hash="hash",
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


def test_rule_a_evaluation_at_59_vs_60_minutes() -> None:
    """Rule A requires exactly 60+ minutes overdue; 59 minutes is pending."""
    med = make_med("med_1", scheduled_times=["08:00"])

    # 59 minutes past slot (08:59 AM)
    now_59 = datetime(2026, 11, 15, 8, 59, tzinfo=TZ)
    misses_59 = evaluate_rule_a(medications=[med], logs=[], now=now_59, tz=TZ)
    assert len(misses_59) == 0

    # 60 minutes past slot (09:00 AM)
    now_60 = datetime(2026, 11, 15, 9, 0, tzinfo=TZ)
    misses_60 = evaluate_rule_a(medications=[med], logs=[], now=now_60, tz=TZ)
    assert len(misses_60) == 1
    assert misses_60[0].medication_id == "med_1"
    assert misses_60[0].scheduled_time == "08:00"

    # If logged (e.g. taken), not overdue
    taken_log = DoseLog(
        id="med_1_2026-11-15_08:00",
        profile_id="default_profile",
        medication_id="med_1",
        medication_name="Metformin",
        scheduled_date="2026-11-15",
        scheduled_time="08:00",
        status=DoseStatus.TAKEN,
        logged_by_member_id="mem_1",
        logged_by_name="Senior",
        logged_at=now_60,
    )
    misses_logged = evaluate_rule_a(medications=[med], logs=[taken_log], now=now_60, tz=TZ)
    assert len(misses_logged) == 0


def test_rule_b_evaluation_inside_and_outside_72h() -> None:
    """Rule B triggers only when 2 or more derived misses fall within the last 72 hours."""
    med = make_med("med_1", scheduled_times=["08:00"])
    now = datetime(2026, 11, 18, 12, 0, tzinfo=TZ)

    # Scenario 1: Exactly 1 miss inside 72h (2026-11-17 08:00, ~28 hours ago)
    # Dose on 2026-11-16 08:00 was logged as TAKEN
    log_16 = DoseLog(
        id="med_1_2026-11-16_08:00",
        profile_id="default_profile",
        medication_id="med_1",
        medication_name="Metformin",
        scheduled_date="2026-11-16",
        scheduled_time="08:00",
        status=DoseStatus.TAKEN,
        logged_by_member_id="mem_1",
        logged_by_name="Senior",
        logged_at=datetime(2026, 11, 16, 8, 5, tzinfo=TZ),
    )
    log_18 = DoseLog(
        id="med_1_2026-11-18_08:00",
        profile_id="default_profile",
        medication_id="med_1",
        medication_name="Metformin",
        scheduled_date="2026-11-18",
        scheduled_time="08:00",
        status=DoseStatus.TAKEN,
        logged_by_member_id="mem_1",
        logged_by_name="Senior",
        logged_at=datetime(2026, 11, 18, 8, 5, tzinfo=TZ),
    )
    # Only 2026-11-17 08:00 is missed
    rule_b_1 = evaluate_rule_b(medications=[med], logs=[log_16, log_18], now=now, tz=TZ)
    assert rule_b_1 is None

    # Scenario 2: 2 misses inside 72h (both 2026-11-16 08:00 and 2026-11-17 08:00 missed)
    rule_b_2 = evaluate_rule_b(medications=[med], logs=[log_18], now=now, tz=TZ)
    assert rule_b_2 is not None
    assert rule_b_2.count >= 2
    assert rule_b_2.latest_miss["scheduled_date"] == "2026-11-17"

    # Scenario 3: 1 miss inside 72h (2026-11-17 08:00, ~28h ago) and 1 miss outside 72h
    # (2026-11-15 08:00, 76h ago). Total 2 misses on calendar, but only 1 inside 72h window.
    rule_b_outside = evaluate_rule_b(medications=[med], logs=[log_16, log_18], now=now, tz=TZ)
    assert rule_b_outside is None

    # Scenario 4: 2 misses inside 72h PLUS 1 miss outside 72h.
    # Total 3 misses on calendar; exactly 2 inside 72h window -> triggers Rule B with count=2!
    # Nov 15 08:00 (missed, 76h ago), Nov 16 08:00 (missed, 52h ago), Nov 17 08:00 (missed, 28h ago)
    rule_b_multi = evaluate_rule_b(medications=[med], logs=[log_18], now=now, tz=TZ)
    assert rule_b_multi is not None
    # 2026-11-16 and 2026-11-17 are within 72h window
    assert rule_b_multi.count == 2
    dates = [m["scheduled_date"] for m in rule_b_multi.missed_items]
    assert "2026-11-16" in dates
    assert "2026-11-17" in dates
    assert "2026-11-15" not in dates


def test_rule_b_boundary_strictly_at_72_hours() -> None:
    """Test boundary condition: a slot at 71h59m is counted; at 72h01m it is excluded."""
    # Scheduled daily at 12:00 PM
    med = make_med("med_b", scheduled_times=["12:00"])
    # Current time: 2026-11-18 12:00 PM
    now = datetime(2026, 11, 18, 12, 0, tzinfo=TZ)
    # 72 hours ago is exactly 2026-11-15 12:00 PM

    # Case A: Slot is 2026-11-15 12:00 PM (exactly 72.0 hours ago) -> cutoff_72h <= slot_dt <= now
    # Plus slot on 2026-11-17 12:00 PM (24h ago). Both missed.
    log_16 = DoseLog(
        id="med_b_2026-11-16_12:00",
        profile_id="default_profile",
        medication_id="med_b",
        medication_name="Metformin",
        scheduled_date="2026-11-16",
        scheduled_time="12:00",
        status=DoseStatus.TAKEN,
        logged_by_member_id="mem_1",
        logged_by_name="Senior",
        logged_at=datetime(2026, 11, 16, 12, 5, tzinfo=TZ),
    )
    log_18 = DoseLog(
        id="med_b_2026-11-18_12:00",
        profile_id="default_profile",
        medication_id="med_b",
        medication_name="Metformin",
        scheduled_date="2026-11-18",
        scheduled_time="12:00",
        status=DoseStatus.TAKEN,
        logged_by_member_id="mem_1",
        logged_by_name="Senior",
        logged_at=datetime(2026, 11, 18, 12, 5, tzinfo=TZ),
    )
    # Misses: Nov 15 12:00 (exactly 72h) and Nov 17 12:00 (24h). Total 2 misses inside window.
    res_at_boundary = evaluate_rule_b(medications=[med], logs=[log_16, log_18], now=now, tz=TZ)
    assert res_at_boundary is not None
    assert res_at_boundary.count == 2


def test_private_medication_exclusion_for_family() -> None:
    """Private medications never appear in family alerts; if only private items, no email."""
    senior = make_member("mem_s", role=MemberRole.SENIOR, email="senior@example.com")
    caretaker = make_member("mem_c", role=MemberRole.CARETAKER, email="care@example.com")
    family = make_member("mem_f", role=MemberRole.FAMILY, email="family@example.com")

    # Item 1: Private medication
    private_item = {
        "medication_id": "med_priv",
        "medication_name": "Anti-Anxiety Med",
        "dosage": "10mg",
        "is_private": True,
        "scheduled_date": "2026-11-15",
        "scheduled_time": "8:00 AM",
    }
    # Item 2: Public medication
    public_item = {
        "medication_id": "med_pub",
        "medication_name": "Vitamin D3",
        "dosage": "1000 IU",
        "is_private": False,
        "scheduled_date": "2026-11-15",
        "scheduled_time": "9:00 AM",
    }

    # Case A: Only private items
    only_priv = [private_item]
    assert filter_escalation_for_member(senior, only_priv) == only_priv
    assert filter_escalation_for_member(caretaker, only_priv) == only_priv
    # Family receives None (no email dispatched!)
    assert filter_escalation_for_member(family, only_priv) is None

    # Case B: Mixed items
    mixed = [private_item, public_item]
    senior_view = filter_escalation_for_member(senior, mixed)
    assert senior_view is not None and len(senior_view) == 2

    family_view = filter_escalation_for_member(family, mixed)
    assert family_view is not None
    assert len(family_view) == 1
    assert family_view[0]["medication_name"] == "Vitamin D3"
    assert not any(item["is_private"] for item in family_view)


def test_inactive_medication_and_pre_creation_slots_produce_no_escalation() -> None:
    """Soft-deactivated medications and slots before medication creation must never escalate."""
    # Med created at 10:00 AM today
    created_dt = datetime(2026, 11, 15, 10, 0, tzinfo=TZ)
    med_pre = make_med("med_pre", scheduled_times=["08:00"], created_at=created_dt)

    now = datetime(2026, 11, 15, 12, 0, tzinfo=TZ)
    # The 08:00 slot is before creation time (10:00 AM), so it's not missed
    misses_pre = evaluate_rule_a(medications=[med_pre], logs=[], now=now, tz=TZ)
    assert len(misses_pre) == 0

    # Inactive medication
    med_inactive = make_med("med_inact", scheduled_times=["08:00"], is_active=False)
    misses_inact = evaluate_rule_a(medications=[med_inactive], logs=[], now=now, tz=TZ)
    assert len(misses_inact) == 0

    # Inactive member gets None
    inactive_member = make_member("mem_inact", role=MemberRole.CARETAKER, is_active=False)
    assert (
        filter_escalation_for_member(
            inactive_member, [{"medication_name": "Metformin", "is_private": False}]
        )
        is None
    )

    # Member without email gets None
    no_email_member = make_member("mem_no_email", role=MemberRole.CARETAKER, email=None)
    assert (
        filter_escalation_for_member(
            no_email_member, [{"medication_name": "Metformin", "is_private": False}]
        )
        is None
    )
