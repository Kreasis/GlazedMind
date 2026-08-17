import unittest
from unittest.mock import patch

from app.agents.chatbot_agent import answer
from app.agents.conversation_router_agent import _contextual_follow_up, _explicit_procedure_intent, _history_choice, route
from app.agents.procedure_agent import assemble
from app.agents.escalation_agent import exact_issue_reference, is_escalation_request, is_failed_troubleshooting_followup, resolve
from app.agents.procedure_scope import BASIC_DEVICE_CHECKS, MASTER_INSTALLATION, metadata_for, prepend_basic_checks, resolve_scope, should_prepend_basic_checks
from app.agents.knowledge_retriever import _terms as retrieval_terms


class ChatbotPipelineTests(unittest.TestCase):
    def test_dynamic_camelcase_document_title_is_searchable(self) -> None:
        terms = retrieval_terms("HandlingRefunds&Voids")
        self.assertIn("refund", terms)
        self.assertIn("void", terms)

    def test_dynamic_uploaded_document_can_be_selected_without_static_metadata(self) -> None:
        candidates = [
            {"source": "HandlingRefunds&Voids", "score": 0.66, "title_coverage": 0.5},
            {"source": "Point of Contacts for escalations", "score": 0.34, "title_coverage": 0.0},
        ]
        result = route("how do I refund an order", [], [item["source"] for item in candidates], candidates)
        self.assertEqual(result["mode"], "support")
        self.assertEqual(result["selected_titles"], ["HandlingRefunds&Voids"])

    def test_refund_wording_selects_dynamic_document_below_old_chatbot_threshold(self) -> None:
        candidates = [
            {"source": "HandlingRefunds&Voids", "score": 0.5277, "title_coverage": 0.5, "content_coverage": 0.5, "vector_score": 0.6848},
            {"source": "General Device Troubleshooting - Basic Checks", "score": 0.2066, "title_coverage": 0.0, "content_coverage": 0.5, "vector_score": 0.4775},
        ]
        result = route("how do I perform a refund", [], [item["source"] for item in candidates], candidates)
        self.assertEqual(result["mode"], "support")
        self.assertEqual(result["selected_titles"], ["HandlingRefunds&Voids"])

    def test_basic_conversation_does_not_select_documents(self) -> None:
        result = route("hola", [], ["NCR - Price change"], [])
        self.assertEqual(result["mode"], "chat")
        self.assertEqual(result["selected_titles"], [])

    def test_numeric_reply_selects_a_document_from_prior_clarification(self) -> None:
        catalog = ["Kitchen Printer", "Receipt Printer"]
        history = [{"role": "assistant", "content": "1. Kitchen Printer\n2. Receipt Printer"}]
        self.assertEqual(_history_choice("2", history, catalog), ["Receipt Printer"])

    def test_new_pos_setup_selects_complete_installation(self) -> None:
        catalog = ["NCR - Registering a device for the POS", "NCR - POS complete, installation process"]
        self.assertEqual(_explicit_procedure_intent("how do I setup a new POS", catalog), ["NCR - POS complete, installation process"])

    def test_difference_follow_up_explains_the_previous_options(self) -> None:
        catalog = ["NCR - Registering a device for the POS", "NCR - POS complete, installation process"]
        history = [{"role": "assistant", "content": "1. NCR - Registering a device for the POS\n2. NCR - POS complete, installation process"}]
        result = _contextual_follow_up("cual es la diferencia", history, catalog)
        self.assertEqual(result["mode"], "clarify")
        self.assertIn("new POS", result["clarification_question"])

    def test_ncr_follow_up_does_not_start_an_unrelated_search(self) -> None:
        catalog = ["NCR - Registering a device for the POS", "NCR - POS complete, installation process"]
        history = [
            {"role": "user", "content": "cual es la diferencia"},
            {"role": "assistant", "content": "1. NCR - Registering a device for the POS\n2. NCR - POS complete, installation process"},
        ]
        result = _contextual_follow_up("ncr", history, catalog)
        self.assertEqual(result["mode"], "clarify")
        self.assertIn("Both options are for NCR", result["clarification_question"])

    def test_spanish_input_still_produces_english_output(self) -> None:
        result = route("hola", [], ["NCR - Price change"], [])
        self.assertEqual(result["language"], "en")
        self.assertTrue(result["reply"].startswith("Hello!"))

    def test_new_pos_uses_master_runbook(self) -> None:
        catalog = [MASTER_INSTALLATION, "NCR - Configuring a cash drawer"]
        result = resolve_scope("How do I set up a new POS?", catalog)
        self.assertEqual(result["title"], MASTER_INSTALLATION)
        self.assertEqual(result["scope"], "complete_installation")

    def test_isolated_component_uses_standalone_guide(self) -> None:
        catalog = [MASTER_INSTALLATION, "NCR - Configuring a cash drawer"]
        result = resolve_scope("How do I configure a cash drawer?", catalog)
        self.assertEqual(result["title"], "NCR - Configuring a cash drawer")
        self.assertEqual(result["scope"], "isolated_task")

    def test_update_price_selects_price_change_guide(self) -> None:
        catalog = [MASTER_INSTALLATION, "NCR - Price change"]
        result = resolve_scope("I would like to update the price from 12 to 15", catalog)
        self.assertEqual(result["title"], "NCR - Price change")

    def test_generic_pos_setup_requires_scope_clarification(self) -> None:
        result = resolve_scope("I need help with a POS setup", [MASTER_INSTALLATION])
        self.assertEqual(result["decision"], "clarify")

    def test_master_metadata_is_exposed(self) -> None:
        self.assertEqual(metadata_for(MASTER_INSTALLATION)["document_type"], "master")

    def test_basic_checks_precede_a_device_malfunction(self) -> None:
        question = "The receipt printer is not printing and appears offline"
        selected = ["NCR - Configuring the receipt printer"]
        self.assertTrue(should_prepend_basic_checks(question))
        self.assertEqual(prepend_basic_checks(question, selected), [BASIC_DEVICE_CHECKS, *selected])

    def test_basic_checks_do_not_precede_planned_work(self) -> None:
        excluded = [
            "Install a new POS",
            "Configure the kitchen printer",
            "Change a menu price",
            "Reset the NCR password",
            "How do I handle an NCR double charge?",
        ]
        for question in excluded:
            with self.subTest(question=question):
                self.assertFalse(should_prepend_basic_checks(question))

    def test_basic_checks_are_not_duplicated(self) -> None:
        selected = [BASIC_DEVICE_CHECKS, "NCR - Configuring the receipt printer"]
        self.assertEqual(prepend_basic_checks("The receipt printer is not working", selected), selected)

    def test_generic_pos_failure_selects_basic_checks_without_clarification(self) -> None:
        catalog = [BASIC_DEVICE_CHECKS, MASTER_INSTALLATION]
        result = resolve_scope("Hey! Customer called, his POS is not working", catalog)
        self.assertEqual(result["decision"], "select")
        self.assertEqual(result["title"], BASIC_DEVICE_CHECKS)

    def test_double_charge_uses_only_double_charge_contact(self) -> None:
        result = resolve("escalate a double charge in NCR", [])
        self.assertEqual(result["mode"], "escalation")
        self.assertEqual(result["contacts"][0]["name"], "Double Charges NCR")
        details = " ".join(result["contacts"][0]["details"])
        self.assertIn("voyixpay.support@ncrvoyix.com", details)
        self.assertNotIn("assist.payments@ncrvoyix.com", details)

    def test_generic_escalation_without_system_asks_for_clarification(self) -> None:
        result = resolve("I need to escalate this", [])
        self.assertEqual(result["mode"], "clarify")
        self.assertEqual(result["contacts"], [])

    def test_customer_called_is_not_an_escalation_request(self) -> None:
        self.assertFalse(is_escalation_request("Hey! Customer called, his POS is not working"))

    def test_explicit_call_request_is_still_an_escalation_request(self) -> None:
        self.assertTrue(is_escalation_request("Who should I call for NCR support?"))

    def test_failed_steps_followup_uses_prior_pos_context_for_escalation(self) -> None:
        history = [
            {"role": "user", "content": "Hey! Customer called, his POS is not working"},
            {"role": "assistant", "content": "I found the verified troubleshooting procedure. Below are all 4 steps from the guide."},
        ]
        question = "I did all the steps, still not working, what can I do?"
        self.assertTrue(is_failed_troubleshooting_followup(question, history))
        result = answer(question, history)
        self.assertEqual(result["mode"], "escalation")
        self.assertEqual(result["contacts"][0]["name"], "NCR Aloha Cloud Support (POS)")
        self.assertIn("documented troubleshooting has been completed", result["answer"])

    def test_successful_steps_do_not_trigger_escalation(self) -> None:
        history = [{"role": "assistant", "content": "Follow these troubleshooting steps."}]
        self.assertFalse(is_failed_troubleshooting_followup("I did all the steps and it is working now", history))

    def test_blocked_procedure_step_triggers_escalation(self) -> None:
        history = [
            {"role": "user", "content": "How do I configure the receipt printer?"},
            {"role": "assistant", "content": "Follow these troubleshooting steps.\nProcedures used: NCR - Configuring the receipt printer"},
        ]
        result = answer("I am stuck on step 4 and cannot complete it", history)
        self.assertEqual(result["mode"], "escalation")
        self.assertEqual(result["contacts"][0]["name"], "NCR Aloha Cloud Support (POS)")

    def test_sticky_printer_failure_returns_both_relevant_contacts(self) -> None:
        history = [
            {"role": "user", "content": "How do I configure a sticky printer?"},
            {"role": "assistant", "content": "Follow these steps.\nProcedures used: Setting up a Sticky Printer"},
        ]
        result = answer("I followed all the steps but it is still not working", history)
        self.assertEqual(result["mode"], "escalation")
        self.assertEqual(
            [contact["name"] for contact in result["contacts"]],
            ["Scale Computing Support", "NCR Aloha Cloud Support (POS)"],
        )

    def test_failure_without_prior_troubleshooting_does_not_auto_escalate(self) -> None:
        self.assertFalse(is_failed_troubleshooting_followup("It is still not working", []))

    def test_vendor_support_question_enters_escalation_flow(self) -> None:
        self.assertTrue(is_escalation_request("who handles a DoorDash customer refund?"))
        result = resolve("who handles a DoorDash customer refund?", [])
        self.assertEqual(result["contacts"][0]["name"], "DoorDash")
        self.assertIn("mxpsupport@doordash.com", " ".join(result["contacts"][0]["details"]))

    def test_double_charge_issue_has_exact_reference_without_contact_word(self) -> None:
        result = exact_issue_reference("I need to know how to handle a double charge in NCR")
        self.assertIsNotNone(result)
        self.assertEqual(result["contacts"][0]["name"], "Double Charges NCR")

    @patch("app.agents.procedure_agent.document_step_records")
    @patch("app.agents.procedure_agent.document_by_title")
    def test_procedure_preserves_order_and_duplicate_steps(self, document_by_title, document_step_records) -> None:
        document_by_title.return_value = {"title": "Test Procedure"}
        document_step_records.return_value = [
            {"text": "Tap NEXT.", "images": ["guide/1.png"]},
            {"text": "Configure the device.", "images": []},
            {"text": "Tap NEXT.", "images": ["guide/2.png"]},
        ]
        sections = assemble(["Test Procedure"])
        self.assertEqual(sections[0]["steps"], ["Tap NEXT.", "Configure the device.", "Tap NEXT."])
        self.assertEqual(sections[0]["step_images"], [["guide/1.png"], [], ["guide/2.png"]])

    @patch("app.agents.chatbot_agent.assemble")
    @patch("app.agents.chatbot_agent.select")
    def test_support_response_uses_only_validated_sections(self, select, assemble) -> None:
        select.return_value = {"mode": "support", "language": "en", "selected_titles": ["Correct Guide"]}
        assemble.return_value = [{"title": "Correct Guide", "steps": ["Step A", "Step B"]}]
        result = answer("help", [])
        self.assertEqual(result["sources"], ["Correct Guide"])
        self.assertEqual(result["sections"][0]["steps"], ["Step A", "Step B"])

    @patch("app.agents.chatbot_agent.assemble")
    @patch("app.agents.chatbot_agent.select")
    def test_support_response_assembles_basic_checks_before_specific_guide(self, select, assemble) -> None:
        select.return_value = {"mode": "support", "language": "en", "selected_titles": ["NCR - Configuring the receipt printer"]}
        assemble.return_value = [
            {"title": BASIC_DEVICE_CHECKS, "steps": ["Check power"]},
            {"title": "NCR - Configuring the receipt printer", "steps": ["Open settings"]},
        ]
        answer("The receipt printer is not working", [])
        assemble.assert_called_once_with([BASIC_DEVICE_CHECKS, "NCR - Configuring the receipt printer"])

    @patch("app.agents.chatbot_agent.select")
    def test_clarification_has_no_sources(self, select) -> None:
        select.return_value = {"mode": "clarify", "language": "en", "clarification_question": "Which printer?"}
        result = answer("printer issue", [])
        self.assertEqual(result["answer"], "Which printer?")
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
