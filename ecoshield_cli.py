"""ECOSHIELD terminal interface.

The CLI and Flask dashboard share the same SQLite database and campaign engine.
Run this only on a host where the operator is authorised to access ECOSHIELD data.
"""
import argparse
import os
import sqlite3
from datetime import datetime, timezone

from assessment_engine import (
    initialize_assessment_schema,
    create_campaign,
    list_campaigns,
    scenario_options,
)
from audit_events import initialize_audit_schema, list_audit_events, record_audit_event


def database_path():
    return os.environ.get("ECOSHIELD_DB_PATH", "ecoshield.db")


def connect(path=None):
    conn = sqlite3.connect(path or database_path())
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT,
            department TEXT,
            risk_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Secure'
        )
        """
    )
    initialize_assessment_schema(conn)
    initialize_audit_schema(conn)
    conn.commit()
    return conn


def command_status(args):
    conn = connect(args.db)
    employees = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    campaigns = conn.execute("SELECT COUNT(*) FROM assessment_campaigns").fetchone()[0]
    assignments = conn.execute("SELECT COUNT(*) FROM assessment_assignments").fetchone()[0]
    completed = conn.execute(
        "SELECT COUNT(*) FROM assessment_assignments WHERE status = 'completed'"
    ).fetchone()[0]
    learning = conn.execute(
        "SELECT COUNT(*) FROM learning_progress WHERE status = 'completed'"
    ).fetchone()[0]
    print("ECOSHIELD STATUS")
    print(f"Database: {args.db or database_path()}")
    print(f"Employees: {employees}")
    print(f"Campaigns: {campaigns}")
    print(f"Assignments completed: {completed}/{assignments}")
    print(f"Learning items completed: {learning}")
    conn.close()


def command_campaigns(args):
    conn = connect(args.db)
    rows = list_campaigns(conn, limit=args.limit)
    if not rows:
        print("No campaigns found.")
    for row in rows:
        print(
            f"#{row['id']}  {row['name']} | {row['department']} | "
            f"{row['scenario_key']} | {row['status']} | "
            f"{row['completed_count']}/{row['assigned_count']} completed"
        )
    conn.close()


def command_audit(args):
    conn = connect(args.db)
    for event in list_audit_events(conn, limit=args.limit):
        print(
            f"{event['occurred_at']} | {event['actor_role']} | "
            f"{event['action']} | {event['target_type'] or '-'}:"
            f"{event['target_ref'] or '-'} | {event['outcome']}"
        )
    conn.close()


def command_campaign_create(args):
    conn = connect(args.db)
    try:
        campaign_id = create_campaign(
            conn,
            args.name,
            args.department,
            args.scenario,
            args.at,
            args.created_by,
            args.timezone,
        )
        record_audit_event(
            conn,
            actor_role="local_cli",
            actor_ref=args.created_by,
            action="campaign.created",
            target_type="campaign",
            target_ref=campaign_id,
            source="cli",
            metadata={
                "department": args.department,
                "scenario_key": args.scenario,
            },
        )
        conn.commit()
    except (ValueError, sqlite3.Error) as exc:
        conn.rollback()
        raise SystemExit(f"Campaign not created: {exc}")
    finally:
        conn.close()
    print(f"Campaign #{campaign_id} created and scheduled.")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ecoshield",
        description="Manage the shared ECOSHIELD database from the terminal.",
    )
    parser.add_argument("--db", help="SQLite database path; defaults to ECOSHIELD_DB_PATH or ecoshield.db.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show a concise readiness overview.")
    status.set_defaults(func=command_status)

    campaigns = sub.add_parser("campaigns", help="List assessment campaigns.")
    campaigns.add_argument("--limit", type=int, default=20)
    campaigns.set_defaults(func=command_campaigns)

    audit = sub.add_parser("audit", help="List recent structured audit events.")
    audit.add_argument("--limit", type=int, default=20)
    audit.set_defaults(func=command_audit)

    create = sub.add_parser("campaign-create", help="Create a scheduled assessment campaign.")
    create.add_argument("--name", required=True)
    create.add_argument("--department", required=True, choices=["All teams", "Finance", "Human Resources", "IT Operations"])
    create.add_argument("--scenario", required=True, choices=[item["key"] for item in scenario_options()])
    create.add_argument("--at", required=True, help="Local ISO date/time, e.g. 2026-11-28T10:00:00.")
    create.add_argument("--timezone", default=os.environ.get("ECOSHIELD_TIMEZONE", "Africa/Kampala"))
    create.add_argument("--created-by", default=os.environ.get("USER", "local-operator"))
    create.set_defaults(func=command_campaign_create)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
