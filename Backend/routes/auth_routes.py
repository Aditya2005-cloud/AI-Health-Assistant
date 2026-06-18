"""
routes/auth_routes.py
---------------------
Authentication routes: signup, login, logout, profile.

Endpoints:
  POST /api/auth/register  → Create new account
  POST /api/auth/login     → Login and get JWT
  POST /api/auth/logout    → Logout (client clears token)
  GET  /api/auth/profile   → Get my profile (JWT required)
  PUT  /api/auth/profile   → Update my profile (JWT required)
"""

import re
import jwt
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from bcrypt import hashpw, checkpw, gensalt
from database import db, User
from middleware import jwt_required
from config import Config

auth_bp = Blueprint("auth", __name__)


# ─── helpers ────────────────────────────────
def make_token(user_id, email):
    """Create a JWT token that expires in JWT_EXPIRES_DAYS days."""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=Config.JWT_EXPIRES_DAYS),
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def is_strong_password(password):
    """Return True if password has >= 8 chars, one uppercase, one lowercase, one digit."""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    return True


def is_valid_phone(phone):
    """Basic phone number format check."""
    return bool(re.match(r"^[+\d\s\-()]{7,20}$", phone))


# ─── POST /api/auth/register ────────────────
@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    """
    Register a new user.
    Required fields: full_name, email, password
    Optional: age, gender, phone, whatsapp, known_allergies,
              medical_conditions, current_medications,
              blood_group, emergency_contact_name, emergency_contact_number
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # ── Validate required fields ──
    required = ["full_name", "email", "password"]
    for field in required:
        if not data.get(field, "").strip():
            return jsonify({"error": f"'{field}' is required"}), 400

    full_name = data["full_name"].strip()
    email = data["email"].strip().lower()
    password = data["password"]

    # ── Validate email format ──
    if not re.match(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$", email):
        return jsonify({"error": "Invalid email address"}), 400

    # ── Validate password strength ──
    if not is_strong_password(password):
        return jsonify({
            "error": "Password must be at least 8 characters with one uppercase letter, one lowercase letter, and one number"
        }), 400

    # ── Validate age if provided ──
    age = data.get("age")
    if age is not None:
        try:
            age = int(age)
            if not 0 <= age <= 120:
                return jsonify({"error": "Age must be between 0 and 120"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Age must be a number"}), 400

    # ── Validate gender if provided ──
    gender = data.get("gender")
    if gender and gender not in ["Male", "Female", "Other"]:
        return jsonify({"error": "Gender must be Male, Female, or Other"}), 400

    # ── Validate phone numbers if provided ──
    phone = data.get("phone", "").strip() or None
    if phone and not is_valid_phone(phone):
        return jsonify({"error": "Invalid phone number format"}), 400

    whatsapp = data.get("whatsapp", "").strip() or None
    if whatsapp and not is_valid_phone(whatsapp):
        return jsonify({"error": "Invalid WhatsApp number format"}), 400

    # ── Validate blood group if provided ──
    blood_group = data.get("blood_group", "").strip() or None
    valid_blood_groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    if blood_group and blood_group not in valid_blood_groups:
        return jsonify({"error": f"Blood group must be one of: {', '.join(valid_blood_groups)}"}), 400

    # ── Check email uniqueness ──
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 409

    # ── Hash password with bcrypt (NEVER store plain text) ──
    password_hash = hashpw(password.encode("utf-8"), gensalt(rounds=12)).decode("utf-8")

    # ── Create user ──
    user = User(
        full_name=full_name,
        age=age,
        gender=gender,
        email=email,
        phone=phone,
        whatsapp=whatsapp,
        known_allergies=data.get("known_allergies", "").strip() or None,
        medical_conditions=data.get("medical_conditions", "").strip() or None,
        current_medications=data.get("current_medications", "").strip() or None,
        blood_group=blood_group,
        emergency_contact_name=data.get("emergency_contact_name", "").strip() or None,
        emergency_contact_number=data.get("emergency_contact_number", "").strip() or None,
        password_hash=password_hash,
    )
    db.session.add(user)
    db.session.commit()

    # ── Generate JWT token ──
    token = make_token(user.id, user.email)

    return jsonify({
        "message": "Account created successfully",
        "token": token,
        "user": user.to_dict(),
    }), 201


# ─── POST /api/auth/login ───────────────────
@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    """
    Login with email and password.
    Returns a JWT token on success.
    Uses the same error for wrong email OR wrong password
    to prevent user enumeration attacks.
    """
    data = request.get_json()
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password are required"}), 400

    email = data["email"].strip().lower()
    password = data["password"]

    # Fetch user by email
    user = User.query.filter_by(email=email).first()

    # Compare password with bcrypt hash
    if not user or not checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        # Same message for wrong email OR wrong password (security best practice)
        return jsonify({"error": "Invalid email or password"}), 401

    # Generate JWT token
    token = make_token(user.id, user.email)

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": user.to_dict(),
    }), 200


# ─── POST /api/auth/logout ──────────────────
@auth_bp.route("/api/auth/logout", methods=["POST"])
@jwt_required
def logout(current_user):
    """
    Logout endpoint.
    JWT is stateless, so the client just deletes the token.
    This endpoint exists for logging and future token blacklist support.
    """
    return jsonify({"message": "Logged out successfully"}), 200


# ─── GET /api/auth/profile ──────────────────
@auth_bp.route("/api/auth/profile", methods=["GET"])
@jwt_required
def get_profile(current_user):
    """Get the authenticated user's full profile."""
    return jsonify({"user": current_user.to_dict()}), 200


# ─── PUT /api/auth/profile ──────────────────
@auth_bp.route("/api/auth/profile", methods=["PUT"])
@jwt_required
def update_profile(current_user):
    """Update the authenticated user's profile fields (not email or password)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Fields the user is allowed to update
    allowed = [
        "full_name", "age", "gender", "phone", "whatsapp",
        "known_allergies", "medical_conditions", "current_medications",
        "blood_group", "emergency_contact_name", "emergency_contact_number",
    ]
    for field in allowed:
        if field in data:
            setattr(current_user, field, data[field])

    db.session.commit()
    return jsonify({
        "message": "Profile updated successfully",
        "user": current_user.to_dict()
    }), 200
