# EcoShield Architecture Specification

**Status:** Draft v1.0  
**Date:** 15 November 2026  
**Repository:** `eco4x/ECOSHIELD-AGENT`  
**Branch:** `docs/architecture-spec`

## 1. Product definition

EcoShield is a Human Risk Management and Security Response Platform. It helps organisations identify, understand, reduce and respond to cybersecurity risk associated with human activity, access and security practices.

It is not limited to phishing simulations, one department, or awareness training. Simulation is one operating mode and one way to demonstrate and validate the platform.

**Product principle:** measure and reduce exposure; do not treat a risk score as proof of misconduct.

## 2. Product modes

EcoShield has two modes built around one shared core.

### 2.1 Simulation Mode

Purpose: investor demonstrations, product evaluation, safe exercises and customer sandbox testing.

- Uses synthetic organisations, identities, events and assets.
- Simulates integrations and response actions; it must never call a real customer system.
- Clearly labels all data and actions as simulated.
- Supports repeatable scenarios, resettable datasets and deterministic test cases.
- Demonstrates the same event, policy, risk and response interfaces used by Live Mode.

### 2.2 Live Enterprise Mode

Purpose: authorised operation within a real organisation.

- Uses tenant-scoped data and explicitly authorised integrations.
- Starts with read-only collection and recommendations.
- Introduces response actions only through documented permissions, approval policies, audit trails and rollback/recovery procedures.
- Supports staged onboarding, integration health checks and least-privilege credentials.
- Never silently reuses simulation data or credentials.

The modes share domain logic and contracts, but use separate data sources, credentials, configuration and response adapters. A mode boundary must be enforced in code, not merely hidden in the user interface.

## 3. High-level architecture

```text
Simulation UI                    Enterprise UI
     |                                 |
Scenario / Demo Adapter        Integration Adapters
     |                                 |
     +---------- Mode Boundary -------+
                       |
                 EcoShield Core
                       |
       +---------------+----------------+
       |               |                |
  Identity &       Event Pipeline   Policy Engine
  Asset Context         |                |
       |            Risk Engine           |
       +---------------+----------------+
                       |
             Response Orchestrator
                       |
              Audit & Reporting
                       |
        Tenant-scoped Data Persistence
```

### Core services

1. **Identity and asset context:** organisation, user, role, team, access context and relevant assets.
2. **Event pipeline:** validates, normalises, deduplicates and records security-relevant events.
3. **Risk engine:** evaluates evidence against explainable, versioned risk rules.
4. **Policy engine:** determines what actions are permitted for a tenant and scenario.
5. **Response orchestrator:** creates recommendations or executes explicitly authorised actions through adapters.
6. **Audit and reporting:** records event provenance, decisions, approvals, actions and outcomes.
7. **Integration framework:** isolates provider-specific APIs behind stable interfaces.

## 4. Organisation-wide human-risk model

The organisation is the top-level risk context. Departments, teams, locations, job functions and access privileges are attributes, not separate risk silos.

Risk views should support:
- Organisation-level trends and exposure.
- Team and department patterns.
- Individual, appropriately access-controlled context.
- Role- and privilege-aware exposure.
- Changes over time and evidence supporting each assessment.

Risk scores must be explainable and evidence-linked. They should include confidence, freshness and contributing factors where practical. Missing data must not be interpreted as safe behaviour. Scores must not be used as automatic grounds for disciplinary action.

## 5. Canonical event contract

All sources should map into a common event structure before risk evaluation.

Minimum logical fields:

- `event_id`: unique identifier for idempotency.
- `tenant_id`: organisation boundary.
- `subject_id`: pseudonymous or internal identity reference where possible.
- `event_type`: normalised event category.
- `source`: simulation or named integration.
- `occurred_at` and `received_at`: timestamps.
- `context`: validated, minimised metadata.
- `evidence_ref`: pointer to controlled evidence, where applicable.
- `schema_version`: event contract version.
- `correlation_id`: links related events.

Do not store passwords, authentication secrets, session tokens or unnecessary personal content. Simulation forms must record interaction outcomes (for example, clicked, reported or submitted a simulated form), never collect real passwords.

## 6. Risk evaluation

- Use configurable, versioned rules rather than scattered hard-coded thresholds.
- Make event processing idempotent.
- Preserve the reason and evidence behind each score change.
- Apply decay or review windows only when explicitly defined and documented.
- Distinguish observed facts, inferred risk and unknown information.
- Test false positives, repeated events, out-of-order events and stale evidence.
- Keep risk calculation separate from response execution.

