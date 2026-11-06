"""Lightweight campaign, assessment, and learning workflow for ECOSHIELD.

This module uses SQLite and the standard library. It records safe training
signals only; it never collects credentials or performs real containment.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SCENARIOS = {
    "phishing_link": {
        "title": "Suspicious link",
        "sender": "Accounts Support",
        "subject": "Review an unexpected account notice",
        "message": "A message asks you to follow a link to review an unexpected account notice. The destination and request have not been verified.",
        "lesson_key": "verify_links",
        "lesson_title": "Pause before opening links",
        "lesson": "Check the sender and destination independently. Do not rely on display text alone. If a message is unexpected or urgent, use a known contact channel to verify it.",
        "next_step": "Hover or inspect the destination where possible, verify the sender, and report unexpected requests through your approved channel.",
    },
    "urgent_payment": {
        "title": "Urgent payment request",
        "sender": "Executive Office",
        "subject": "Urgent supplier payment",
        "message": "A message appears to come from a senior colleague and requests an urgent supplier payment with limited context.",
        "lesson_key": "verify_payment",
        "lesson_title": "Verify unusual payment requests",
        "lesson": "Payment changes and urgent transfers should be verified using a second, known communication channel and the organisation's approval process. Do not use contact details supplied only in the suspicious message.",
        "next_step": "Pause the transaction and verify the request with the known approver using an established contact method.",
    },
    "unexpected_attachment": {
        "title": "Unexpected attachment",
        "sender": "Document Services",
        "subject": "Document awaiting review",
        "message": "An unexpected message asks you to open an attachment to view an important document. No file is provided in this simulation.",
        "lesson_key": "handle_attachments",
        "lesson_title": "Handle unexpected attachments safely",
        "lesson": "Unexpected attachments can be used to deliver malware or steal information. Confirm that the sender expected you to receive the file and use approved scanning and reporting procedures.",
        "next_step": "Verify the file with the sender through a known channel. Report unexpected attachments instead of opening them.",
    },
    "mfa_fatigue": {
        "title": "Unexpected MFA approval",
        "sender": "Identity Support",
        "subject": "Approve sign-in request",
        "message": "A sign-in approval request appears even though you did not initiate a login.",
        "lesson_key": "mfa_requests",
        "lesson_title": "Reject unexpected MFA prompts",
        "lesson": "Never approve an authentication request you did not initiate. Deny the prompt and report it using your organisation's approved process. Repeated prompts may indicate attempted account access.",
        "next_step": "Deny the unexpected prompt and report it. Never share a one-time code with anyone.",
    },
}


def scenario_options():
    return [
        {"key": key, "title": value["title"], "subject": value["subject"]}
        for key, value in SCENARIOS.items()
    ]


def initialize_assessment_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS assessment_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            scenario_key TEXT NOT NULL,
            scheduled_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled',
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assessment_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            employee_name TEXT NOT NULL,
            department TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'assigned',
            interaction TEXT,
            signal TEXT,
            assigned_at TEXT NOT NULL,
            completed_at TEXT,
            UNIQUE(campaign_id, employee_id)
        );

        CREATE TABLE IF NOT EXISTS learning_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL UNIQUE,
            employee_name TEXT NOT NULL,
            lesson_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'assigned',
            assigned_at TEXT NOT NULL,
            completed_at TEXT
        );
        """
    )


def _utc_now():
    return datetime.now(timezone.utc)


def _parse_schedule(value, timezone_name):
    try:
        local_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown campaign timezone.") from exc

    try:
        scheduled = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Enter a valid campaign date and time.") from exc

    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=local_zone)
    return scheduled.astimezone(timezone.utc)


