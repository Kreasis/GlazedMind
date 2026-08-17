import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import auto_ack
from app.services.acknowledgment import create_acknowledgment


class AcknowledgmentAgentTests(unittest.TestCase):
    @patch("app.services.acknowledgment._custom_paragraph")
    def test_fixed_format_wraps_the_custom_ticket_paragraph(self, custom_paragraph) -> None:
        custom_paragraph.return_value = "We will begin working on adding the requested seasonal item to your NCR menu."
        message = create_acknowledgment({"ticket": "Menu request", "description": "Add a seasonal item"})
        self.assertTrue(message.startswith("Thank you for contacting Glazed Mind Help Desk."))
        self.assertIn("adding the requested seasonal item", message)
        self.assertTrue(message.endswith("Best regards,\nGlazed Mind Help Desk"))

    @patch("app.services.acknowledgment._custom_paragraph", side_effect=TimeoutError)
    def test_safe_fallback_is_used_when_ollama_is_unavailable(self, custom_paragraph) -> None:
        message = create_acknowledgment({"ticket": "Unclassified request"})
        self.assertIn("Unclassified request", message)
        self.assertNotIn("POS", message)

    @patch("app.services.acknowledgment._custom_paragraph", side_effect=ValueError("policy"))
    def test_fallback_remains_specific_to_price_change(self, custom_paragraph) -> None:
        message = create_acknowledgment({
            "ticket": "FC7777",
            "description": "I please update the price for my glazed donuts, from 1 to $3",
        })
        self.assertIn("update the price for your glazed donuts, from 1 to $3", message)
        self.assertNotIn("reviewing the details you provided", message)

    def test_legacy_completed_ids_migrate_without_reprocessing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "acknowledged_ticket_ids.json"
            state_path.write_text(json.dumps(["123", "456"]), encoding="utf-8")
            with patch.object(auto_ack, "_state_path", state_path):
                state = auto_ack._load_state()
            self.assertTrue(state["123"]["acknowledgment_posted"])
            self.assertTrue(state["123"]["status_updated"])

    def test_phase_state_is_saved_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "acknowledged_ticket_ids.json"
            state = {"123": {"acknowledgment_posted": True, "status_updated": False, "update_id": "999"}}
            with patch.object(auto_ack, "_state_path", state_path):
                auto_ack._save_state(state)
                loaded = auto_ack._load_state()
            self.assertEqual(loaded, state)

    def test_first_touch_can_only_be_claimed_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "acknowledged_ticket_ids.json"
            with patch.object(auto_ack, "_state_path", state_path):
                self.assertTrue(auto_ack.claim_first_touch("123"))
                self.assertFalse(auto_ack.claim_first_touch("123"))
                auto_ack.release_first_touch("123")
                self.assertTrue(auto_ack.claim_first_touch("123"))

    @patch("app.services.acknowledgment.urlopen")
    def test_native_ollama_response_is_parsed(self, urlopen_mock) -> None:
        response = urlopen_mock.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"message": {"content": json.dumps({"custom_paragraph": "We will begin working on setting up your new sticky printer for beverage labels."})}}).encode()
        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://ollama", "OLLAMA_API_KEY": "key"}):
            message = create_acknowledgment({"ticket": "Sticky printer", "description": "Set up for beverage labels"})
        self.assertIn("setting up your new sticky printer", message)
        request = urlopen_mock.call_args.args[0]
        sent = json.loads(request.data.decode())
        self.assertFalse(sent["think"])

    @patch("app.services.acknowledgment.urlopen")
    def test_natural_future_tense_variation_is_accepted(self, urlopen_mock) -> None:
        response = urlopen_mock.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"message": {"content": json.dumps({"custom_paragraph": "We will start working on updating the price of your glazed donuts from $1 to $3. Please stay tuned for the next steps."})}}).encode()
        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://ollama", "OLLAMA_API_KEY": "key"}):
            message = create_acknowledgment({"ticket": "FC7777", "description": "Update my glazed donuts from $1 to $3"})
        self.assertIn("updating the price of your glazed donuts", message)

    @patch("app.services.auto_ack._stop")
    @patch("app.services.auto_ack.change_ticket_status", side_effect=[RuntimeError("temporary status failure"), None])
    @patch("app.services.auto_ack.post_ticket_update", return_value="update-1")
    @patch("app.services.auto_ack.create_acknowledgment", return_value="message")
    @patch("app.services.auto_ack.fetch_tickets")
    def test_status_retry_does_not_post_a_second_acknowledgment(self, fetch_tickets, create_message, post_update, change_status, stop_event) -> None:
        ticket = {"id": "new-1", "status": "New Reply", "ticket": "Request", "description": "Details"}
        fetch_tickets.return_value = [ticket]
        stop_event.is_set.side_effect = [False, False, True]
        stop_event.wait.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "acknowledged_ticket_ids.json"
            state_path.write_text(json.dumps({"version": 2, "tickets": {}}), encoding="utf-8")
            with patch.object(auto_ack, "_state_path", state_path), patch.dict("os.environ", {"AUTO_ACK_INTERVAL_SECONDS": "10"}):
                auto_ack._poll()
        self.assertEqual(post_update.call_count, 1)
        self.assertEqual(change_status.call_count, 2)


if __name__ == "__main__":
    unittest.main()
