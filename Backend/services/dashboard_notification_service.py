"""
services/dashboard_notification_service.py
-----------------------------------------
Service layer for managing user dashboard notifications in the database.
"""

import logging
from database import db
from database.models import DashboardNotification

logger = logging.getLogger(__name__)

def create_dashboard_notification(user_id: int, title: str, message: str, notification_type: str = "reminder") -> bool:
    """Create a new dashboard notification log for a user."""
    try:
        notification = DashboardNotification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()
        logger.info("[DashboardNotificationService] Alert logged for user #%d: '%s'", user_id, title)
        return True
    except Exception as e:
        logger.exception("[DashboardNotificationService] Failed to create notification: %s", e)
        return False

def mark_notification_as_read(user_id: int, notification_id: int) -> bool:
    """Mark a notification as read for a given user."""
    try:
        notification = DashboardNotification.query.filter_by(
            id=notification_id, user_id=user_id
        ).first()
        if not notification:
            return False
        notification.is_read = True
        db.session.commit()
        return True
    except Exception as e:
        logger.exception("[DashboardNotificationService] Failed to mark read: %s", e)
        return False
