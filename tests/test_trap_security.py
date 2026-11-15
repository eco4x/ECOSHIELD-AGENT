"""Security regression tests for the department-level simulation capture endpoint."""

import base64
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("ECOSHIELD_SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
os.environ.setdefault("ECOSHIELD_ADMIN_EMAIL", "admin@example.test")
os.environ.setdefault("ECOSHIELD_ADMIN_PASSWORD", "test-admin-password-123")
os.environ.setdefault("ECOSHIELD_EMPLOYEE_EMAIL", "employee@example.test")
os.environ.setdefault("ECOSHIELD_EMPLOYEE_PASSWORD", "test-employee-password-123")
os.environ.setdefault("ECOSHIELD_COOKIE_SECURE", "false")

import trap
import web_dashboard


class TrapSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "shared-ecoshield.db")
        self.trap_db_patch = patch.object(trap, "DB_PATH", self.db_path)
        self.dashboard_db_patch = patch.object(web_dashboard, "DB_PATH", self.db_path)
        self.trap_db_patch.start()
        self.dashboard_db_patch.start()
        self.token_patch = patch.dict(os.environ, {"ECOSHIELD_SIMULATION_TOKEN": "test-simulation-token"})
        self.token_patch.start()

        web_dashboard.initialize_database()
        web_dashboard.ensure_seed_data()
        trap.app.config.update(TESTING=True)
        self.client = trap.app.test_client()

    def tearDown(self):
        self.token_patch.stop()
        self.dashboard_db_patch.stop()
        self.trap_db_patch.stop()
        self.temp_dir.cleanup()

    def auth_headers(self):
        value = base64.b64encode(b"simulator:test-simulation-token").decode("ascii")
        return {"Authorization": "Basic " + value}

    def test_simulation_page_does_not_request_passwords(self):
        response = self.client.get("/?dept=finance")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'type="password"', response.data.lower())
        self.assertNotIn(b'name="password"', response.data.lower())

    def test_capture_requires_simulator_authentication(self):
        response = self.client.post("/capture", data={"dept": "finance"})
        self.assertEqual(response.status_code, 401)

    def test_unknown_department_is_rejected(self):
        response = self.client.post(
            "/capture",
            data={"dept": "unknown"},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)

    def test_capture_uses_dashboard_database_and_does_not_mark_compromised(self):
        before = web_dashboard.get_db_connection()
        employee_before = before.execute(
            "SELECT id, risk_score, status FROM employees WHERE department = ?",
            ("Finance",),
        ).fetchone()
        before.close()
        self.assertIsNotNone(employee_before)

        response = self.client.post(
            "/capture",
            data={"dept": "finance"},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 200)

        after = web_dashboard.get_db_connection()
        employee_after = after.execute(
            "SELECT risk_score, status FROM employees WHERE id = ?",
            (employee_before["id"],),
        ).fetchone()
        after.close()

        self.assertEqual(employee_after["risk_score"], min(100, employee_before["risk_score"] + 25))
        self.assertEqual(employee_after["status"], employee_before["status"])
        self.assertNotEqual(employee_after["status"], "Compromised")


if __name__ == "__main__":
    unittest.main()
