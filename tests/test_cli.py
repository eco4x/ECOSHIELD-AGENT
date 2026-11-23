"""Smoke tests for the ECOSHIELD terminal interface."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "ecoshield_cli.py")


class CliSmokeTests(unittest.TestCase):
    def test_cli_creates_campaign_and_lists_shared_database_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "cli-test.db")
            scheduled = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
            base = [sys.executable, CLI, "--db", db_path]

            created = subprocess.run(
                base + [
                    "campaign-create", "--name", "CLI smoke test",
                    "--department", "Finance", "--scenario", "phishing_link",
                    "--at", scheduled, "--timezone", "Africa/Kampala",
                    "--created-by", "test-operator",
                ],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            self.assertIn("created and scheduled", created.stdout)

            campaigns = subprocess.run(
                base + ["campaigns"], cwd=ROOT,
                capture_output=True, text=True, check=True,
            )
            self.assertIn("CLI smoke test", campaigns.stdout)

            audit = subprocess.run(
                base + ["audit"], cwd=ROOT,
                capture_output=True, text=True, check=True,
            )
            self.assertIn("campaign.created", audit.stdout)



    def test_cli_and_dashboard_read_the_same_environment_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "shared-ecoshield.db")
            env = os.environ.copy()
            env["ECOSHIELD_DB_PATH"] = db_path
            env["ECOSHIELD_SECRET_KEY"] = "test-secret-key-that-is-long-enough-123"
            env["ECOSHIELD_ADMIN_EMAIL"] = "admin@example.test"
            env["ECOSHIELD_ADMIN_PASSWORD"] = "admin-password-long"
            env["ECOSHIELD_EMPLOYEE_EMAIL"] = "employee@example.test"
            env["ECOSHIELD_EMPLOYEE_PASSWORD"] = "employee-password-long"

            scheduled = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
            created = subprocess.run(
                [
                    sys.executable, CLI, "campaign-create",
                    "--name", "Shared database integration",
                    "--department", "Finance",
                    "--scenario", "phishing_link",
                    "--at", scheduled,
                    "--timezone", "Africa/Kampala",
                ],
                cwd=ROOT, env=env, capture_output=True, text=True, check=True,
            )
            self.assertIn("created and scheduled", created.stdout)

            dashboard_reader = (
                "from web_dashboard import get_db_connection; "
                "from assessment_engine import list_campaigns; "
                "conn = get_db_connection(); "
                "rows = list_campaigns(conn); "
                "print('|'.join(row['name'] for row in rows)); "
                "conn.close()"
            )
            read = subprocess.run(
                [sys.executable, "-c", dashboard_reader],
                cwd=ROOT, env=env, capture_output=True, text=True, check=True,
            )
            self.assertIn("Shared database integration", read.stdout)

if __name__ == "__main__":
    unittest.main()
