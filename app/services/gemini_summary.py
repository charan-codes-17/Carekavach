import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from app.config import Settings, get_settings

logger = logging.getLogger("carekavach.gemini")

SYSTEM_INSTRUCTION = (
    "You are a compassionate adherence assistant for an elderly care routine. "
    "Summarize adherence schedule facts in 1 to 2 short, plain, non-clinical sentences. "
    "UNDER NO CIRCUMSTANCES provide medical advice, diagnoses, treatment recommendations, "
    "dosage changes, or drug interaction information. Focus purely on schedule routine logistics."
)

FORBIDDEN_CLINICAL_TERMS = (
    "dose change",
    "increase",
    "decrease",
    "diagnos",
    "interaction",
    "side effect",
    "stop taking",
)


@dataclass(frozen=True)
class ScheduleFacts:
    """Aggregated, non-personal schedule metrics for non-clinical summary generation."""

    doses_scheduled_today: int = 0
    doses_taken_today: int = 0
    overdue_doses_count: int = 0
    max_overdue_minutes: int = 0
    misses_in_last_72h: int = 0


def build_facts_prompt(facts: ScheduleFacts) -> str:
    """Construct prompt with aggregated facts ONLY (strictly zero names, emails, or med names)."""
    parts: list[str] = []
    if facts.overdue_doses_count > 0:
        parts.append(
            f"{facts.overdue_doses_count} dose(s) currently overdue by up to "
            f"{facts.max_overdue_minutes} minutes."
        )
    if facts.misses_in_last_72h > 0:
        parts.append(
            f"{facts.misses_in_last_72h} missed dose slot(s) recorded in the past 72 hours."
        )
    if facts.doses_scheduled_today > 0:
        parts.append(
            f"Today's routine: {facts.doses_scheduled_today} scheduled dose(s), "
            f"{facts.doses_taken_today} confirmed taken."
        )

    if not parts:
        return "Schedule status: Adherence routine requires check-in."

    return "Schedule status: " + " ".join(parts)


def build_deterministic_fallback(facts: ScheduleFacts) -> str:
    """Deterministic plain-text summary fallback when Gemini is slow, disabled, or offline."""
    if facts.overdue_doses_count > 0 and facts.misses_in_last_72h > 1:
        return (
            f"Routine update: {facts.overdue_doses_count} scheduled dose is overdue by "
            f"{facts.max_overdue_minutes} minutes, with {facts.misses_in_last_72h} "
            "misses recorded over the past 72 hours."
        )
    if facts.overdue_doses_count > 0:
        return (
            f"Routine update: {facts.overdue_doses_count} scheduled dose is currently overdue by "
            f"{facts.max_overdue_minutes} minutes."
        )
    if facts.misses_in_last_72h > 0:
        return (
            f"Routine update: {facts.misses_in_last_72h} scheduled doses were missed in the "
            "last 72 hours."
        )
    return "Routine update: Schedule status check-in required."


def sanitize_summary(text: str, fallback: str) -> str:
    """Strip markdown, enforce max ~300 chars, and reject clinical/medical terms."""
    # Strip markdown symbols: backticks, bold/italics, bullet marks, headers
    cleaned = re.sub(r"[`*_~#]", "", text)
    cleaned = re.sub(r"^\s*[-+*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = " ".join(cleaned.split()).strip()

    if not cleaned:
        return fallback

    # Check for forbidden clinical terminology
    lower_cleaned = cleaned.lower()
    for term in FORBIDDEN_CLINICAL_TERMS:
        if term in lower_cleaned:
            logger.warning("Clinical term '%s' detected in summary output; discarding.", term)
            return fallback

    # Cap at ~300 characters
    if len(cleaned) > 300:
        cleaned = cleaned[:300].rsplit(" ", 1)[0] + "."

    return cleaned


async def generate_summary(
    facts: ScheduleFacts,
    settings: Settings | None = None,
    client: Any | None = None,
) -> str:
    """Generate non-clinical pattern summary with strict 3.0s timeout and fail-safe fallback.

    Never raises, never delays email sending, never logs secrets.
    """
    settings = settings or get_settings()
    fallback = build_deterministic_fallback(facts)

    if not settings.GEMINI_API_KEY:
        return fallback

    prompt = build_facts_prompt(facts)

    def _call_gemini_sync() -> str | None:
        c = client or genai.Client(api_key=settings.GEMINI_API_KEY)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
            max_output_tokens=100,
        )
        resp = c.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        return getattr(resp, "text", None)

    try:
        raw_text = await asyncio.wait_for(asyncio.to_thread(_call_gemini_sync), timeout=3.0)
        if not raw_text:
            return fallback
        return sanitize_summary(raw_text, fallback)
    except Exception as exc:
        # Never log API key or fail into caller
        logger.info(
            "Gemini summary generation skipped (%s). Using deterministic fallback.",
            exc.__class__.__name__,
        )
        return fallback
