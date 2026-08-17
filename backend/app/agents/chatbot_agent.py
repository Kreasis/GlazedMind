"""Orchestrates conversation routing, retrieval, procedure assembly, and presentation."""
from app.agents.document_selector_agent import select
from app.agents.escalation_agent import exact_issue_reference, is_escalation_request, is_failed_troubleshooting_followup, resolve, resolve_failed_troubleshooting
from app.agents.helpdesk_writer import present
from app.agents.procedure_agent import assemble
from app.agents.procedure_scope import prepend_basic_checks

def answer(question: str, history: list[dict[str, str]] | None = None) -> dict[str, object]:
    history = history or []
    if is_failed_troubleshooting_followup(question, history):
        escalation = resolve_failed_troubleshooting(question, history)
        if escalation["mode"] == "escalation":
            return {
                **escalation,
                "answer": "Since the documented troubleshooting has been completed and the issue is still not resolved, the next step is to escalate it using the contact below.",
                "follow_up": "Include the store/FC number, affected device, actions already completed, and any remaining error message when contacting support.",
                "sections": [],
            }
        return {
            **escalation,
            "answer": str(escalation.get("answer", "Which system or device is still not working?")),
            "follow_up": "Once you confirm the affected system, I can provide the correct documented escalation contact.",
            "sections": [],
        }
    if is_escalation_request(question):
        escalation = resolve(question, history)
        if escalation["mode"] == "clarify":
            return {**escalation, "follow_up": "", "sections": []}
        return {
            **escalation,
            "answer": "I found the documented escalation reference that matches this system and issue.",
            "follow_up": "Use the documented details below and preserve any approval, CC, or support-hour instructions.",
            "sections": [],
        }
    plan = select(question, history)
    mode = str(plan.get("mode", "clarify"))
    language = str(plan.get("language", "en"))

    if mode == "chat":
        return {"mode": "chat", "answer": str(plan.get("reply", "")), "follow_up": "", "sections": [], "sources": []}
    if mode == "clarify":
        reference = exact_issue_reference(question)
        if reference:
            return {
                **reference,
                "answer": "I could not find a documented troubleshooting procedure for this issue. However, Point of Contacts for escalations contains an exact escalation reference for it, so I recommend contacting the team below.",
                "follow_up": "Use only the documented contact details shown below.",
                "sections": [],
            }
        return {
            "mode": "clarify",
            "answer": str(plan.get("clarification_question", "I need one more detail before choosing a procedure.")),
            "follow_up": "",
            "sections": [],
            "sources": [],
        }

    selected_titles = [str(title) for title in plan.get("selected_titles", [])]
    selected_titles = prepend_basic_checks(question, selected_titles)
    sections = assemble(selected_titles)
    if not sections:
        reference = exact_issue_reference(question)
        if reference:
            return {
                **reference,
                "answer": "I could not find a documented troubleshooting procedure for this issue. However, Point of Contacts for escalations contains an exact escalation reference for it, so I recommend contacting the team below.",
                "follow_up": "Use only the documented contact details shown below.",
                "sections": [],
            }
        message = (
            "Encontré una guía relacionada, pero no contiene pasos operativos que pueda presentar con seguridad. ¿Puedes darme más detalles?"
            if language == "es"
            else "I found a related guide, but it does not contain operational steps I can safely present. Could you provide more detail?"
        )
        return {"mode": "clarify", "answer": message, "follow_up": "", "sections": [], "sources": []}
    framing = present(language, sections)
    return {
        "mode": "support",
        **framing,
        "sections": sections,
        "sources": list(dict.fromkeys(str(section.get("source", section["title"])) for section in sections)),
    }
