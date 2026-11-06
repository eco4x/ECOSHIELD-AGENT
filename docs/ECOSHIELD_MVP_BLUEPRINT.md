# ECOSHIELD — Product Direction and MVP Blueprint

## Product direction

ECOSHIELD is a lightweight security-readiness and human-risk platform for small teams that do not have a dedicated security operations centre. It helps a team run repeatable security assessments, understand risky behaviours, deliver relevant micro-learning, and measure whether security habits improve.

The Render-hosted demonstration is inspiration and evidence of the original direction, not a specification to copy. The GitHub implementation is the product source of truth. We should preserve useful working concepts while improving the workflow, security model, usability, and measurement.

### Initial customer

Small organisations and teams that need practical security awareness and basic human-risk visibility but cannot justify a full SOC stack or a dedicated analyst.

The initial product should be fast to configure, inexpensive to operate, understandable to a non-specialist administrator, and useful without SIEM, EDR, or identity-provider integrations.

## Product loop

1. **Assess** — An administrator creates a campaign, chooses a scenario and audience, and schedules a controlled assessment.
2. **Observe** — ECOSHIELD records safe behavioural signals such as opened, clicked, reported, ignored, or completed. It must never collect real passwords or other secrets.
3. **Explain** — The system explains what the behaviour indicates, what it does not prove, and why the signal matters.
4. **Educate** — The employee receives a short lesson and a practical action matched to the observed gap.
5. **Retest** — A later assessment checks whether behaviour improved.
6. **Report** — The administrator sees team-level patterns, participation, reporting behaviour, learning completion, and changes over time.

## MVP capabilities

### 1. Team and campaign management
- Manage a small employee directory and departments.
- Create one-time or recurring assessment campaigns.
- Select an audience by employee or department.
- Set a start time, end time, and campaign status.
- Show the campaign schedule and its delivery/participation state.
- Make timezone handling explicit; default display timezone is Africa/Kampala unless configured otherwise.

### 2. Safe simulation library
Start with a small, reusable library of controlled scenarios:
- Suspicious link / phishing message.
- Unexpected attachment.
- Impersonation or urgent payment request.
- MFA fatigue / unexpected approval request.
- QR-code or shortened-link awareness.

Scenarios must be clearly controlled training exercises. They must not harvest credentials, execute attachments, deliver malware, or impersonate a real third party without authorisation. For the first MVP, in-app or manually shared test links are preferable to sending external email automatically.

### 3. Behaviour and risk indicators
Use explainable signals rather than an opaque employee score. Track, where available:
- Interaction outcome (clicked, ignored, reported, completed).
- Reporting rate and time-to-report.
- Repeat behaviour across campaigns.
- Learning completion and retest outcome.
- Participation and campaign coverage.

Show the evidence behind every indicator. Avoid treating one click as proof that an employee is compromised or unsafe. Do not use public employee leaderboards or punitive rankings.

### 4. Targeted micro-learning
- Recommend a short lesson based on the observed behaviour.
- Keep lessons practical and concise.
- Record completion.
- Offer a follow-up assessment.
- Show the employee what they can do differently next time.

### 5. Small-team dashboard
The administrator should quickly understand:
- Which campaigns are scheduled, active, or complete.
- Which departments have participated.
- The most common behaviour gaps.
- Reporting and learning-completion rates.
- Whether the team is improving across repeated assessments.

### 6. Safe response guidance
Provide suggested next steps and a record of what the administrator did. The MVP may simulate response actions, but must label them as simulated. It must not claim to isolate a device, revoke access, lock a real account, or contact an incident team unless an actual integration performed that action and the result was verified.

## Design principles

- **Lightweight first:** Flask and SQLite are suitable for a controlled single-instance MVP; avoid adding infrastructure without a demonstrated need.
- **Privacy by design:** collect the minimum behavioural data required; no real credentials; restrict employee-level detail to authorised roles.
- **Explainable:** show the event, rule, reason, and recommended action behind every risk indicator.
- **Non-punitive:** use assessments to improve team readiness, not shame or rank employees.
- **Reliable scheduling:** scheduled work must have an explicit execution mechanism, timezone, retry policy, and visible status. A campaign must not be shown as sent or completed merely because it was created.
- **Honest product claims:** distinguish simulated behaviour from real security controls and rule-based analysis from AI.

## MVP acceptance criteria for the founder meetings

A credible first demonstration should allow us to:
1. Sign in as an administrator.
2. Create a campaign for a selected employee or department.
3. Set a future schedule and see its status.
4. Run a controlled simulation using a safe test interaction.
5. Record the outcome against the correct campaign and employee.
6. Recommend and display a relevant learning item.
7. Record learning completion and a follow-up assessment.
8. Show a simple team report comparing the initial assessment with the retest.
9. Demonstrate role restrictions and explain which actions are simulated.

If a feature is not implemented end-to-end, the interface and pitch must label it as planned or simulated.

## Delivery sequence

### Before the first founder meeting
- Stabilise the existing login, role checks, simulation and event records.
- Remove misleading claims about credential capture, AI, network isolation, and real account locking.
- Build one end-to-end campaign path with a small synthetic team.
- Prepare a repeatable demo dataset and reset procedure.

### After the first meeting
- Prioritise feedback from founders.
- Improve campaign scheduling and audience management.
- Complete targeted learning and retest reporting.
- Validate the need with potential small-business users before adding integrations.

### Later roadmap
- Optional email/calendar integrations.
- Multi-tenant organisation support.
- External identity, endpoint, and SIEM integrations.
- Stronger analytics after collecting sufficient, consented data.
- More advanced automation only where an integration can safely verify the action.

## Current implementation caveats

The existing repository contains a Flask dashboard, a department-level trap simulator, SQLite employee/event records, and rule-based risk/response logic. It is a prototype, not yet the complete campaign-to-learning product described above.

The current employee login is configured for one demo employee, and the dashboard's simulation scenarios are static. Scheduled campaign management, per-employee campaign assignment, targeted learning progress, and measured retests still need to be implemented and tested.

The existing alert watcher is rule-based despite some UI labels saying "AI". Its isolation details are simulated text, not verified network isolation. These labels must be corrected before external demonstrations.
