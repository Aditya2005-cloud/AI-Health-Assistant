"""
Database models for the AI Health Assistant.
Defines all MySQL tables using SQLAlchemy ORM.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User account model for patient authentication."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)
    existing_conditions = db.Column(db.Text, nullable=True)
    allergies = db.Column(db.Text, nullable=True)
    current_medications = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    consultations = db.relationship(
        "Consultation", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "age": self.age,
            "gender": self.gender,
            "blood_group": self.blood_group,
            "existing_conditions": self.existing_conditions,
            "allergies": self.allergies,
            "current_medications": self.current_medications,
        }


class Consultation(db.Model):
    """Consultation record storing each AI health check session."""

    __tablename__ = "consultations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    symptoms_input = db.Column(db.Text, nullable=False)
    gemini_analysis = db.Column(db.JSON, nullable=True)
    groq_validation = db.Column(db.JSON, nullable=True)
    severity = db.Column(db.String(20), nullable=True)
    is_emergency = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

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


class OTCMedicine(db.Model):
    """Database of over-the-counter medicines available in India."""

    __tablename__ = "otc_medicines"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    generic_name = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    purpose = db.Column(db.Text, nullable=True)
    common_dosage = db.Column(db.String(200), nullable=True)
    warnings = db.Column(db.Text, nullable=True)
    available_in_india = db.Column(db.Boolean, default=True)
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
