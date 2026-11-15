# EcoShield Implementation Plan

**Version:** 1.0  
**Date:** 15 November 2026  
**Repository:** eco4x/ECOSHIELD-AGENT  
**Architecture baseline:** docs/ARCHITECTURE_SPEC.md  
**Audit baseline:** docs/REPOSITORY_AUDIT.md  
**Candidate MVP branch:** security/harden-trap-capture

## 1. Objective

Move EcoShield from its current prototype and candidate simulation MVP toward the approved Human Risk Management and Security Response Platform architecture. Preserve useful work, validate it before reuse, and introduce the shared core incrementally.

This plan does not authorise a wholesale merge, production deployment, collection of real employee credentials, or live response actions.

## 2. Branch and change-control strategy

- Keep main as the protected stable baseline.
- Keep security/harden-trap-capture as a candidate source branch; do not merge it directly.
- Keep docs/architecture-spec as the design record.
- Create implementation branches from a reviewed, tested baseline, using small, reviewable changes.
- Prefer a selective port of approved files and commits over a 43-commit bulk merge.
- Require a pull request, test evidence and review for each milestone.
- Keep simulation and live integration configuration, credentials, data stores and action adapters strictly separated.

Suggested implementation branches:
- feature/mvp-hardening
- feature/shared-event-contract
- feature/shared-risk-core
- feature/simulation-adapter
- feature/tenant-foundation
- feature/read-only-integration

## 3. Delivery phases and acceptance gates

### Phase 0 — Establish a reproducible baseline

Tasks:
1. Confirm current branch heads and record the exact commit SHAs.
2. Review the candidate branch diff against main, including every changed and deleted file.
3. Run the existing CI workflow and test suite in a controlled environment.
4. Record Python version, dependency versions, database path, environment variables and deployment process.
5. Reproduce the current simulation flow and capture its expected behaviour.
6. Add missing tests before changing behaviour.

Acceptance gate:
- Baseline test results are recorded, including failures.
- No test is described as passing unless its command and result are captured.
- No real credentials or customer data are used.
- No production database or live service is modified.

### Phase 1 — Harden the simulation MVP

Priority fixes:
1. Remove all password-like fields and ensure simulation never accepts, stores or logs real passwords, tokens or secrets.
2. Use one explicit database configuration path across Trap, dashboard and worker.
3. Replace name-based identity lookups with stable synthetic subject IDs.
4. Replace the status label Compromised for training interactions with a neutral training or assessment state.
5. Validate department, campaign and scenario identifiers against server-side allowlists.
6. Add unique event IDs and idempotent event recording so retries cannot inflate scores.
7. Make seed data creation idempotent.
8. Ensure simulated response actions are visibly labelled and cannot call external systems.
9. Add audit records for campaign creation, assignment, interaction, score change and simulated response.
10. Confirm CSRF, session, authentication, rate limiting, security headers and secret handling through tests.

Required tests:
- Unauthenticated and unauthorised access is denied.
- CSRF failures are rejected.
- Invalid department and scenario values are rejected.
- Duplicate event delivery does not double-count.
- Repeated initialisation does not duplicate employees.
- No password or secret is persisted or logged.
- Dashboard and Trap use the same configured database.
- Training events do not imply actual account compromise.
- Simulation response adapter makes no external network calls.

Acceptance gate:
- Existing and new tests pass in CI.
- Simulation is safe to demonstrate using synthetic data.
- Known limitations are documented.
- No live integration credentials are present in the simulation environment.

### Phase 2 — Define and implement shared core contracts

Implement small, independently tested interfaces before moving application code:
- TenantContext: tenant identity and authorised scope.
- Subject: stable pseudonymous identity and organisation context.
- Event: event_id, tenant_id, subject_id, event_type, source, occurred_at, received_at, schema_version, correlation_id and minimised context.
- RiskAssessment: score or category, rationale, evidence references, confidence and rule version.
- PolicyDecision: permitted action, reason, required approval and policy version.
- ResponseResult: requested action, approval reference, execution status, provider reference and verification result.

Requirements:
- Validate all incoming data.
- Enforce tenant scope at service and repository boundaries.
- Make event ingestion idempotent.
- Keep risk calculation separate from response execution.
- Preserve event provenance and decision rationale.
- Treat missing evidence as unknown, not proof of safe or unsafe behaviour.

Acceptance gate:
- Contract and validation tests pass.
- Cross-tenant access tests prove isolation.
- Duplicate and out-of-order event tests behave deterministically.
- No UI or provider-specific code is required by the core.

### Phase 3 — Extract shared risk and policy services

