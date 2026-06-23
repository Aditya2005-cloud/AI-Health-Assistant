# Medivio Roadmap

This document outlines the short-term and long-term goals for the Medivio Dual-AI Health Assistant platform.

## Phase 1: Infrastructure and Refactoring (Current Phase)
- [x] Migrate from SQLite to MySQL for production readiness.
- [x] Centralize notification logic (replace Twilio with Free multi-channel notifications).
- [x] Refactor routes and services using plain English, modular blueprints.
- [x] Integrate robust background task scheduling (`APScheduler`).
- [x] Implement complete testing suite covering all CRUD, AI, and Notification endpoints.
- [x] Standardize GitHub repository and generate documentation (`README.md`, `installation_guide.md`, `project_structure.md`).

## Phase 2: Feature Expansion
- [ ] **Multi-lingual Support**: Allow the platform to handle localized symptom intake and translate AI reports to regional languages.
- [ ] **Dockerization**: Provide a `docker-compose.yml` to spin up the Flask API and MySQL instance instantly.
- [ ] **Computer Vision Integrations**: Allow users to upload photos of symptoms or past physical medical reports to be processed via Gemini Vision.
- [ ] **Enhanced Analytics**: Implement a user dashboard with charts showing health trends over time based on historic consultations.

## Phase 3: Platform Evolution
- [ ] **Mobile Application**: Port the Vanilla JS web application into a cross-platform React Native or Flutter mobile application.
- [ ] **Human-in-the-Loop (HITL) Dashboard**: Provide an interface for licensed physicians to review and digitally sign off on AI-generated treatment plans.
- [ ] **EHR Integrations**: Conform to FHIR/HL7 standards to exchange data with official electronic health records.
