"""
email_notification_service/gmail_sender.py
------------------------------------------
Low-level SMTP sender for Gmail using App Password authentication.

Responsibilities:
  - Open a secure TLS (STARTTLS on port 587) or SSL (port 465) connection
  - Authenticate with Gmail App Password — NEVER the account password
  - Build RFC 5322-compliant MIME messages with production-grade headers
  - Send a multi-part HTML + plain-text email with UTF-8 encoding
  - Retry up to 3 times on transient network failures (exponential backoff)
  - Log every attempt for auditability
  - Return a structured result with delivery status and diagnostics

Anti-Spam Best Practices Implemented:
  - All styles INLINED (Gmail/Outlook/Yahoo strip <style> blocks)
  - Proper RFC 5322 headers (Message-ID, Date, Reply-To, Return-Path)
  - List-Unsubscribe for one-click unsubscribe (Gmail surfaces this)
  - Feedback-ID header for Gmail Postmaster reputation tracking
  - text/plain part always attached first as fallback
  - DKIM-friendly domain in Message-ID
  - Correct Content-Transfer-Encoding for UTF-8
  - No spammy subject patterns, no ALL CAPS subjects
  - Precedence: transactional (not bulk/marketing)

Public API:
    send_consultation_email_message(to_address, subject, text_body, html_body) -> dict
        Returns {
            "success": bool,
            "message_id": str | None,
            "smtp_response": str | None,
            "error": str | None,
            "attempts": int,
        }
"""

import smtplib
import logging
import time
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, formataddr, make_msgid
from email.header import Header

from .config import GmailConfig

logger = logging.getLogger(__name__)

# Retry settings
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2  # Delay doubles each attempt: 2s, 4s, 8s


def _build_mime_message(to_address: str, subject: str, text_body: str, html_body: str) -> MIMEMultipart:
    """
    Construct a production-grade MIME email with all headers required by
    RFC 5322 and recommended by Gmail / Outlook / Yahoo spam filters.

    CRITICAL Anti-Spam Headers:
      - Message-ID       : Unique per message (prevents duplicate detection issues)
      - Date             : RFC 2822 formatted timestamp (missing = instant spam flag)
      - Reply-To         : Signals a real sender identity
      - Return-Path      : Bounce address (must match From domain for SPF)
      - List-Unsubscribe : Allows one-click unsubscribe (Gmail surfaces this in UI)
      - Feedback-ID      : Gmail Postmaster Tools reputation tracking
      - X-Mailer         : Identifies the sending application (legitimate senders set this)
      - MIME-Version     : Explicit MIME version declaration
      - Precedence       : Marks as transactional mail (not marketing/bulk)
      - X-Auto-Response-Suppress : Prevents auto-replies (Outlook)
      - X-Priority       : Normal priority (high priority = spam signal)

    CRITICAL Structure:
      - multipart/alternative with text/plain FIRST, text/html SECOND
      - text/plain must be a genuine readable version (not empty)
      - Both parts must use UTF-8 charset explicitly
    """
    message = MIMEMultipart("alternative")

    # ── Generate a globally unique Message-ID ────────────────────────────────
    # Format: <UUID@sender-domain> — RFC 5322 compliant
    sender_domain = GmailConfig.SENDER_ADDRESS.split("@")[-1] if "@" in GmailConfig.SENDER_ADDRESS else "gmail.com"
    message_id = make_msgid(domain=sender_domain)

    # ── Core identity headers ────────────────────────────────────────────────
    message["Subject"]    = str(Header(subject, "utf-8"))
    message["From"]       = formataddr((GmailConfig.SENDER_NAME, GmailConfig.SENDER_ADDRESS))
    message["To"]         = to_address
    message["Reply-To"]   = formataddr((GmailConfig.SENDER_NAME, GmailConfig.SENDER_ADDRESS))
    message["Return-Path"] = GmailConfig.SENDER_ADDRESS

    # ── Anti-spam compliance headers ─────────────────────────────────────────
    message["Message-ID"]   = message_id
    message["Date"]         = formatdate(localtime=True)
    message["MIME-Version"] = "1.0"
    message["X-Mailer"]     = "Medivio Health Platform v2.0"
    message["Precedence"]   = "transactional"
    message["X-Priority"]   = "3"  # Normal priority (1=High triggers spam)

    # Prevent auto-reply loops (Outlook, Exchange)
    message["X-Auto-Response-Suppress"] = "OOF, AutoReply"

    # Gmail Postmaster Tools: helps build sender reputation
    # Format: campaignId:customerId:mailerId:senderId
    message["Feedback-ID"] = f"medivio-consult:{sender_domain}:health-report:medivio"

    # List-Unsubscribe header — Gmail uses this to show the unsubscribe button
    # instead of marking as spam. Even for transactional mail, this helps.
    message["List-Unsubscribe"] = f"<mailto:{GmailConfig.SENDER_ADDRESS}?subject=unsubscribe>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    # ── Attach plain text part first (fallback for text-only clients) ────────
    text_part = MIMEText(text_body, "plain", "utf-8")
    text_part.set_charset("utf-8")
    message.attach(text_part)

    # ── Attach HTML part second (preferred by modern clients) ────────────────
    html_part = MIMEText(html_body, "html", "utf-8")
    html_part.set_charset("utf-8")
    message.attach(html_part)

    return message, message_id