Tasks:
1. Move risk calculation into a pure service with versioned, configurable rules.
2. Record the evidence and rationale for every assessment.
3. Add organisation-wide aggregation with team and department as contextual dimensions.
4. Distinguish observed behaviour, inferred risk and missing information.
5. Add policy evaluation without executing actions.
6. Add tests for thresholds, repeated events, decay windows if configured, stale evidence and false-positive cases.

Acceptance gate:
- Same input events and rule version produce deterministic assessments.
- Assessments are explainable and traceable.
- Risk scores are not treated as proof of misconduct or grounds for automatic discipline.

### Phase 4 — Build Simulation Mode on the shared core

Tasks:
1. Port the candidate dashboard and campaign/learning workflows selectively after review.
2. Replace direct database mutations with shared event and risk services.
3. Implement a simulator response adapter that records intended outcomes only.
4. Provide synthetic organisation setup, scenario execution, event timeline and assessment rationale.
5. Support reset and replay with deterministic fixtures.
6. Label all simulated identities, events, scores and actions clearly.

Acceptance gate:
- The end-to-end demo journey works from scenario launch to event, assessment, recommendation and simulated response.
- Simulation cannot access live provider credentials or endpoints.
- Reset and replay produce predictable results.
- Demo data cannot be mistaken for customer production data.

### Phase 5 — Enterprise foundation, initially read-only

Tasks:
1. Implement tenant-aware authentication and role-based authorisation.
2. Add tenant isolation tests at API, service and persistence layers.
3. Define secret storage, rotation, retention, deletion and audit policies.
4. Select one initial customer integration based on customer need and available test environment.
5. Implement that integration read-only with least-privilege scopes.
6. Add webhook verification, replay protection, retry handling and integration health reporting where applicable.
7. Document deployment, backup, restore and incident procedures.

Acceptance gate:
- Tenant isolation and authorisation tests pass.
- No integration can write or perform response actions.
- Data retention and deletion behaviour is documented and tested.
- Integration failures do not corrupt event or risk state.

### Phase 6 — Controlled response capability

Only begin after Phases 1–5 have passed their gates.

Tasks:
1. Define an explicit catalogue of permitted response actions.
2. Require tenant policy and appropriate human approval for disruptive actions.
3. Implement provider-specific adapters with least privilege.
4. Add idempotency, timeouts, retry limits and safe failure handling.
5. Verify provider outcomes and record immutable audit evidence.
6. Define rollback or recovery steps where the provider supports them.
7. Keep automatic high-impact actions disabled by default.

Acceptance gate:
- Unauthorised actions are denied by default.
- Approval identity and policy rationale are recorded.
- Duplicate requests cannot trigger duplicate actions.
- Partial failures and recovery paths are tested.
- A simulation adapter and a live adapter cannot be confused or interchanged by configuration accident.

## 4. First sprint: concrete work order

The first implementation sprint should stay within the candidate simulation MVP and must not introduce live integrations.

1. Capture the branch comparison and baseline CI result.
2. Review the candidate branch's complete changed-file list and security-sensitive diffs.
3. Add tests for Trap capture, database-path consistency, event duplication and training status semantics.
4. Fix the database-path mismatch and stable synthetic identity handling.
5. Remove any remaining credential-like input and verify that secrets are neither stored nor logged.
6. Correct the training status model and add event audit records.
7. Run the full test suite and CI again.
8. Produce a pull request with before/after evidence and unresolved risks.

Sprint exit criteria:
- Tests demonstrate the critical safety properties.
- CI results are recorded and reproducible.
- The simulation demo remains functional.
- Main remains unchanged until review and explicit merge approval.

## 5. Non-goals for the first MVP

- No production employee monitoring.
- No real password, session-token or authentication-secret collection.
- No automatic account suspension or access revocation.
- No broad SIEM or endpoint deployment.
- No claim of enterprise readiness based on a demo.
- No disciplinary scoring or opaque employee ranking.
- No bulk merge of the candidate branch.

## 6. Key decisions still requiring product input

These should be settled before the relevant phase, not guessed in code:
1. Initial customer segment and highest-value human-risk use case.
2. First read-only integration.
3. Required hosting and data-residency model.
4. Retention period and customer deletion requirements.
5. Initial risk taxonomy and governance model.
6. Roles allowed to view individual-level assessments.

## 7. Immediate next action

Begin Phase 0 by reviewing the full candidate-branch diff and running its existing CI/tests. Publish the exact commands, environment assumptions, results and failures. Only then start Phase 1 fixes on a dedicated implementation branch.
