"""
config.py
---------
Loads all app settings from the .env file.
This is the ONLY place where environment variables are read.
"""

import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load .env file from the Backend folder
load_dotenv()


class Config:
    """Central configuration class — all settings come from .env."""

    # ---- Flask ----
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    # ---- MySQL ----
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "health_ai")

    # SQLAlchemy connection string (password is URL-encoded for special characters)
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- JWT ----
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_EXPIRES_DAYS = int(os.getenv("JWT_EXPIRES_DAYS", 7))

    # ---- AI APIs ----
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ---- SSO ----
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

    # ---- Reminder Scheduler ----
    REMINDER_INTERVAL = int(os.getenv("REMINDER_INTERVAL", 1))
