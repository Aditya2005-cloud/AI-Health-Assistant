"""
Routes package - Contains all Flask route blueprints.
"""

from routes.auth_routes import auth_bp
from routes.consult_routes import consult_bp
from routes.medicine_routes import medicine_bp

__all__ = ["auth_bp", "consult_bp", "medicine_bp"]
