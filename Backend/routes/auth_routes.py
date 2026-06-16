"""
Authentication Routes Blueprint
Handles registration, login, and profile management.
"""

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["full_name", "email", "password"]
    for field in required:
        if field not in data or not data[field]:
            return jsonify({"error": f"'{field}' is required"}), 400

    # Check if email already exists
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(
        full_name=data["full_name"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        age=data.get("age"),
        gender=data.get("gender"),
        blood_group=data.get("blood_group"),
        existing_conditions=data.get("existing_conditions"),
        allergies=data.get("allergies"),
        current_medications=data.get("current_medications"),
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Registration successful",
        "user": user.to_dict(),
    }), 201

@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    """Login an existing user."""
    data = request.get_json()

    if not data or "email" not in data or "password" not in data:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=data["email"]).first()

    if not user or not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({
        "message": "Login successful",
        "user": user.to_dict(),
    }), 200

@auth_bp.route("/api/auth/profile/<int:user_id>", methods=["GET"])
def get_profile(user_id):
    """Get user profile."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_dict()}), 200

@auth_bp.route("/api/auth/profile/<int:user_id>", methods=["PUT"])
def update_profile(user_id):
    """Update user profile."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    updatable_fields = [
        "full_name", "age", "gender", "blood_group",
        "existing_conditions", "allergies", "current_medications",
    ]
    for field in updatable_fields:
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    return jsonify({"message": "Profile updated", "user": user.to_dict()}), 200
