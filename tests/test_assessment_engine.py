"""Unit tests for the lightweight assessment workflow (stdlib unittest)."""
import sqlite3
import unittest
from datetime import timedelta

from assessment_engine import (
    _utc_now,
    activate_due_campaigns,
    complete_learning,
    create_campaign,
    initialize_assessment_schema,
    record_interaction,
)


class AssessmentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department TEXT, risk_score INTEGER DEFAULT 0)"
        )
        self.conn.execute(
            "INSERT INTO employees (id, name, department, risk_score) VALUES (1, 'Test Employee', 'Finance', 20)"
        )
        initialize_assessment_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def make_due_campaign(self):
        scheduled = (_utc_now() + timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds")
        campaign_id = create_campaign(
            self.conn, "Unit test campaign", "Finance", "phishing_link",
            scheduled, "Test Admin", "UTC"
        )
        due_at = _utc_now() + timedelta(minutes=2)
        return campaign_id, due_at

    def test_due_campaign_activation_is_idempotent(self):
        campaign_id, due_at = self.make_due_campaign()
        self.assertEqual(activate_due_campaigns(self.conn, due_at), 1)
        self.assertEqual(activate_due_campaigns(self.conn, due_at), 0)
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM assessment_assignments WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()[0]
        self.assertEqual(rows, 1)

    def test_assessment_outcome_updates_bounded_risk_signal(self):
        _, due_at = self.make_due_campaign()
        activate_due_campaigns(self.conn, due_at)
        assignment_id = self.conn.execute(
            "SELECT id FROM assessment_assignments"
        ).fetchone()[0]

        signal = record_interaction(self.conn, assignment_id, "Test Employee", "clicked")
        score = self.conn.execute(
            "SELECT risk_score FROM employees WHERE id = 1"
        ).fetchone()[0]
        self.assertEqual(signal, "needs_guidance")
        self.assertEqual(score, 35)

    def test_reporting_reduces_risk_indicator_without_below_zero(self):
        _, due_at = self.make_due_campaign()
        activate_due_campaigns(self.conn, due_at)
        assignment_id = self.conn.execute(
            "SELECT id FROM assessment_assignments"
        ).fetchone()[0]
        record_interaction(self.conn, assignment_id, "Test Employee", "reported")
        score = self.conn.execute(
            "SELECT risk_score FROM employees WHERE id = 1"
        ).fetchone()[0]
        self.assertEqual(score, 15)

    def test_employee_cannot_submit_another_employees_assignment(self):
        _, due_at = self.make_due_campaign()
        activate_due_campaigns(self.conn, due_at)
        assignment_id = self.conn.execute(
            "SELECT id FROM assessment_assignments"
        ).fetchone()[0]
        with self.assertRaises(LookupError):
            record_interaction(self.conn, assignment_id, "Different Employee", "clicked")

    def test_learning_completion_is_recorded(self):
        _, due_at = self.make_due_campaign()
        activate_due_campaigns(self.conn, due_at)
        assignment_id = self.conn.execute(
            "SELECT id FROM assessment_assignments"
        ).fetchone()[0]
        record_interaction(self.conn, assignment_id, "Test Employee", "clicked")
        complete_learning(self.conn, assignment_id, "Test Employee")
        status = self.conn.execute(
            "SELECT status FROM learning_progress WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()[0]
        self.assertEqual(status, "completed")


if __name__ == "__main__":
    unittest.main()
