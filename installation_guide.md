# Installation Guide

This document provides complete instructions for setting up and running the Medivio Dual-AI Health Assistant platform on your local Windows PC.

## Prerequisites

Make sure you have the following installed on your system:
- **Python 3.9+** (Ensure "Add Python to PATH" is checked during installation)
- **MySQL Server 8.0+**
- **Git**

## Setup Steps

### 1. Clone the Repository
```bash
git clone https://github.com/Aditya2005-cloud/AI-Health-Assistant.git
cd AI-Health-Assistant
```

### 2. Configure Virtual Environment
Create and activate a Python virtual environment:
```bash
# Create the environment
python -m venv .venv

# Activate (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install Backend Dependencies
Install all required packages from `requirements.txt`:
```bash
pip install -r Backend/requirements.txt
```

### 4. Setup Environment Variables
Copy the env template:
```bash
copy Backend\.env.example Backend\.env
```
Open `Backend/.env` in your editor and provide:
- `SECRET_KEY` and `JWT_SECRET_KEY` (Generate secure random strings)
- MySQL credentials (`MYSQL_PASSWORD`, database name `health_ai`)
- AI keys (`GEMINI_API_KEY`, `GROQ_API_KEY`)
- Gmail SMTP authentication details (`GMAIL_SENDER_ADDRESS`, `GMAIL_APP_PASSWORD`)

### 5. Running the Application
Ensure MySQL is running, then start the server:
```bash
cd Backend
python app.py
```
Open your browser and navigate to `http://localhost:5000` to access the portal.

### 6. Running Tests
To run the automated suite of backend endpoints, run:
```bash
python test_backend.py
```
