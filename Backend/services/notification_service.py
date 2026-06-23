"""
services/notification_service.py
--------------------------------
Central Notification Service.

Coordinates dispatches of notifications across different channels:
1. Dashboard notifications (written to the database)
2. Gmail email notifications (via SMTP)
3. Browser notifications (served via API polling)
"""

import logging
from database import db
from database.models import User, DashboardNotification
from email_notification_service.gmail_sender import send_consultation_email_message

logger = logging.getLogger(__name__)

def send_medicine_reminder_notification(user_id: int, medicine_name: str, dosage: str, instructions: str) -> bool:
    """
    Orchestrates sending a medicine reminder across all free notification channels:
    - Inserts a DashboardNotification into the MySQL database.
    - Sends an email alert to the user's Gmail.
    """
    try:
        user = db.session.get(User, user_id)
        if not user:
            logger.error("[NotificationService] User #%d not found. Skipping reminder.", user_id)
            return False

        # 1. Create Dashboard Notification
        title = f"⏰ Take Medicine: {medicine_name}"
        message = f"It is time to take your {medicine_name} ({dosage or 'dosage not specified'}). Instructions: {instructions or 'None'}"
        
        notification = DashboardNotification(
            user_id=user.id,
            title=title,
            message=message,
            notification_type="reminder",
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()
        logger.info("[NotificationService] Created dashboard notification for user #%d: '%s'", user.id, title)

        # 2. Send Gmail Notification
        email_subject = f"⏰ Medicine Reminder: {medicine_name} - Medivio"
        email_text = (
            f"Hi {user.full_name},\n\n"
            f"This is an automated reminder to take your medicine:\n\n"
            f"  Medicine: {medicine_name}\n"
            f"  Dosage: {dosage or 'Not specified'}\n"
            f"  Instructions: {instructions or 'Not specified'}\n\n"
            f"Please take it as scheduled.\n\n"
            f"Stay healthy,\nMedivio Health Assistant"
        )
        email_html = (
            f"<p>Hi {user.full_name},</p>"
            f"<p>This is an automated reminder to take your medicine:</p>"
            f"<ul>"
            f"  <li><strong>Medicine:</strong> {medicine_name}</li>"
            f"  <li><strong>Dosage:</strong> {dosage or 'Not specified'}</li>"
            f"  <li><strong>Instructions:</strong> {instructions or 'Not specified'}</li>"
            f"</ul>"
            f"<p>Please take it as scheduled.</p>"
            f"<br><p>Stay healthy,<br>Medivio Health Assistant</p>"
        )

        email_success = send_consultation_email_message(
            to_address=user.email,
            subject=email_subject,
            text_body=email_text,
            html_body=email_html
        )

        if email_success:
            logger.info("[NotificationService] Sent email reminder to %s.", user.email)
        else:
            logger.warning("[NotificationService] Email reminder delivery failed to %s.", user.email)

        return True

    except Exception as e:
        logger.exception("[NotificationService] Error sending reminder: %s", e)
        return False
