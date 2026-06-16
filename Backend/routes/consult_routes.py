"""
Consultation Routes Blueprint
Handles symptom analysis and consultation history retrieval.
"""

from flask import Blueprint, request, jsonify
from database import db, User, Consultation
from services import ai_doctor_pipeline

consult_bp = Blueprint("consult", __name__)

@consult_bp.route("/api/consult", methods=["POST"])
def consult():
    """
    Main AI consultation endpoint.
    Accepts user symptoms and runs the dual-AI pipeline.
    """
    data = request.get_json()

    if not data or "symptoms" not in data or not data["symptoms"].strip():
        return jsonify({"error": "Please describe your symptoms"}), 400

    user_id = data.get("user_id")
    symptoms = data["symptoms"]

    # Build patient context from request or profile
    patient_context = {}
    if data.get("age"):
        patient_context["Age"] = data.get("age")
    if data.get("gender"):
        patient_context["Gender"] = data.get("gender")

    if user_id:
        user = User.query.get(user_id)
        if user:
            if not patient_context.get("Age") and user.age:
                patient_context["Age"] = user.age
            if not patient_context.get("Gender") and user.gender:
                patient_context["Gender"] = user.gender
            patient_context.update({
                "Blood Group": user.blood_group,
                "Existing Conditions": user.existing_conditions,
                "Known Allergies": user.allergies,
                "Current Medications": user.current_medications,
            })

    # Run AI Doctor Pipeline
    result = ai_doctor_pipeline(symptoms, patient_context)

    # Save consultation to database if user is logged in
    if user_id:
        consultation = Consultation(
            user_id=user_id,
            symptoms_input=symptoms,
            gemini_analysis=result.get("gemini_response"),
            groq_validation=result.get("groq_response"),
            severity=result.get("severity"),
            is_emergency=result.get("is_emergency", False),
        )
        db.session.add(consultation)
        db.session.commit()
        result["consultation_id"] = consultation.id

    return jsonify(result), 200

@consult_bp.route("/api/consultations/<int:user_id>", methods=["GET"])
def get_consultations(user_id):
    """Get consultation history for a user."""
    consultations = (
        Consultation.query
        .filter_by(user_id=user_id)
        .order_by(Consultation.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({
        "consultations": [c.to_dict() for c in consultations]
    }), 200

@consult_bp.route("/api/consultation/<int:consultation_id>", methods=["GET"])
def get_consultation(consultation_id):
    """Get a single consultation detail."""
    consultation = Consultation.query.get(consultation_id)
    if not consultation:
        return jsonify({"error": "Consultation not found"}), 404
    return jsonify({"consultation": consultation.to_dict()}), 200
