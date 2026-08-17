"""Routes escalation requests to exact entries in Point of Contacts for escalations."""
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from docx import Document

SOURCE_TITLE = "Point of Contacts for escalations"
CONTACTS_PATH = Path(__file__).resolve().parents[2] / "knowledge-base" / f"{SOURCE_TITLE}.docx"

# Routing metadata only. Contact details remain in the DOCX and are extracted at runtime.
ROUTES = [
    {"name": "NCR Aloha Cloud Support (POS)", "start": "NCR Aloha Cloud Support (POS)", "end": "Payments Assist", "terms": {"ncr", "aloha", "pos", "terminal", "point of sale"}},
    {"name": "Payments Assist (Credit Card Processor)", "start": "Payments Assist", "end": "Connected Payments", "terms": {"payments assist", "credit card processor", "payment processor", "processor", "procesador", "payment", "payments", "pago", "pagos", "tarjetas"}},
    {"name": "Connected Payments", "start": "Connected Payments", "end": "For Credit Card Reader Registration", "terms": {"connected payments"}},
    {"name": "Credit Card Reader Registration", "start": "For Credit Card Reader Registration", "end": "PCI Compliance", "terms": {"credit card reader registration", "card reader registration", "reader registration", "registro lector", "registrar lector"}},
    {"name": "PCI Compliance Contact (NCR)", "start": "PCI Compliance Contact", "end": "Double Charges", "terms": {"pci", "pci compliance", "compliance"}},
    {"name": "Double Charges NCR", "start": "Double Charges NCR", "end": "Escalate NCR", "terms": {"double charges", "double charge", "duplicate charge", "charged twice", "cargo doble", "cobro doble"}},
    {"name": "NCR Escalation", "start": "Escalate NCR", "end": "OLO HELP", "terms": {"ncr escalation", "escalate ncr", "silver escalate", "escalar ncr"}},
    {"name": "OLO Help / Menu Related", "start": "OLO HELP", "end": "Scale Computing Support", "terms": {"olo", "olo menu", "menu related"}},
    {"name": "Scale Computing Support", "start": "Scale Computing Support", "end": "SageNet Support", "terms": {"scale", "network", "firewall", "internet", "red"}},
    {"name": "SageNet Digital Signage Support", "start": "SageNet Support", "end": "DTiQ Drive Thru Support", "terms": {"sagenet", "digital menu board", "digital signage", "front screen", "monitor", "content management", "menu board"}},
    {"name": "SageNet Menu Update", "start": "SageNet Support", "end": "DTiQ Drive Thru Support", "terms": {"sagenet menu update", "digital menu update", "menu board update"}, "include_only": {"Menu update"}},
    {"name": "DTiQ Headsets Support", "start": "DTiQ Drive Thru Support", "end": "UBER Help", "terms": {"dtiq", "headset", "headsets", "drive thru headset", "auriculares"}, "include_only": {"Headsets", "drivethrusupport"}},
    {"name": "DTiQ Camera / Surveillance Support", "start": "DTiQ Drive Thru Support", "end": "UBER Help", "terms": {"camera", "cameras", "surveillance", "360"}, "include_only": {"Cameras", "360", "Surveillance", "Support@dtiq"}},
    {"name": "DTiQ Timer Reporting", "start": "DTiQ Drive Thru Support", "end": "UBER Help", "terms": {"timer", "timer reporting", "panorama"}, "include_only": {"panoramasupport", "Timer Reporting"}},
    {"name": "Uber Help", "start": "UBER Help", "end": "Synergy Suite Support", "terms": {"uber", "uber help", "uber merchant"}},
    {"name": "SynergySuite Support", "start": "Synergy Suite Support", "end": "Supplychain Bakemark", "terms": {"synergy", "synergy suite", "synergysuite"}},
    {"name": "Supply Chain / Bakemark", "start": "Supplychain Bakemark", "end": "3PT Refunds", "terms": {"bakemark", "supplychain", "supply chain", "incomplete order", "delete order", "borrar orden", "orden incompleta"}},
    {"name": "3PT Refunds - Uber", "start": "3PT Refunds", "end": "Doordash", "terms": {"3pt refund", "3pt refunds", "third party refund", "uber refund"}},
    {"name": "DoorDash", "start": "Doordash", "end": "Saivory", "terms": {"doordash", "door dash", "cancelled order refund", "customer refund"}},
    {"name": "Saivory Website", "start": "Saivory will be in charge", "end": "CLUTCH", "terms": {"saivory", "saivory website"}},
    {"name": "Clutch Website", "start": "CLUTCH (website)", "end": "PAYTRONIX", "terms": {"clutch", "clutch website"}},
    {"name": "Paytronix App Support", "start": "PAYTRONIX (app issues)", "end": None, "terms": {"paytronix", "app", "app issue", "app issues", "discount", "discounts", "redeem rewards", "rewards"}},
]

