import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.agents.monday_followup_agent import create_followup, interval_days
from app.services import auto_followup


class FollowupAgentTests(unittest.TestCase):
    def test_priority_intervals(self) -> None:
        self.assertEqual(interval_days("Low Priority"), 3)
        self.assertEqual(interval_days("Medium Priority"), 2)
        self.assertEqual(interval_days("High Priority"), 1)

    def test_final_message_explains_resolution(self) -> None:
        message = create_followup({"description": "I need help with my cash drawer"}, 3)
        self.assertIn("third and final follow-up", message)
        self.assertIn("marking this ticket as resolved", message)
        self.assertIn("cash drawer", message)

    @patch("app.services.auto_followup.change_ticket_status")
    @patch("app.services.auto_followup.post_ticket_update", return_value="followup-update")
    @patch("app.services.auto_followup.fetch_ticket_context")
    def test_high_priority_followup_is_sent_after_one_day(self, fetch_context, post_update, change_status) -> None:
        fetch_context.return_value = {
            "viewer": {"id": "agent-1"},
            "tickets": [{
                "id": "ticket-1", "status": "Awaiting Customer", "priority": "High Priority",
                "description": "I need help with my cash drawer", "date": "2026-08-10",
                "updates": [{"id": "u1", "creator_id": "agent-1", "created_at": "2026-08-10T10:00:00Z"}],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "followup_state.json"
            state_path.write_text(json.dumps({"version": 1, "tickets": {"ticket-1": {
                "eligible": True, "followup_count": 0, "last_contact_at": "2026-08-10T10:00:00+00:00"
            }}}), encoding="utf-8")
            with patch.object(auto_followup, "_state_path", state_path):
                actions = auto_followup.process_once(datetime(2026, 8, 11, 10, 1, tzinfo=timezone.utc), initialize_baseline=False)
                state = json.loads(state_path.read_text(encoding="utf-8"))["tickets"]
        self.assertEqual(actions[0]["attempt"], 1)
        self.assertEqual(state["ticket-1"]["followup_count"], 1)
        post_update.assert_called_once()
        change_status.assert_not_called()

    @patch("app.services.auto_followup.change_ticket_status")
    @patch("app.services.auto_followup.post_ticket_update")
    @patch("app.services.auto_followup.fetch_ticket_context")
    def test_customer_reply_cancels_followups(self, fetch_context, post_update, change_status) -> None:
        fetch_context.return_value = {
            "viewer": {"id": "agent-1"},
            "tickets": [{
                "id": "ticket-2", "status": "Awaiting Customer", "priority": "High Priority",
                "updates": [
                    {"id": "agent", "creator_id": "agent-1", "created_at": "2026-08-10T10:00:00Z"},
                    {"id": "customer", "creator_id": "customer-1", "created_at": "2026-08-10T11:00:00Z"},
                ],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "followup_state.json"
            state_path.write_text(json.dumps({"version": 1, "tickets": {"ticket-2": {
                "eligible": True, "followup_count": 0, "last_contact_at": "2026-08-10T10:00:00+00:00"
            }}}), encoding="utf-8")
            with patch.object(auto_followup, "_state_path", state_path):
                actions = auto_followup.process_once(datetime(2026, 8, 12, tzinfo=timezone.utc), initialize_baseline=False)
        self.assertEqual(actions, [{"item_id": "ticket-2", "action": "customer_replied"}])
        post_update.assert_not_called()
        change_status.assert_not_called()

    @patch("app.services.auto_followup.change_ticket_status")
    @patch("app.services.auto_followup.post_ticket_update", return_value="final-update")
    @patch("app.services.auto_followup.fetch_ticket_context")
    def test_third_followup_resolves_ticket(self, fetch_context, post_update, change_status) -> None:
        fetch_context.return_value = {
            "viewer": {"id": "agent-1"},
            "tickets": [{
                "id": "ticket-3", "status": "Awaiting Customer", "priority": "Low Priority",
                "description": "Please confirm the replacement device", "updates": [],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "followup_state.json"
            state_path.write_text(json.dumps({"version": 1, "tickets": {"ticket-3": {
                "eligible": True, "followup_count": 2, "last_contact_at": "2026-08-01T00:00:00+00:00"
            }}}), encoding="utf-8")
            with patch.object(auto_followup, "_state_path", state_path):
                actions = auto_followup.process_once(datetime(2026, 8, 4, 0, 1, tzinfo=timezone.utc), initialize_baseline=False)
        self.assertEqual(actions[0]["action"], "resolved")
        self.assertEqual(actions[0]["attempt"], 3)
        change_status.assert_called_once_with("ticket-3", "Resolved")

    @patch("app.services.auto_followup.fetch_ticket_context")
    def test_first_live_pass_baselines_existing_tickets(self, fetch_context) -> None:
        fetch_context.return_value = {
            "viewer": {"id": "agent-1"},
            "tickets": [{"id": "old-ticket", "status": "Awaiting Customer", "updates": []}],
        }
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "followup_state.json"
            with patch.object(auto_followup, "_state_path", state_path):
                actions = auto_followup.process_once(datetime(2026, 8, 12, tzinfo=timezone.utc))
                state = json.loads(state_path.read_text(encoding="utf-8"))["tickets"]
        self.assertEqual(actions[0]["action"], "baseline_initialized")
        self.assertFalse(state["old-ticket"]["eligible"])

    def test_demo_mode_uses_priority_minutes(self) -> None:
        with patch.dict("os.environ", {"DEMO_MODE": "true", "AUTO_FOLLOWUP_TIME_UNIT": "minutes"}):
            self.assertEqual(auto_followup._due_delta("High Priority").total_seconds(), 60)
            self.assertEqual(auto_followup._due_delta("Medium Priority").total_seconds(), 120)
            self.assertEqual(auto_followup._due_delta("Low Priority").total_seconds(), 180)

    def test_minutes_are_rejected_outside_demo_mode(self) -> None:
        with patch.dict("os.environ", {"DEMO_MODE": "false", "AUTO_FOLLOWUP_TIME_UNIT": "minutes"}):
            self.assertEqual(auto_followup._due_delta("High Priority").total_seconds(), 86400)


if __name__ == "__main__":
    unittest.main()
