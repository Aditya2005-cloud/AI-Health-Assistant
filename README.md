# 🩺 AI Health Assistant

A professional, modular, and resilient health analysis platform featuring a multidisciplinary **AI Clinical Consultation Board**. This application takes patient symptoms, triages them through a Resident Clinician, refines the case via an Attending Consultant Physician, and generates a unified, layman-friendly validated health advisory report.

---

## 🚀 Key Features

*   **Multidisciplinary Case Conference**: Uses a dual-AI pipeline simulating a real hospital consultation:
    *   **Resident Clinician** (Gemini): Performs initial patient intake, gathers age/gender context, lists provisional differentials, and suggests a care routine.
    *   **Attending Consultant** (Groq): Reviews the resident's intake, removes unstated symptoms or assumptions, validates safe OTC options, outlines strict contraindications, and signs off on the final protocol.
*   **System Resilience (Failover Core)**: Includes an automatic failover mechanism. If the primary API (Gemini) encounters rate limits (`429 RESOURCE_EXHAUSTED`), the pipeline seamlessly transitions to a secondary engine (Groq) for both intake and validation, maintaining 100% uptime.
*   **Unified Professional Layout**: Exposes only one consolidated, highly professional Medical Board advisory panel to the patient. No internal technical model names are revealed.
*   **Indian OTC Medicine Finder**: Recommends safe over-the-counter (OTC) medicines commonly available in local Indian pharmacies with clear clinical justifications.
*   **User Profiles & History Tracking**: Fully secure user login with hashed credentials and a local MySQL database to save and load past consultations.

---

## 🛠️ The Technology Stack & Why It Was Chosen

### Backend
1.  **Flask (Python)**: A lightweight, micro-framework chosen for its simplicity, speed, and support for modular Blueprint routing.
2.  **Flask-SQLAlchemy (ORM)**: Decouples python code from SQL. Chosen to easily switch database backends if needed and to write clean, model-based queries.
3.  **MySQL Database**: A robust, standard relational database chosen for transactional safety and structural indexing of users, consultation histories, and OTC medicines.

### AI Integration
1.  **Google GenAI SDK (`google-genai` & `google-generativeai`)**: Used for the primary intake phase. Gemini provides rich, structured clinical text extraction. The code is written with a **dual-SDK wrapper** to run under any Python environment regardless of package version.
2.  **Groq API (Llama-3)**: Selected for its blazingly fast inference speeds, making it ideal for real-time validation checks and instant fallbacks.

### Frontend
1.  **HTML5 & CSS3 (Glassmorphism design)**: Sleek, high-end dark-themed aesthetic with custom gradients, smooth transitions, and responsive grids.
2.  **Vanilla JavaScript**: High performance, zero-dependency scripting to control views, track state, trigger loading steps, and display report animations.

---

## 📂 Project Structure

```text
AI Health Assistant/
├── Backend/
│   ├── app.py                # Main Flask application & database initialization
│   ├── config.py             # Configuration loader (API keys & DB creds)
│   ├── requirements.txt      # Backend Python dependencies
│   ├── database/
│   │   ├── db.py             # Database session manager
│   │   ├── models.py         # User, Consultation, and Medicine models
│   │   └── setup_database.sql # MySQL database initialization schema
│   ├── prompts/
│   │   ├── gemini_prompt.py  # System prompts for Resident Clinician
│   │   └── groq_prompt.py    # System prompts for Attending Consultant
│   ├── routes/
│   │   ├── __init__.py       # Blueprint registry
│   │   ├── auth_routes.py    # Auth APIs (login/register)
│   │   ├── consult_routes.py # Consultation pipeline API
│   │   └── medicine_routes.py# Medicine database retrieval API
│   └── services/
│       ├── __init__.py
│       └── ai_service.py     # Dual-AI sequential pipeline & resilience core
├── frontend/
│   ├── index.html            # Main UI index file
│   ├── style.css             # Sleek dark-mode glassmorphic styling
│   └── app.js                # Frontend controllers & DOM rendering engine
└── README.md
```

---

## ⚙️ Setup Instructions

### 1. Configure the Environment
Duplicate the **`Backend/.env.example`** file as **`Backend/.env`** and fill in your keys:

```env
# API Keys (Keep secure)
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# MySQL Configuration (Optional: defaults to root/root if not specified)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=ai_health_assistant
```

### 2. Set Up the MySQL Database (Automatic or Manual)
*   **Automatic Setup (Recommended)**: Simply running the app in Step 4 will automatically create the database `ai_health_assistant`, configure all tables, and seed the OTC medicines database for you.
*   **Manual Setup (Optional)**: If you prefer manual setup, log into your MySQL client and run the database setup script:
    ```bash
    mysql -u root -p < Backend/database/setup_database.sql
    ```

### 3. Install Dependencies
Activate your virtual environment and install the required Python libraries:

```bash
# Activate Virtual Environment (Windows CMD)
.venv\Scripts\activate.bat

# Install Requirements
pip install -r Backend/requirements.txt
```

### 4. Run the Application
Start the Flask development server:

```bash
cd Backend
python app.py
```
Open **`http://localhost:5000`** in your browser to start using the assistant!

---

## ⚕️ Disclaimer
This AI Health Assistant is strictly for **informational and educational purposes**. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a licensed healthcare provider for medical concerns.
