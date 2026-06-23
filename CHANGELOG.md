# Changelog
All notable changes to this project will be documented in this file.

## [1.5.0] - 2026-06-23
### Added
- Integrated **Medicine Reminders & Central Notification System**:
  - Background time auditor scheduler using `APScheduler`.
  - Core dispatching service (`notification_service.py`) for email, dashboard, and browser alerts.
  - Interactive Web Notifications API permission checker, token/polling handling, and Toast-based fallback alerts.
  - MySQL database dashboard notification history logs and read/unread status management.
  - Added new blueprint endpoints: `POST /api/reminders`, `GET /api/reminders`, `DELETE /api/reminders/<id>`, `POST /api/reminders/<id>/toggle`, and `GET /api/notifications` operations.
- Appended verification tests for medicine reminders and notifications to the automated backend testing suite (`test_backend.py`).

### Changed
- Replaced Twilio-based SMS gateway entirely with free multi-channel notifications (Gmail + Dashboard + Browser).
- Shifted all SMS routes to cleaner blueprints and files named using plain English (e.g. `browser_notification_service.py`, `dashboard_notification_service.py`, `medicine_reminder_scheduler.py`).

### Removed
- Cleaned up and deleted all old Twilio/Android SMS gateway client code, templates, and environment variables.
