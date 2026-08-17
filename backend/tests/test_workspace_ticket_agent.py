import unittest
from unittest.mock import patch

from app.agents.procedure_scope import BASIC_DEVICE_CHECKS, MASTER_INSTALLATION
from app.agents.workspace_ticket_agent import _select_titles, troubleshoot


class WorkspaceTicketAgentTests(unittest.TestCase):
    def test_new_pos_without_install_verb_uses_complete_runbook(self) -> None:
        selected = _select_titles(
            "FC1562\nI need help with my new POS",
            [MASTER_INSTALLATION, "NCR - Registering a device for the POS"],
            [],
        )
        self.assertEqual(selected, [MASTER_INSTALLATION])

    @patch("app.agents.workspace_ticket_agent.assemble")
    @patch("app.agents.workspace_ticket_agent.retrieve")
    def test_workspace_returns_sections_without_chat_copy(self, retrieve, assemble) -> None:
        retrieve.return_value = {
            "catalog": [MASTER_INSTALLATION],
            "candidates": [],
        }
        assemble.return_value = [{"title": MASTER_INSTALLATION, "steps": ["Step A"], "step_images": [[]]}]
        result = troubleshoot("I need help with my new POS")
        self.assertEqual(result["mode"], "procedure")
        self.assertEqual(result["sources"], [MASTER_INSTALLATION])
        self.assertNotIn("answer", result)
        self.assertNotIn("follow_up", result)
        self.assertNotIn("contacts", result)

    @patch("app.agents.workspace_ticket_agent.assemble")
    @patch("app.agents.workspace_ticket_agent.retrieve")
    def test_existing_device_failure_keeps_basic_checks(self, retrieve, assemble) -> None:
        guide = "NCR - Configuring a cash drawer"
        retrieve.return_value = {
            "catalog": [BASIC_DEVICE_CHECKS, guide],
            "candidates": [{"source": guide, "score": 0.8, "title_coverage": 0.8}],
        }
        assemble.return_value = [
            {"title": BASIC_DEVICE_CHECKS, "steps": ["Check power"]},
            {"title": guide, "steps": ["Open settings"]},
        ]
        result = troubleshoot("My cash drawer is not working")
        assemble.assert_called_once_with([BASIC_DEVICE_CHECKS, guide])
        self.assertEqual(len(result["sections"]), 2)

    @patch("app.agents.workspace_ticket_agent.assemble", return_value=[])
    @patch("app.agents.workspace_ticket_agent.retrieve", return_value={"catalog": [], "candidates": []})
    def test_no_match_does_not_invent_steps(self, retrieve, assemble) -> None:
        result = troubleshoot("Unrecognized request")
        self.assertEqual(result, {"mode": "no_match", "sections": [], "sources": []})


if __name__ == "__main__":
    unittest.main()
