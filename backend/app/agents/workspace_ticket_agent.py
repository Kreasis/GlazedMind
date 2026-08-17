"""Read-only Workspace agent: ticket context in, documented procedure sections out."""
import re
import unicodedata

from app.agents.knowledge_retriever import confident_title, retrieve
from app.agents.procedure_agent import assemble
from app.agents.procedure_scope import MASTER_INSTALLATION, prepend_basic_checks, resolve_scope


def _terms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    return set(re.findall(r"[a-z0-9]+", normalized))


def _select_titles(ticket_context: str, catalog: list[str], candidates: list[dict[str, object]]) -> list[str]:
    """Select a procedure without conversation, clarification, or escalation."""
    terms = _terms(ticket_context)

    # Monday tickets are complete work items, not open-ended chat turns. A
    # request mentioning a new/replacement POS means the complete installation
    # runbook even when the customer does not use the verb "install".
    if "pos" in terms and terms & {"new", "replacement", "replacemente"} and MASTER_INSTALLATION in catalog:
        return [MASTER_INSTALLATION]

    scoped = resolve_scope(ticket_context, catalog)
    if scoped and scoped.get("decision") == "select":
        return [str(scoped["title"])]

    # Use the same dynamic confidence decision as Chatbot. Workspace never
    # asks follow-up questions, but it must select the same dominant document.
    dynamic_title = confident_title(candidates)
    if dynamic_title:
        return [dynamic_title]
    return []


def troubleshoot(ticket_context: str) -> dict[str, object]:
    retrieved = retrieve(ticket_context)
    catalog = [str(title) for title in retrieved.get("catalog", [])]
    candidates = list(retrieved.get("candidates", []))
    selected = _select_titles(ticket_context, catalog, candidates)
    selected = prepend_basic_checks(ticket_context, selected, catalog)
    sections = assemble(selected)
    return {
        "mode": "procedure" if sections else "no_match",
        "sections": sections,
        "sources": list(dict.fromkeys(str(section.get("source", section["title"])) for section in sections)),
    }
