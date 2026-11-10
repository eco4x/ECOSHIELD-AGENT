"""Flask dashboard authorization and simulation-language tests."""
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

import web_dashboard


class DashboardSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test-ecoshield.db")
        self.db_patch = patch.object(web_dashboard, "DB_PATH", self.db_path)
        self.db_patch.start()
        web_dashboard.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            SESSION_COOKIE_SECURE=False,
        )
        web_dashboard.initialize_database()
        web_dashboard.ensure_seed_data()
        self.client = web_dashboard.app.test_client()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def login(self, email, password):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )

    def test_admin_api_rejects_anonymous_requests(self):
        response = self.client.get("/api/profiles")
        self.assertEqual(response.status_code, 401)

    def test_employee_cannot_access_admin_profiles_api(self):
        response = self.login("employee@example.test", "test-employee-password-123")
        self.assertEqual(response.status_code, 302)
        denied = self.client.get("/api/profiles")
        self.assertEqual(denied.status_code, 403)

    def test_admin_can_access_profiles_api(self):
        response = self.login("admin@example.test", "test-admin-password-123")
        self.assertEqual(response.status_code, 302)
        allowed = self.client.get("/api/profiles")
        self.assertEqual(allowed.status_code, 200)
        self.assertIsInstance(allowed.get_json(), list)

    def test_employee_cannot_view_campaign_reports(self):
        self.login("employee@example.test", "test-employee-password-123")
        response = self.client.get("/campaigns/1/report")
        self.assertEqual(response.status_code, 403)

    def test_legacy_analysis_path_remains_available(self):
        self.login("admin@example.test", "test-admin-password-123")
        response = self.client.post("/api/ai/analyze", json={"events": []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["analysis_type"], "rule_based_training_signal")

    def test_analysis_endpoint_is_explicitly_rule_based_and_non_containment(self):
        self.login("admin@example.test", "test-admin-password-123")
        response = self.client.post(
            "/api/readiness/analyze",
            json={"events": [{"impact": 18, "event_type": "Simulated phishing", "user": "Demo Employee"}]},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["analysis_type"], "rule_based_training_signal")
        self.assertFalse(payload["real_containment_performed"])
        self.assertIn("not evidence of compromise", payload["summary"])
        self.assertTrue(any("retest" in item.lower() for item in payload["suggestions"]))

    def test_security_headers_are_present(self):
        response = self.client.get("/login")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")


if __name__ == "__main__":
    unittest.main()
