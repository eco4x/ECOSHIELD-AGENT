# 🛡️ ECOSHIELD

**Lightweight security readiness for small teams.**

ECOSHIELD is an early-stage EcoTechLabs project exploring a practical way for small organisations to assess human-related security risks, deliver targeted awareness education, and measure improvement without needing a dedicated SOC team.

The intended product loop is:

1. **Assess** — run controlled security-awareness campaigns.
2. **Observe** — record safe behaviours such as clicking, reporting, or completing an exercise.
3. **Explain** — show what the signal means and why it matters.
4. **Educate** — provide short, relevant learning.
5. **Retest** — measure whether behaviour improves.
6. **Report** — give administrators a clear view of team readiness.

The product direction and MVP acceptance criteria are documented in [docs/ECOSHIELD_MVP_BLUEPRINT.md](docs/ECOSHIELD_MVP_BLUEPRINT.md).

## Current prototype

The repository currently contains:

- `web_dashboard.py` — Flask readiness dashboard, role-based demo login, controlled simulation feed, employee profiles, campaign planner, employee assessment/learning pages, and rule-based training recommendations.
- `assessment_engine.py` — SQLite-backed campaign scheduling, team assignments, safe interaction recording, and scenario-specific learning recommendations.
- `trap.py` — controlled department-level simulation endpoint. It does not request real employee passwords.
- `vault.py` — SQLite employee profile and risk-score setup.
- `sentinel.py` — rule-based monitoring and simulated account-status changes.
- `dashboard.py` — lightweight terminal risk view.
- `general.py` — terminal summary report.

**Important:** The current implementation is a prototype. Campaign creation, per-employee assignment, safe response recording, scenario-specific lesson completion, and an independent polling scheduler worker are present on the `security/harden-trap-capture` branch. The scheduler worker must be run as a separate, single-instance process alongside the web service; it checks for due campaigns every 15 seconds by default and uses a process lock to prevent duplicate workers on one host. Assessment interactions update a bounded 0–100 employee risk indicator using documented training-signal weights (clicked +15, ignored +5, reported −5). These are awareness indicators, not evidence of compromise. The prototype now supports aggregate campaign outcome reports and linked retest comparisons for the same audience and scenario. It still does not send real emails or support multiple independently authenticated employee accounts; the dashboard uses one configured employee demo login. It is not a complete multi-tenant team-readiness reporting platform. Do not describe the prototype as a complete or production-ready security platform.

## Product and safety principles

- Never collect real passwords, authentication codes, or other employee secrets.
- Use controlled scenarios and synthetic data for demonstrations.
- Make risk indicators explainable and avoid treating one interaction as proof of compromise.
- Do not shame employees or expose public employee rankings.
- Clearly distinguish simulated response actions from actions actually carried out by an integration.
- The current event watcher and analysis endpoint are rule-based, not AI detection engines.
- The current prototype does not perform verified network isolation or real identity-provider account lockout.

## Dashboard security configuration

The dashboard fails closed unless these server-side environment variables are configured:

- `ECOSHIELD_SECRET_KEY` — at least 32 characters.
- `ECOSHIELD_ADMIN_EMAIL`
- `ECOSHIELD_ADMIN_PASSWORD` — at least 12 characters.
- `ECOSHIELD_EMPLOYEE_EMAIL`
- `ECOSHIELD_EMPLOYEE_PASSWORD` — at least 12 characters.

Use unique private values. Never commit secrets or expose them in client-side code.

The dashboard uses signed sessions with HttpOnly and SameSite=Lax cookies, a 30-minute session lifetime, CSRF protection on POST forms, a five-attempt-per-minute login limit, security response headers, and role checks on administrative routes. Sensitive dashboard APIs and event exports require an administrator session. The built-in server runs with debug disabled and binds to localhost by default. Local SQLite data is stored in `ecoshield.db` by default; set `ECOSHIELD_DB_PATH` to choose a persistent database path. Database files are excluded from source control.

For local HTTP development only, set `ECOSHIELD_COOKIE_SECURE=false`. Leave secure cookies enabled behind HTTPS. The built-in Flask server is for local testing only; use a production WSGI server behind HTTPS for deployment.

Example local configuration (replace all values; never commit them):

```bash
export ECOSHIELD_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ECOSHIELD_ADMIN_EMAIL='admin@example.test'
export ECOSHIELD_ADMIN_PASSWORD='replace-with-a-long-unique-password'
export ECOSHIELD_EMPLOYEE_EMAIL='employee@example.test'
export ECOSHIELD_EMPLOYEE_PASSWORD='replace-with-another-long-unique-password'
export ECOSHIELD_COOKIE_SECURE=false
python web_dashboard.py
```

In a second terminal or a separate Render Background Worker using the same environment variables, start the campaign scheduler:

```bash
python scheduler_worker.py
```

Run exactly one scheduler worker for this SQLite database. The worker and web service must use the same working directory and `ecoshield.db` file. On Render, deploy the worker as a separate Background Worker with the same repository branch and required environment variables; do not start the worker inside every web-server process.

## Simulation endpoint security

The `POST /capture` endpoint in `trap.py` requires HTTP Basic authentication:

- Username: `simulator`
- Password: the value configured in `ECOSHIELD_SIMULATION_TOKEN`

If the token is not configured, capture is disabled and the endpoint returns HTTP 503. The endpoint accepts only predefined department keys (`finance`, `hr`, and `it`) and is limited to five requests per minute per client address.

For local development:

```bash
export ECOSHIELD_SIMULATION_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python trap.py
```

Do not put the token in source control or client-side code. The default rate-limit storage is in-memory; a shared backend is needed for multi-worker deployments.

## Development status

ECOSHIELD is under active development and is not intended for production deployment in its current form. Features should be described as implemented only after they are integrated and tested end-to-end.

## Author

Developed by **eco4x** · EcoTechLabs
