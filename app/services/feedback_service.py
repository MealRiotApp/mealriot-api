import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _build_feedback_html(
    user_name: str, user_email: str, message: str,
    user_agent: str, screen_width: int | None, screen_height: int | None,
    page_url: str | None,
) -> str:
    screen = f"{screen_width}x{screen_height}" if screen_width and screen_height else "Unknown"
    return f"""
    <h2>User Feedback</h2>
    <p><strong>From:</strong> {user_name} ({user_email})</p>
    <p><strong>Page:</strong> {page_url or 'Not provided'}</p>
    <h3>Message</h3>
    <p>{message}</p>
    <h3>Device Info</h3>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
        <tr><td><strong>User Agent</strong></td><td>{user_agent}</td></tr>
        <tr><td><strong>Screen Size</strong></td><td>{screen}</td></tr>
    </table>
    """


async def send_feedback_email(
    user_name: str, user_email: str, message: str, user_agent: str,
    screen_width: int | None = None, screen_height: int | None = None,
    page_url: str | None = None,
    screenshot_data: bytes | None = None, screenshot_filename: str | None = None,
) -> None:
    settings = get_settings()
    smtp_host = getattr(settings, "smtp_host", None)
    smtp_user = getattr(settings, "smtp_user", None)
    smtp_pass = getattr(settings, "smtp_pass", None)

    if not all([smtp_host, smtp_user, smtp_pass]):
        raise RuntimeError("SMTP not configured")

    html = _build_feedback_html(user_name, user_email, message, user_agent, screen_width, screen_height, page_url)

    msg = MIMEMultipart()
    msg["Subject"] = f"MealRiot Feedback from {user_name}"
    msg["From"] = smtp_user
    msg["To"] = settings.admin_email
    msg.attach(MIMEText(html, "html"))

    if screenshot_data and screenshot_filename:
        img = MIMEImage(screenshot_data)
        img.add_header("Content-Disposition", "attachment", filename=screenshot_filename)
        msg.attach(img)

    def _send():
        with smtplib.SMTP(smtp_host, 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Feedback email sent from %s", user_email)

    try:
        await asyncio.to_thread(_send)
    except Exception as e:
        logger.error("Failed to send feedback email: %s", e)
        raise