A score is a decision-support signal, not a verdict about an employee.

## 7. Response safety model

Response levels:

1. **Observe:** ingest and display evidence.
2. **Recommend:** propose a response with rationale.
3. **Approve:** require an authorised human decision.
4. **Execute:** invoke a permitted integration action.
5. **Verify:** confirm the provider accepted the action and record the outcome.
6. **Recover:** provide a documented reversal or remediation path where supported.

Default Live Mode behaviour is read-only plus recommendations. Account suspension, access revocation, session termination or other disruptive actions require explicit tenant policy, least-privilege integration scopes and approval. Emergency automation, if later introduced, must be narrowly scoped, tested and auditable.

Simulation Mode substitutes a simulator adapter for every external action adapter.

## 8. Multi-tenancy, privacy and security requirements

These are foundational requirements, not later enhancements.

- Enforce tenant isolation in application services and data access.
- Authorise every request server-side; never rely on frontend visibility.
- Apply role-based access control and least privilege.
- Encrypt data in transit and at rest using managed, appropriate controls.
- Store secrets outside source control and rotate them.
- Minimise personal data; define retention and deletion policies.
- Record administrative access, configuration changes, approvals and response actions.
- Validate and constrain all external input.
- Protect integration webhooks with authentication, replay protection and signature validation where supported.
- Separate simulation and live credentials, databases and environment configuration.
- Use secure defaults and fail closed for unauthorised actions.

## 9. Initial repository direction

Preserve the existing repository and evolve it incrementally. Do not discard the current implementation before mapping its behaviour and tests.

Proposed target structure (to be adapted after a fresh repository inventory):

```text
apps/
  web/                       # user interface and API entry points
  simulation/                # scenario and demo experience
core/
  identity/
  events/
  risk/
  policy/
  response/
  audit/
integrations/
  simulation/
  identity/
  email/
  siem/
  endpoint/
data/
  migrations/
tests/
  unit/
  integration/
  security/
docs/
  ARCHITECTURE_SPEC.md
```

Existing Vault, Trap, Sentinel and Dashboard responsibilities should be mapped into these boundaries. Reuse sound logic; refactor unsafe or tightly coupled code. Avoid creating empty modules merely to match this diagram.

## 10. Delivery roadmap

### Phase 0 — Baseline and design
- Inventory the complete repository and deployment configuration.
- Capture current behaviour and establish baseline tests.
- Map existing modules to the target architecture.
- Agree the first supported user journeys and data sources.

### Phase 1 — Safe shared core
- Define tenant, identity, event and audit data models.
- Implement validated event ingestion and idempotency.
- Implement explainable risk evaluation and policy interfaces.
- Add unit and integration tests.

### Phase 2 — Simulation MVP
- Build synthetic organisation setup and realistic scenarios.
- Connect the scenario adapter to the shared core.
- Show event timeline, risk rationale, recommendations and simulated outcomes.
- Make reset/replay reliable and visibly label simulated content.

### Phase 3 — Enterprise foundation
- Implement authentication, tenant isolation, RBAC, audit and retention controls.
- Add integration configuration and health checks.
- Begin with one carefully selected read-only integration.

### Phase 4 — Controlled response
- Add approval workflows and response adapters.
- Test failure handling, duplicate delivery, timeouts and recovery.
- Enable only explicitly authorised actions.

### Phase 5 — Validation and expansion
- Run security, privacy, reliability and performance testing.
- Validate tenant isolation and mode separation.
- Add integrations based on customer evidence and product priorities.

## 11. Definition of done

A capability is not complete merely because a demo screen works.

- Unit and integration tests pass.
- Tenant boundaries are tested.
- Simulation cannot reach live integrations.
- Live actions are denied by default unless authorised.
- Events and decisions are auditable and idempotent.
- Risk outcomes have an explainable rationale.
- Errors, retries and partial failures are handled safely.
- Documentation and operational runbooks are updated.

## 12. Decisions to confirm during implementation

The following remain design decisions, not assumed facts:

1. Initial customer segment and first enterprise use case.
2. First live integration (prefer one read-only source initially).
3. Authentication and identity-provider strategy.
4. Data residency, retention and deployment requirements.
5. Initial risk taxonomy and scoring methodology.
6. Which response actions, if any, are in scope for the first live release.

## 13. Immediate next step

Complete a fresh read-only inventory of the repository, map the current Python modules and deployment setup to this specification, then propose a small implementation plan with tests. Keep `main` unchanged until the plan and changes are reviewed.
