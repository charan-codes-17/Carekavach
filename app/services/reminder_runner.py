import logging
import uuid
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.clock import Clock
from app.config import Settings
from app.models import (
    AuditEntry,
    DoseLog,
    Medication,
    Member,
    MemberRole,
    ReminderNotification,
)
from app.repositories import AlreadyExistsError, BaseRepository
from app.services.adherence import format_time_12h
from app.services.email import EmailService
from app.services.escalation import (
    evaluate_rule_a,
    evaluate_rule_b,
    filter_escalation_for_member,
)
from app.services.gemini_summary import ScheduleFacts, generate_summary

logger = logging.getLogger("carekavach.reminders")


async def run_reminders(
    repo: BaseRepository,
    clock: Clock,
    settings: Settings,
    email_service: EmailService | None = None,
    profile_id: str = "default_profile",
) -> dict[str, int]:
    """Execute reminder and escalation scans with deterministic idempotency.

    Scans:
    1. Upcoming doses in next 30 minutes with no log.
    2. Overdue doses per Rule A (60+ minutes overdue, no log).
    3. Adherence pattern escalation per Rule B (>=2 derived misses in last 72h).
    4. Appointments approximately 24 hours and 2 hours away (+/- 8 minute window).

    Returns JSON counts only: sent, logged, skipped_duplicate, failed.
    """
    counts = {
        "sent": 0,
        "logged": 0,
        "skipped_duplicate": 0,
        "failed": 0,
    }

    if email_service is None:
        email_service = EmailService(settings=settings)

    profile = await repo.get_profile(profile_id)
    tz_name = profile.timezone if profile else settings.DEFAULT_TIMEZONE
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Asia/Kolkata")

    senior_name = profile.senior_name if profile else "Senior"
    now = clock.now()
    now_tz = now.astimezone(tz)
    today_str = now_tz.strftime("%Y-%m-%d")

    # Fetch active medications, dose logs (4-day range to cover 72h window), and members
    medications: list[Medication] = await repo.list_medications(profile_id, active_only=True)
    start_logs_date = (now_tz - timedelta(days=4)).strftime("%Y-%m-%d")
    logs: list[DoseLog] = await repo.list_dose_logs(
        profile_id, start_date=start_logs_date, end_date=today_str
    )
    logs_by_slot: dict[str, DoseLog] = {log.id: log for log in logs}
    members: list[Member] = await repo.list_members(profile_id)

    async def dispatch(
        task_type: str,
        target_id: str,
        slot_date: str,
        slot_time: str,
        recipient: Member,
        subject: str,
        template_name: str,
        context: dict[str, Any],
    ) -> None:
        """Atomic idempotency check before sending."""
        if not recipient.email:
            return

        notification_id = f"{task_type}_{target_id}_{slot_date}_{slot_time}_{recipient.id}"
        notification = ReminderNotification(
            id=notification_id,
            profile_id=profile_id,
            task_type=task_type,
            target_id=target_id,
            sent_to=[recipient.email],
            sent_at=now,
        )

        try:
            await repo.create_reminder_notification(notification)
        except AlreadyExistsError:
            counts["skipped_duplicate"] += 1
            return

        result = await email_service.send_template(
            recipient=recipient.email,
            subject=subject,
            template_name=template_name,
            context=context,
        )

        if result.status == "sent":
            counts["sent"] += 1
        elif result.status == "logged":
            counts["logged"] += 1
        else:
            counts["failed"] += 1

    # ──────────────────────────────────────────────────────────────────────────
    # SCAN 1: Upcoming Doses in Next 30 Minutes
    # ──────────────────────────────────────────────────────────────────────────
    thirty_mins_ahead = now_tz + timedelta(minutes=30)
    for med in medications:
        if not med.is_active:
            continue

        for t_str in med.scheduled_times:
            parts = t_str.split(":")
            slot_t = time(int(parts[0]), int(parts[1]))
            slot_dt = datetime.combine(now_tz.date(), slot_t, tzinfo=tz)

            # Skip slots before medication created_at
            if slot_dt < med.created_at.astimezone(tz):
                continue

            # Check if strictly in the next 30 minutes (now < slot_dt <= now + 30m)
            if not (now_tz < slot_dt <= thirty_mins_ahead):
                continue

            # Check if already logged
            slot_id = f"{med.id}_{today_str}_{t_str}"
            if slot_id in logs_by_slot:
                continue

            # Dispatch to authorized recipients
            formatted_time = format_time_12h(t_str)
            for mem in members:
                if not mem.is_active or not mem.email:
                    continue
                # Privacy rule: Family never gets private medications
                if mem.role == MemberRole.FAMILY and med.is_private:
                    continue

                context = {
                    "recipient_name": mem.name,
                    "senior_name": senior_name,
                    "medication_name": med.name,
                    "dosage": med.dosage,
                    "scheduled_time": formatted_time,
                    "scheduled_date": today_str,
                    "instructions": med.instructions,
                }
                subject = (
                    f"CareKavach Reminder: Upcoming Scheduled Dose ({med.name} at {formatted_time})"
                )
                await dispatch(
                    task_type="dose_upcoming",
                    target_id=med.id,
                    slot_date=today_str,
                    slot_time=t_str,
                    recipient=mem,
                    subject=subject,
                    template_name="dose_upcoming",
                    context=context,
                )

    # ──────────────────────────────────────────────────────────────────────────
    # SCAN 2: Overdue Doses per Rule A (60+ min overdue, no log)
    # ──────────────────────────────────────────────────────────────────────────
    rule_a_misses = evaluate_rule_a(
        medications=medications,
        logs=logs,
        now=now,
        tz=tz,
        lookback_hours=24,
    )
    for miss in rule_a_misses:
        miss_dict = {
            "slot_id": miss.slot_id,
            "medication_id": miss.medication_id,
            "medication_name": miss.medication_name,
            "dosage": miss.dosage,
            "is_private": miss.is_private,
            "scheduled_date": miss.scheduled_date,
            "scheduled_time": format_time_12h(miss.scheduled_time),
        }
        overdue_min = max(60, int((now_tz - miss.slot_datetime).total_seconds() / 60))
        facts_a = ScheduleFacts(
            doses_scheduled_today=len(medications),
            overdue_doses_count=1,
            max_overdue_minutes=overdue_min,
        )
        summary_a = await generate_summary(facts_a, settings=settings)

        for mem in members:
            visible_items = filter_escalation_for_member(mem, [miss_dict])
            if not visible_items:
                continue

            context = {
                "recipient_name": mem.name,
                "senior_name": senior_name,
                "reason": "A scheduled dose is 60+ minutes overdue with no log recorded.",
                "missed_items": visible_items,
                "summary": summary_a,
            }
            subject = f"CareKavach Alert: Overdue Dose for {senior_name} - {miss.medication_name}"
            await dispatch(
                task_type="escalation_rule_a",
                target_id=miss.medication_id,
                slot_date=miss.scheduled_date,
                slot_time=miss.scheduled_time,
                recipient=mem,
                subject=subject,
                template_name="dose_missed_escalation",
                context=context,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # SCAN 3: Rule B Escalation (2 or more derived misses in last 72 hours)
    # ──────────────────────────────────────────────────────────────────────────
    rule_b = evaluate_rule_b(
        medications=medications,
        logs=logs,
        now=now,
        tz=tz,
    )
    if rule_b is not None:
        latest = rule_b.latest_miss
        facts_b = ScheduleFacts(
            doses_scheduled_today=len(medications),
            overdue_doses_count=len(rule_a_misses),
            misses_in_last_72h=rule_b.count,
        )
        summary_b = await generate_summary(facts_b, settings=settings)
        formatted_misses = [
            {
                "medication_name": item["medication_name"],
                "dosage": item.get("dosage", ""),
                "is_private": item.get("is_private", False),
                "scheduled_date": item["scheduled_date"],
                "scheduled_time": format_time_12h(item["scheduled_time"]),
            }
            for item in rule_b.missed_items
        ]

        for mem in members:
            visible_items = filter_escalation_for_member(mem, formatted_misses)
            if not visible_items:
                continue

            context = {
                "recipient_name": mem.name,
                "senior_name": senior_name,
                "reason": (
                    f"Adherence alert: {rule_b.count} scheduled doses were missed over "
                    "the past 72 hours."
                ),
                "missed_items": visible_items,
                "summary": summary_b,
            }
            subject = f"CareKavach Alert: Multiple Overdue Doses for {senior_name}"
            await dispatch(
                task_type="escalation_rule_b",
                target_id=latest["medication_id"],
                slot_date=latest["scheduled_date"],
                slot_time=latest["scheduled_time"],
                recipient=mem,
                subject=subject,
                template_name="dose_missed_escalation",
                context=context,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # SCAN 4: Appointments About 24 Hours and 2 Hours Away (+/- 8 min window)
    # ──────────────────────────────────────────────────────────────────────────
    appointments = await repo.list_appointments(profile_id=profile_id, upcoming_only=False, now=now)
    for appt in appointments:
        if appt.appointment_datetime <= now:
            continue  # Ignore past appointments

        delta_minutes = (appt.appointment_datetime - now).total_seconds() / 60.0

        task_type: str | None = None
        window_label: str = ""
        if 1440 - 8 <= delta_minutes <= 1440 + 8:
            task_type = "appointment_reminder_24h"
            window_label = "tomorrow (in approximately 24 hours)"
        elif 120 - 8 <= delta_minutes <= 120 + 8:
            task_type = "appointment_reminder_2h"
            window_label = "in approximately 2 hours"

        if task_type is None:
            continue

        appt_tz = appt.appointment_datetime.astimezone(tz)
        appt_date_str = appt_tz.strftime("%Y-%m-%d")
        appt_time_raw = appt_tz.strftime("%H:%M")
        appt_time_str = format_time_12h(appt_time_raw)

        for mem in members:
            if not mem.is_active or not mem.email:
                continue

            context = {
                "recipient_name": mem.name,
                "senior_name": senior_name,
                "window_label": window_label,
                "doctor_name": appt.doctor_name,
                "specialty": appt.specialty,
                "location": appt.location,
                "appointment_time": appt_time_str,
                "appointment_date": appt_date_str,
                "notes": appt.notes,
            }
            subject = (
                f"CareKavach Reminder: Upcoming Appointment with Dr. {appt.doctor_name} "
                f"({window_label})"
            )
            await dispatch(
                task_type=task_type,
                target_id=appt.id,
                slot_date=appt_date_str,
                slot_time=appt_time_raw,
                recipient=mem,
                subject=subject,
                template_name="appointment_reminder",
                context=context,
            )

    # Record non-sensitive audit entry
    audit_entry = AuditEntry(
        id=f"audit_reminders_{int(now.timestamp())}_{uuid.uuid4().hex[:6]}",
        profile_id=profile_id,
        action="REMINDERS_TASK_EXECUTED",
        actor_name="scheduler",
        details=counts,
        timestamp=now,
    )
    await repo.create_audit_entry(audit_entry)

    logger.info(
        "Reminders scan completed: sent=%d, logged=%d, skipped_duplicate=%d, failed=%d",
        counts["sent"],
        counts["logged"],
        counts["skipped_duplicate"],
        counts["failed"],
    )
    return counts
