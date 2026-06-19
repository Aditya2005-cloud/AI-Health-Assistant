-- ============================================================
-- AI Health Assistant - MySQL Database Setup
-- ============================================================
-- This script manually creates only the database shell.
-- All tables are auto-created by Flask-SQLAlchemy on startup.
--
-- IMPORTANT: The database name below must match MYSQL_DATABASE
-- in your Backend/.env file (default: health_ai)
--
-- Run with:
--   mysql -u root -p < Backend/database/setup_database.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS `health_ai`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `health_ai`;

-- Tables (users, consultations, otc_medicines) are created
-- automatically when you run: python app.py
-- No manual SQL table creation is needed.
