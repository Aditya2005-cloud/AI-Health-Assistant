"""
routes/notification.py
----------------------
API routes for user notifications and email delivery status.

Endpoints:
  GET  /api/notifications             → All notifications for user
  GET  /api/notifications/unread      → Unread notifications only
  POST /api/notifications/<id>/read   → Mark one as read
  POST /api/notifications/mark-read   → Mark all as read

  GET  /api/email-status              → Email delivery history (paginated)
  GET  /api/email-status/<id>         → Status for a specific consultation
  POST /api/email-status/<id>/resend  → Resend a failed/skipped email
  POST /api/email-status/send-test    → Send a test email to verify delivery
"""

import logging
import base64
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, Response
from database import db
from database.models import DashboardNotification, EmailLog
from middleware import jwt_required

logger = logging.getLogger(__name__)

notification_bp = Blueprint("notification", __name__)


# ─────────────────────────────────────────────
# Dashboard Notification Routes
# ─────────────────────────────────────────────

@notification_bp.route("/api/notifications", methods=["GET"])
@jwt_required
def get_all_notifications(current_user):
    """Retrieve all notifications for the logged-in user."""
    notifications = (
        DashboardNotification.query
        .filter_by(user_id=current_user.id)
        .order_by(DashboardNotification.created_at.desc())
        .all()
    )
    return jsonify({
        "notifications": [n.to_dict() for n in notifications],
        "total": len(notifications)
    }), 200

@notification_bp.route("/api/notifications/unread", methods=["GET"])
@jwt_required
def get_unread_notifications(current_user):
    """Retrieve only unread notifications for the logged-in user."""
    notifications = (
        DashboardNotification.query
        .filter_by(user_id=current_user.id, is_read=False)
        .order_by(DashboardNotification.created_at.desc())
        .all()
    )
    return jsonify({
        "notifications": [n.to_dict() for n in notifications],
        "unread_count": len(notifications)
    }), 200

@notification_bp.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
@jwt_required
def mark_single_read(current_user, notification_id):
    """Mark a single notification as read."""
    notification = DashboardNotification.query.filter_by(
        id=notification_id, user_id=current_user.id
    ).first()
    
    if not notification:
        return jsonify({"error": "Notification not found"}), 404
        
    notification.is_read = True
    db.session.commit()
    return jsonify({"message": "Notification marked as read"}), 200

@notification_bp.route("/api/notifications/mark-read", methods=["POST"])
@jwt_required
def mark_all_read(current_user):
    """Mark all unread notifications for the user as read."""
    unread_notifications = DashboardNotification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).all()
    
    for notification in unread_notifications:
        notification.is_read = True
        
    db.session.commit()
    return jsonify({"message": "All notifications marked as read", "count": len(unread_notifications)}), 200


# ─────────────────────────────────────────────
# Email Delivery Status Routes
# ─────────────────────────────────────────────

