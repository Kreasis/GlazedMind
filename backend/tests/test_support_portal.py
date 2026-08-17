import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import monday, support_portal
from app.services.ticket_matching import same_support_topic


class SupportPortalTests(unittest.TestCase):
    def payload(self) -> dict[str, object]:
        return {
            "store_code": "FC8888",
            "customer_name": "Jamie Store",
            "customer_email": "jamie@example.com",
            "subject": "Cash drawer is not opening",
            "description": "The cash drawer stopped opening after the last transaction.",
            "request_type": "Issue",
            "priority": "High Priority",
        }

    def test_new_case_creates_and_acknowledges_one_monday_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "support_cases.json"
            with patch.object(support_portal, "_data_path", data_path), \
                 patch.object(support_portal, "fetch_tickets", return_value=[]), \
                 patch.object(support_portal, "claim_first_touch", return_value=True), \
                 patch.object(support_portal, "create_support_ticket", return_value={"id": "100", "ticket": "FC8888 - Cash drawer", **self.payload()}) as create_ticket, \
                 patch.object(support_portal, "create_acknowledgment", return_value="Personalized acknowledgment"), \
                 patch.object(support_portal, "post_ticket_update", return_value="update-1") as post_update, \
                 patch.object(support_portal, "change_ticket_status") as change_status, \
                 patch.object(support_portal, "record_handled_ticket"), \
                 patch.object(support_portal, "append_activity"):
                result = support_portal.create_case(self.payload())
            self.assertEqual(result["monday_item_id"], "100")
            self.assertEqual(result["status"], "In Progress")
            self.assertEqual([message["role"] for message in result["messages"]], ["customer", "agent"])
            self.assertTrue(result["access_token"])
            create_ticket.assert_called_once()
            post_update.assert_called_once_with("100", "Personalized acknowledgment")
            change_status.assert_called_once_with("100", "In Progress")

    def test_customer_reply_reuses_case_and_monday_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "support_cases.json"
            with patch.object(support_portal, "_data_path", data_path), \
                 patch.object(support_portal, "fetch_tickets", return_value=[]), \
                 patch.object(support_portal, "claim_first_touch", return_value=True), \
                 patch.object(support_portal, "create_support_ticket", return_value={"id": "100", "ticket": "FC8888 - Cash drawer", **self.payload()}) as create_ticket, \
                 patch.object(support_portal, "create_acknowledgment", return_value="Acknowledgment"), \
                 patch.object(support_portal, "post_ticket_update", side_effect=["update-1", "update-2"]) as post_update, \
                 patch.object(support_portal, "change_ticket_status") as change_status, \
                 patch.object(support_portal, "record_handled_ticket"), \
                 patch.object(support_portal, "append_activity"):
                created = support_portal.create_case(self.payload())
                result = support_portal.add_customer_message(created["id"], created["access_token"], "I also restarted the POS.")
            self.assertEqual(result["monday_item_id"], "100")
            self.assertEqual(result["status"], "New Reply")
            self.assertEqual(len(result["messages"]), 3)
            create_ticket.assert_called_once()
            self.assertEqual(post_update.call_count, 2)
            self.assertEqual(change_status.call_args_list[-1].args, ("100", "New Reply"))

    def test_status_retry_does_not_duplicate_portal_acknowledgment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "support_cases.json"
            with patch.object(support_portal, "_data_path", data_path), \
                 patch.object(support_portal, "fetch_tickets", return_value=[]), \
                 patch.object(support_portal, "claim_first_touch", return_value=True), \
                 patch.object(support_portal, "create_support_ticket", return_value={"id": "100", "ticket": "FC8888 - Cash drawer", **self.payload()}), \
                 patch.object(support_portal, "create_acknowledgment", return_value="Acknowledgment"), \
                 patch.object(support_portal, "post_ticket_update", return_value="update-1"), \
                 patch.object(support_portal, "change_ticket_status", side_effect=RuntimeError("retry later")), \
                 patch.object(support_portal, "record_handled_ticket"), \
                 patch.object(support_portal, "append_activity"):
                result = support_portal.create_case(self.payload())
            replies = [message for message in result["messages"] if message["role"] == "agent"]
            self.assertEqual(len(replies), 1)
            self.assertEqual(result["automation_status"], "pending")

    def test_monday_updates_are_added_once_to_the_web_conversation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "support_cases.json"
            with patch.object(support_portal, "_data_path", data_path), \
                 patch.object(support_portal, "fetch_tickets", return_value=[]), \
                 patch.object(support_portal, "claim_first_touch", return_value=True), \
                 patch.object(support_portal, "create_support_ticket", return_value={"id": "100", "ticket": "FC8888 - Cash drawer", **self.payload()}), \
                 patch.object(support_portal, "create_acknowledgment", return_value="Acknowledgment"), \
                 patch.object(support_portal, "post_ticket_update", return_value="update-1"), \
                 patch.object(support_portal, "change_ticket_status"), \
                 patch.object(support_portal, "record_handled_ticket"), \
                 patch.object(support_portal, "append_activity"), \
                 patch.object(support_portal, "fetch_ticket_updates", return_value={"viewer": {}, "updates": [{"id": "agent-2", "body": "<p>Please check the power cable.</p>", "created_at": "2026-08-14T12:00:00Z"}]}), \
                 patch.object(support_portal, "fetch_board", return_value={"items": [{"id": "100", "status": "Awaiting Customer"}]}):
                created = support_portal.create_case(self.payload())
                first = support_portal.get_case(created["id"], created["access_token"])
                second = support_portal.get_case(created["id"], created["access_token"])
            replies = [message for message in second["messages"] if message["content"] == "Please check the power cable."]
            self.assertEqual(len(replies), 1)
            self.assertEqual(first["status"], "Awaiting Customer")

    def test_same_store_and_same_intent_links_existing_ticket(self) -> None:
        existing = {
            "id": "existing-1989", "store_code": "FC1989", "status": "In Progress",
            "ticket": "FC1989", "description": "I need to install my new POS",
        }
        payload = {
            **self.payload(), "store_code": "FC1989",
            "subject": "I've got a new POS and I need to install it",
            "description": "I've got a new POS and I need to install it",
        }
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "support_cases.json"
            with patch.object(support_portal, "_data_path", data_path), \
                 patch.object(support_portal, "fetch_tickets", return_value=[existing]), \
                 patch.object(support_portal, "create_support_ticket") as create_ticket, \
                 patch.object(support_portal, "post_ticket_update", return_value="linked-update") as post_update, \
                 patch.object(support_portal, "change_ticket_status") as change_status, \
                 patch.object(support_portal, "append_activity"):
                result = support_portal.create_case(payload)
        self.assertEqual(result["monday_item_id"], "existing-1989")
        self.assertTrue(result["matched_existing"])
        self.assertEqual(result["automation_status"], "linked")
        create_ticket.assert_not_called()
        post_update.assert_called_once()
        change_status.assert_not_called()

    def test_different_work_for_same_store_is_not_a_topic_match(self) -> None:
        self.assertFalse(same_support_topic(
            "I need to install my new POS",
            "Please update the price of glazed donuts from $1 to $3",
        ))


