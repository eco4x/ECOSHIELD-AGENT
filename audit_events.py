"""Structured, privacy-conscious audit events for ECOSHIELD.

Only caller-approved metadata is stored. Never pass passwords, tokens, session
cookies, authentication codes, or raw request bodies to this module.
"""
import json
from datetime import datetime, timezone


def initialize_audit_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            actor_ref TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_ref TEXT,
            outcome TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'application',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_time ON audit_events(occurred_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_action ON audit_events(action)"
    )


def record_audit_event(
    conn,
    *,
    actor_role,
    action,
    outcome="success",
    actor_ref=None,
    target_type=None,
    target_ref=None,
    source="application",
    metadata=None,
):
    """Insert one structured event; metadata must contain non-sensitive facts."""
    if not actor_role or not action or not outcome:
        raise ValueError("actor_role, action, and outcome are required.")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise TypeError("metadata must be a dictionary.")

    # Keep metadata small and JSON-safe. Callers must explicitly select fields.
    metadata_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    if len(metadata_json) > 2000:
        raise ValueError("Audit metadata exceeds the 2000-character limit.")

    cursor = conn.execute(
        """
        INSERT INTO audit_events (
            occurred_at, actor_role, actor_ref, action, target_type,
            target_ref, outcome, source, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            str(actor_role)[:40],
            str(actor_ref)[:80] if actor_ref is not None else None,
            str(action)[:80],
            str(target_type)[:40] if target_type is not None else None,
            str(target_ref)[:80] if target_ref is not None else None,
            str(outcome)[:40],
            str(source)[:40],
            metadata_json,
        ),
    )
    return cursor.lastrowid


def list_audit_events(conn, limit=50):
    limit = max(1, min(int(limit), 200))
    rows = conn.execute(
        """
        SELECT id, occurred_at, actor_role, actor_ref, action, target_type,
               target_ref, outcome, source, metadata_json
        FROM audit_events
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]