def send_consultation_email_message(to_address: str, subject: str, text_body: str, html_body: str) -> dict:
    """
    Send an email containing both plain text and HTML formatted variants.

    Returns a structured result dict instead of a bare bool, enabling
    the caller to log delivery status, message IDs, and error diagnostics.

    Returns:
        {
            "success": bool,
            "message_id": str | None,
            "smtp_response": str | None,
            "error": str | None,
            "attempts": int,
        }
    """
    result = {
        "success": False,
        "message_id": None,
        "smtp_response": None,
        "error": None,
        "attempts": 0,
    }

    # ── Guard: validate config before touching the network ────────────────────
    if not GmailConfig.validate():
        result["error"] = "Gmail is not configured. Set GMAIL_SENDER_ADDRESS and GMAIL_APP_PASSWORD in .env."
        raise RuntimeError(result["error"])

    # ── Guard: basic email address sanity check ───────────────────────────────
    if not to_address or "@" not in to_address:
        logger.error(
            "[GmailSender] Invalid recipient address: '%s'. Email not sent.", to_address
        )
        result["error"] = f"Invalid recipient address: '{to_address}'"
        return result

    mime_message, message_id = _build_mime_message(to_address, subject, text_body, html_body)
    result["message_id"] = message_id

    # ── Retry loop ────────────────────────────────────────────────────────────
    for attempt in range(1, _MAX_RETRIES + 1):
        result["attempts"] = attempt
        try:
            logger.info(
                "[GmailSender] Attempt %d/%d → connecting to %s:%d (Message-ID: %s)",
                attempt, _MAX_RETRIES, GmailConfig.SMTP_HOST, GmailConfig.SMTP_PORT, message_id,
            )

            smtp_response_text = None

            if GmailConfig.SMTP_PORT == 465:
                # SSL connection (no STARTTLS upgrade needed)
                with smtplib.SMTP_SSL(
                    GmailConfig.SMTP_HOST,
                    GmailConfig.SMTP_PORT,
                    timeout=GmailConfig.SMTP_TIMEOUT,
                ) as server:
                    server.login(GmailConfig.SENDER_ADDRESS, GmailConfig.APP_PASSWORD)
                    smtp_result = server.sendmail(
                        GmailConfig.SENDER_ADDRESS,
                        to_address,
                        mime_message.as_string(),
                    )
                    smtp_response_text = f"Accepted (SSL). Refused: {smtp_result}" if smtp_result else "Accepted (SSL/465)"
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
                    smtp_result = server.sendmail(
                        GmailConfig.SENDER_ADDRESS,
                        to_address,
                        mime_message.as_string(),
                    )
                    smtp_response_text = f"Accepted (TLS). Refused: {smtp_result}" if smtp_result else "Accepted (TLS/587)"

            logger.info(
                "[GmailSender] ✅ Email sent to '%s' successfully (attempt %d, Message-ID: %s). SMTP: %s",
                to_address, attempt, message_id, smtp_response_text,
            )
            result["success"] = True
            result["smtp_response"] = smtp_response_text
            return result

        except smtplib.SMTPAuthenticationError as auth_err:
            # Wrong credentials — retrying won't help
            error_msg = f"Authentication FAILED. Check GMAIL_SENDER_ADDRESS and GMAIL_APP_PASSWORD. Error: {auth_err}"
            logger.error("[GmailSender] %s", error_msg)
            result["error"] = error_msg
            return result

        except smtplib.SMTPRecipientsRefused as refused_err:
            # Server rejected the recipient address — retrying won't help
            error_msg = f"Recipient '{to_address}' was refused by Gmail: {refused_err}"
            logger.error("[GmailSender] %s", error_msg)
            result["error"] = error_msg
            return result

        except (smtplib.SMTPException, OSError, TimeoutError, socket.error) as transient_err:
            # Network / transient error — retry with backoff
            delay = _RETRY_BASE_DELAY_SECONDS ** attempt
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "[GmailSender] Transient error (attempt %d/%d): %s — retrying in %ds.",
                    attempt, _MAX_RETRIES, transient_err, delay,
                )
                time.sleep(delay)
            else:
                error_msg = f"All {_MAX_RETRIES} attempts exhausted. Last error: {transient_err}"
                logger.error(
                    "[GmailSender] %s. Email to '%s' NOT sent.", error_msg, to_address,
                )
                result["error"] = error_msg
                return result

        except Exception as unexpected_err:
            # Catch-all safety net
            error_msg = f"Unexpected error: {unexpected_err}"
            logger.exception(
                "[GmailSender] %s sending to '%s'", error_msg, to_address,
            )
            result["error"] = error_msg
            return result

    result["error"] = "Exhausted all retry attempts"
    return result  # Safety net — should not reach here
