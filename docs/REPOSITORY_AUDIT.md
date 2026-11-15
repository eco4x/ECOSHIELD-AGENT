# EcoShield Repository Audit

**Date:** 15 November 2026  
**Audit type:** Read-only architecture and code review  
**Repository:** `eco4x/ECOSHIELD-AGENT`  
**Baseline:** `main`  
**Additional branch reviewed:** `security/harden-trap-capture`  
**Architecture reference:** `docs/ARCHITECTURE_SPEC.md` on `docs/architecture-spec`

## 1. Executive summary

The repository contains two materially different implementation states:

- `main` is an early Flask/SQLite proof of concept with four small modules: Vault, Trap, Sentinel and a command-line Dashboard.
- `security/harden-trap-capture` is 43 commits ahead of `main` and contains a substantially expanded small-team readiness MVP: a web dashboard, campaign and assessment engine, scheduled worker, tests, CI workflow, and safer simulation behaviour.

**Recommendation:** Do not restart the project and do not merge the 43-commit branch blindly. Treat it as a candidate MVP implementation to review and selectively retain. The next engineering step is to establish a tested baseline and reconcile the best parts of that branch with the approved architecture specification.

This audit is based on the files retrieved and compared. It is not a complete penetration test, runtime test, deployment validation or exhaustive repository-tree audit.

## 2. Branch and repository findings

| Item | Observed state |
|---|---|
| Default branch | `main` |
| `main` baseline commit | `7f1d6b189a890463e5abb8cea92ac7f974cb0bac` |
| Architecture document branch | `docs/architecture-spec` |
| Existing expanded implementation branch | `security/harden-trap-capture` |
| Expanded branch divergence | 43 commits ahead, 0 behind main at audit time |
| Expanded branch CI workflow | `.github/workflows/ecoshield-checks.yml` |
| Expanded branch tests | `tests/test_assessment_engine.py`, `tests/test_dashboard_security.py` |

The expanded branch adds `assessment_engine.py`, `scheduler_worker.py`, `web_dashboard.py`, campaign and learning workflows, tests, a CI workflow and an MVP blueprint. It also removes a tracked SQLite database file and modifies Trap and dependency configuration.

## 3. Main branch: current implementation

### Vault — `vault.py`

- Creates a SQLite `employees` table.
- Inserts the same three seed employees on every invocation.
- Has no uniqueness constraint or idempotent seed operation.
- Uses a relative database path, making the selected database depend on the process working directory.

**Assessment:** Useful prototype data-layer logic, but seed creation and database configuration need redesign before reuse.

### Trap — `trap.py`

- Renders a Flask simulation page.
- Requests an employee email and a network password.
- The capture handler does not use or persist those submitted values, but asking for a real password is still unsafe and undermines user trust.
- The department parameter defaults and SQL matching are inconsistent: the route uses short keys such as `hr`, while the database contains full department names.
- A single interaction adds 25 points and marks matching employee records as `Compromised`.

**Assessment:** Retain the concept of controlled scenarios, but replace credential-style forms with safe interaction choices and explicit synthetic events. Do not reuse the current capture flow as-is.

### Sentinel — `sentinel.py`

- Polls SQLite indefinitely every five seconds.
- Treats a risk score of 50 as a trigger to change employee status to `LOCKED`.
- The implementation only updates a database field; it does not lock real network credentials.
- Selects and updates by employee name rather than a stable identity key.
- Has no event identity, durable decision history, configurable policy or external response adapter.

**Assessment:** Preserve the separation between detection and response as a concept. Rebuild the implementation around event IDs, explainable policies, recommendations and a simulated response adapter.

### Dashboard — `dashboard.py`

- Prints department and risk score values from SQLite.
- Does not retrieve or display employee status.
- Prints explanatory colour labels that are not actually rendered as colour-coded status indicators.

**Assessment:** This is a diagnostic CLI, not an enterprise dashboard. The expanded branch's web dashboard is a more relevant starting point for the MVP interface.

## 4. Expanded branch: candidate MVP implementation

The `security/harden-trap-capture` branch is materially more advanced than `main`.

### Reusable capabilities found

- Flask web dashboard with separate demo administrator and employee roles.
- Environment-configured credentials and secret key; signed sessions, CSRF protection, login rate limiting and security headers.
- Simulation capture no longer asks for passwords; it requires a configured server-side simulation token and accepts predefined department keys.
- Campaign creation, scheduling, employee assignments and controlled interaction recording.
- Scenario-specific micro-learning, completion tracking and baseline-linked retest reports.
- Separate polling scheduler worker with a single-process lock.
- Unit tests for assessment workflows and dashboard access controls.
- GitHub Actions workflow that compiles Python and runs unittest discovery.
- MVP blueprint with explicit non-punitive, privacy and simulation-safety principles.

These capabilities are aligned with the Simulation Mode and early product-validation goals in the Architecture Specification.

### Important limitations and risks to resolve

