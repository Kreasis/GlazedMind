"""Independent agent that decides and writes customer follow-up messages."""

import re


PRIORITY_DAYS = {"low": 3, "medium": 2, "high": 1}


def interval_days(priority: object) -> int:
    normalized = str(priority or "").strip().lower()
    for label, days in PRIORITY_DAYS.items():
        if label in normalized:
            return days
    return PRIORITY_DAYS["medium"]


def _request_summary(ticket: dict[str, object]) -> str:
    description = " ".join(str(ticket.get("description") or "").split()).strip()
    title = " ".join(str(ticket.get("ticket") or "").split()).strip()
    text = description or title or "your support request"
    text = re.sub(r"^(?:hi|hello|hey|good morning|good afternoon)[,!.:;\s-]*", "", text, flags=re.I)
    text = re.sub(r"\bFC\d{3,}\b\s*[-:]*\s*", "", text, flags=re.I).strip(" -:;,.")
    text = re.sub(r"^(?:i\s+)?please\s+", "", text, flags=re.I)
    text = re.sub(r"^(?:i\s+)?(?:would\s+like|want|need)\s+(?:you\s+)?to\s+", "", text, flags=re.I)
    text = re.sub(r"^i\s+need\s+help\s+(?:to|with)\s+", "", text, flags=re.I)
    text = re.sub(r"\bmy\b", "your", text, flags=re.I)
    return text.rstrip(" .!?")[:240] or "your support request"


def create_followup(ticket: dict[str, object], attempt: int) -> str:
    request = _request_summary(ticket)
    if attempt >= 3:
        return (
            f"Hello, this is our third and final follow-up regarding your request to {request}.\n\n"
            "Since we have not received a response after three follow-up attempts, we are marking this ticket "
            "as resolved for now. If you still need assistance, please reply to this ticket and we will be happy "
            "to continue helping you.\n\nBest regards,\nGlazed Mind Help Desk"
        )
    ordinal = "first" if attempt == 1 else "second"
    return (
        f"Hello, this is our {ordinal} follow-up regarding your request to {request}.\n\n"
        "When you have a moment, please reply with the requested information or let us know whether you still "
        "need assistance.\n\nBest regards,\nGlazed Mind Help Desk"
    )
