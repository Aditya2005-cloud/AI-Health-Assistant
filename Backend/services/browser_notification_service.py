"""
services/browser_notification_service.py
----------------------------------------
Service layer for fetching notifications to be rendered in the browser.
"""

import logging
from database.models import DashboardNotification

logger = logging.getLogger(__name__)

def fetch_unread_notifications_for_browser(user_id: int) -> list:
    """Retrieve all unread notifications for a user to display in the browser."""
    try:
        notifications = (
            DashboardNotification.query
            .filter_by(user_id=user_id, is_read=False)
            .order_by(DashboardNotification.created_at.desc())
            .all()
        )
        return [n.to_dict() for n in notifications]
    except Exception as e:
        logger.exception("[BrowserNotificationService] Failed to fetch unread notifications: %s", e)
        return []
