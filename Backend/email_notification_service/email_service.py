"""
email_notification_service/email_service.py
-------------------------------------------
Orchestration layer — the single entry point for sending consultation emails.

v2.0 Changes:
  - Records every email attempt in the `email_logs` database table
  - Tracks delivery status (queued → delivered / failed / skipped)
  - Stores RFC 5322 Message-ID, SMTP response, and error diagnostics
  - Allows users to verify delivery via the /api/email-status endpoint

Ties together:
  - email_template.py  → generates the full email content
  - gmail_sender.py    → delivers the email via Gmail SMTP
  - database/models.py → EmailLog model for delivery tracking

Usage in consult_routes.py (after db.session.commit()):

    from email_notification_service import dispatch_consultation_email

    dispatch_consultation_email(
        patient_name         = current_user.full_name,
        age                  = current_user.age,
        gender               = current_user.gender,
        symptoms_description = symptoms,
        symptom_tags         = result.get("severity", ""),
        medical_history      = current_user.medical_conditions,
        allergies            = current_user.known_allergies,
        ai_assessment        = result.get("groq_response") or result.get("gemini_response"),
        user_email           = current_user.email,
        user_id              = current_user.id,
        consultation_id      = consultation.id,
        background           = True,   # fire-and-forget (default)
    )

When background=True (default):
  - Spawns a daemon thread — the HTTP response returns INSTANTLY
  - Email failure NEVER breaks the consultation flow
  - Thread is automatically cleaned up when the process exits
  - Delivery status is persisted in the email_logs table regardless
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from .email_template import build_consultation_email
from .gmail_sender import send_consultation_email_message
from .config import GmailConfig

logger = logging.getLogger(__name__)


def _extract_assessment_text(ai_result) -> str:
    """
    Safely flatten the AI pipeline's response (str OR nested dict) into
    a single plain-text string for the email template.

    Handles the real response structures returned by Gemini / Groq.
    """
    if ai_result is None:
        return ""

    if isinstance(ai_result, str):
        return ai_result.strip()

    if not isinstance(ai_result, dict):
        return str(ai_result).strip()

    # ── Try top-level string keys (Groq / Gemini direct responses) ────────────
    for key in (
        "patient_summary",
        "presentation_summary",
        "summary",
        "condition",
        "diagnosis",
        "assessment",
        "raw_response",
    ):
        value = ai_result.get(key)
        if value and isinstance(value, str) and value.strip():
            return value.strip()

    # ── Try nested objects (e.g. junior_clinician_assessment) ─────────────────
    for nested_key in ("junior_clinician_assessment", "senior_doctor_review", "clinical_summary"):
        nested = ai_result.get(nested_key)
        if isinstance(nested, dict):
            for key in ("presentation_summary", "summary", "patient_summary"):
                value = nested.get(key)
                if value and isinstance(value, str) and value.strip():
                    return value.strip()

    # ── Last resort: join all string values ───────────────────────────────────
    parts = [f"{k}: {v.strip()}" for k, v in ai_result.items() if isinstance(v, str) and v.strip()]
    return "\n".join(parts)


def _update_email_log(app, log_id: int, **kwargs) -> None:
    """
    Safely update an EmailLog record within the Flask application context.
    This is called from a background thread, so we need to push an app context.
    """
    try:
        with app.app_context():
            from database import db
            from database.models import EmailLog

            log_entry = db.session.get(EmailLog, log_id)
            if not log_entry:
                logger.warning("[EmailService] EmailLog #%d not found for update.", log_id)
                return

            for key, value in kwargs.items():
                if hasattr(log_entry, key):
                    setattr(log_entry, key, value)

            db.session.commit()
            logger.info(
                "[EmailService] EmailLog #%d updated: status=%s",
                log_id, kwargs.get("status", "unknown")
            )
    except Exception as exc:
        logger.exception("[EmailService] Failed to update EmailLog #%d: %s", log_id, exc)


def _send_email_task(patient_data: dict, app=None, log_id: int = None) -> None:
    """
    Worker executed in a background thread.
    Calls the template builder then the SMTP sender.
    All exceptions are caught here — this thread must NEVER crash silently.

    Records delivery result back to the EmailLog table if app context is available.
    """
    patient_name = patient_data.get("patient_name", "Patient")
    user_email   = patient_data.get("user_email", "")

    try:
        logger.info(
            "[EmailService] Building email for '%s' → %s", patient_name, user_email
        )

        # Step 1: Generate email content (both text and HTML variants)
        email_payload = build_consultation_email(patient_data)
        subject   = email_payload["subject"]
        text_body = email_payload["text_body"]
        html_body = email_payload["html_body"]
        to_email  = email_payload.get("to_email") or user_email

        if not to_email:
            logger.warning(
                "[EmailService] No recipient address for '%s'. Skipping email.", patient_name
            )
            if app and log_id:
                _update_email_log(app, log_id,
                    status="skipped",
                    error_message="No recipient email address available",
                    failed_at=datetime.now(timezone.utc),
                )
            return

        logger.info(
            "[EmailService] Sending HTML report '%s' to '%s'.", subject, to_email
        )

        # Update the log with the subject now that we have it
        if app and log_id:
            _update_email_log(app, log_id, subject=subject)

        # Inject dynamic open tracking pixel
        if log_id:
            base_url = "http://localhost:5000"
            if app:
                base_url = app.config.get("APP_BASE_URL", "http://localhost:5000").rstrip("/")
            tracking_pixel_url = f"{base_url}/api/email-status/track/{log_id}.gif"
            tracking_tag = f'<img src="{tracking_pixel_url}" width="1" height="1" alt="" style="display:none;width:1px;height:1px;" />'
            if "</body>" in html_body:
                html_body = html_body.replace("</body>", f"{tracking_tag}\n</body>")
            else:
                html_body += tracking_tag

        # Step 2: Send via Gmail SMTP (returns structured result dict)
        send_result = send_consultation_email_message(
            to_address=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

        # Step 3: Record delivery result
        if send_result["success"]:
            logger.info("[EmailService] ✅ Email delivered to '%s'. Message-ID: %s", to_email, send_result["message_id"])
            if app and log_id:
                _update_email_log(app, log_id,
                    status="delivered",
                    message_id=send_result.get("message_id"),
                    smtp_response=send_result.get("smtp_response"),
                    retry_count=send_result.get("attempts", 1),
                    delivered_at=datetime.now(timezone.utc),
                )
        else:
            logger.warning(
                "[EmailService] ❌ Delivery FAILED for '%s'. Error: %s",
                to_email, send_result.get("error", "Unknown")
            )
            if app and log_id:
                _update_email_log(app, log_id,
                    status="failed",
                    message_id=send_result.get("message_id"),
                    error_message=send_result.get("error"),
                    retry_count=send_result.get("attempts", 0),
                    failed_at=datetime.now(timezone.utc),
                )

    except Exception as exc:
        logger.exception(
            "[EmailService] Unhandled exception for patient '%s': %s", patient_name, exc
        )
        if app and log_id:
            _update_email_log(app, log_id,
                status="failed",
                error_message=f"Unhandled exception: {exc}",
                failed_at=datetime.now(timezone.utc),
            )


def dispatch_consultation_email(
    patient_name:         str,
    age:                  Optional[str],
    gender:               Optional[str],
    symptoms_description: str,
    symptom_tags:         Optional[str],
    medical_history:      Optional[str],
    allergies:            Optional[str],
    ai_assessment,                       # str | dict — accepts either
    user_email:           str,
    user_id:              int   = None,
    consultation_id:      int   = None,
    background:           bool  = True,
) -> Optional[int]:
    """
    Public API — generate and dispatch a consultation summary email.

    Called immediately after db.session.commit() in consult_routes.py.

    Args:
        patient_name         : Patient's full name.
        age                  : Patient's age (str or int).
        gender               : Patient's gender.
        symptoms_description : Free-text symptoms submitted by patient.
        symptom_tags         : Severity tag from AI (e.g. "Moderate").
        medical_history      : Known conditions / current medications.
        allergies            : Known allergies (comma-separated string).
        ai_assessment        : Raw AI response (Groq dict preferred, str ok).
        user_email           : Recipient email address.
        user_id              : Database user ID (for email log tracking).
        consultation_id      : Database consultation ID (for linking).
        background           : True → fire-and-forget thread. False → synchronous.

    Returns:
        int | None — The EmailLog record ID if tracking is enabled, else None.
    """
    # ── Skip entirely if Gmail is not configured ──────────────────────────────
    if not GmailConfig.validate():
        logger.warning(
            "[EmailService] Gmail not configured — no email will be sent. "
            "Set GMAIL_SENDER_ADDRESS and GMAIL_APP_PASSWORD in .env."
        )
        return None

    # ── Flatten the AI response to plain text ─────────────────────────────────
    assessment_text = _extract_assessment_text(ai_assessment)

    # ── Build the patient data dict ───────────────────────────────────────────
    patient_data = {
        "patient_name":         (patient_name or "Patient").strip(),
        "age":                  str(age) if age else "Not specified",
        "gender":               (gender or "Not specified").strip(),
        "symptoms_description": (symptoms_description or "").strip(),
        "symptom_tags":         (symptom_tags or "").strip(),
        "medical_history":      (medical_history or "").strip(),
        "allergies":            (allergies or "").strip(),
        "ai_assessment":        assessment_text,
        "user_email":           (user_email or "").strip(),
    }

    # ── Create an EmailLog record (status: queued) ────────────────────────────
    log_id = None
    app = None
    if user_id:
        try:
            from flask import current_app
            app = current_app._get_current_object()

            from database import db
            from database.models import EmailLog

            email_log = EmailLog(
                user_id=user_id,
                consultation_id=consultation_id,
                recipient_email=(user_email or "").strip(),
                subject="(generating...)",
                status="queued",
            )
            db.session.add(email_log)
            db.session.commit()
            log_id = email_log.id
            logger.info("[EmailService] EmailLog #%d created (queued) for user #%d.", log_id, user_id)
        except Exception as log_err:
            logger.warning("[EmailService] Could not create EmailLog entry: %s", log_err)

    if background:
        thread = threading.Thread(
            target=_send_email_task,
            args=(patient_data,),
            kwargs={"app": app, "log_id": log_id},
            name=f"email-consult-{patient_name}",
            daemon=True,
        )
        thread.start()
        logger.info(
            "[EmailService] Background email thread started for '%s' (EmailLog #%s).", patient_name, log_id
        )
    else:
        # Synchronous mode — useful for tests
        _send_email_task(patient_data, app=app, log_id=log_id)

    return log_id