ESCALATION_TERMS = {"escalate", "escalation", "escalar", "escalacion", "contact", "contacto", "email", "correo", "phone", "telefono", "call", "llamar", "vendor support", "a quien", "who handles", "who supports", "quien maneja", "quien atiende"}
COMPLETED_TROUBLESHOOTING_PHRASES = {
    "did all the steps", "completed all the steps", "followed all the steps",
    "tried all the steps", "finished the steps", "did everything",
    "tried everything", "completed the troubleshooting",
}
ISSUE_PERSISTS_PHRASES = {
    "still not working", "still doesnt work", "still does not work",
    "did not fix", "didnt fix", "issue persists", "problem persists",
    "same issue", "same problem", "nothing changed", "continues to fail",
    "did not work", "didnt work", "not resolved", "unresolved",
    "could not complete", "couldnt complete", "cannot complete",
    "cant complete", "unable to complete", "step failed", "step does not work",
    "step doesnt work", "stuck on", "blocked at", "error at", "failed at",
}

def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")

def _contains_term(normalized: str, term: str) -> bool:
    """Match complete words/phrases so `call` does not match `called`."""
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return re.search(pattern, normalized) is not None

def is_escalation_request(question: str) -> bool:
    normalized = _normalize(question)
    vendor_terms = {"olo", "scale", "sagenet", "dtiq", "uber", "synergy", "bakemark", "doordash", "door dash", "saivory", "clutch", "paytronix"}
    vendor_reference = any(_contains_term(normalized, term) for term in vendor_terms)
    support_context = any(_contains_term(normalized, term) for term in {"support", "help", "refund", "issue", "problem", "contact", "phone", "email", "handles"})
    return any(_contains_term(normalized, term) for term in ESCALATION_TERMS) or (vendor_reference and support_context)

def is_failed_troubleshooting_followup(question: str, history: list[dict[str, str]]) -> bool:
    """Detect a failed result only when a troubleshooting exchange precedes it."""
    normalized = _normalize(question)
    completed = any(phrase in normalized for phrase in COMPLETED_TROUBLESHOOTING_PHRASES)
    persists = any(phrase in normalized for phrase in ISSUE_PERSISTS_PHRASES)
    if not persists:
        return False
    assistant_context = " ".join(
        _normalize(item.get("content", ""))
        for item in history[-6:]
        if item.get("role") == "assistant"
    )
    prior_procedure = any(term in assistant_context for term in {"procedure", "troubleshooting", "steps", "guide"})
    return completed or prior_procedure

def resolve_failed_troubleshooting(question: str, history: list[dict[str, str]]) -> dict[str, object]:
    """Resolve escalation using the original issue retained in conversation history."""
    conversation_context = " ".join(item.get("content", "") for item in history[-10:])
    normalized = _normalize(f"{conversation_context} {question}")
    route_names: list[str] = []

    def add_route(name: str) -> None:
        if name not in route_names:
            route_names.append(name)

    # Specific workflows take precedence over their broader platform.
    if any(term in normalized for term in {"double charge", "double charges", "charged twice", "duplicate charge"}):
        add_route("Double Charges NCR")
    elif any(term in normalized for term in {"credit processor", "payment processor", "payments assist"}):
        add_route("Payments Assist (Credit Card Processor)")
    elif any(term in normalized for term in {"card reader registration", "credit card reader registration"}):
        add_route("Credit Card Reader Registration")

    if "sticky printer" in normalized:
        # This procedure crosses Scale whitelisting and NCR configuration.
        add_route("Scale Computing Support")
        add_route("NCR Aloha Cloud Support (POS)")
    if any(term in normalized for term in {"scale", "network", "firewall", "internet"}):
        add_route("Scale Computing Support")
    if any(term in normalized for term in {"olo", "online ordering", "menu related"}):
        add_route("OLO Help / Menu Related")
    if any(term in normalized for term in {"dtiq", "headset", "drive thru headset"}):
        add_route("DTiQ Headsets Support")
    if any(term in normalized for term in {"camera", "surveillance"}):
        add_route("DTiQ Camera / Surveillance Support")
    if any(term in normalized for term in {"doordash", "door dash"}):
        add_route("DoorDash")
    if any(term in normalized for term in {"ncr", "aloha", "pos", "receipt printer", "kitchen printer", "cash drawer", "kds", "boh terminal"}):
        add_route("NCR Aloha Cloud Support (POS)")

    if route_names:
        contacts = [_entry(next(route for route in ROUTES if route["name"] == name)) for name in route_names]
        return {"mode": "escalation", "contacts": contacts, "sources": [SOURCE_TITLE]}

    prior_user_context = " ".join(item.get("content", "") for item in history[-8:] if item.get("role") == "user")
    return resolve(f"{prior_user_context} {question}".strip(), history)

