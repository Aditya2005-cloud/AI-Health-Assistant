"""
Database package - SQLAlchemy models and DB initialization.
"""

from database.models import db, User, Consultation, OTCMedicine

__all__ = ["db", "User", "Consultation", "OTCMedicine"]