class MondaySupportTicketTests(unittest.TestCase):
    def test_create_support_ticket_maps_visible_board_columns(self) -> None:
        board = {
            "groups": [{"id": "open", "title": "Open Tickets"}],
            "columns": [
                {"id": "status", "title": "Status"}, {"id": "priority", "title": "Priority"},
                {"id": "type", "title": "Request Type"}, {"id": "person", "title": "Requestor Name"},
                {"id": "email", "title": "Email"}, {"id": "number", "title": "Ticket Number"},
                {"id": "description", "title": "Description"}, {"id": "date", "title": "Date"},
            ],
            "items": [],
        }
        captured: dict[str, object] = {}

        def request(_query: str, variables: dict[str, object]) -> dict[str, object]:
            captured.update(variables)
            return {"data": {"create_item": {"id": "100", "name": "FC8888 - Drawer"}}}

        with patch.object(monday, "_config", return_value=("token", "board", "url")), \
             patch.object(monday, "fetch_board", return_value=board), \
             patch.object(monday, "_request", side_effect=request):
            result = monday.create_support_ticket({
                "store_code": "FC8888", "subject": "Drawer", "description": "Not opening",
                "customer_name": "Jamie", "customer_email": "jamie@example.com",
                "priority": "High Priority", "request_type": "Issue",
            })
        values = json.loads(str(captured["columnValues"]))
        self.assertEqual(result["id"], "100")
        self.assertEqual(captured["groupId"], "open")
        self.assertEqual(values["status"], {"label": "New Reply"})
        self.assertEqual(values["number"], "FC8888")
        self.assertEqual(values["email"], "jamie@example.com")


if __name__ == "__main__":
    unittest.main()
