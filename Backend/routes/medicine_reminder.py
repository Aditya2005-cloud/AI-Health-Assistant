"""
routes/medicine_reminder.py
----------------------------
Medicine Reminder API routes — all protected by JWT.
"""

import re
import logging
from datetime import datetime, timezone, time as dt_time
from flask import Blueprint, request, jsonify
from database import db
from database.models import MedicineReminder
from middleware import jwt_required

logger = logging.getLogger(__name__)

reminder_bp = Blueprint("reminder", __name__)

def _parse_time(time_str):
    """Parse a time string (HH:MM or HH:MM:SS) into a Python time object."""
    if not time_str:
        return None
    try:
        parts = time_str.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return dt_time(hour, minute)
    except (ValueError, IndexError):
        return None

def _parse_date(date_str):
    """Parse a date string (YYYY-MM-DD) into a Python date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None

# ─── POST /api/reminders ───────────────
@reminder_bp.route("/api/reminders", methods=["POST"])
@jwt_required
def create_reminder(current_user):
    """
    Create a new medicine reminder.
    Required: medicine_name, reminder_time (HH:MM)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    medicine_name = (data.get("medicine_name") or "").strip()
    if not medicine_name:
        return jsonify({"error": "'medicine_name' is required"}), 400

    time_str = (data.get("reminder_time") or "").strip()
    reminder_time = _parse_time(time_str)
    if not reminder_time:
        return jsonify({"error": "'reminder_time' is required (format: HH:MM)"}), 400

    frequency = (data.get("frequency") or "daily").strip().lower()
    valid_frequencies = ["daily", "weekly", "specific_days"]
    if frequency not in valid_frequencies:
        return jsonify({"error": f"'frequency' must be one of: {', '.join(valid_frequencies)}"}), 400

    reminder_days = (data.get("reminder_days") or "").strip().lower()
    valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    if frequency in ("weekly", "specific_days") and reminder_days:
        day_list = [d.strip() for d in reminder_days.split(",")]
        invalid = [d for d in day_list if d not in valid_days]
        if invalid:
            return jsonify({"error": f"Invalid day(s): {', '.join(invalid)}"}), 400

    start_date = _parse_date(data.get("start_date"))
    end_date = _parse_date(data.get("end_date"))

    if start_date and end_date and end_date < start_date:
        return jsonify({"error": "end_date cannot be before start_date"}), 400

    reminder = MedicineReminder(
        user_id=current_user.id,
        medicine_name=medicine_name,
        dosage=(data.get("dosage") or "").strip() or None,
        instructions=(data.get("instructions") or "").strip() or None,
        reminder_time=reminder_time,
        frequency=frequency,
        reminder_days=reminder_days or None,
        start_date=start_date,
        end_date=end_date,
        is_active=True,
    )
    db.session.add(reminder)
    db.session.commit()

    logger.info("[ReminderRoutes] Reminder #%d created for user %d: %s at %s", reminder.id, current_user.id, medicine_name, time_str)

    return jsonify({
        "message": "Medicine reminder created successfully",
        "reminder": reminder.to_dict(),
    }), 201

# ─── GET /api/reminders ────────────────
@reminder_bp.route("/api/reminders", methods=["GET"])
@jwt_required
def list_reminders(current_user):
    """List all medicine reminders for the logged-in user."""
    reminders = (
        MedicineReminder.query
        .filter_by(user_id=current_user.id)
        .order_by(MedicineReminder.reminder_time.asc())
        .all()
    )
    return jsonify({
        "reminders": [r.to_dict() for r in reminders],
        "total": len(reminders),
    }), 200

# ─── GET /api/reminders/<id> ───────────
@reminder_bp.route("/api/reminders/<int:reminder_id>", methods=["GET"])
@jwt_required
def get_reminder(current_user, reminder_id):
    """Get one reminder."""
    r = MedicineReminder.query.filter_by(id=reminder_id, user_id=current_user.id).first()
    if not r:
        return jsonify({"error": "Reminder not found"}), 404
    return jsonify({"reminder": r.to_dict()}), 200

# ─── PUT /api/reminders/<id> ───────────
@reminder_bp.route("/api/reminders/<int:reminder_id>", methods=["PUT"])
@jwt_required
def update_reminder(current_user, reminder_id):
    """Update an existing medicine reminder."""
    r = MedicineReminder.query.filter_by(id=reminder_id, user_id=current_user.id).first()
    if not r:
        return jsonify({"error": "Reminder not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "medicine_name" in data:
        name = (data["medicine_name"] or "").strip()
        if not name:
            return jsonify({"error": "'medicine_name' cannot be empty"}), 400
        r.medicine_name = name

    if "dosage" in data:
        r.dosage = (data["dosage"] or "").strip() or None

    if "instructions" in data:
        r.instructions = (data["instructions"] or "").strip() or None

    if "reminder_time" in data:
        parsed = _parse_time(data["reminder_time"])
        if not parsed:
            return jsonify({"error": "Invalid time format (use HH:MM)"}), 400
        r.reminder_time = parsed

    if "frequency" in data:
        freq = (data["frequency"] or "daily").strip().lower()
        if freq not in ("daily", "weekly", "specific_days"):
            return jsonify({"error": "Invalid frequency"}), 400
        r.frequency = freq

    if "reminder_days" in data:
        r.reminder_days = (data["reminder_days"] or "").strip().lower() or None

    if "start_date" in data:
        r.start_date = _parse_date(data["start_date"])

    if "end_date" in data:
        r.end_date = _parse_date(data["end_date"])

    if "is_active" in data:
        r.is_active = bool(data["is_active"])

    db.session.commit()

    return jsonify({
        "message": "Reminder updated successfully",
        "reminder": r.to_dict(),
    }), 200

# ─── DELETE /api/reminders/<id> ────────
@reminder_bp.route("/api/reminders/<int:reminder_id>", methods=["DELETE"])
@jwt_required
def delete_reminder(current_user, reminder_id):
    """Delete one reminder."""
    r = MedicineReminder.query.filter_by(id=reminder_id, user_id=current_user.id).first()
    if not r:
        return jsonify({"error": "Reminder not found"}), 404

    db.session.delete(r)
    db.session.commit()

    return jsonify({"message": "Reminder deleted successfully"}), 200

# ─── POST /api/reminders/<id>/toggle ───
@reminder_bp.route("/api/reminders/<int:reminder_id>/toggle", methods=["POST"])
@jwt_required
def toggle_reminder(current_user, reminder_id):
    """Toggle a reminder active status."""
    r = MedicineReminder.query.filter_by(id=reminder_id, user_id=current_user.id).first()
    if not r:
        return jsonify({"error": "Reminder not found"}), 404

    r.is_active = not r.is_active
    db.session.commit()

    status = "activated" if r.is_active else "deactivated"
    return jsonify({
        "message": f"Reminder {status} successfully",
        "reminder": r.to_dict(),
    }), 200
