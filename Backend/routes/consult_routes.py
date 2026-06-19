"""
routes/consult_routes.py
------------------------
Consultation routes — all protected by JWT.

Endpoints:
  POST /api/consult              → Run AI consultation (JWT required)
  GET  /api/history              → Get my consultation history (JWT required)
  GET  /api/history/<id>         → Get one consultation (JWT required)
  DELETE /api/history/<id>       → Delete one consultation (JWT required)

  # Legacy URLs (still work for frontend compatibility)
  GET  /api/consultations/<uid>  → Same as GET /api/history
  GET  /api/consultation/<id>    → Same as GET /api/history/<id>
"""

from flask import Blueprint, request, jsonify
from database import db, User, Consultation
from services import ai_doctor_pipeline
from middleware import jwt_required
import logging

logger = logging.getLogger(__name__)

# ── Email service (fire-and-forget after AI assessment) ──────────────────────
try:
    from g_mail_user import dispatch_consultation_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    logger.warning(
        "[ConsultRoutes] g_mail_user package not found. "
        "Consultation emails will be disabled."
    )

consult_bp = Blueprint("consult", __name__)


# ─── Emergency keyword detection ────────────
EMERGENCY_KEYWORDS = [
    "chest pain", "difficulty breathing", "can't breathe", "shortness of breath",
    "stroke", "face drooping", "slurred speech", "loss of consciousness",
    "fainted", "unresponsive", "severe bleeding", "coughing blood",
    "vomiting blood", "seizure", "convulsion", "fits",
    "suicidal", "want to die", "kill myself", "self-harm",
    "anaphylaxis", "severe allergic", "throat swelling", "swollen throat",
    "overdose", "poisoning",
]

def detect_emergency(text):
    """Return True if the text contains any emergency keyword."""
    text_lower = text.lower()
    found = [kw for kw in EMERGENCY_KEYWORDS if kw in text_lower]
    return bool(found), found


# ─── POST /api/consult ──────────────────────
@consult_bp.route("/api/consult", methods=["POST"])
@jwt_required
def consult(current_user):
    """
    Main AI consultation endpoint.
    - Requires JWT (user must be logged in)
    - Injects full patient profile automatically into the AI prompt
    - Detects emergencies before calling AI
    - Saves result to consultation history
    """
    data = request.get_json()

    # Accept 'symptoms' or 'question' — both mean the same thing
    symptoms = (data.get("symptoms") or data.get("question") or "").strip()

    if not symptoms:
        return jsonify({"error": "Please describe your symptoms"}), 400
    if len(symptoms) < 10:
        return jsonify({"error": "Please provide more detail (minimum 10 characters)"}), 400

    # ── Step 1: Emergency detection ──
    is_emergency, found_keywords = detect_emergency(symptoms)

    if is_emergency:
        # Return immediate emergency response without calling AI
        emergency_result = {
            "success": True,
            "is_emergency": True,
            "severity": "Emergency",
            "gemini_response": {
                "patient_summary": f"Emergency keywords detected: {', '.join(found_keywords)}.",
                "possible_causes": [],
                "recommended_actions": {
                    "immediate": "🚨 SEEK IMMEDIATE MEDICAL ATTENTION. Call 102 (Ambulance) or 112 (Emergency) NOW.",
                    "otc_medicines": [],
                    "home_remedies": [],
                },
                "red_flags": [
                    "This appears to be a medical emergency.",
                    "Do NOT rely on AI advice for emergency situations.",
                    "Call 102 (Ambulance) or 112 (Emergency) immediately.",
                ],
                "when_to_see_doctor": "IMMEDIATELY — this is an emergency.",
                "disclaimer": "🚨 This may be a medical emergency. Please seek immediate medical attention or call your local emergency number. Do NOT wait for AI advice.",
            },
            "groq_response": None,
            "is_fallback": False,
        }

        # Still save to history
        consultation = Consultation(
            user_id=current_user.id,
            symptoms_input=symptoms,
            gemini_analysis=emergency_result["gemini_response"],
            groq_validation=None,
            severity="Emergency",
            is_emergency=True,
        )
        db.session.add(consultation)
        db.session.commit()
        emergency_result["consultation_id"] = consultation.id

        return jsonify(emergency_result), 200

    # ── Step 2: Build patient context from the user's full profile ──
    # This is automatically injected — user doesn't need to type it
    patient_context = {
        "Name": current_user.full_name,
        "Age": current_user.age,
        "Gender": current_user.gender,
        "Blood Group": current_user.blood_group,
        "Known Allergies": current_user.known_allergies,
        "Medical Conditions": current_user.medical_conditions,
        "Current Medications": current_user.current_medications,
        "Emergency Contact": current_user.emergency_contact_name,
    }
    # Remove empty values
    patient_context = {k: v for k, v in patient_context.items() if v}

    # ── Step 3: Run dual-AI pipeline ──
    result = ai_doctor_pipeline(symptoms, patient_context)

    # ── Step 4: Save consultation to database ──
    consultation = Consultation(
        user_id=current_user.id,
        symptoms_input=symptoms,
        gemini_analysis=result.get("gemini_response"),
        groq_validation=result.get("groq_response"),
        severity=result.get("severity", "low"),
        is_emergency=result.get("is_emergency", False),
    )
    db.session.add(consultation)
    db.session.commit()
    result["consultation_id"] = consultation.id

    # ── Send consultation summary email (background thread) ──────────────────
    # This runs in a daemon thread — it never blocks or breaks the API response.
    if EMAIL_SERVICE_AVAILABLE and current_user.email:
        try:
            dispatch_consultation_email(
                patient_name         = current_user.full_name,
                age                  = current_user.age,
                gender               = current_user.gender,
                symptoms_description = symptoms,
                symptom_tags         = result.get("severity", ""),
                medical_history      = current_user.medical_conditions,
                allergies            = current_user.known_allergies,
                ai_assessment        = result.get("groq_response") or result.get("gemini_response"),
                user_email           = current_user.email,
                background           = True,   # fire-and-forget
            )
        except Exception as email_err:
            # Email failure must NEVER break the consultation response
            logger.warning(
                "[ConsultRoutes] Email dispatch failed (non-critical): %s", email_err
            )

    return jsonify(result), 200


