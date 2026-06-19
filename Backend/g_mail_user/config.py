"""
g_mail_user/config.py
---------------------
Loads all Gmail / SMTP settings from environment variables.

This is the ONLY file that reads email-related env vars.
No credentials are ever hardcoded here.

Required .env entries:
    GMAIL_SENDER_ADDRESS   — your Gmail address (e.g. clinic@gmail.com)
    GMAIL_APP_PASSWORD     — 16-char App Password (NOT your Gmail login password)
    GMAIL_SENDER_NAME      — display name shown to recipients  (optional)
    GMAIL_SMTP_HOST        — defaults to smtp.gmail.com        (optional)
    GMAIL_SMTP_PORT        — defaults to 587 for TLS           (optional)
    GMAIL_SMTP_TIMEOUT     — seconds to wait for SMTP          (optional)
    GMAIL_SILENT_FAIL      — if True, email errors don't crash app (optional)

How to get a Gmail App Password:
    1. Enable 2-Step Verification: https://myaccount.google.com/security
    2. Create App Password:        https://myaccount.google.com/apppasswords
    3. Choose App: Mail, Device: Other → name it "AI Health Assistant"
    4. Copy the 16-character code into GMAIL_APP_PASSWORD in .env
"""

import os
import logging
from dotenv import load_dotenv

# Load .env from the Backend folder (two levels up from this file)
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_backend_dir, ".env"), override=False)

logger = logging.getLogger(__name__)


class GmailConfig:
    """
    Central configuration class for the Gmail email service.
    All values are sourced from environment variables — never hardcoded.
    """

    # ── Sender identity ───────────────────────────────────────────────────────
    SENDER_ADDRESS: str = os.getenv("GMAIL_SENDER_ADDRESS", "").strip()
    SENDER_NAME: str    = os.getenv("GMAIL_SENDER_NAME", "AI Health Assistant").strip()
    APP_PASSWORD: str   = os.getenv("GMAIL_APP_PASSWORD", "").strip()

    # ── SMTP connection ───────────────────────────────────────────────────────
    SMTP_HOST: str = os.getenv("GMAIL_SMTP_HOST", "smtp.gmail.com").strip()
    SMTP_PORT: int = int(os.getenv("GMAIL_SMTP_PORT", "587"))

    # ── Behaviour ─────────────────────────────────────────────────────────────
    SMTP_TIMEOUT: int = int(os.getenv("GMAIL_SMTP_TIMEOUT", "30"))
    # SILENT_FAIL: True → log errors but don't re-raise (consultation still succeeds)
    SILENT_FAIL: bool = os.getenv("GMAIL_SILENT_FAIL", "True").strip().lower() == "true"

    @classmethod
    def validate(cls) -> bool:
        """
        Check that mandatory environment variables are set.
        Returns True if configuration is complete, False otherwise.
        Logs a clear error message for each missing variable.
        """
        is_valid = True

        if not cls.SENDER_ADDRESS:
            logger.error(
                "[GmailConfig] GMAIL_SENDER_ADDRESS is not set in .env — "
                "add: GMAIL_SENDER_ADDRESS=your_email@gmail.com"
            )
            is_valid = False

        if not cls.APP_PASSWORD:
            logger.error(
                "[GmailConfig] GMAIL_APP_PASSWORD is not set in .env — "
                "generate one at: https://myaccount.google.com/apppasswords"
            )
            is_valid = False

        return is_valid
