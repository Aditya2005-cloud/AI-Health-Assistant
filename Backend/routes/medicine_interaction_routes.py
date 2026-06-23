"""
routes/medicine_interaction_routes.py
-------------------------------------
Marketplace medicine endpoints backed by the dataset.

Endpoints:
  GET  /api/medicines               → List all marketplace medicines
  GET  /api/medicines/<id>          → Get one medicine detail
  GET  /api/marketplace             → Alias for the marketplace list
  POST /api/medicines/recommend     → Groq-assisted symptom-based shortlist
  POST /api/marketplace/recommend   → Alias for symptom-based shortlist
"""

from flask import Blueprint, jsonify, request

from config import Config
from services.medicine_marketplace_service import (
    load_marketplace_catalog,
    recommend_medicines_with_groq,
)

import jwt

medicine_bp = Blueprint("medicine", __name__)


def get_optional_user():
    """Load the current user from JWT if one is present."""
    from database import db, User

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        return db.session.get(User, payload.get("user_id"))
    except Exception:
        return None


def flag_conflict(medicine, user):
    """Check for allergy or condition conflicts using the medicine text."""
    if not user:
        return None

    allergies = (user.known_allergies or "").lower()
    warnings = " ".join(
        [
            medicine.get("warnings", ""),
            medicine.get("purpose", ""),
            medicine.get("composition", ""),
            medicine.get("name", ""),
        ]
    ).lower()

    for allergy in [item.strip() for item in allergies.split(",") if item.strip()]:
        if allergy in warnings:
            return f"May conflict with your allergy: {allergy}"
    return None


def enrich_medicine_payload(medicine, current_user=None):
    payload = dict(medicine)
    payload["conflict_warning"] = flag_conflict(medicine, current_user)
    return payload


def get_catalog_response(medicines, current_user=None):
    return {
        "medicines": [enrich_medicine_payload(medicine, current_user) for medicine in medicines]
    }


def resolve_medicines_from_query():
    symptoms = request.args.get("symptoms", "").strip()
    search = request.args.get("search", "").strip().lower()

    catalog = load_marketplace_catalog()
    if symptoms:
        current_user = get_optional_user()
        medicines = recommend_medicines_with_groq(symptoms, current_user=current_user, limit=50)
        return medicines, current_user

    current_user = get_optional_user()
    medicines = catalog
    if search:
        medicines = [
            medicine
            for medicine in catalog
            if search in medicine.get("name", "").lower()
            or search in medicine.get("product_name", "").lower()
            or search in medicine.get("composition", "").lower()
            or search in medicine.get("category", "").lower()
        ]
    return medicines, current_user


@medicine_bp.route("/api/medicines", methods=["GET"])
@medicine_bp.route("/api/marketplace", methods=["GET"])
def get_medicines():
    """Return marketplace medicines, optionally filtered by search or symptoms."""
    medicines, current_user = resolve_medicines_from_query()
    return jsonify(get_catalog_response(medicines, current_user)), 200


@medicine_bp.route("/api/medicines/recommend", methods=["POST"])
@medicine_bp.route("/api/marketplace/recommend", methods=["POST"])
def recommend_medicines():
    """Return a Groq-assisted shortlist for the given symptoms."""
    data = request.get_json(silent=True) or {}
    symptoms = (data.get("symptoms") or data.get("query") or "").strip()
    if not symptoms:
        return jsonify({"error": "Please describe your symptoms"}), 400

    current_user = get_optional_user()
    medicines = recommend_medicines_with_groq(symptoms, current_user=current_user, limit=12)
    return jsonify(
        {
            "symptoms": symptoms,
            "medicines": [enrich_medicine_payload(medicine, current_user) for medicine in medicines],
        }
    ), 200


@medicine_bp.route("/api/medicines/<int:medicine_id>", methods=["GET"])
def get_medicine(medicine_id):
    """Return a single marketplace medicine by ID."""
    catalog = load_marketplace_catalog()
    medicine = next((item for item in catalog if item.get("id") == medicine_id), None)
    if not medicine:
        return jsonify({"error": "Medicine not found"}), 404
    return jsonify({"medicine": enrich_medicine_payload(medicine, get_optional_user())}), 200
