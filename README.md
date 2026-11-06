# 🛡️ ECOSHIELD AGENT

**Human-Risk Simulation & SOAR Workflow Prototype**

---

### 📖 Overview

ECOSHIELD is a prototype cybersecurity framework designed to simulate how human-risk signals (e.g., phishing interaction, credential misuse) can trigger automated response workflows in a Security Operations (SOC) environment.

The project focuses on bridging **user behavior analysis** with **automated mitigation logic**, demonstrating how deception-based signals can be used to drive SOAR-like responses.

---

### 🧠 Core Concept

Instead of relying purely on system logs, ECOSHIELD explores:

* Detection of risky user behavior via controlled deception (honey-tokens)
* Mapping those signals into automated response actions
* Isolating impact based on contextual risk (e.g., department-level)

This serves as a **proof-of-concept for integrating human-risk intelligence into SOC automation pipelines**.

---

### ⚙️ System Components

* **Vault (`vault.py`)**
  SQLite-based store for user identity and simulated risk scoring.

* **Trap (`trap.py`)**
  Flask-based simulation layer used to trigger user interactions and emulate phishing/deception scenarios.

* **Sentinel (`sentinel.py`)**
  Rule-based automation engine that monitors events and executes predefined response actions.

* **Dashboard (`dashboard.py`)**
  Lightweight command-line interface for visualizing simulated risk states and system activity.

---

### 🔁 Simulated Workflow

1. User interacts with a deception trigger (Trap)
2. Event is recorded and evaluated against risk logic (Vault)
3. Sentinel processes the event
4. Predefined response action is triggered (e.g., simulated credential lock, session termination)
5. Dashboard reflects updated system state

---

### 🧪 Purpose & Scope

This project is a **controlled simulation environment**, intended to:

* Demonstrate SOAR workflow logic
* Explore human-risk-driven detection models
* Serve as a foundation for future integration with real security tools (e.g., SIEM, IAM, EDR)

---

### 🔌 Future Integration Direction

Planned evolution includes:

* Integration with external logging systems (SIEM)
* API-based response actions (identity/access control systems)
* Enhanced detection logic (multi-vector threat simulation)
* AI-assisted log interpretation for SOC analysts

---

### 🔐 Simulation Endpoint Security

The simulation form does not request employee email addresses or passwords. It records only a controlled department-level test event.

The `POST /capture` endpoint requires HTTP Basic authentication:
- Username: `simulator`
- Password: the value configured in the server environment variable `ECOSHIELD_SIMULATION_TOKEN`

Set a long, unique token in the hosting environment before using the capture endpoint. Do not commit the token to the repository or place it in client-side code. If the variable is not configured, capture is disabled and the endpoint returns HTTP 503.

The endpoint accepts only the predefined department keys (`finance`, `hr`, and `it`) and is limited to five requests per minute per client address. The default rate-limit storage is in-memory for local development. For multi-worker or production deployments, configure `RATELIMIT_STORAGE_URI` to use a shared rate-limit backend such as Redis.

For local development, set the environment variable before starting the app:

```bash
export ECOSHIELD_SIMULATION_TOKEN='replace-with-a-long-random-token'
python trap.py
```

When prompted by the browser, use username `simulator` and the configured token. Use a different secret-management method for your hosting platform; never put real employee credentials into this simulation.

---

### ⚠️ Disclaimer

ECOSHIELD is a **prototype and research-oriented project**.
It is not intended for production deployment in its current form.

---

### 👤 Author

Developed by **eco4x**
Part of EcoTechLabs Security Research

### Dashboard security configuration

The dashboard fails closed unless these server-side environment variables are configured: `ECOSHIELD_SECRET_KEY` (at least 32 characters), `ECOSHIELD_ADMIN_EMAIL`, `ECOSHIELD_ADMIN_PASSWORD` (at least 12 characters), `ECOSHIELD_EMPLOYEE_EMAIL`, and `ECOSHIELD_EMPLOYEE_PASSWORD` (at least 12 characters). Use unique private values. Do not commit secrets or expose them in client-side code. The former hard-coded demo accounts and admin token have been removed.

The dashboard uses signed sessions with HttpOnly and SameSite=Lax cookies, a 30-minute session lifetime, CSRF protection on POST forms, and a five-attempt-per-minute login limit. Sensitive dashboard APIs, administrative actions, and event exports require an administrator session. Employee incident reports are restricted to events belonging to that employee. Security response headers are enabled. The built-in server runs with debug disabled and binds to localhost by default.

For local HTTP development only, set `ECOSHIELD_COOKIE_SECURE=false`; leave secure cookies enabled behind HTTPS. The built-in Flask server is for local testing only. Use a production WSGI server behind HTTPS for deployment. Set `ECOSHIELD_HOST` only when a different bind address is intentionally required.

Example local configuration (replace all values; never commit them):

```bash
export ECOSHIELD_SECRET_KEY='replace-with-at-least-32-random-characters'
export ECOSHIELD_ADMIN_EMAIL='admin@example.test'
export ECOSHIELD_ADMIN_PASSWORD='replace-with-a-long-unique-password'
export ECOSHIELD_EMPLOYEE_EMAIL='employee@example.test'
export ECOSHIELD_EMPLOYEE_PASSWORD='replace-with-another-long-unique-password'
export ECOSHIELD_COOKIE_SECURE=false
python web_dashboard.py
```
