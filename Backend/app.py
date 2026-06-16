"""
Flask Application - AI Health Assistant
Main application entry point. Registers blueprints and starts the server.
"""

from flask import Flask, send_from_directory
from flask_cors import CORS
import os
import mysql.connector

from config import Config
from database import db, OTCMedicine
from routes import auth_bp, consult_bp, medicine_bp


def _auto_create_database():
    """
    Automatically create the MySQL database if it doesn't exist.
    Uses mysql-connector-python so no manual SQL step is needed.
    """
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
        )
        cursor = connection.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DATABASE}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        connection.commit()
        cursor.close()
        connection.close()
        print(f"[OK] Database '{Config.MYSQL_DATABASE}' is ready.")
    except mysql.connector.Error as e:
        print(f"[ERROR] MySQL connection failed: {e}")
        print("    -> Make sure MySQL is running and your database config is correct.")
        raise


def create_app():
    """Application factory pattern."""

    # Auto-create database if not exists
    _auto_create_database()

    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend"),
        static_url_path="",
    )
    app.config.from_object(Config)
    CORS(app)

    # Initialize Database
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(consult_bp)
    app.register_blueprint(medicine_bp)

    # Static routes
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        return send_from_directory(app.static_folder, path)

    with app.app_context():
        db.create_all()
        _seed_otc_medicines()
        print("[OK] All tables created and OTC medicines seeded.")

    return app


def _seed_otc_medicines():
    """Seed the OTC medicines database with common Indian medicines."""
    if OTCMedicine.query.first():
        return  # Already seeded

    medicines = [
        OTCMedicine(name="Crocin 650", generic_name="Paracetamol", category="Pain & Fever",
                     purpose="Relief from mild to moderate pain and fever", common_dosage="1 tablet every 4-6 hours",
                     warnings="Do not exceed 4g per day. Avoid with liver disease.", price_range="₹20-₹35"),
        OTCMedicine(name="Dolo 650", generic_name="Paracetamol", category="Pain & Fever",
                     purpose="Fever and body pain relief", common_dosage="1 tablet every 4-6 hours",
                     warnings="Avoid alcohol. Do not exceed recommended dose.", price_range="₹25-₹40"),
        OTCMedicine(name="Combiflam", generic_name="Ibuprofen + Paracetamol", category="Pain & Fever",
                     purpose="Pain, inflammation and fever", common_dosage="1 tablet 2-3 times daily after food",
                     warnings="Take after food. Not for stomach ulcer patients.", price_range="₹30-₹50"),
        OTCMedicine(name="Vicks VapoRub", generic_name="Camphor + Menthol + Eucalyptus Oil", category="Cold & Cough",
                     purpose="Relief from cold, cough and nasal congestion", common_dosage="Apply on chest and throat",
                     warnings="For external use only. Keep away from eyes.", price_range="₹50-₹150"),
        OTCMedicine(name="Benadryl Cough Syrup", generic_name="Diphenhydramine", category="Cold & Cough",
                     purpose="Dry cough relief", common_dosage="10ml every 4-6 hours",
                     warnings="May cause drowsiness. Avoid driving.", price_range="₹80-₹120"),
        OTCMedicine(name="Strepsils", generic_name="Amylmetacresol + Dichlorobenzyl Alcohol", category="Cold & Cough",
                     purpose="Sore throat relief", common_dosage="1 lozenge every 2-3 hours",
                     warnings="Do not exceed 12 lozenges per day.", price_range="₹40-₹80"),
        OTCMedicine(name="Digene", generic_name="Dried Aluminium Hydroxide Gel + Magnesium Hydroxide", category="Digestive",
                     purpose="Acidity and gas relief", common_dosage="1-2 tablets after meals",
                     warnings="Long-term use may cause mineral imbalance.", price_range="₹50-₹100"),
        OTCMedicine(name="Eno", generic_name="Sodium Bicarbonate + Citric Acid", category="Digestive",
                     purpose="Quick acidity relief", common_dosage="1 sachet in water when needed",
                     warnings="High sodium content. Avoid with hypertension.", price_range="₹10-₹50"),
        OTCMedicine(name="Pudin Hara", generic_name="Mentha Oil", category="Digestive",
                     purpose="Stomach ache and indigestion relief", common_dosage="1-2 capsules after meals",
                     warnings="Not for children under 5 years.", price_range="₹30-₹60"),
        OTCMedicine(name="Gelusil MPS", generic_name="Magaldrate + Simethicone", category="Digestive",
                     purpose="Heartburn and gas relief", common_dosage="1-2 tablets after meals",
                     warnings="Avoid with kidney disease.", price_range="₹60-₹100"),
        OTCMedicine(name="ORS (Electral)", generic_name="Oral Rehydration Salts", category="Digestive",
                     purpose="Rehydration during diarrhea", common_dosage="1 sachet in 1 litre of water",
                     warnings="Use within 24 hours of preparation.", price_range="₹20-₹30"),
        OTCMedicine(name="Cetirizine (Cetzine)", generic_name="Cetirizine", category="Allergy",
                     purpose="Allergic rhinitis, itching, hives", common_dosage="1 tablet daily",
                     warnings="May cause drowsiness. Avoid with alcohol.", price_range="₹20-₹50"),
        OTCMedicine(name="Allegra 120", generic_name="Fexofenadine", category="Allergy",
                     purpose="Non-drowsy allergy relief", common_dosage="1 tablet daily",
                     warnings="Avoid fruit juices within 2 hours.", price_range="₹80-₹150"),
        OTCMedicine(name="Volini Spray", generic_name="Diclofenac Diethylamine", category="Pain Relief",
                     purpose="Muscle pain and joint pain relief", common_dosage="Spray on affected area 3-4 times daily",
                     warnings="For external use only. Avoid on broken skin.", price_range="₹100-₹250"),
        OTCMedicine(name="Moov Cream", generic_name="Diclofenac + Methyl Salicylate + Menthol", category="Pain Relief",
                     purpose="Back pain and muscle pain relief", common_dosage="Apply on affected area 2-3 times daily",
                     warnings="For external use only. Wash hands after use.", price_range="₹70-₹180"),
        OTCMedicine(name="Burnol", generic_name="Aminacrine + Cetrimide", category="First Aid",
                     purpose="Minor burns and cuts", common_dosage="Apply thin layer on affected area",
                     warnings="For external use only. Seek medical help for severe burns.", price_range="₹50-₹80"),
        OTCMedicine(name="Betadine", generic_name="Povidone-Iodine", category="First Aid",
                     purpose="Antiseptic for wounds", common_dosage="Apply on wound after cleaning",
                     warnings="May stain clothes. Avoid on deep wounds.", price_range="₹60-₹120"),
        OTCMedicine(name="Dulcolax", generic_name="Bisacodyl", category="Digestive",
                     purpose="Constipation relief", common_dosage="1-2 tablets at bedtime",
                     warnings="Not for daily use. Drink plenty of water.", price_range="₹40-₹80"),
        OTCMedicine(name="Nasivion Nasal Drops", generic_name="Oxymetazoline", category="Cold & Cough",
                     purpose="Nasal congestion relief", common_dosage="2-3 drops in each nostril",
                     warnings="Do not use for more than 3 consecutive days.", price_range="₹70-₹120"),
        OTCMedicine(name="Iodex", generic_name="Methyl Salicylate + Menthol", category="Pain Relief",
                     purpose="Joint and muscle pain", common_dosage="Apply on affected area 2-3 times daily",
                     warnings="For external use only. Avoid near eyes.", price_range="₹50-₹120"),
    ]

    db.session.add_all(medicines)
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
