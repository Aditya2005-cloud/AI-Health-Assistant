"""
database/models.py
------------------
SQLAlchemy ORM models for the AI Health Assistant.

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
