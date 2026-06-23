-- ============================================================
-- Medivio — Medicine Reminder & Dashboard Notification Migration
-- ============================================================
-- Safe migration: adds the medicine_reminders and dashboard_notifications
-- tables without affecting any existing tables or data.
--
-- This script is OPTIONAL — Flask-SQLAlchemy auto-creates
-- all tables on startup via db.create_all(). Run this only
-- if you need to create the tables manually in MySQL:
--
--   mysql -u root -p health_ai < Backend/database/migration_medicine_reminders.sql
-- ============================================================

USE `health_ai`;

-- ── Create medicine_reminders table ─────────────────────────
CREATE TABLE IF NOT EXISTS `medicine_reminders` (
    `id`              INT AUTO_INCREMENT PRIMARY KEY,
    `user_id`         INT NOT NULL,
    `medicine_name`   VARCHAR(200) NOT NULL,
    `dosage`          VARCHAR(100) DEFAULT NULL,
    `instructions`    TEXT DEFAULT NULL,
    `reminder_time`   TIME NOT NULL,
    `frequency`       VARCHAR(20) NOT NULL DEFAULT 'daily',
    `reminder_days`   VARCHAR(100) DEFAULT NULL,
    `start_date`      DATE DEFAULT NULL,
    `end_date`        DATE DEFAULT NULL,
    `is_active`       TINYINT(1) NOT NULL DEFAULT 1,
    `last_sent_at`    DATETIME DEFAULT NULL,
    `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Foreign key: each reminder belongs to a user
    CONSTRAINT `fk_reminder_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE CASCADE,

    -- Index for scheduler queries (find active reminders quickly)
    INDEX `idx_active_time` (`is_active`, `reminder_time`),
    INDEX `idx_user_id` (`user_id`)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- ── Create dashboard_notifications table ────────────────────
CREATE TABLE IF NOT EXISTS `dashboard_notifications` (
    `id`                 INT AUTO_INCREMENT PRIMARY KEY,
    `user_id`            INT NOT NULL,
    `title`              VARCHAR(200) NOT NULL,
    `message`            TEXT NOT NULL,
    `notification_type`  VARCHAR(50) NOT NULL DEFAULT 'reminder',
    `is_read`            TINYINT(1) NOT NULL DEFAULT 0,
    `created_at`         DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key: each notification belongs to a user
    CONSTRAINT `fk_notification_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE CASCADE,

    INDEX `idx_notification_user` (`user_id`),
    INDEX `idx_notification_read` (`is_read`)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

SELECT 'Migration complete: medicine_reminders and dashboard_notifications tables are ready.' AS status;
