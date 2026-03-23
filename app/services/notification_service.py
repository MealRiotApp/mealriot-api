import asyncio
import smtplib
from email.mime.text import MIMEText
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)


def _send_email_sync(to: str, subject: str, body: str) -> None:
    """Send email via SMTP. Runs in thread to not block async."""
    settings = get_settings()
    smtp_host = getattr(settings, "smtp_host", None)
    smtp_user = getattr(settings, "smtp_user", None)
    smtp_pass = getattr(settings, "smtp_pass", None)

    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.info(f"SMTP not configured. Would send to {to}: {subject}")
        return

    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to

    try:
        with smtplib.SMTP(smtp_host, 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"Email sent to {to}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


async def notify_admin_new_user(user_name: str, user_email: str) -> None:
    """Notify admin when a new user signs up and needs approval."""
    settings = get_settings()
    admin_email = settings.admin_email

    subject = f"NutriLog: New user awaiting approval — {user_name}"
    body = f"""
    <h2>New User Registration</h2>
    <p><strong>Name:</strong> {user_name}</p>
    <p><strong>Email:</strong> {user_email}</p>
    <p>Log in to the <a href="{settings.frontend_url}/admin">Admin Panel</a> to approve or reject this user.</p>
    """

    await asyncio.to_thread(_send_email_sync, admin_email, subject, body)