def exact_issue_reference(question: str) -> dict[str, object] | None:
    """Return a contact only when the issue itself identifies one unambiguous route."""
    normalized = _normalize(question)
    matches: list[tuple[int, dict[str, object]]] = []
    for route in ROUTES:
        distinctive = [term for term in route["terms"] if " " in term and term in normalized]
        if distinctive:
            matches.append((max(len(term) for term in distinctive), route))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return None
    return {"mode": "escalation", "contacts": [_entry(matches[0][1])], "sources": [SOURCE_TITLE]}

@lru_cache(maxsize=1)
def _lines() -> list[str]:
    if not CONTACTS_PATH.exists():
        return []
    lines: list[str] = []
    for paragraph in Document(CONTACTS_PATH).paragraphs:
        lines.extend(line.strip() for line in paragraph.text.splitlines() if line.strip())
    return lines

def _entry(route: dict[str, object]) -> dict[str, object]:
    lines = _lines()
    start_text = str(route["start"]).lower()
    end_text = str(route.get("end") or "").lower()
    start = next((index for index, line in enumerate(lines) if start_text in line.lower()), -1)
    if start < 0:
        return {"name": route["name"], "details": []}
    end = next((index for index in range(start + 1, len(lines)) if end_text and end_text in lines[index].lower()), len(lines))
    details = lines[start + 1:end]
    include_only = route.get("include_only")
    if isinstance(include_only, set):
        details = [line for line in details if any(marker.lower() in line.lower() for marker in include_only)]
    return {"name": route["name"], "details": details}

def _mentioned_options(history: list[dict[str, str]]) -> list[dict[str, object]]:
    assistant_messages = [item.get("content", "") for item in history if item.get("role") == "assistant"]
    if not assistant_messages:
        return []
    last = assistant_messages[-1]
    return [route for route in ROUTES if str(route["name"]) in last]

def resolve(question: str, history: list[dict[str, str]]) -> dict[str, object]:
    normalized = _normalize(question)
    choice_match = re.fullmatch(r"(?:option |opcion )?([1-9])", normalized.strip(" .,!?") )
    if choice_match:
        options = _mentioned_options(history)
        index = int(choice_match.group(1)) - 1
        if index < len(options):
            selected = options[index]
            return {"mode": "escalation", "contacts": [_entry(selected)], "sources": [SOURCE_TITLE]}

    scored: list[tuple[int, int, dict[str, object]]] = []
    for route_index, route in enumerate(ROUTES):
        matches = [term for term in route["terms"] if term in normalized]
        if matches:
            scored.append((max(len(term) for term in matches), -route_index, route))
    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    if not scored:
        return {"mode": "clarify", "answer": "Which system or vendor needs escalation, and what is the issue?", "contacts": [], "sources": []}

    best_length = scored[0][0]
    candidates = [item[2] for item in scored if item[0] >= best_length - 2][:4]
    # Generic NCR/POS or app requests require the specific issue to avoid mixing contacts.
    generic = str(candidates[0]["name"]) in {"NCR Aloha Cloud Support (POS)", "Paytronix App Support"}
    if generic and len(normalized.split()) <= 5:
        return {"mode": "clarify", "answer": "What specific issue needs escalation? For example: NCR POS, payment processor, card reader registration, PCI, double charge, or app rewards/discounts.", "contacts": [], "sources": []}
    if len(candidates) > 1 and scored[0][0] == scored[1][0]:
        options = "\n".join(f"{index}. {route['name']}" for index, route in enumerate(candidates, 1))
        return {"mode": "clarify", "answer": f"I found several escalation paths. Which one applies?\n\n{options}", "contacts": [], "sources": []}

    selected = candidates[0]
    return {"mode": "escalation", "contacts": [_entry(selected)], "sources": [SOURCE_TITLE]}