1. **Not multi-tenant:** The dashboard uses configured demo administrator and employee credentials, with one employee login rather than independently authenticated users across multiple customer organisations.
2. **Identity model is prototype-level:** Several dashboard and assessment paths identify people by display name. Stable tenant-scoped subject IDs and proper identity-provider mapping are required.
3. **SQLite deployment constraints:** The application and scheduler share a SQLite database. This may be acceptable for a controlled single-instance MVP, but is not a suitable default for horizontally scaled enterprise deployment.
4. **Trap/database configuration mismatch:** The revised `trap.py` connects to the literal `ecoshield.db`, while the web dashboard supports `ECOSHIELD_DB_PATH`. If that environment variable points elsewhere, the simulation and dashboard can write to different databases.
5. **Training state semantics:** The revised Trap still increments a risk score and sets employee status to `Compromised`. That label conflicts with the safer product principle that a training interaction is not evidence of account compromise. Use a training indicator or review state instead.
6. **Simulation authorisation:** HTTP Basic authentication protects the capture endpoint with a server-side token. Confirm TLS, secret rotation, deployment scope and whether the endpoint is exposed only to authorised test participants.
7. **Rate-limit storage:** The documented default is in-memory. Multi-worker deployment requires a shared rate-limit backend.
8. **Scheduler operation:** The worker is a separate process and its lock is host-local. Deployment must guarantee one worker per database and reliable persistent storage.
9. **Testing coverage:** The workflow runs compile checks and unittest discovery. The visible test set covers assessment logic and dashboard security, but no dedicated Trap capture tests were found in the compared branch files. Passing CI would not establish end-to-end correctness or enterprise readiness.
10. **Deployment claims:** The inspected files do not establish a verified production deployment, durable database configuration or end-to-end Render worker operation.

## 5. Architecture-spec alignment

| Architecture requirement | Main | Expanded branch | Remaining work |
|---|---|---|---|
| Simulation mode | Basic | Substantially developed | Separate simulator adapters and strict mode boundary |
| Shared core contracts | No | Partial | Formal event, identity, risk and response interfaces |
| Organisation-wide risk context | Department-oriented | Team/department campaigns | Organisation and tenant-level model |
| Explainable risk indicators | Hard-coded threshold | Rule-based training indicators | Versioned rules, evidence and confidence |
| Safe response orchestration | Simulated status update | Recommendations / simulated actions | Policy, approvals, adapter execution and verification |
| Tenant isolation | No | No complete multi-tenant implementation | Tenant-scoped data and authorisation |
| RBAC | No | Demo admin/employee roles | Real identity lifecycle and granular permissions |
| Audit trail | Minimal | Events, reports and action records | Immutable/protected audit design and provenance |
| Live integrations | No | Not established | Read-only integration framework first |
| Automated tests | Not found | Initial unit/security tests and CI | Trap, integration, tenant-isolation and end-to-end tests |

## 6. Reuse versus rebuild decision

### Reuse after review

- The campaign and assessment workflow in `assessment_engine.py`.
- The scenario catalogue and targeted learning concepts.
- The web dashboard layout and role-separated user journeys in `web_dashboard.py`.
- The scheduler as an MVP-only component, after operational testing.
- The security configuration patterns, CSRF controls, rate limiting and access-control tests.
- The CI workflow as a starting point.

### Refactor before reuse

- Trap capture and all risk/status updates.
- Database access and schema ownership.
- Employee identity and all name-based lookups.
- Risk aggregation and campaign reporting.
- Scheduler/database coordination.
- Audit event structure and response semantics.

### Rebuild as shared-core services

- Tenant-aware identity and asset context.
- Canonical event ingestion and validation.
- Idempotent event processing.
- Explainable, versioned risk evaluation.
- Policy evaluation and response orchestration.
- Integration adapter contracts.
- Tenant isolation and organisation-wide reporting.

## 7. Recommended next steps

1. Preserve `main` and both existing development branches.
2. Treat `security/harden-trap-capture` as a candidate MVP baseline, not as production-ready code.
3. Run its CI workflow and tests in a controlled environment; record actual results before claiming a pass.
4. Add dedicated tests for Trap authentication, department validation, database-path consistency and safe event recording.
5. Reconcile its MVP blueprint with `docs/ARCHITECTURE_SPEC.md`; resolve the initial-customer scope explicitly rather than allowing the small-team MVP to define the final enterprise product.
6. Design the shared event, tenant and identity contracts before implementing live integrations.
7. Develop the shared core and simulation mode in isolated branches. Keep live enterprise integrations read-only until access controls, auditability and tenant isolation are verified.

## 8. Audit conclusion

**Do not discard the existing work. Do not merge the expanded branch without review.**

The expanded branch already contains much of the presentation-oriented MVP that the product needs. The best route is to preserve that work, test and harden it, then extract its useful campaign, learning and dashboard capabilities behind a properly defined shared core.

The current repository is a prototype with a promising MVP branch—not yet an enterprise-grade human-risk platform. The architecture specification remains the target design; this audit provides the bridge from the current implementation to that target.