# ─── GET /api/history ───────────────────────
@consult_bp.route("/api/history", methods=["GET"])
@jwt_required
def get_history(current_user):
    """Get the logged-in user's consultation history (most recent first)."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    consultations = (
        Consultation.query
        .filter_by(user_id=current_user.id)
        .order_by(Consultation.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        "consultations": [c.to_dict() for c in consultations.items],
        "total": consultations.total,
        "page": page,
        "pages": consultations.pages,
    }), 200


# ─── GET /api/history/<id> ──────────────────
@consult_bp.route("/api/history/<int:consultation_id>", methods=["GET"])
@jwt_required
def get_one(current_user, consultation_id):
    """Get one consultation — only if it belongs to the logged-in user."""
    c = Consultation.query.filter_by(id=consultation_id, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "Consultation not found"}), 404
    return jsonify({"consultation": c.to_dict()}), 200


# ─── DELETE /api/history/<id> ───────────────
@consult_bp.route("/api/history/<int:consultation_id>", methods=["DELETE"])
@jwt_required
def delete_one(current_user, consultation_id):
    """Delete one consultation — only if it belongs to the logged-in user."""
    c = Consultation.query.filter_by(id=consultation_id, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "Consultation not found"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Consultation deleted"}), 200


# ─── Legacy routes (frontend compatibility) ─
@consult_bp.route("/api/consultations/<int:user_id>", methods=["GET"])
@jwt_required
def legacy_history(current_user, user_id):
    """Legacy URL — ignores user_id param, always returns the JWT user's history."""
    consultations = (
        Consultation.query
        .filter_by(user_id=current_user.id)
        .order_by(Consultation.created_at.desc())
        .limit(20).all()
    )
    return jsonify({"consultations": [c.to_dict() for c in consultations]}), 200


@consult_bp.route("/api/consultation/<int:consultation_id>", methods=["GET"])
@jwt_required
def legacy_get_one(current_user, consultation_id):
    """Legacy URL — get one consultation (JWT user must own it)."""
    c = Consultation.query.filter_by(id=consultation_id, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "Consultation not found"}), 404
    return jsonify({"consultation": c.to_dict()}), 200
