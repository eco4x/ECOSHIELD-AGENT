"""Unit tests for the lightweight assessment workflow (stdlib unittest)."""
import sqlite3
import unittest
from datetime import timedelta

from assessment_engine import (
    _utc_now,
    activate_due_campaigns,
    campaign_report,
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

        signal = record_interaction(self.conn, assignment_id, 1, "clicked")
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
        record_interaction(self.conn, assignment_id, 1, "reported")
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
            record_interaction(self.conn, assignment_id, 999, "clicked")

    def test_learning_completion_is_recorded(self):
        _, due_at = self.make_due_campaign()
        activate_due_campaigns(self.conn, due_at)
        assignment_id = self.conn.execute(
            "SELECT id FROM assessment_assignments"
        ).fetchone()[0]
        record_interaction(self.conn, assignment_id, 1, "clicked")
        complete_learning(self.conn, assignment_id, 1)
        status = self.conn.execute(
            "SELECT status FROM learning_progress WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()[0]
        self.assertEqual(status, "completed")


    def test_duplicate_names_are_separated_by_employee_id(self):
        self.conn.execute(
            "INSERT INTO employees (id, name, department, risk_score) VALUES (2, 'Test Employee', 'Finance', 0)"
        )
        campaign_id, due_at = self.make_due_campaign()
        self.assertEqual(activate_due_campaigns(self.conn, due_at), 1)

        employee_one = self.conn.execute(
            "SELECT id FROM assessment_assignments WHERE campaign_id = ? AND employee_id = 1",
            (campaign_id,),
        ).fetchone()[0]
        employee_two = self.conn.execute(
            "SELECT id FROM assessment_assignments WHERE campaign_id = ? AND employee_id = 2",
            (campaign_id,),
        ).fetchone()[0]

        self.assertEqual(len(__import__("assessment_engine").list_employee_assignments(self.conn, 1)), 1)
        self.assertEqual(len(__import__("assessment_engine").list_employee_assignments(self.conn, 2)), 1)
        with self.assertRaises(LookupError):
            record_interaction(self.conn, employee_two, 1, "clicked")

        record_interaction(self.conn, employee_two, 2, "clicked")
        with self.assertRaises(LookupError):
            complete_learning(self.conn, employee_two, 1)
        complete_learning(self.conn, employee_two, 2)
        self.assertNotEqual(employee_one, employee_two)

    def test_individual_campaign_targets_only_the_selected_employee_id(self):
        self.conn.execute(
            "INSERT INTO employees (id, name, department, risk_score) VALUES (2, 'Second Employee', 'Finance', 0)"
        )
        scheduled = (_utc_now() + timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds")
        campaign_id = create_campaign(
            self.conn, "Individual retest", "Finance", "phishing_link",
            scheduled, "Test Admin", "UTC", target_employee_id=2
        )

        self.assertEqual(activate_due_campaigns(self.conn, _utc_now() + timedelta(minutes=2)), 1)
        rows = self.conn.execute(
            "SELECT employee_id FROM assessment_assignments WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchall()
        self.assertEqual([row[0] for row in rows], [2])

    def test_retest_report_compares_click_reporting_and_learning_rates(self):
        baseline_time = (_utc_now() + timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds")
        baseline_id = create_campaign(
            self.conn, "Baseline", "Finance", "phishing_link",
            baseline_time, "Test Admin", "UTC"
        )
        baseline_due = _utc_now() + timedelta(minutes=2)
        activate_due_campaigns(self.conn, baseline_due)
        baseline_assignment = self.conn.execute(
            "SELECT id FROM assessment_assignments WHERE campaign_id = ?",
            (baseline_id,),
        ).fetchone()[0]
        record_interaction(self.conn, baseline_assignment, 1, "clicked")

        retest_time = (_utc_now() + timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds")
        retest_id = create_campaign(
            self.conn, "Retest", "Finance", "phishing_link",
            retest_time, "Test Admin", "UTC", baseline_id
        )
        retest_due = _utc_now() + timedelta(minutes=2)
        activate_due_campaigns(self.conn, retest_due)
        retest_assignment = self.conn.execute(
            "SELECT id FROM assessment_assignments WHERE campaign_id = ?",
            (retest_id,),
        ).fetchone()[0]
        record_interaction(self.conn, retest_assignment, 1, "reported")
        complete_learning(self.conn, retest_assignment, 1)

        report = campaign_report(self.conn, retest_id)
        self.assertEqual(report["metrics"]["response_rate"], 100.0)
        self.assertEqual(report["metrics"]["click_rate"], 0.0)
        self.assertEqual(report["metrics"]["report_rate"], 100.0)
        self.assertEqual(report["metrics"]["learning_completion_rate"], 100.0)
        self.assertEqual(report["comparison"]["click_rate_change_pp"], -100.0)
        self.assertEqual(report["comparison"]["report_rate_change_pp"], 100.0)
        self.assertEqual(report["comparison"]["learning_completion_change_pp"], 100.0)

    def test_retest_must_match_completed_baseline_scenario_and_audience(self):
        baseline_time = (_utc_now() + timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds")
        baseline_id = create_campaign(
            self.conn, "Baseline", "Finance", "phishing_link",
            baseline_time, "Test Admin", "UTC"
        )
        activate_due_campaigns(self.conn, _utc_now() + timedelta(minutes=2))
        baseline_assignment = self.conn.execute(
            "SELECT id FROM assessment_assignments WHERE campaign_id = ?",
            (baseline_id,),
        ).fetchone()[0]
        record_interaction(self.conn, baseline_assignment, 1, "clicked")
        with self.assertRaises(ValueError):
            create_campaign(
                self.conn, "Invalid retest", "Finance", "urgent_payment",
                baseline_time, "Test Admin", "UTC", baseline_id
            )

    def test_all_team_campaign_assigns_finance_hr_and_it_once_across_repeated_scheduler_polls(self):
        self.conn.executemany(
            "INSERT INTO employees (id, name, department, risk_score) VALUES (?, ?, ?, ?)",
            [
                (2, "HR Employee", "Human Resources", 0),
                (3, "IT Employee", "IT Operations", 0),
            ],
        )
        scheduled = (_utc_now() + timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds")
        campaign_id = create_campaign(
            self.conn, "All teams regression", "All teams", "phishing_link",
            scheduled, "Test Admin", "UTC"
        )
        due_at = _utc_now() + timedelta(minutes=2)

        self.assertEqual(activate_due_campaigns(self.conn, due_at), 1)
        self.assertEqual(activate_due_campaigns(self.conn, due_at), 0)
        rows = self.conn.execute(
            "SELECT employee_name, department, COUNT(*) FROM assessment_assignments "
            "WHERE campaign_id = ? GROUP BY employee_name, department ORDER BY department",
            (campaign_id,),
        ).fetchall()
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows],
            [
                ("HR Employee", "Human Resources", 1),
                ("IT Employee", "IT Operations", 1),
                ("Test Employee", "Finance", 1),
            ],
        )


if __name__ == "__main__":
    unittest.main()
