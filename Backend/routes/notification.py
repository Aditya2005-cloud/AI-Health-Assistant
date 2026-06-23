"""
routes/notification.py
----------------------
API routes for user notifications.
"""

import logging
from flask import Blueprint, jsonify, request
from database import db
from database.models import DashboardNotification
from middleware import jwt_required

logger = logging.getLogger(__name__)

notification_bp = Blueprint("notification", __name__)

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
