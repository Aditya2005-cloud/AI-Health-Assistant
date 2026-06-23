"""
routes/__init__.py
"""
from .user_authentication_routes import auth_bp
from .clinical_consultation_routes import consult_bp
from .medicine_interaction_routes import medicine_bp
from .medicine_reminder import reminder_bp
from .notification import notification_bp
