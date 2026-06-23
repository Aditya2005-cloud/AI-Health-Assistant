"""
app.py
------
Medivio — Flask Application Entry Point

Run with:
    python app.py

What happens on startup:
  1. Auto-creates the MySQL database if it doesn't exist
  2. Creates all tables (users, consultations, otc_medicines, medicine_reminders)
  3. Seeds the marketplace cache from the dataset when needed
  4. Starts the SMS reminder scheduler (if Android SMS Gateway is configured)
  5. Starts the Flask dev server on http://localhost:5000
"""

import logging
import os
import re
import mysql.connector
from flask import Flask, send_from_directory
from flask_cors import CORS

logger = logging.getLogger(__name__)

from config import Config
from database import db, OTCMedicine
from services.medicine_marketplace_service import load_marketplace_catalog
from routes import auth_bp, consult_bp, medicine_bp, reminder_bp, notification_bp


# ─────────────────────────────────────────────
# Step 1: Auto-create MySQL database
# ─────────────────────────────────────────────
def create_database_if_missing():
    """Connect to MySQL without selecting a DB and create it if it doesn't exist."""
    db_name = Config.MYSQL_DATABASE

    # Validate database name to prevent SQL injection via env vars
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        raise ValueError(
            f"[DB] Invalid database name '{db_name}'. "
            "Only alphanumeric characters and underscores are allowed."
        )

    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
        )
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("[DB] Database '%s' is ready.", db_name)
    except mysql.connector.Error as e:
        logger.error("[DB] MySQL connection failed: %s", e)
        logger.error("  → Make sure MySQL is running and your .env DB settings are correct.")
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
    app.register_blueprint(reminder_bp)
    app.register_blueprint(notification_bp)

    # ── Serve frontend files ──
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/assets/<path:path>")
    def serve_assets(path):
        assets_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        return send_from_directory(assets_folder, path)

    @app.route("/<path:path>")
    def serve_static(path):
        return send_from_directory(app.static_folder, path)

    # ── Create tables and seed data ──
    with app.app_context():
        db.create_all()
        seed_medicines()
        logger.info("[DB] All tables are ready.")

    # ── Start medicine reminder scheduler (non-blocking background thread) ──
    try:
        from services.medicine_reminder_scheduler import start_medicine_reminder_scheduler
        start_medicine_reminder_scheduler(app)
    except Exception as e:
        logger.warning("[Scheduler] Scheduler failed to start (non-critical): %s", e)

    return app


# ─────────────────────────────────────────────
# Step 3: Seed OTC Medicines (runs once)
# ─────────────────────────────────────────────
def seed_medicines():
    """Seed the marketplace database from the dataset when needed."""
    existing_count = OTCMedicine.query.count()

    # Replace the legacy hardcoded seed set with dataset-driven marketplace items.
    if existing_count:
        legacy_names = {
            "Crocin 650",
            "Dolo 650",
            "Combiflam",
            "Vicks VapoRub",
            "Benadryl Cough Syrup",
            "Strepsils",
            "Digene",
            "Eno",
            "Pudin Hara",
            "ORS (Electral)",
            "Cetirizine (Cetzine)",
            "Allegra 120",
            "Volini Spray",
            "Moov Cream",
            "Burnol",
            "Betadine",
            "Dulcolax",
            "Nasivion Nasal Drops",
            "Iodex",
            "Gelusil MPS",
        }
        current_names = {medicine.name for medicine in OTCMedicine.query.limit(50).all()}
        if existing_count > 25 or not current_names.intersection(legacy_names):
            return

        db.session.query(OTCMedicine).delete()
        db.session.commit()

    medicines = []
    for medicine in load_marketplace_catalog()[:250]:
        medicines.append(
            OTCMedicine(
                name=medicine["name"],
                generic_name=medicine.get("generic_name"),
                category=medicine.get("category"),
                purpose=medicine.get("purpose"),
                common_dosage=medicine.get("common_dosage"),
                warnings=medicine.get("warnings"),
                price_range=medicine.get("price_range"),
            )
        )

    if not medicines:
        return

    db.session.add_all(medicines)
    db.session.commit()
    logger.info("[DB] Seeded %d marketplace medicines from the dataset.", len(medicines))


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
