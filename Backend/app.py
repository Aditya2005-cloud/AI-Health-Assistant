"""
app.py
------
AI Health Assistant — Flask Application Entry Point

Run with:
    python app.py

What happens on startup:
  1. Auto-creates the MySQL database if it doesn't exist
  2. Creates all tables (users, consultations, otc_medicines)
  3. Seeds the OTC medicine database (only on first run)
  4. Starts the Flask dev server on http://localhost:5000
"""

import os
import mysql.connector
from flask import Flask, send_from_directory
from flask_cors import CORS

from config import Config
from database import db, OTCMedicine
from routes import auth_bp, consult_bp, medicine_bp


# ─────────────────────────────────────────────
# Step 1: Auto-create MySQL database
# ─────────────────────────────────────────────
def create_database_if_missing():
    """Connect to MySQL without selecting a DB and create it if it doesn't exist."""
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
        )
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DATABASE}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[DB] Database '{Config.MYSQL_DATABASE}' is ready.")
    except mysql.connector.Error as e:
        print(f"[ERROR] MySQL connection failed: {e}")
        print("  → Make sure MySQL is running and your .env DB settings are correct.")
        raise


# ─────────────────────────────────────────────
# Step 2: Create Flask app
# ─────────────────────────────────────────────
def create_app():
    """Application factory — creates and configures the Flask app."""

    # Auto-create DB before Flask initializes
    create_database_if_missing()

    app = Flask(
        __name__,
        # Serve the frontend folder as static files from the same server
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend"),
        static_url_path="",
    )

    # Load config from config.py
    app.config.from_object(Config)

    # Allow cross-origin requests from the frontend
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize database with the app
    db.init_app(app)

    # Register all route blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(consult_bp)
    app.register_blueprint(medicine_bp)

    # ── Serve frontend files ──
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        return send_from_directory(app.static_folder, path)

    # ── Create tables and seed data ──
    with app.app_context():
        db.create_all()
        seed_medicines()
        print("[DB] All tables are ready.")

    return app


