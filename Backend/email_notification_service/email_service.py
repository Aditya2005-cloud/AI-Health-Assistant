"""
email_notification_service/email_service.py
-------------------------------------------
Orchestration layer — the single entry point for sending consultation emails.

Ties together:
  - email_template.py  → generates the full email content
  - gmail_sender.py    → delivers the email via Gmail SMTP

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
        background           = True,   # fire-and-forget (default)
    )

When background=True (default):
  - Spawns a daemon thread — the HTTP response returns INSTANTLY
  - Email failure NEVER breaks the consultation flow
  - Thread is automatically cleaned up when the process exits
"""

import logging
import threading
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


def _send_email_task(patient_data: dict) -> None:
    """
    Worker executed in a background thread.
    Calls the template builder then the SMTP sender.
    All exceptions are caught here — this thread must NEVER crash silently.
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
            return

        logger.info(
            "[EmailService] Sending HTML report '%s' to '%s'.", subject, to_email
        )

        # Step 2: Send via Gmail SMTP
        success = send_consultation_email_message(
            to_address=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

        if success:
            logger.info("[EmailService] HTML Email delivered to '%s'.", to_email)
        else:
            logger.warning(
                "[EmailService] Delivery FAILED for '%s'. "
                "Check SMTP credentials and network connectivity.", to_email
            )

    except Exception as exc:
        logger.exception(
            "[EmailService] Unhandled exception for patient '%s': %s", patient_name, exc
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
    background:           bool = True,
) -> None:
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
        background           : True → fire-and-forget thread. False → synchronous.

    Returns:
        None
    """
    # ── Skip entirely if Gmail is not configured ──────────────────────────────
    if not GmailConfig.validate():
        logger.warning(
            "[EmailService] Gmail not configured — no email will be sent. "
            "Set GMAIL_SENDER_ADDRESS and GMAIL_APP_PASSWORD in .env."
        )
        return

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

    if background:
        thread = threading.Thread(
            target=_send_email_task,
            args=(patient_data,),
            name=f"email-consult-{patient_name}",
            daemon=True,
        )
        thread.start()
        logger.info(
            "[EmailService] Background email thread started for '%s'.", patient_name
        )
    else:
        # Synchronous mode — useful for tests
        _send_email_task(patient_data)
