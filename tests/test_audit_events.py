"""Tests for structured audit-event storage."""
import json
import sqlite3
import unittest

from audit_events import initialize_audit_schema, list_audit_events, record_audit_event


class AuditEventTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        initialize_audit_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_records_structured_event_without_raw_secrets(self):
        record_audit_event(
            self.conn,
            actor_role="admin",
            action="campaign.created",
            target_type="campaign",
            target_ref="12",
            metadata={"department": "Finance", "scenario": "phishing_link"},
        )
        self.conn.commit()
        event = list_audit_events(self.conn)[0]
        self.assertEqual(event["action"], "campaign.created")
        self.assertEqual(event["target_ref"], "12")
        self.assertEqual(json.loads(event["metadata_json"])["department"], "Finance")
        self.assertNotIn("password", event["metadata_json"].lower())

    def test_rejects_missing_required_fields_and_oversized_metadata(self):
        with self.assertRaises(ValueError):
            record_audit_event(self.conn, actor_role="", action="test")
        with self.assertRaises(ValueError):
            record_audit_event(
                self.conn, actor_role="admin", action="test",
                metadata={"note": "x" * 2100},
            )

    def test_audit_listing_caps_limit(self):
        for index in range(3):
            record_audit_event(self.conn, actor_role="admin", action=f"event.{index}")
        self.conn.commit()
        self.assertEqual(len(list_audit_events(self.conn, 2)), 2)


if __name__ == "__main__":
    unittest.main()