def create_campaign(conn, name, department, scenario_key, scheduled_at, created_by, timezone_name="Africa/Kampala"):
    name = (name or "").strip()
    department = (department or "").strip()
    scenario_key = (scenario_key or "").strip()

    if not name or len(name) > 80:
        raise ValueError("Campaign name must contain 1 to 80 characters.")
    if department not in {"All teams", "Finance", "Human Resources", "IT Operations"}:
        raise ValueError("Choose a valid team.")
    if scenario_key not in SCENARIOS:
        raise ValueError("Choose a valid simulation scenario.")
    if not created_by:
        raise ValueError("A signed-in administrator is required.")

    scheduled_utc = _parse_schedule(scheduled_at, timezone_name)
    now = _utc_now()
    if scheduled_utc < now.replace(second=0, microsecond=0):
        raise ValueError("Choose a schedule time that is not in the past.")

    cursor = conn.execute(
        """
        INSERT INTO assessment_campaigns
            (name, department, scenario_key, scheduled_at, status, created_at, created_by)
        VALUES (?, ?, ?, ?, 'scheduled', ?, ?)
        """,
        (
            name,
            department,
            scenario_key,
            scheduled_utc.isoformat(timespec="seconds"),
            now.isoformat(timespec="seconds"),
            created_by,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def activate_due_campaigns(conn, now=None):
    """Create one assignment per matching employee for campaigns whose time has arrived."""
    now = now or _utc_now()
    now_text = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    due = conn.execute(
        "SELECT id, department FROM assessment_campaigns WHERE status = 'scheduled' AND scheduled_at <= ?",
        (now_text,),
    ).fetchall()

    activated = 0
    for campaign in due:
        if campaign["department"] == "All teams":
            employees = conn.execute(
                "SELECT id, name, department FROM employees ORDER BY name"
            ).fetchall()
        else:
            employees = conn.execute(
                "SELECT id, name, department FROM employees WHERE department = ? ORDER BY name",
                (campaign["department"],),
            ).fetchall()

        if not employees:
            conn.execute(
                "UPDATE assessment_campaigns SET status = 'no_targets' WHERE id = ?",
                (campaign["id"],),
            )
            continue

        for employee in employees:
            conn.execute(
                """
                INSERT OR IGNORE INTO assessment_assignments
                    (campaign_id, employee_id, employee_name, department, status, assigned_at)
                VALUES (?, ?, ?, ?, 'assigned', ?)
                """,
                (
                    campaign["id"],
                    employee["id"],
                    employee["name"],
                    employee["department"],
                    now_text,
                ),
            )
        conn.execute(
            "UPDATE assessment_campaigns SET status = 'active' WHERE id = ?",
            (campaign["id"],),
        )
        activated += 1

    conn.commit()
    return activated


def list_campaigns(conn, limit=20):
    rows = conn.execute(
        """
        SELECT c.*,
               COUNT(a.id) AS assigned_count,
               SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) AS completed_count
        FROM assessment_campaigns c
        LEFT JOIN assessment_assignments a ON a.campaign_id = c.id
        GROUP BY c.id
        ORDER BY c.scheduled_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_employee_assignments(conn, employee_name):
    rows = conn.execute(
        """
        SELECT a.id, a.campaign_id, a.employee_name, a.department, a.status,
               a.interaction, a.signal, a.assigned_at, a.completed_at,
               c.name AS campaign_name, c.scenario_key, c.scheduled_at,
               l.status AS learning_status, l.lesson_key
        FROM assessment_assignments a
        JOIN assessment_campaigns c ON c.id = a.campaign_id
        LEFT JOIN learning_progress l ON l.assignment_id = a.id
        WHERE a.employee_name = ?
        ORDER BY c.scheduled_at DESC
        LIMIT 20
        """,
        (employee_name,),
    ).fetchall()

    assignments = []
    for row in rows:
        item = dict(row)
        scenario = SCENARIOS.get(item["scenario_key"], {})
        item["scenario_title"] = scenario.get("title", "Security assessment")
        item["scenario_sender"] = scenario.get("sender", "Training team")
        item["scenario_subject"] = scenario.get("subject", "")
        item["scenario_message"] = scenario.get("message", "")
        item["lesson_title"] = scenario.get("lesson_title", "Security learning")
        item["lesson"] = scenario.get("lesson", "")
        item["next_step"] = scenario.get("next_step", "")
        assignments.append(item)
    return assignments


def record_interaction(conn, assignment_id, employee_name, interaction):
    if interaction not in {"clicked", "reported", "ignored"}:
        raise ValueError("Choose a valid simulation response.")

    row = conn.execute(
        """
        SELECT a.id, a.status, a.employee_name, c.scenario_key
        FROM assessment_assignments a
        JOIN assessment_campaigns c ON c.id = a.campaign_id
        WHERE a.id = ?
        """,
        (assignment_id,),
    ).fetchone()

    if row is None or row["employee_name"] != employee_name:
        raise LookupError("Assessment not found.")
    if row["status"] != "assigned":
        raise ValueError("This assessment has already been completed.")

    signal = {
        "clicked": "needs_guidance",
        "reported": "protective_behaviour",
        "ignored": "not_reported",
    }[interaction]
    now_text = _utc_now().isoformat(timespec="seconds")
    lesson_key = SCENARIOS[row["scenario_key"]]["lesson_key"]

    conn.execute(
        """
        UPDATE assessment_assignments
        SET status = 'completed', interaction = ?, signal = ?, completed_at = ?
        WHERE id = ?
        """,
        (interaction, signal, now_text, assignment_id),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO learning_progress
            (assignment_id, employee_name, lesson_key, status, assigned_at)
        VALUES (?, ?, ?, 'assigned', ?)
        """,
        (assignment_id, employee_name, lesson_key, now_text),
    )

    remaining = conn.execute(
        """
        SELECT COUNT(*) FROM assessment_assignments
        WHERE campaign_id = (SELECT campaign_id FROM assessment_assignments WHERE id = ?)
          AND status != 'completed'
        """,
        (assignment_id,),
    ).fetchone()[0]
    if remaining == 0:
        conn.execute(
            """
            UPDATE assessment_campaigns SET status = 'completed'
            WHERE id = (SELECT campaign_id FROM assessment_assignments WHERE id = ?)
            """,
            (assignment_id,),
        )
    conn.commit()
    return signal


def complete_learning(conn, assignment_id, employee_name):
    now_text = _utc_now().isoformat(timespec="seconds")
    cursor = conn.execute(
        """
        UPDATE learning_progress
        SET status = 'completed', completed_at = ?
        WHERE assignment_id = ? AND employee_name = ? AND status = 'assigned'
        """,
        (now_text, assignment_id, employee_name),
    )
    if cursor.rowcount == 0:
        raise LookupError("Learning item not found or already completed.")
    conn.commit()