@notification_bp.route("/api/email-status", methods=["GET"])
@jwt_required
def get_email_delivery_history(current_user):
    """
    Get the email delivery history for the logged-in user.

    Query params:
        page     (int) : Page number (default: 1)
        per_page (int) : Items per page (default: 20, max: 50)
        status   (str) : Filter by status (queued | delivered | failed | skipped)

    Returns a paginated list of email delivery logs with full diagnostics.
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 50)
    status_filter = request.args.get("status", "").strip().lower()

    query = EmailLog.query.filter_by(user_id=current_user.id)

    if status_filter in ("queued", "delivered", "failed", "skipped"):
        query = query.filter_by(status=status_filter)

    email_logs = (
        query
        .order_by(EmailLog.queued_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Build summary statistics
    total_delivered = EmailLog.query.filter_by(user_id=current_user.id, status="delivered").count()
    total_failed = EmailLog.query.filter_by(user_id=current_user.id, status="failed").count()
    total_queued = EmailLog.query.filter_by(user_id=current_user.id, status="queued").count()

    return jsonify({
        "email_logs": [log.to_dict() for log in email_logs.items],
        "total": email_logs.total,
        "page": page,
        "pages": email_logs.pages,
        "summary": {
            "delivered": total_delivered,
            "failed": total_failed,
            "queued": total_queued,
        }
    }), 200


@notification_bp.route("/api/email-status/<int:consultation_id>", methods=["GET"])
@jwt_required
def get_email_status_for_consultation(current_user, consultation_id):
    """
    Get the email delivery status for a specific consultation.

    This is the primary endpoint for checking "did my email arrive?"
    after a consultation is completed.
    """
    email_log = EmailLog.query.filter_by(
        user_id=current_user.id,
        consultation_id=consultation_id,
    ).order_by(EmailLog.queued_at.desc()).first()

    if not email_log:
        return jsonify({
            "found": False,
            "message": "No email record found for this consultation. "
                       "Email may not have been triggered (e.g. Gmail not configured).",
        }), 200

    return jsonify({
        "found": True,
        "email_log": email_log.to_dict(),
        "delivery_verified": email_log.status == "delivered",
        "human_status": _human_readable_status(email_log),
    }), 200


@notification_bp.route("/api/email-status/<int:consultation_id>/resend", methods=["POST"])
@jwt_required
def resend_consultation_email(current_user, consultation_id):
    """
    Resend a consultation email that previously failed or was skipped.

    This allows users to retry delivery when they didn't receive the email.
    Rate limited: max 3 resends per consultation.
    """
    from database.models import Consultation

    # Verify the consultation belongs to this user
    consultation = Consultation.query.filter_by(
        id=consultation_id, user_id=current_user.id
    ).first()

    if not consultation:
        return jsonify({"error": "Consultation not found"}), 404

    # Check resend count (prevent abuse)
    existing_logs = EmailLog.query.filter_by(
        user_id=current_user.id,
        consultation_id=consultation_id,
    ).all()

    if len(existing_logs) >= 4:  # 1 original + 3 resends max
        return jsonify({
            "error": "Maximum resend limit reached (3 resends). "
                     "Please check your spam folder or verify your email address.",
            "resend_count": len(existing_logs) - 1,
        }), 429

    # Check if the last attempt was delivered successfully
    latest_log = max(existing_logs, key=lambda l: l.queued_at) if existing_logs else None
    if latest_log and latest_log.status == "delivered":
        return jsonify({
            "error": "The email was already delivered successfully. "
                     "Please check your inbox, spam, or promotions folder.",
            "email_log": latest_log.to_dict(),
        }), 200

    # Dispatch the email again
    try:
        from email_notification_service import dispatch_consultation_email

        log_id = dispatch_consultation_email(
            patient_name         = current_user.full_name,
            age                  = current_user.age,
            gender               = current_user.gender,
            symptoms_description = consultation.symptoms_input,
            symptom_tags         = consultation.severity or "",
            medical_history      = current_user.medical_conditions,
            allergies            = current_user.known_allergies,
            ai_assessment        = consultation.groq_validation or consultation.gemini_analysis,
            user_email           = current_user.email,
            user_id              = current_user.id,
            consultation_id      = consultation.id,
            background           = True,
        )

        return jsonify({
            "success": True,
            "message": f"Email is being resent to {current_user.email}. "
                       "Check your inbox in 1-2 minutes.",
            "email_log_id": log_id,
            "resend_count": len(existing_logs),
        }), 200

    except Exception as e:
        logger.exception("[Notification] Resend failed for consultation #%d: %s", consultation_id, e)
        return jsonify({
            "error": "Failed to resend email. Please try again later.",
            "detail": str(e),
        }), 500


@notification_bp.route("/api/email-status/send-test", methods=["POST"])
@jwt_required
def send_test_email(current_user):
    """
    Send a test email to verify the user's email is configured correctly
    and emails are reaching their inbox (not spam).

    This helps users confirm their email setup before relying on
    consultation emails.
    """
    from email_notification_service.config import GmailConfig
    from email_notification_service.gmail_sender import send_consultation_email_message

    if not GmailConfig.validate():
        return jsonify({
            "error": "Email service is not configured. Contact support.",
        }), 503

    if not current_user.email or "@" not in current_user.email:
        return jsonify({
            "error": "No valid email address on your account. Please update your profile.",
        }), 400

    # Rate limit: max 1 test email per 5 minutes
    recent_test = EmailLog.query.filter(
        EmailLog.user_id == current_user.id,
        EmailLog.subject.like("%Delivery Test%"),
        EmailLog.queued_at >= datetime.now(timezone.utc).replace(
            minute=datetime.now(timezone.utc).minute - 5
        ),
    ).first()

    if recent_test:
        return jsonify({
            "error": "Please wait 5 minutes between test emails.",
            "last_test": recent_test.to_dict(),
        }), 429

    # Build a simple test email
    subject = "Medivio - Email Delivery Test"
    text_body = (
        f"Hello {current_user.full_name},\n\n"
        "This is a test email from Medivio to verify that emails are "
        "reaching your inbox correctly.\n\n"
        "If you received this email:\n"
        "  - Your email configuration is working correctly\n"
        "  - Consultation summary emails will be delivered to this address\n\n"
        "If this email landed in your Spam folder:\n"
        "  - Please mark it as 'Not Spam'\n"
        "  - Add our sender address to your contacts\n"
        "  - This will ensure future emails reach your inbox\n\n"
        "Warm regards,\n"
        "Medivio Team\n"
    )
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;line-height:1.6;color:#334155;background-color:#f8fafc;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;">
<tr><td align="center" style="padding:20px 10px;">
<table role="presentation" width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;background-color:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;">
<tr><td style="background:linear-gradient(135deg,#0f766e,#0d9488);padding:24px;text-align:center;color:#ffffff;">
    <h1 style="margin:0;font-size:22px;font-weight:700;color:#ffffff;">Medivio</h1>
    <p style="margin:4px 0 0 0;font-size:13px;color:#ccfbf1;">Email Delivery Verification</p>
</td></tr>
<tr><td style="padding:30px 24px;">
    <h2 style="margin:0 0 16px 0;font-size:18px;color:#1e293b;">Hello {current_user.full_name},</h2>
    <p style="font-size:14px;color:#475569;margin:0 0 16px 0;">
        This is a test email to verify that emails from Medivio are reaching your inbox correctly.
    </p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;margin:20px 0;">
    <tr><td style="padding:16px;">
        <p style="margin:0 0 8px 0;font-size:14px;font-weight:700;color:#166534;">If you see this in your inbox:</p>
        <p style="margin:0;font-size:14px;color:#334155;">Your email is configured correctly. Consultation summaries will be delivered to <strong>{current_user.email}</strong>.</p>
    </td></tr></table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#fef2f2;border:1px solid #fecaca;border-radius:8px;margin:16px 0;">
    <tr><td style="padding:16px;">
        <p style="margin:0 0 8px 0;font-size:14px;font-weight:700;color:#991b1b;">If this landed in Spam:</p>
        <ul style="margin:0;padding-left:20px;font-size:14px;color:#334155;">
            <li style="margin-bottom:6px;">Mark this email as <strong>"Not Spam"</strong></li>
            <li style="margin-bottom:6px;">Add <strong>{GmailConfig.SENDER_ADDRESS}</strong> to your contacts</li>
            <li>This trains your email provider to trust future emails from us</li>
        </ul>
    </td></tr></table>
</td></tr>
<tr><td style="padding:20px;background-color:#f1f5f9;text-align:center;font-size:12px;color:#64748b;border-top:1px solid #e2e8f0;">
    Warm regards, <strong>Medivio Team</strong>
</td></tr>
</table>
</td></tr></table>
</body></html>"""

    # Create an email log entry
    email_log = EmailLog(
        user_id=current_user.id,
        consultation_id=None,
        recipient_email=current_user.email,
        subject=subject,
        status="queued",
    )
    db.session.add(email_log)
    db.session.commit()

    # Send synchronously (test emails should give immediate feedback)
    result = send_consultation_email_message(
        to_address=current_user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    if result["success"]:
        email_log.status = "delivered"
        email_log.message_id = result.get("message_id")
        email_log.smtp_response = result.get("smtp_response")
        email_log.delivered_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Test email sent to {current_user.email}. "
                       "Please check your inbox (and spam folder) within 1-2 minutes.",
            "email_log": email_log.to_dict(),
            "tips": [
                "Check your Inbox, Spam, and Promotions tabs",
                f"If in Spam, mark as 'Not Spam' and add {GmailConfig.SENDER_ADDRESS} to contacts",
                "Gmail users: check the 'Updates' or 'Promotions' tab",
                "Outlook users: check the 'Other' or 'Junk' folder",
            ],
        }), 200
    else:
        email_log.status = "failed"
        email_log.error_message = result.get("error")
        email_log.retry_count = result.get("attempts", 0)
        email_log.failed_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            "success": False,
            "error": "Test email could not be sent.",
            "detail": result.get("error"),
            "email_log": email_log.to_dict(),
        }), 500


