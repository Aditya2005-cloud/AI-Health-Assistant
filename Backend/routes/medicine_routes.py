"""
Medicine Routes Blueprint
Handles OTC medicine retrieval and searching.
"""

from flask import Blueprint, request, jsonify
from database import OTCMedicine

medicine_bp = Blueprint("medicine", __name__)

@medicine_bp.route("/api/medicines", methods=["GET"])
def get_medicines():
    """Get OTC medicines list, optionally filtered by category."""
    category = request.args.get("category")
    query = OTCMedicine.query
    if category:
        query = query.filter_by(category=category)
    medicines = query.all()
    return jsonify({
        "medicines": [m.to_dict() for m in medicines]
    }), 200

@medicine_bp.route("/api/medicines/search", methods=["GET"])
def search_medicines():
    """Search medicines by name."""
    q = request.args.get("q", "")
    if not q:
        return jsonify({"medicines": []}), 200
    medicines = OTCMedicine.query.filter(
        OTCMedicine.name.ilike(f"%{q}%")
    ).all()
    return jsonify({
        "medicines": [m.to_dict() for m in medicines]
    }), 200
