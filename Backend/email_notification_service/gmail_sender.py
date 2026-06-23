"""
email_notification_service/gmail_sender.py
------------------------------------------
Low-level SMTP sender for Gmail using App Password authentication.

Responsibilities:
  - Open a secure TLS (STARTTLS on port 587) or SSL (port 465) connection
  - Authenticate with Gmail App Password — NEVER the account password
  - Send a plain-text email with UTF-8 encoding
  - Retry up to 3 times on transient network failures (exponential backoff)
  - Log every attempt for auditability

Public API:
    send_plain_text_email(to_address, subject, body) -> bool
"""

import smtplib
import logging
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .config import GmailConfig

logger = logging.getLogger(__name__)

# Retry settings
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2  # Delay doubles each attempt: 2s, 4s, 8s


def _build_mime_message(to_address: str, subject: str, text_body: str, html_body: str) -> MIMEMultipart:
    """
    Construct a MIME email message object with both Plain Text and HTML alternatives.
    """
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"]    = f"{GmailConfig.SENDER_NAME} <{GmailConfig.SENDER_ADDRESS}>"
    message["To"]      = to_address

    # Attach plain text part first (fallback)
    text_part = MIMEText(text_body, "plain", "utf-8")
    message.attach(text_part)

    # Attach HTML part second (preferred by modern clients)
    html_part = MIMEText(html_body, "html", "utf-8")
    message.attach(html_part)

    return message


def send_consultation_email_message(to_address: str, subject: str, text_body: str, html_body: str) -> bool:
    """
    Send an email containing both plain text and HTML formatted variants.
    """
    # ── Guard: validate config before touching the network ────────────────────
    if not GmailConfig.validate():
        raise RuntimeError(
            "Gmail is not configured. "
            "Set GMAIL_SENDER_ADDRESS and GMAIL_APP_PASSWORD in your .env file."
        )

    # ── Guard: basic email address sanity check ───────────────────────────────
    if not to_address or "@" not in to_address:
        logger.error(
            "[GmailSender] Invalid recipient address: '%s'. Email not sent.", to_address
        )
        return False

    mime_message = _build_mime_message(to_address, subject, text_body, html_body)

    # ── Retry loop ────────────────────────────────────────────────────────────
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(
                "[GmailSender] Attempt %d/%d → connecting to %s:%d",
                attempt, _MAX_RETRIES, GmailConfig.SMTP_HOST, GmailConfig.SMTP_PORT,
            )

            if GmailConfig.SMTP_PORT == 465:
                # SSL connection (no STARTTLS upgrade needed)
                with smtplib.SMTP_SSL(
                    GmailConfig.SMTP_HOST,
                    GmailConfig.SMTP_PORT,
                    timeout=GmailConfig.SMTP_TIMEOUT,
                ) as server:
                    server.login(GmailConfig.SENDER_ADDRESS, GmailConfig.APP_PASSWORD)
                    server.sendmail(
                        GmailConfig.SENDER_ADDRESS,
                        to_address,
                        mime_message.as_string(),
                    )
            else:
                # TLS connection via STARTTLS (port 587, Gmail default)
                with smtplib.SMTP(
                    GmailConfig.SMTP_HOST,
                    GmailConfig.SMTP_PORT,
                    timeout=GmailConfig.SMTP_TIMEOUT,
                ) as server:
                    server.ehlo()        # Greet SMTP server
                    server.starttls()    # Upgrade plain connection to TLS
                    server.ehlo()        # Re-greet after TLS upgrade
                    server.login(GmailConfig.SENDER_ADDRESS, GmailConfig.APP_PASSWORD)
                    server.sendmail(
                        GmailConfig.SENDER_ADDRESS,
                        to_address,
                        mime_message.as_string(),
                    )

            logger.info(
                "[GmailSender] Email sent to '%s' successfully (attempt %d).",
                to_address, attempt,
            )
            return True

        except smtplib.SMTPAuthenticationError as auth_err:
            # Wrong credentials — retrying won't help
            logger.error(
                "[GmailSender] Authentication FAILED. "
                "Check GMAIL_SENDER_ADDRESS and GMAIL_APP_PASSWORD. Error: %s", auth_err,
            )
            return False

        except smtplib.SMTPRecipientsRefused as refused_err:
            # Server rejected the recipient address — retrying won't help
            logger.error(
                "[GmailSender] Recipient '%s' was refused by Gmail: %s",
                to_address, refused_err,
            )
            return False

        except (smtplib.SMTPException, OSError, TimeoutError) as transient_err:
            # Network / transient error — retry with backoff
            delay = _RETRY_BASE_DELAY_SECONDS ** attempt
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "[GmailSender] Transient error (attempt %d/%d): %s — retrying in %ds.",
                    attempt, _MAX_RETRIES, transient_err, delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "[GmailSender] All %d attempts exhausted. Email to '%s' NOT sent. "
                    "Last error: %s",
                    _MAX_RETRIES, to_address, transient_err,
                )
                return False

        except Exception as unexpected_err:
            # Catch-all safety net
            logger.exception(
                "[GmailSender] Unexpected error sending to '%s': %s",
                to_address, unexpected_err,
            )
            return False

    return False  # Safety net — should not reach here
