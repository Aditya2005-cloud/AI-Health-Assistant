"""
routes/medicine_routes.py
--------------------------
OTC Medicine browser endpoint.

Endpoints:
  GET /api/medicines       → List all OTC medicines
  GET /api/medicines/<id>  → Get one medicine detail

If the user is logged in (JWT provided), medicines that conflict
with their known allergies are flagged automatically.
"""

from flask import Blueprint, request, jsonify
from database import db, OTCMedicine
from config import Config
import jwt

medicine_bp = Blueprint("medicine", __name__)


def get_optional_user():
    """
    Try to load the current user from JWT without requiring it.
    Returns the User object or None if not logged in.
    """
    from database import User
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        return User.query.get(payload.get("user_id"))
    except Exception:
        return None


def flag_conflict(medicine, user):
    """
    Check if a medicine's warnings conflict with the user's allergies.
    Returns a short warning string or None if safe.
    """
    if not user:
        return None
    allergies = (user.known_allergies or "").lower()
    conditions = (user.medical_conditions or "").lower()
    warnings = (medicine.warnings or "").lower()
    name = (medicine.generic_name or medicine.name or "").lower()

    # Check allergy keywords against medicine name and warnings
    for allergy in [a.strip() for a in allergies.split(",") if a.strip()]:
        if allergy in warnings or allergy in name:
            return f"May conflict with your allergy: {allergy}"
    return None


# ─── GET /api/medicines ─────────────────────
@medicine_bp.route("/api/medicines", methods=["GET"])
def get_medicines():
    """
    Return all OTC medicines.
    If the user is logged in, flags any medicines conflicting with their allergies.
    """
    current_user = get_optional_user()
    medicines = OTCMedicine.query.all()

    result = []
    for m in medicines:
        data = m.to_dict()
        conflict = flag_conflict(m, current_user)
        data["conflict_warning"] = conflict  # None if safe, string if conflict
        result.append(data)

    return jsonify({"medicines": result}), 200


# ─── GET /api/medicines/<id> ────────────────
@medicine_bp.route("/api/medicines/<int:medicine_id>", methods=["GET"])
def get_medicine(medicine_id):
    """Return a single medicine by ID."""
    m = OTCMedicine.query.get(medicine_id)
    if not m:
        return jsonify({"error": "Medicine not found"}), 404
    return jsonify({"medicine": m.to_dict()}), 200