def _human_readable_status(email_log) -> str:
    """Convert an EmailLog status to a friendly message for the user."""
    if email_log.status == "delivered":
        if email_log.opened_at:
            return (
                f"Your consultation email was successfully delivered to {email_log.recipient_email} "
                f"and was opened on {email_log.opened_at.strftime('%d %b %Y at %I:%M %p')}."
            )
        return (
            f"Your consultation email was successfully delivered to {email_log.recipient_email}. "
            f"If you don't see it in your inbox, please check your Spam or Promotions folder."
        )
    elif email_log.status == "failed":
        return (
            f"The email to {email_log.recipient_email} could not be delivered after "
            f"{email_log.retry_count} attempt(s). Error: {email_log.error_message or 'Unknown'}. "
            f"Please verify your email address is correct and try resending."
        )
    elif email_log.status == "queued":
        return (
            f"Your email is currently being processed and will be delivered shortly to "
            f"{email_log.recipient_email}."
        )
    elif email_log.status == "skipped":
        return (
            f"The email was skipped: {email_log.error_message or 'No recipient address available'}."
        )
    return f"Status: {email_log.status}"


# ── Open Tracking Pixel (1x1 Transparent GIF) ──────────────────────────────────
_GIF_1X1_BYTES = base64.b64decode(b"R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

@notification_bp.route("/api/email-status/track/<int:log_id>.gif", methods=["GET"])
def track_email_open(log_id):
    """
    Tracking pixel endpoint. Returns a 1x1 transparent GIF and updates
    the opened_at timestamp for the associated EmailLog.
    """
    try:
        email_log = EmailLog.query.get(log_id)
        if email_log:
            # Only update if not already opened
            if not email_log.opened_at:
                email_log.opened_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info("[EmailTracker] EmailLog #%d marked as opened at %s", log_id, email_log.opened_at)
    except Exception as e:
        logger.error("[EmailTracker] Failed to update EmailLog #%d open status: %s", log_id, e)
    
    # Return the transparent 1x1 GIF image with cache-control headers to prevent caching
    response = Response(_GIF_1X1_BYTES, mimetype="image/gif")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
