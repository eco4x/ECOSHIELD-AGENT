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


if __name__ == "__main__":
    unittest.main()
