

---

## 🛡️ ECOSHIELD AGENT

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

### ⚠️ Disclaimer

ECOSHIELD is a **prototype and research-oriented project**.
It is not intended for production deployment in its current form.

---

### 👤 Author

Developed by **eco4x**
Part of EcoTechLabs Security Research



Say the word.

## Authentication and access-control setup

The web dashboard no longer ships with demo usernames, passwords, or an admin token. Accounts are stored in SQLite and passwords are stored as Werkzeug password hashes.

Set these environment variables before starting the dashboard:

- `ECOSHIELD_SECRET_KEY`: a cryptographically random secret (for example, generate one with Python's `secrets.token_hex(32)`).
- `ECOSHIELD_BOOTSTRAP_ADMIN_EMAIL`: initial administrator email.
- `ECOSHIELD_BOOTSTRAP_ADMIN_PASSWORD`: initial administrator password (minimum 14 characters).
- `ECOSHIELD_COOKIE_SECURE`: keep `true` when served over HTTPS; set `false` only for local HTTP development.

Optional employee bootstrap account:

- `ECOSHIELD_BOOTSTRAP_EMPLOYEE_EMAIL`
- `ECOSHIELD_BOOTSTRAP_EMPLOYEE_PASSWORD` (minimum 14 characters)
- `ECOSHIELD_BOOTSTRAP_EMPLOYEE_NAME`
- `ECOSHIELD_BOOTSTRAP_EMPLOYEE_DEPARTMENT`

Example for local development (use your own values):

```bash
export ECOSHIELD_SECRET_KEY="$(python -c "import secrets; print(secrets.token_hex(32))")"
export ECOSHIELD_COOKIE_SECURE=false
export ECOSHIELD_BOOTSTRAP_ADMIN_EMAIL="admin@example.test"
export ECOSHIELD_BOOTSTRAP_ADMIN_PASSWORD="replace-with-a-unique-strong-password"
python web_dashboard.py
```

The first startup creates the configured account if it does not already exist. Remove the bootstrap password from the runtime environment after account creation. Do not commit secrets or production database files. Production deployment must use HTTPS, a strong externally managed secret, and a persistent protected database.

### Authentication controls in this branch

- Database-backed account records with hashed passwords.
- Administrator and employee roles; administrative actions and event exports require the administrator role.
- Authenticated access to dashboard routes and APIs.
- Session cookies configured as HttpOnly and SameSite=Lax, with a 30-minute lifetime.
- CSRF token validation for state-changing requests.
- No default demo credentials or password/token displayed in the dashboard.
- Flask debug mode disabled.

This is an initial hardening step, not a complete production security review. Rate limiting, MFA, account recovery, session revocation, audit logging, tenant isolation, and deployment-level security still require implementation and testing.

