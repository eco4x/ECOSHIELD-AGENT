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
from organization_model import (ensure_organization_schema, create_organization, create_department)


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

    def test_seed_data_repairs_partially_populated_employee_table(self):
        conn = web_dashboard.get_db_connection()
        conn.execute("DELETE FROM employees WHERE name IN (?, ?)", ("Marcus Ward", "Sarah Connor"))
        conn.commit()
        conn.close()

        web_dashboard.ensure_seed_data()
        conn = web_dashboard.get_db_connection()
        rows = conn.execute(
            "SELECT name, department, COUNT(*) FROM employees GROUP BY name, department ORDER BY name"
        ).fetchall()
        conn.close()
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows],
            [("Alice Vance", "Finance", 1), ("Marcus Ward", "Human Resources", 1), ("Sarah Connor", "IT Operations", 1)],
        )

    def test_repeated_vault_initialization_does_not_duplicate_employees(self):
        import vault

        with patch.dict(os.environ, {"ECOSHIELD_DB_PATH": self.db_path}):
            vault.setup_vault()
            vault.setup_vault()

        conn = web_dashboard.get_db_connection()
        rows = conn.execute(
            "SELECT name, COUNT(*) FROM employees GROUP BY name ORDER BY name"
        ).fetchall()
        conn.close()
        self.assertEqual(
            [(row[0], row[1]) for row in rows],
            [("Alice Vance", 1), ("Marcus Ward", 1), ("Sarah Connor", 1)],
        )


    def test_organization_migration_preserves_employee_ids_and_duplicate_names(self):
        conn = web_dashboard.get_db_connection()
        conn.execute("INSERT INTO employees (id, name, department) VALUES (101, 'Alex Kim', 'Finance')")
        conn.execute("INSERT INTO employees (id, name, department) VALUES (102, 'Alex Kim', 'Finance')")
        conn.commit()
        ensure_organization_schema(conn)
        rows = conn.execute(
            """SELECT e.id, e.organization_id, e.department_id, o.name, d.name
               FROM employees e JOIN organizations o ON o.id = e.organization_id
               JOIN departments d ON d.id = e.department_id
               WHERE e.id IN (101, 102) ORDER BY e.id"""
        ).fetchall()
        self.assertEqual([row["id"] for row in rows], [101, 102])
        self.assertEqual(rows[0]["organization_id"], rows[1]["organization_id"])
        self.assertEqual(rows[0]["department_id"], rows[1]["department_id"])
        self.assertEqual(rows[0][3], "ECOSHIELD Demo Organization")
        self.assertEqual(rows[0][4], "Finance")
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM employees WHERE name = 'Alex Kim' AND department = 'Finance'"
        ).fetchone()[0], 2)
        conn.close()

    def test_organization_migration_is_repeatable(self):
        conn = web_dashboard.get_db_connection()
        ensure_organization_schema(conn)
        ensure_organization_schema(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0], 1)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM departments WHERE name = 'Finance'"
        ).fetchone()[0], 1)
        conn.close()


    def test_admin_can_create_organization_and_department(self):
        self.login("admin@example.test", "test-admin-password-123")
        response = self.client.post("/api/organizations", json={"name": "Northwind Finance"})
        self.assertEqual(response.status_code, 201)
        organization_id = response.get_json()["id"]
        department = self.client.post(
            f"/api/organizations/{organization_id}/departments",
            json={"name": "Risk"},
        )
        self.assertEqual(department.status_code, 201)
        listing = self.client.get(f"/api/organizations/{organization_id}/departments")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.get_json()[0]["name"], "Risk")

    def test_department_cannot_be_assigned_across_organizations(self):
        self.login("admin@example.test", "test-admin-password-123")
        conn = web_dashboard.get_db_connection()
        first = conn.execute("SELECT id FROM organizations WHERE slug = 'ecoshield-demo'").fetchone()[0]
        employee = conn.execute("SELECT id FROM employees WHERE name = 'Alice Vance'").fetchone()[0]
        second = create_organization(conn, "Separate Tenant")
        foreign_department = create_department(conn, second, "Finance")
        conn.close()
        response = self.client.post(
            f"/api/organizations/{first}/employees/{employee}/department",
            json={"department_id": foreign_department},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("does not belong", response.get_json()["error"])

    def test_employee_cannot_manage_organizations(self):
        self.login("employee@example.test", "test-employee-password-123")
        response = self.client.get("/api/organizations")
        self.assertEqual(response.status_code, 403)

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
