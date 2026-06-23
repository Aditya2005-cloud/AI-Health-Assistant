# Project Structure

This document outlines the codebase layout and directory structure of the Medivio project.

## Directory Tree

```
AI-Health-Assistant/
├── Backend/
│   ├── app.py                      # Flask Application Factory and Startup Server
│   ├── config.py                   # Configuration and Environment variable loader
│   ├── requirements.txt            # Python Dependencies list
│   ├── .env.example                # Configuration template
│   ├── test_backend.py             # Integration test suite
│   │
│   ├── database/
│   │   ├── __init__.py             # Exposes models & db session
│   │   ├── models.py               # SQLAlchemy Database Models (Users, Reminders, Notifications)
│   │   └── migration_medicine_reminders.sql   # SQL migration scripts
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth_middleware.py      # JWT validation decorator
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── gemini_prompt.py        # Stage 1 Resident Intake prompt
│   │   └── groq_prompt.py          # Stage 2 Senior Consultant validation prompt
│   │
│   ├── routes/
│   │   ├── __init__.py             # Blueprint assembly registry
│   │   ├── clinical_consultation_routes.py # AI doctor consultations
│   │   ├── medicine_interaction_routes.py  # Medicine search and query filters
│   │   ├── medicine_reminder.py    # CRUD scheduler configurations
│   │   ├── notification.py         # Read/unread status history fetchers
│   │   └── user_authentication_routes.py   # JWT registration and logins
│   │
│   └── services/
│       ├── __init__.py
│       ├── artificial_intelligence_diagnostic_service.py # Dual-model clinical pipeline
│       ├── browser_notification_service.py               # Browser push content providers
│       ├── dashboard_notification_service.py             # Database notification writes
│       ├── medicine_marketplace_service.py               # Local OTC catalog seeding
│       ├── medicine_reminder_scheduler.py               # Background scheduler loop
│       └── notification_service.py                       # Unified notifier coordinator
│
└── frontend/
    ├── index.html                  # Main Single Page App UI shell
    ├── style.css                   # Glassmorphic Dark UI styles
    └── app.js                      # Controller logic (Auth, Consultations, Reminders)
```

## Module Responsibilities

- **Backend/app.py**: Initializes Flask, connects the MySQL database, registers blueprints, seeds OTC medicines, and registers background scheduler hooks on thread start.
- **Backend/routes/**: Contains blueprints partitioned cleanly by context domain (e.g. reminders, auth, notifications, consultation).
- **Backend/services/**: Core engine layers (AI, Reminders scheduler, Notifications coordinator) isolated from API endpoints.
- **frontend/**: Single-page application rendering the interactive UI with Glassmorphic styles and asynchronous API requests.