# ─────────────────────────────────────────────
# Step 3: Seed OTC Medicines (runs once)
# ─────────────────────────────────────────────
def seed_medicines():
    """Add OTC medicines to the database if the table is empty."""
    if OTCMedicine.query.first():
        return  # Already seeded — skip

    medicines = [
        OTCMedicine(name="Crocin 650", generic_name="Paracetamol", category="Pain & Fever",
                    purpose="Relief from mild to moderate pain and fever",
                    common_dosage="1 tablet every 4-6 hours (max 4 tablets/day)",
                    warnings="Do not exceed 4g/day. Avoid with alcohol or liver disease.",
                    price_range="₹20-₹35"),
        OTCMedicine(name="Dolo 650", generic_name="Paracetamol", category="Pain & Fever",
                    purpose="Fever and body pain relief",
                    common_dosage="1 tablet every 4-6 hours",
                    warnings="Avoid alcohol. Do not exceed recommended dose.",
                    price_range="₹25-₹40"),
        OTCMedicine(name="Combiflam", generic_name="Ibuprofen + Paracetamol", category="Pain & Fever",
                    purpose="Pain, inflammation and fever",
                    common_dosage="1 tablet 2-3 times daily after food",
                    warnings="Take after food. Not for stomach ulcer or kidney patients.",
                    price_range="₹30-₹50"),
        OTCMedicine(name="Vicks VapoRub", generic_name="Camphor + Menthol + Eucalyptus Oil", category="Cold & Cough",
                    purpose="Relief from cold, cough and nasal congestion",
                    common_dosage="Apply on chest and throat",
                    warnings="For external use only. Keep away from eyes. Not for children under 2.",
                    price_range="₹50-₹150"),
        OTCMedicine(name="Benadryl Cough Syrup", generic_name="Diphenhydramine", category="Cold & Cough",
                    purpose="Dry cough relief",
                    common_dosage="10ml every 4-6 hours (adults)",
                    warnings="May cause drowsiness. Avoid driving. Avoid alcohol.",
                    price_range="₹80-₹120"),
        OTCMedicine(name="Strepsils", generic_name="Amylmetacresol + Dichlorobenzyl Alcohol", category="Cold & Cough",
                    purpose="Sore throat relief",
                    common_dosage="1 lozenge every 2-3 hours (max 12/day)",
                    warnings="Do not exceed 12 lozenges per day.",
                    price_range="₹40-₹80"),
        OTCMedicine(name="Digene", generic_name="Aluminium Hydroxide + Magnesium Hydroxide", category="Digestive",
                    purpose="Acidity and heartburn relief",
                    common_dosage="1-2 tablets after meals and at bedtime",
                    warnings="Long-term use may cause mineral imbalance. Avoid with kidney disease.",
                    price_range="₹50-₹100"),
        OTCMedicine(name="Eno", generic_name="Sodium Bicarbonate + Citric Acid", category="Digestive",
                    purpose="Quick acidity relief",
                    common_dosage="1 sachet in 200ml water when needed",
                    warnings="High sodium. Avoid with hypertension or heart disease.",
                    price_range="₹10-₹50"),
        OTCMedicine(name="Pudin Hara", generic_name="Mentha Oil", category="Digestive",
                    purpose="Stomach ache and indigestion relief",
                    common_dosage="1-2 capsules after meals",
                    warnings="Not for children under 5 years.",
                    price_range="₹30-₹60"),
        OTCMedicine(name="ORS (Electral)", generic_name="Oral Rehydration Salts", category="Digestive",
                    purpose="Rehydration during diarrhea and vomiting",
                    common_dosage="1 sachet in 1 litre of clean water",
                    warnings="Use within 24 hours. Seek care if diarrhea persists beyond 2 days.",
                    price_range="₹20-₹30"),
        OTCMedicine(name="Cetirizine (Cetzine)", generic_name="Cetirizine", category="Allergy",
                    purpose="Allergic rhinitis, itching, hives",
                    common_dosage="1 tablet (10mg) daily",
                    warnings="May cause mild drowsiness. Avoid alcohol.",
                    price_range="₹20-₹50"),
        OTCMedicine(name="Allegra 120", generic_name="Fexofenadine", category="Allergy",
                    purpose="Non-drowsy allergy relief",
                    common_dosage="1 tablet (120mg) twice daily",
                    warnings="Avoid fruit juice within 4 hours (reduces absorption).",
                    price_range="₹80-₹150"),
        OTCMedicine(name="Volini Spray", generic_name="Diclofenac Diethylamine", category="Pain Relief",
                    purpose="Muscle pain and joint pain",
                    common_dosage="Spray on affected area 3-4 times daily",
                    warnings="External use only. Avoid on broken skin. Not for NSAID-allergic patients.",
                    price_range="₹100-₹250"),
        OTCMedicine(name="Moov Cream", generic_name="Diclofenac + Methyl Salicylate + Menthol", category="Pain Relief",
                    purpose="Back pain and muscle stiffness",
                    common_dosage="Apply on affected area 2-3 times daily",
                    warnings="External use only. Wash hands after use.",
                    price_range="₹70-₹180"),
        OTCMedicine(name="Burnol", generic_name="Aminacrine + Cetrimide", category="First Aid",
                    purpose="Minor burns and cuts",
                    common_dosage="Apply thin layer on affected area",
                    warnings="External use only. See a doctor for severe burns.",
                    price_range="₹50-₹80"),
        OTCMedicine(name="Betadine", generic_name="Povidone-Iodine", category="First Aid",
                    purpose="Antiseptic for wounds and cuts",
                    common_dosage="Apply on clean wound; cover with dressing",
                    warnings="Avoid with iodine allergy or thyroid disease.",
                    price_range="₹60-₹120"),
        OTCMedicine(name="Dulcolax", generic_name="Bisacodyl", category="Digestive",
                    purpose="Constipation relief",
                    common_dosage="1-2 tablets at bedtime with water",
                    warnings="Not for daily use. Drink plenty of water.",
                    price_range="₹40-₹80"),
        OTCMedicine(name="Nasivion Nasal Drops", generic_name="Oxymetazoline", category="Cold & Cough",
                    purpose="Nasal congestion relief",
                    common_dosage="2-3 drops per nostril every 8-12 hours",
                    warnings="Do NOT use more than 3 consecutive days. Avoid with hypertension.",
                    price_range="₹70-₹120"),
        OTCMedicine(name="Iodex", generic_name="Methyl Salicylate + Menthol", category="Pain Relief",
                    purpose="Joint and muscle pain relief",
                    common_dosage="Apply on affected area 2-3 times daily",
                    warnings="External use only. Avoid near eyes.",
                    price_range="₹50-₹120"),
        OTCMedicine(name="Gelusil MPS", generic_name="Magaldrate + Simethicone", category="Digestive",
                    purpose="Heartburn, gas and acid reflux",
                    common_dosage="1-2 tablets (chewed) after meals and at bedtime",
                    warnings="Avoid with kidney disease.",
                    price_range="₹60-₹100"),
    ]

    db.session.add_all(medicines)
    db.session.commit()
    print(f"[DB] Seeded {len(medicines)} OTC medicines.")


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    app.run(
        debug=Config.FLASK_DEBUG,
        host="0.0.0.0",
        port=5000,
    )
