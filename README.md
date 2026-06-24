# 🩺 Medivio

> A production-ready AI-powered health consultation platform built with Python (Flask), Google Gemini, Groq (Llama-3), and MySQL — featuring a dual-AI clinical pipeline, JWT authentication, automated email summaries, and an Indian OTC medicine database.

---

## 📋 Table of Contents

1. [Features](#-features)
2. [Tech Stack](#️-tech-stack)
3. [Project Structure](#-project-structure)
4. [Installation Guide](#️-installation-guide)
5. [Environment Variables](#-environment-variables)
6. [Gmail Email Setup](#-gmail-email-setup)
7. [Usage](#-usage)
8. [API Reference](#-api-reference)
9. [Screenshots](#-screenshots)
10. [Troubleshooting](#️-troubleshooting)
11. [FAQ](#-faq)
12. [Contributing](#-contributing)
13. [License](#-license)
14. [Credits](#-credits)
15. [Support](#-support)

---

## ✨ Features

### 🤖 Dual-AI Clinical Pipeline
The core of the application runs a two-stage AI consultation that mimics a real hospital workflow:

| Stage | AI Model | Role |
|-------|----------|------|
| **Stage 1 — Intake** | Google Gemini 2.0 Flash | Acts as a Resident Clinician: analyses symptoms, builds differential diagnoses, suggests safe OTC options |
| **Stage 2 — Validation** | Groq Llama-3.3-70B | Acts as a Senior Consultant: cross-checks Stage 1, removes hallucinated symptoms, validates medicines, signs off final report |

### 🔄 Automatic Failover (100% Uptime)
If Gemini hits a rate limit (`429 RESOURCE_EXHAUSTED`) or goes offline, the system automatically promotes Groq to perform both roles — the user never sees an error.

### 🚨 Emergency Detection
Before any AI call, the system scans the submitted symptoms for 25+ emergency keywords (chest pain, stroke signs, suicidal ideation, anaphylaxis, etc.). If detected:
- AI consultation is **skipped entirely**
- An immediate emergency response is returned
- 112 / 102 emergency numbers are shown
- An urgent email is sent to the patient

### 💊 Indian OTC Medicine Database
20 pre-seeded over-the-counter medicines commonly available in Indian pharmacies, with:
- Generic name and brand name
- Recommended dosage
- Warnings and contraindications
- Approximate price range (₹)
- Categories: Pain & Fever, Cold & Cough, Digestive, Allergy, First Aid, Pain Relief

### 📧 Automated Email Consultation & Deliverability Diagnostics
After every AI consultation, a professionally formatted HTML email is automatically dispatched to the patient's registered address using a non-blocking background daemon thread. Key enhancements include:
- **Anti-Spam Optimization**: Layout refactored to standard, high-compatibility inline CSS tables ensuring perfect rendering in desktop/web clients (Gmail, Outlook, Yahoo) and bypassing spam classification rules.
- **RFC 5322 Email Compliance**: Hardened headers (`Feedback-ID`, `Return-Path`, `List-Unsubscribe`, `X-Priority`) built-in to establish domain reliability and high sender reputation.
- **Open-Tracking Pixel**: Employs a dynamic 1x1 transparent tracking GIF. When the user opens the email, the event logs the `opened_at` timestamp in the database.
- **Delivery Status Dashboard**: Integrated directly inside the Reminders & Notifications page of the UI, displaying recipient address, delivery state (Queued, Delivered, Failed), sent time, open time, a **Send Test Email** trigger, and manual **Resend** utilities for failed/unreceived messages.

### 🔔 Free Multi-Channel Notification & Reminders
A completely free, custom-built notification infrastructure (no Twilio required):
- **Medicine Scheduler**: A background `APScheduler` loop constantly polls for active medicine reminders and triggers dispatches.
- **Interactive Browser Alerts**: Using the HTML5 Web Notifications API, it triggers native desktop popups when a reminder fires. Falls back elegantly to in-app Toast messages if permissions are blocked.
- **Dashboard History**: All alerts are logged into a permanent MySQL `dashboard_notifications` table, viewable via the Reminders Dashboard UI.


### 🔐 Secure Authentication
- JWT (JSON Web Token) based login — stateless, scalable
- Passwords hashed with `bcrypt` (never stored in plain text)
- Tokens expire after 7 days (configurable)
- All consultation endpoints require a valid JWT

### 👤 Full Medical Profile
Each registered patient stores:
- Full name, age, gender, blood group
- Known allergies (auto-injected into AI prompt)
- Medical conditions and current medications
- Emergency contact name and number
- Phone and WhatsApp numbers

### 📜 Consultation History
Every consultation is saved to MySQL with:
- Symptoms submitted
- Full Gemini analysis JSON
- Full Groq validation JSON
- Severity level (low / medium / high / emergency)
- Emergency flag
- Timestamp

### 🎨 Premium Dark UI
- Glassmorphism design with custom gradients
- Animated loading sequence with clinical progress steps
- Fully responsive layout
- Zero external CSS frameworks — pure CSS3

---

## 🛠️ Tech Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.9+ | Core language |
| Flask | 3.1.1 | Web framework |
| Flask-SQLAlchemy | 3.1.1 | ORM layer |
| MySQL Connector | 9.7.0 | Database driver |
| PyJWT | 2.8.0 | JWT authentication |
| bcrypt | 4.1.3 | Password hashing |
| python-dotenv | 1.2.2 | Environment variable loading |
| google-genai | latest | Gemini AI SDK |
| groq | 1.4.0 | Groq AI SDK |
| werkzeug | 3.1.3 | WSGI utilities |

### AI Models
| Model | Provider | Role |
|-------|----------|------|
| `gemini-2.0-flash` | Google DeepMind | Primary medical analyst |
| `llama-3.3-70b-versatile` | Groq | Validator + fallback analyst |

### Frontend
| Technology | Purpose |
|------------|---------|
| HTML5 | Structure and semantic layout |
| CSS3 | Glassmorphism dark-mode design |
| Vanilla JavaScript | State management, API calls, DOM rendering |

### Email
| Technology | Purpose |
|------------|---------|
| Python `smtplib` | SMTP connection (stdlib — no extra install) |
| Python `email` | MIME message construction (stdlib) |
| Gmail SMTP + App Password | Delivery via TLS (port 587) or SSL (port 465) |

### Database
| Technology | Purpose |
|------------|---------|
| MySQL 8.0+ | Primary relational database |
| Tables: `users`, `consultations`, `otc_medicines` | Data storage |

---

## 📂 Project Structure

```
Medivio/
│
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
│   │   └── user_authentication_middleware.py  # JWT validation decorator
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── gemini_diagnostic_prompt.py        # Stage 1 Resident Intake prompt
│   │   └── groq_validation_prompt.py          # Stage 2 Senior Consultant validation prompt
│   │
│   ├── routes/
│   │   ├── __init__.py             # Blueprint assembly registry
│   │   ├── clinical_consultation_routes.py # AI doctor consultations
│   │   ├── medicine_interaction_routes.py  # Medicine search and query filters
│   │   ├── medicine_reminder.py    # CRUD scheduler configurations
│   │   ├── notification.py         # Read/unread status history fetchers
│   │   └── user_authentication_routes.py   # JWT registration and logins
│   │
│   ├── email_notification_service/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── email_service.py
│   │   ├── email_template.py
│   │   └── gmail_sender.py
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
├── frontend/
│   ├── index.html                # Single-page application shell
│   ├── style.css                 # Dark glassmorphism stylesheet
│   └── app.js                    # Frontend logic (auth, consultation, history)
│
├── .gitignore                    # Excludes .env, .venv, __pycache__, etc.
└── README.md                     # This file
```

---

## ⚙️ Installation Guide

### Prerequisites

Before starting, make sure you have the following installed:

| Requirement | Version | Download |
|-------------|---------|----------|
| Python | 3.9 or higher | [python.org](https://www.python.org/downloads/) |
| MySQL Server | 8.0 or higher | [mysql.com](https://dev.mysql.com/downloads/mysql/) |
| Git | Any recent version | [git-scm.com](https://git-scm.com/) |

You also need free API keys from:
- **Google AI Studio** → for Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **Groq Console** → for Llama-3: [console.groq.com/keys](https://console.groq.com/keys)

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/Aditya2005-cloud/AI-Health-Assistant.git
cd AI-Health-Assistant
```

---

### Step 2 — Create a Virtual Environment

```bash
# Create the virtual environment (run once)
python -m venv .venv

# Activate on Windows (Command Prompt)
.venv\Scripts\activate.bat

# Activate on Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Activate on macOS / Linux
source .venv/bin/activate
```

> **Tip:** Your terminal prompt should now show `(.venv)` at the beginning.

---

### Step 3 — Install Dependencies

```bash
pip install -r Backend/requirements.txt
```

No extra packages are needed for Gmail — it uses Python's built-in `smtplib`.

---

### Step 4 — Configure Environment Variables

Copy the example file and fill in your values:

```bash
# Windows
copy Backend\.env.example Backend\.env

# macOS / Linux
cp Backend/.env.example Backend/.env
```

Then open `Backend/.env` and fill in all values. See the [Environment Variables](#-environment-variables) section below for details.

---

### Step 5 — Start MySQL

Make sure your MySQL server is running. The application will **automatically**:
- Create the database if it does not exist
- Create all tables (`users`, `consultations`, `otc_medicines`)
- Seed 20 OTC medicines on first run

No manual SQL commands are needed.

---

### Step 6 — Run the Application

```bash
cd Backend
python app.py
```

Open your browser and go to: **`http://localhost:5000`**

You should see the Medivio login page.

---

## 🔑 Environment Variables

Create `Backend/.env` by copying `Backend/.env.example`. **Never commit `.env` to Git.**

```env
# ── Flask ──────────────────────────────────────
SECRET_KEY=replace_with_a_random_32_char_string
FLASK_DEBUG=True

# ── MySQL Database ──────────────────────────────
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_root_password
MYSQL_DATABASE=health_ai

# ── JWT Authentication ──────────────────────────
JWT_SECRET_KEY=replace_with_a_random_32_char_string
JWT_EXPIRES_DAYS=7

# ── Google Gemini ───────────────────────────────
# Get from: https://aistudio.google.com/apikey
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash

# ── Groq ────────────────────────────────────────
# Get from: https://console.groq.com/keys
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# ── Gmail Email Service ─────────────────────────
# See "Gmail Email Setup" section below
GMAIL_SENDER_ADDRESS=your_gmail@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
GMAIL_SENDER_NAME=Medivio Health
GMAIL_SMTP_HOST=smtp.gmail.com
GMAIL_SMTP_PORT=587
GMAIL_SMTP_TIMEOUT=30
GMAIL_SILENT_FAIL=True
APP_BASE_URL=http://localhost:5000

```

### Variable Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Flask session secret — use a long random string |
| `MYSQL_PASSWORD` | ✅ | Your MySQL root or user password |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `GROQ_API_KEY` | ✅ | Groq API key |
| `JWT_SECRET_KEY` | ✅ | JWT signing secret — use a long random string |
| `GMAIL_SENDER_ADDRESS` | ⚠️ Optional | Gmail address that sends consultation emails |
| `GMAIL_APP_PASSWORD` | ⚠️ Optional | 16-character Gmail App Password |
| `GMAIL_SILENT_FAIL` | ❌ | `True` = email errors don't crash the app (recommended) |
| `FLASK_DEBUG` | ❌ | Set to `False` in production |

> **Note:** Email is optional. If `GMAIL_SENDER_ADDRESS` or `GMAIL_APP_PASSWORD` are missing, the app skips email sending silently — consultations still work normally.

---

## 📧 Gmail Email Setup

Email uses Gmail App Password authentication (not your regular Gmail password). This is a one-time setup.

### Step 1 — Enable 2-Step Verification
Go to [myaccount.google.com/security](https://myaccount.google.com/security) and enable **2-Step Verification**.

### Step 2 — Generate an App Password
Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- Select App: **Mail**
- Select Device: **Other** → type `Medivio`
- Click **Generate**
- Copy the 16-character code shown

### Step 3 — Add to .env
```env
GMAIL_SENDER_ADDRESS=your_gmail@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
```

### How it works
```
Patient submits symptoms
        ↓
AI consultation runs (Gemini → Groq)
        ↓
Result saved to MySQL
        ↓
Background thread spawned (non-blocking)
        ↓
Email template built (12 sections)
        ↓
Email sent via Gmail SMTP (TLS port 587)
        ↓
HTTP response returned to frontend (instantly)
```

---

## 💻 Usage

### Registering a New Account

1. Open `http://localhost:5000`
2. Click **Register**
3. Fill in your medical profile:
   - Full name, email, password
   - Age, gender, blood group
   - Known allergies (important — used in AI prompts and email)
   - Medical conditions and current medications
   - Emergency contact details
4. Click **Create Account**

### Running a Consultation

1. Log in with your credentials
2. In the consultation input box, describe your symptoms in plain English
   - Example: *"I have had a headache for 2 days with mild fever and body aches"*
3. Click **Get AI Consultation**
4. The system runs a 2-stage AI analysis (typically 5–15 seconds)
5. A professional clinical report appears on screen
6. A detailed email summary is sent to your registered email address

### Viewing Consultation History

- Click **History** in the navigation
- Browse all past consultations with timestamps and severity levels
- Click any entry to expand the full report
- Delete individual consultations as needed

### Browsing OTC Medicines

- Click **Medicines** in the navigation
- Browse 20 pre-loaded OTC medicines
- Filter by category: Pain & Fever, Cold & Cough, Digestive, Allergy, etc.
- Each entry shows brand name, generic name, dosage, warnings, and price range

---

## 📡 API Reference

All API endpoints are prefixed with `/api/`. Protected endpoints require the JWT token in the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/register` | ❌ | Create a new account |
| `POST` | `/api/login` | ❌ | Login and receive JWT |
| `GET` | `/api/profile` | ✅ | Get current user profile |
| `PUT` | `/api/profile` | ✅ | Update medical profile |

**Register body:**
```json
{
  "full_name": "Aditya Sharma",
  "email": "aditya@example.com",
  "password": "securePassword123",
  "age": 22,
  "gender": "Male",
  "blood_group": "O+",
  "known_allergies": "Penicillin",
  "medical_conditions": "None",
  "current_medications": "None"
}
```

**Login response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": { "id": 1, "full_name": "Aditya Sharma", "email": "aditya@example.com" }
}
```

### Consultations & Email Diagnostics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/consult` | ✅ | Run AI consultation |
| `GET` | `/api/history` | ✅ | Get consultation history (paginated) |
| `GET` | `/api/history/<id>` | ✅ | Get single consultation |
| `DELETE` | `/api/history/<id>` | ✅ | Delete a consultation |
| `GET` | `/api/email-status` | ✅ | Fetch email logs & status history |
| `GET` | `/api/email-status/track/<log_id>.gif` | ❌ | Dynamic open-tracking pixel resolution |
| `POST` | `/api/email-status/send-test` | ✅ | Trigger deliverability verification test |
| `POST` | `/api/email-status/<log_id>/resend` | ✅ | Manually request a resend for an email |

**Consult body:**
```json
{
  "symptoms": "I have had fever and body pain for 3 days with a sore throat"
}
```

**Consult response:**
```json
{
  "success": true,
  "consultation_id": 42,
  "severity": "Moderate",
  "is_emergency": false,
  "is_fallback": false,
  "gemini_response": { ... },
  "groq_response": { ... }
}
```

### Medicines

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/medicines` | ❌ | List all OTC medicines |
| `GET` | `/api/medicines?category=Digestive` | ❌ | Filter by category |

---

## 📸 Screenshots

> Add screenshots of your application here. Replace the placeholders below with real images.

```
📷 Login Page         → screenshots/login.png
📷 Registration Form  → screenshots/register.png
📷 Consultation UI    → screenshots/consultation.png
📷 AI Report          → screenshots/report.png
📷 Medicine Finder    → screenshots/medicines.png
📷 History Page       → screenshots/history.png
📷 Sample Email       → screenshots/email.png
```

*To add screenshots: take screenshots of your running app, save them in a `screenshots/` folder, and embed them here using:*
```markdown
![Login Page](screenshots/login.png)
```

---

## 🛠️ Troubleshooting

### App won't start — MySQL connection error

**Error:** `mysql.connector.errors.InterfaceError: 2003: Can't connect to MySQL server`

**Fix:**
1. Confirm MySQL is running: open MySQL Workbench or run `mysql -u root -p`
2. Check `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` in `.env`
3. Make sure there are no extra spaces or quotes around values

---

### Gemini API error — 429 or quota exceeded

**Error:** `RESOURCE_EXHAUSTED` or `429 Too Many Requests`

**Fix:** This is expected for free-tier Gemini keys. The app **automatically falls back to Groq** — you do not need to do anything. Check the terminal logs to confirm: you will see `[Resilience] Initiating Groq Analyst Fallback`.

---

### Email not being sent

**Symptom:** No email arrives after consultation

**Check these in order:**
1. Are `GMAIL_SENDER_ADDRESS` and `GMAIL_APP_PASSWORD` set in `.env`?
2. Is the App Password the 16-character code (not your Gmail login password)?
3. Is 2-Step Verification enabled on your Google Account?
4. Check terminal logs for `[GmailSender]` or `[EmailService]` lines
5. Try setting `GMAIL_SILENT_FAIL=False` temporarily to see the full error

---

### JWT token errors — 401 Unauthorized

**Error:** `{"error": "Token is missing"}` or `{"error": "Token is invalid or expired"}`

**Fix:**
1. Log in again to get a fresh token
2. Make sure the `Authorization` header is: `Bearer <token>` (note the space)
3. Check `JWT_EXPIRES_DAYS` — default is 7 days

---

### `ModuleNotFoundError` on startup

**Error:** `ModuleNotFoundError: No module named 'flask'` (or similar)

**Fix:** The virtual environment is not activated.
```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# Then reinstall
pip install -r Backend/requirements.txt
```

---

### PowerShell script execution policy error (Windows)

**Error:** `cannot be loaded because running scripts is disabled on this system`

**Fix:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### Database tables not created

**Symptom:** `Table 'health_ai.users' doesn't exist`

**Fix:** The app auto-creates tables on startup. If this error appears:
1. Check that `MYSQL_DATABASE=health_ai` is in `.env`
2. Confirm MySQL user has `CREATE` privileges
3. Restart the app: `python app.py`

---

## ❓ FAQ

**Q: Is this a real medical tool? Can I use it instead of a doctor?**
A: No. This is strictly an informational tool built for educational and demonstration purposes. Always consult a licensed physician for medical concerns. The app itself displays a disclaimer on every consultation.

---

**Q: Are my health details stored securely?**
A: Yes. Passwords are hashed with bcrypt and never stored in plain text. The database runs locally on your machine — no data is sent to third-party servers other than your symptom text to Gemini/Groq APIs for processing.

---

**Q: Can I run this without a Gmail account?**
A: Yes. Gmail is optional. If `GMAIL_SENDER_ADDRESS` or `GMAIL_APP_PASSWORD` are not set, the app skips email sending and consultations work normally.

---

**Q: Does this work with free API keys?**
A: Yes. Both Gemini (free tier via Google AI Studio) and Groq (free tier) work. The built-in failover ensures the app keeps working even when Gemini hits its free-tier rate limit.

---

**Q: Can I deploy this to a production server?**
A: Yes, with modifications:
- Set `FLASK_DEBUG=False` in `.env`
- Use a production WSGI server (e.g. Gunicorn): `gunicorn -w 4 app:create_app()`
- Use environment variables from your server instead of a `.env` file
- Put a reverse proxy (Nginx) in front of Gunicorn

---

**Q: Why are there two AI models instead of one?**
A: The dual-model pipeline improves accuracy and safety. Gemini performs the initial intake (broader reasoning), and Groq validates the output (removing hallucinations and unsafe recommendations). If either fails, the other fills in — giving 100% uptime.

---

**Q: What is a Gmail App Password and why do I need it?**
A: Google no longer allows apps to log in with your regular Gmail password. An App Password is a 16-character code you generate in your Google Account settings that lets apps send email on your behalf securely. See the [Gmail Email Setup](#-gmail-email-setup) section.

---

**Q: Can I add more OTC medicines to the database?**
A: Yes. Open `Backend/app.py` and add more `OTCMedicine(...)` entries to the `seed_medicines()` function, then restart the app.

---

## 🤝 Contributing

Contributions are welcome! Here is how to get started:

### 1. Fork the Repository
Click the **Fork** button on the top right of this page.

### 2. Clone Your Fork
```bash
git clone https://github.com/your-username/AI-Health-Assistant.git
cd AI-Health-Assistant
```

### 3. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 4. Make Your Changes
- Follow the existing code style (comments, docstrings, function naming)
- Never hardcode credentials — use environment variables
- Add docstrings to all new functions
- Keep medical rules intact (no certain diagnoses, OTC only, check allergies)

### 5. Test Your Changes
```bash
cd Backend
python app.py
# Test manually or run: python test_backend.py
```

### 6. Submit a Pull Request
```bash
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```
Then open a Pull Request on GitHub with a clear description of what you changed and why.

### Contribution Guidelines
- Keep the medical disclaimer intact on all outputs
- Do not suggest prescription-only medications in the email template
- Do not commit `.env` files or real API keys
- Keep the dual-AI pipeline architecture intact
- Write clean, readable Python with comments

---

## 📜 License

This project is licensed under the **MIT License**.

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

## 🙏 Credits

| Contribution | Technology / Provider |
|---|---|
| Primary AI Model | [Google Gemini 2.0 Flash](https://deepmind.google/technologies/gemini/) |
| Validation AI Model | [Groq — Llama-3.3-70B](https://console.groq.com/) |
| Web Framework | [Flask](https://flask.palletsprojects.com/) |
| Database ORM | [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) |
| Authentication | [PyJWT](https://pyjwt.readthedocs.io/) + [bcrypt](https://pypi.org/project/bcrypt/) |
| Email Delivery | Python stdlib `smtplib` + Gmail SMTP |
| UI Design Inspiration | Glassmorphism design language |

Built with ❤️ by **Aditya** — a passionate developer building real-world AI applications.

---

## ⭐ Support

If this project helped you, please consider giving it a **star** on GitHub!

```
⭐ Star this repo → https://github.com/Aditya2005-cloud/AI-Health-Assistant
```

It helps other developers discover the project and motivates continued development.

### Found a bug?
Open an [Issue](https://github.com/Aditya2005-cloud/AI-Health-Assistant/issues) with:
- A clear title describing the bug
- Steps to reproduce it
- What you expected vs what happened
- Your OS and Python version

### Have a feature idea?
Open an [Issue](https://github.com/Aditya2005-cloud/AI-Health-Assistant/issues) with the label `enhancement` and describe your idea.

---

## ⚕️ Medical Disclaimer

> **This Medivio service is strictly for informational and educational purposes only.**
> It is NOT a substitute for professional medical advice, diagnosis, or treatment.
> Always consult a licensed healthcare provider for any medical concerns.
> In a medical emergency, call **112** (National Emergency) or **102** (Ambulance) immediately.
> Never delay seeking medical attention based on information from this application.
