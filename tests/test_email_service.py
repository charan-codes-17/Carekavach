import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.services.email import EmailService, render_email


def test_render_email_escapes_user_text_and_no_medical_advice() -> None:
    """User-supplied text must be auto-escaped in HTML and plain text must be purely logistical."""
    context = {
        "recipient_name": "<script>alert('xss')</script>Alice",
        "senior_name": "Grandpa <b>Ramesh</b>",
        "medication_name": "Amlodipine & Metformin",
        "dosage": "5mg < 10mg",
        "scheduled_time": "8:00 AM",
        "scheduled_date": "2026-11-15",
        "instructions": "Take with water & avoid fasting",
    }
    text, html = render_email("dose_upcoming", context)

    # HTML must escape special characters
    assert "<script>" not in html
    assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;Alice" in html
    assert "&amp;" in html
    assert "&lt; 10mg" in html

    # Plain text contains the raw content cleanly
    assert "<script>alert('xss')</script>Alice" in text
    assert "Take with water & avoid fasting" in text

    # Boundary check: Purely logistical, zero medical advice
    for rendered in (text, html):
        lower = rendered.lower()
        assert "medical advice" not in lower or "does not provide medical advice" in lower
        assert "diagnosis" not in lower
        assert "treatment" not in lower


@pytest.mark.asyncio
async def test_email_service_log_backend_writes_to_stdout() -> None:
    """Log backend writes full rendered email to stdout and returns 'logged'."""
    settings = Settings(EMAIL_BACKEND="log", EMAIL_FROM="CareKavach <test@carekavach.local>")
    service = EmailService(settings=settings)

    stdout_capture = io.StringIO()
    with patch.object(sys, "stdout", stdout_capture):
        res = await service.send(
            recipient="senior@example.com",
            subject="Upcoming Dose",
            text_content="Your 8:00 AM dose is scheduled.",
            html_content="<p>Your 8:00 AM dose is scheduled.</p>",
        )

    assert res.status == "logged"
    assert res.backend == "log"
    assert res.error is None

    output = stdout_capture.getvalue()
    assert "To: senior@example.com" in output
    assert "Subject: Upcoming Dose" in output
    assert "Your 8:00 AM dose is scheduled." in output


@pytest.mark.asyncio
async def test_email_service_smtp_success() -> None:
    """SMTP backend delivers via smtplib and returns 'sent'."""
    settings = Settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="smtp.example.com",
        SMTP_PORT=587,
        SMTP_USER="smtp_user",
        SMTP_PASSWORD="smtp_password",
    )
    service = EmailService(settings=settings)

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance
    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        res = await service.send(
            recipient="caretaker@example.com",
            subject="Test Subject",
            text_content="Text body",
            html_content="<p>HTML body</p>",
        )

    assert res.status == "sent"
    assert res.backend == "smtp"
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with("smtp_user", "smtp_password")
    mock_smtp_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_email_service_smtp_failure_falls_back_to_log_without_raising() -> None:
    """SMTP exception falls back to log backend and redacts secrets from error messages."""
    super_secret_pw = "SUPER_SECRET_SMTP_PASS_12345"
    settings = Settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="smtp.example.com",
        SMTP_PORT=587,
        SMTP_USER="smtp_user",
        SMTP_PASSWORD=super_secret_pw,
    )
    service = EmailService(settings=settings)

    stdout_capture = io.StringIO()
    with (
        patch(
            "smtplib.SMTP",
            side_effect=Exception(f"Connection timed out with secret={super_secret_pw}"),
        ),
        patch.object(sys, "stdout", stdout_capture),
    ):
        res = await service.send(
            recipient="caretaker@example.com",
            subject="Alert Subject",
            text_content="Missed dose details",
            html_content="<p>Missed dose details</p>",
        )

    # Must fall back to log backend
    assert res.status == "logged"
    assert res.backend == "log"
    assert res.error is not None
    # Secret must NEVER leak in res.error or stdout
    assert super_secret_pw not in res.error
    assert "[REDACTED]" in res.error
    assert super_secret_pw not in stdout_capture.getvalue()
    assert "Missed dose details" in stdout_capture.getvalue()


@pytest.mark.asyncio
async def test_email_service_resend_success() -> None:
    """Resend backend sends via httpx API when configured."""
    settings = Settings(
        EMAIL_BACKEND="resend",
        RESEND_API_KEY="re_test_key_123",
        EMAIL_FROM="CareKavach <noreply@carekavach.local>",
    )
    service = EmailService(settings=settings)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
        res = await service.send(
            recipient="member@example.com",
            subject="Resend Subject",
            text_content="Text body",
            html_content="<p>HTML body</p>",
        )

    assert res.status == "sent"
    assert res.backend == "resend"
    mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_email_service_resend_failure_falls_back_to_log_without_secrets() -> None:
    """Resend API failure falls back to log backend and redacts API key."""
    super_secret_api_key = "re_CONFIDENTIAL_KEY_9999"
    settings = Settings(
        EMAIL_BACKEND="resend",
        RESEND_API_KEY=super_secret_api_key,
        EMAIL_FROM="CareKavach <noreply@carekavach.local>",
    )
    service = EmailService(settings=settings)

    stdout_capture = io.StringIO()
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=Exception(f"HTTP 401 Unauthorized for key={super_secret_api_key}"),
        ),
        patch.object(sys, "stdout", stdout_capture),
    ):
        res = await service.send(
            recipient="member@example.com",
            subject="Resend Alert",
            text_content="Text content",
            html_content="<p>HTML content</p>",
        )

    assert res.status == "logged"
    assert res.backend == "log"
    assert res.error is not None
    assert super_secret_api_key not in res.error
    assert "[REDACTED]" in res.error
    assert super_secret_api_key not in stdout_capture.getvalue()
