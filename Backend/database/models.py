"""
database/models.py
------------------
SQLAlchemy ORM models for Medivio.

Tables:
  - users         → patient accounts (full medical profile)
  - consultations → AI consultation history per user
  - otc_medicines → OTC medicine database (seeded on startup)
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ─────────────────────────────────────────────
# User Model
# ─────────────────────────────────────────────
class User(db.Model):
    """Patient account with full medical profile."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.Enum("Male", "Female", "Other"), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    whatsapp = db.Column(db.String(20), nullable=True)
    known_allergies = db.Column(db.Text, nullable=True)
    medical_conditions = db.Column(db.Text, nullable=True)
    current_medications = db.Column(db.Text, nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_number = db.Column(db.String(20), nullable=True)

    # Password is ALWAYS stored as a bcrypt hash — never plain text
    password_hash = db.Column(db.String(256), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # One user → many consultations
    consultations = db.relationship(
        "Consultation", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        """Return user data as dict. Password hash is NEVER included."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "age": self.age,
            "gender": self.gender,
            "email": self.email,
            "phone": self.phone,
            "whatsapp": self.whatsapp,
            "known_allergies": self.known_allergies,
            "medical_conditions": self.medical_conditions,
            "current_medications": self.current_medications,
            "blood_group": self.blood_group,
            "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_number": self.emergency_contact_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────
# Consultation Model
# ─────────────────────────────────────────────
class Consultation(db.Model):
    """Stores each AI health consultation session."""

    __tablename__ = "consultations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # The patient's typed question/symptoms
    symptoms_input = db.Column(db.Text, nullable=False)

    # AI responses stored as JSON
    gemini_analysis = db.Column(db.JSON, nullable=True)
    groq_validation = db.Column(db.JSON, nullable=True)

    # Risk level: low / medium / high / emergency
    severity = db.Column(db.String(20), nullable=True, default="low")
    is_emergency = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "symptoms_input": self.symptoms_input,
            "gemini_analysis": self.gemini_analysis,
            "groq_validation": self.groq_validation,
            "severity": self.severity,
            "is_emergency": self.is_emergency,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────
# OTC Medicine Model
# ─────────────────────────────────────────────
class OTCMedicine(db.Model):
    """Over-the-counter medicines available in India."""

    __tablename__ = "otc_medicines"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    generic_name = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    purpose = db.Column(db.Text, nullable=True)
    common_dosage = db.Column(db.String(200), nullable=True)
    warnings = db.Column(db.Text, nullable=True)
    price_range = db.Column(db.String(50), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "generic_name": self.generic_name,
            "category": self.category,
            "purpose": self.purpose,
            "common_dosage": self.common_dosage,
            "warnings": self.warnings,
            "price_range": self.price_range,
        }


# ─────────────────────────────────────────────
# Medicine Reminder Model (SMS Automation)
# ─────────────────────────────────────────────
class MedicineReminder(db.Model):
    """
    Stores scheduled medicine reminders for SMS notifications.

    Each reminder belongs to a user and defines:
      - Which medicine to take
      - When to send the reminder (time of day)
      - How often (daily, weekly, specific days)
      - Optional start/end dates for course duration
    """

    __tablename__ = "medicine_reminders"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Medicine details
    medicine_name = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(100), nullable=True)         # e.g. "500mg"
    instructions = db.Column(db.Text, nullable=True)          # e.g. "Take after food"

    # Schedule
    reminder_time = db.Column(db.Time, nullable=False)        # e.g. 08:00, 14:00
    frequency = db.Column(
        db.String(20), nullable=False, default="daily"        # daily | weekly | specific_days
    )
    reminder_days = db.Column(
        db.String(100), nullable=True                         # e.g. "monday,wednesday,friday"
    )

    # Course duration (optional)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)

    # Status tracking
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_sent_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship back to User
    reminder_user = db.relationship("User", backref=db.backref("medicine_reminders", lazy=True))

    def to_dict(self):
        """Return reminder data as dict."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "medicine_name": self.medicine_name,
            "dosage": self.dosage,
            "instructions": self.instructions,
            "reminder_time": self.reminder_time.strftime("%H:%M") if self.reminder_time else None,
            "frequency": self.frequency,
            "reminder_days": self.reminder_days,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
            "last_sent_at": self.last_sent_at.isoformat() if self.last_sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────
# Dashboard Notification Model
# ─────────────────────────────────────────────
class DashboardNotification(db.Model):
    """Stores system and failure alerts shown to the user on the dashboard."""

    __tablename__ = "dashboard_notifications"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False, default="reminder") # reminder | alert | info
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship back to User
    notification_user = db.relationship("User", backref=db.backref("dashboard_notifications", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
