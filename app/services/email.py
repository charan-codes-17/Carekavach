import asyncio
import logging
import smtplib
import sys
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Literal

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings, get_settings

logger = logging.getLogger("carekavach.email")

EmailStatus = Literal["sent", "logged", "failed"]

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


@dataclass(frozen=True)
class EmailResult:
    """Immutable outcome of an email dispatch attempt."""

    status: EmailStatus  # "sent", "logged", or "failed"
    recipient: str
    subject: str
    backend: str
    error: str | None = None


def render_email(template_name: str, context: dict[str, Any]) -> tuple[str, str]:
    """Render (text_body, html_body) for a given template base name.

    Jinja autoescape ensures all user-supplied variables in HTML are escaped.
    """
    txt_template = jinja_env.get_template(f"{template_name}.txt")
    html_template = jinja_env.get_template(f"{template_name}.html")
    text_content = txt_template.render(**context)
    html_content = html_template.render(**context)
    return text_content, html_content


class EmailService:
    """Email delivery service supporting SMTP, Resend HTTPS API, and stdout logging fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _sanitize_error(self, message: str) -> str:
        """Strip sensitive credentials from error messages."""
        sanitized = message
        if self.settings.SMTP_PASSWORD:
            sanitized = sanitized.replace(self.settings.SMTP_PASSWORD, "[REDACTED]")
        if self.settings.RESEND_API_KEY:
            sanitized = sanitized.replace(self.settings.RESEND_API_KEY, "[REDACTED]")
        if self.settings.SCHEDULER_SECRET:
            sanitized = sanitized.replace(self.settings.SCHEDULER_SECRET, "[REDACTED]")
        return sanitized

    def _send_log(
        self, recipient: str, subject: str, text_content: str, html_content: str
    ) -> EmailResult:
        """Write full rendered email to stdout without throwing."""
        banner = (
            f"\n{'=' * 20} EMAIL DISPATCH [LOG BACKEND] {'=' * 20}\n"
            f"To: {recipient}\n"
            f"From: {self.settings.EMAIL_FROM}\n"
            f"Subject: {subject}\n"
            "--- Plain Text Content ---\n"
            f"{text_content}\n"
            "--- HTML Content ---\n"
            f"{html_content}\n"
            f"{'=' * 68}\n"
        )
        sys.stdout.write(banner)
        sys.stdout.flush()
        return EmailResult(status="logged", recipient=recipient, subject=subject, backend="log")

    def _send_smtp_sync(
        self, recipient: str, subject: str, text_content: str, html_content: str
    ) -> EmailResult:
        """Synchronous SMTP delivery with STARTTLS and 10s timeout."""
        if not self.settings.SMTP_HOST:
            raise ValueError("SMTP_HOST is not configured")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.settings.EMAIL_FROM
        msg["To"] = recipient

        part1 = MIMEText(text_content, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT, timeout=10.0) as server:
            server.starttls()
            if self.settings.SMTP_USER and self.settings.SMTP_PASSWORD:
                server.login(self.settings.SMTP_USER, self.settings.SMTP_PASSWORD)
            server.send_message(msg)

        return EmailResult(status="sent", recipient=recipient, subject=subject, backend="smtp")

    async def _send_resend(
        self, recipient: str, subject: str, text_content: str, html_content: str
    ) -> EmailResult:
        """HTTPS delivery via Resend API with 10s timeout."""
        if not self.settings.RESEND_API_KEY:
            raise ValueError("RESEND_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.settings.EMAIL_FROM,
            "to": [recipient],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()

        return EmailResult(status="sent", recipient=recipient, subject=subject, backend="resend")

    async def send(
        self,
        recipient: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> EmailResult:
        """Send email via configured backend. Never raises; falls back to log on any error."""
        backend = (self.settings.EMAIL_BACKEND or "log").lower().strip()

        if backend == "log":
            try:
                return self._send_log(recipient, subject, text_content, html_content)
            except Exception as exc:
                return EmailResult(
                    status="failed",
                    recipient=recipient,
                    subject=subject,
                    backend="log",
                    error=self._sanitize_error(str(exc)),
                )

        try:
            if backend == "smtp":
                return await asyncio.to_thread(
                    self._send_smtp_sync, recipient, subject, text_content, html_content
                )
            if backend == "resend":
                return await self._send_resend(recipient, subject, text_content, html_content)

            logger.warning("Unrecognized EMAIL_BACKEND '%s', defaulting to log", backend)
            return self._send_log(recipient, subject, text_content, html_content)
        except Exception as exc:
            sanitized_err = self._sanitize_error(f"{exc.__class__.__name__}: {str(exc)}")
            logger.warning(
                "Email dispatch failed via %s (%s). Falling back to log backend.",
                backend,
                exc.__class__.__name__,
            )
            try:
                fallback_res = self._send_log(recipient, subject, text_content, html_content)
                return EmailResult(
                    status=fallback_res.status,
                    recipient=recipient,
                    subject=subject,
                    backend="log",
                    error=sanitized_err,
                )
            except Exception as fallback_exc:
                return EmailResult(
                    status="failed",
                    recipient=recipient,
                    subject=subject,
                    backend="log",
                    error=self._sanitize_error(str(fallback_exc)),
                )

    async def send_template(
        self,
        recipient: str,
        subject: str,
        template_name: str,
        context: dict[str, Any],
    ) -> EmailResult:
        """Render templates and dispatch email."""
        text_content, html_content = render_email(template_name, context)
        return await self.send(
            recipient=recipient,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
        )
