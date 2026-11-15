import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.services.email import render_email
from app.services.gemini_summary import (
    FORBIDDEN_CLINICAL_TERMS,
    ScheduleFacts,
    build_deterministic_fallback,
    build_facts_prompt,
    generate_summary,
    sanitize_summary,
)


def test_prompt_construction_contains_no_personal_identifying_information() -> None:
    """Prompt must strictly contain aggregated schedule metrics: zero personal or med names."""
    facts = ScheduleFacts(
        doses_scheduled_today=4,
        doses_taken_today=2,
        overdue_doses_count=1,
        max_overdue_minutes=75,
        misses_in_last_72h=3,
    )
    prompt = build_facts_prompt(facts)

    # Must contain factual numbers
    assert "1 dose(s) currently overdue by up to 75 minutes." in prompt
    assert "3 missed dose slot(s) recorded in the past 72 hours." in prompt
    assert "4 scheduled dose(s), 2 confirmed taken." in prompt

    # Strictly forbidden: names, emails, medications, user text
    forbidden_tokens = [
        "Ramesh",
        "Sharma",
        "Anil",
        "Priya",
        "example.com",
        "@",
        "Metformin",
        "Aspirin",
        "Insulin",
        "patient",
        "senior",
    ]
    for token in forbidden_tokens:
        assert token.lower() not in prompt.lower()


@pytest.mark.asyncio
async def test_missing_api_key_returns_deterministic_fallback_immediately() -> None:
    """When GEMINI_API_KEY is empty/unset, returns deterministic fallback without calling API."""
    settings = Settings(GEMINI_API_KEY="", GEMINI_MODEL="gemini-2.5-flash")
    facts = ScheduleFacts(overdue_doses_count=1, max_overdue_minutes=65)

    summary = await generate_summary(facts, settings=settings)
    assert summary == build_deterministic_fallback(facts)
    assert "65 minutes" in summary


@pytest.mark.asyncio
async def test_api_timeout_returns_fallback_within_3s() -> None:
    """Gemini call exceeding 3.0s timeout must be aborted cleanly and return fallback."""
    settings = Settings(GEMINI_API_KEY="test_gemini_key", GEMINI_MODEL="gemini-2.5-flash")
    facts = ScheduleFacts(overdue_doses_count=2, max_overdue_minutes=90, misses_in_last_72h=2)

    def slow_call(*args: Any, **kwargs: Any) -> Any:
        # Sleep for longer than the 3.0s timeout
        time.sleep(4.0)
        return MagicMock(text="Too late response")

    mock_client = MagicMock()
    mock_client.models.generate_content = slow_call

    start_time = time.monotonic()
    summary = await generate_summary(facts, settings=settings, client=mock_client)
    elapsed = time.monotonic() - start_time

    # Must finish around 3.0s (allow small scheduler jitter)
    assert elapsed < 3.8
    assert summary == build_deterministic_fallback(facts)
    assert "90 minutes" in summary


@pytest.mark.asyncio
async def test_api_error_returns_fallback_without_raising_or_leaking_key() -> None:
    """API errors (quota, network, 500) must return fallback and never leak credentials."""
    secret_key = "AIzaSySUPER_SECRET_GEMINI_KEY_77777"
    settings = Settings(GEMINI_API_KEY=secret_key, GEMINI_MODEL="gemini-2.5-flash")
    facts = ScheduleFacts(overdue_doses_count=1, max_overdue_minutes=60)

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception(
        f"API Error 429 ResourceExhausted for key={secret_key}"
    )

    with patch("app.services.gemini_summary.logger.info") as mock_log:
        summary = await generate_summary(facts, settings=settings, client=mock_client)

    assert summary == build_deterministic_fallback(facts)
    # Ensure secret key is never logged
    for call_args in mock_log.call_args_list:
        log_msg = str(call_args)
        assert secret_key not in log_msg


@pytest.mark.parametrize("clinical_phrase", FORBIDDEN_CLINICAL_TERMS)
def test_clinical_terms_are_rejected(clinical_phrase: str) -> None:
    """Any output containing clinical or medical advice terms must be rejected."""
    fallback = "Routine update: 1 dose is overdue."
    unsafe_output = f"Please consider a {clinical_phrase} based on schedule trends."

    sanitized = sanitize_summary(unsafe_output, fallback)
    assert sanitized == fallback


def test_sanitize_summary_strips_markdown_and_caps_length() -> None:
    """Markdown symbols must be stripped and text capped at ~300 characters."""
    fallback = "Routine update: Status ok."
    raw_markdown = "**Notice:** `Scheduled` routine shows _one_ pending slot. # Please follow up."

    cleaned = sanitize_summary(raw_markdown, fallback)
    assert "*" not in cleaned
    assert "`" not in cleaned
    assert "_" not in cleaned
    assert "#" not in cleaned
    assert "Notice: Scheduled routine shows one pending slot. Please follow up." in cleaned

    # Very long response
    long_raw = "Routine update for morning schedule. " * 20
    cleaned_long = sanitize_summary(long_raw, fallback)
    assert len(cleaned_long) <= 300
    assert cleaned_long.endswith(".")


@pytest.mark.asyncio
async def test_success_output_is_used() -> None:
    """Valid, non-clinical 2-sentence response is returned cleanly."""
    settings = Settings(GEMINI_API_KEY="valid_key", GEMINI_MODEL="gemini-2.5-flash")
    facts = ScheduleFacts(overdue_doses_count=1, max_overdue_minutes=60)

    expected_text = (
        "One scheduled morning dose is currently overdue. All other doses were confirmed on time."
    )
    mock_resp = MagicMock()
    mock_resp.text = expected_text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    summary = await generate_summary(facts, settings=settings, client=mock_client)
    assert summary == expected_text


def test_escalation_email_renders_with_and_without_summary() -> None:
    """Email template renders cleanly with summary provided, and remains complete when omitted."""
    base_context = {
        "recipient_name": "Anil Kumar",
        "senior_name": "Ramesh Sharma",
        "reason": "A scheduled dose is 60+ minutes overdue with no log recorded.",
        "missed_items": [
            {
                "medication_name": "Metformin",
                "dosage": "500mg",
                "scheduled_date": "2026-11-15",
                "scheduled_time": "8:00 AM",
            }
        ],
    }

    # Case 1: Without summary (summary absent/None)
    txt_no_sum, html_no_sum = render_email("dose_missed_escalation", base_context)
    assert "Pattern Summary:" not in txt_no_sum
    assert "Pattern Summary:" not in html_no_sum
    assert "Notice: A scheduled dose is 60+ minutes overdue" in txt_no_sum
    assert "Metformin" in html_no_sum

    # Case 2: With summary provided
    context_with_sum = dict(base_context)
    expected_sum = "Routine update: 1 dose is overdue by 60 minutes."
    context_with_sum["summary"] = expected_sum
    txt_sum, html_sum = render_email("dose_missed_escalation", context_with_sum)
    assert f"Pattern Summary: {expected_sum}" in txt_sum
    assert f"<strong>Pattern Summary:</strong> {expected_sum}" in html_sum
