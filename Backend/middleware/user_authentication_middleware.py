"""
middleware/user_authentication_middleware.py
--------------------------------------------
JWT authentication decorator.

Usage:
    from middleware.user_authentication_middleware import jwt_required

    @app.route("/api/protected")
    @jwt_required
    def protected(current_user):
        return jsonify({"user": current_user.to_dict()})

How it works:
  1. Reads the "Authorization: Bearer <token>" header.
  2. Decodes and verifies the JWT using JWT_SECRET_KEY from config.
  3. Loads the user from the database.
  4. Injects the user object as the first argument to the route function.
  5. Returns 401 if the token is missing, expired, or invalid.
"""

import jwt
from datetime import datetime, timezone
from functools import wraps
from flask import request, jsonify
from database import db, User
from config import Config


def jwt_required(f):
    """Decorator that protects a route — requires a valid JWT token."""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from Authorization header: "Bearer <token>"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Access denied. No token provided."}), 401

        try:
            # Decode the JWT — raises exception if expired or invalid
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired. Please login again."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token. Please login again."}), 401

        # Load user from database
        current_user = db.session.get(User, user_id)
        if not current_user:
            return jsonify({"error": "User not found. Token invalid."}), 401

        # Pass the user object into the route function
        return f(current_user, *args, **kwargs)

    return decorated
