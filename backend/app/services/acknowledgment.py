"""Natural first-touch acknowledgments grounded in the Monday ticket."""
import json
import logging
import os
import re
from pathlib import Path

from urllib.request import Request, urlopen

POLICY_PATH = Path(__file__).resolve().parents[2] / "prompts" / "monday_acknowledgment_agent.md"
logger = logging.getLogger(__name__)


def _ticket_request(ticket: dict[str, object]) -> tuple[str, str]:
    """Return a short request fragment and the connector that reads naturally."""
    description = " ".join(str(ticket.get("description") or "").split()).strip()
    title = " ".join(str(ticket.get("ticket") or "").split()).strip()
    text = description or title
    text = re.sub(r"^(?:hi|hello|hey|good morning|good afternoon)[,!.:;\s-]*", "", text, flags=re.I)
    text = re.sub(r"\bFC\d{3,}\b\s*[-:]*\s*", "", text, flags=re.I).strip(" -:;,.\t")
    text = re.sub(r"^(?:i\s+)?please\s+", "", text, flags=re.I)

    to_request = re.match(
        r"^(?:i\s+)?(?:would\s+like|want|need)\s+(?:you\s+)?to\s+(.+)$|^(?:can|could|would)\s+you\s+(.+)$",
        text,
        flags=re.I,
    )
    if to_request:
        text = next(group for group in to_request.groups() if group)
        connector = "to"
    else:
        help_to = re.match(r"^i\s+need\s+help\s+to\s+(.+)$", text, flags=re.I)
        help_with = re.match(r"^i\s+need\s+help\s+with\s+(.+)$", text, flags=re.I)
        if help_to:
            text, connector = help_to.group(1), "to"
        elif help_with:
            text, connector = help_with.group(1), "with"
        elif re.match(r"^[a-z]+\b", text, flags=re.I):
            connector = "to"
        else:
            connector = "with"

    text = re.sub(r"\bmy\b", "your", text, flags=re.I)
    text = re.sub(r"\bme\b", "you", text, flags=re.I)
    return text.rstrip(" .!?"), connector


def _grounded_fallback(ticket: dict[str, object]) -> str:
    request, connector = _ticket_request(ticket)
    if not request:
        return "We will begin reviewing your request. Please stay tuned for the next steps."
    return f"We will begin working on your request {connector} {request}. Please stay tuned for the next steps."

def _custom_paragraph(ticket: dict[str, object]) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("OLLAMA_API_KEY", "").strip()
    if not base_url or not api_key:
        raise RuntimeError("Ollama is not configured for acknowledgment generation")
    payload = {
        "title": str(ticket.get("ticket") or "").strip(),
        "description": " ".join(str(ticket.get("description") or "").split()),
        "request_type": str(ticket.get("request_type") or "").strip(),
    }
    native_payload = {
        "model": os.getenv("OLLAMA_ACK_MODEL", "qwen3.5:4b"),
        "messages": [
            {"role": "system", "content": POLICY_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "stream": False,
        "think": False,
        "format": "json",
        "keep_alive": "10m",
        "options": {"temperature": 0.25, "num_predict": 120},
    }
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(native_payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urlopen(request, timeout=float(os.getenv("OLLAMA_ACK_TIMEOUT_SECONDS", "20"))) as response:
        content = str(json.loads(response.read().decode("utf-8")).get("message", {}).get("content", "{}"))
    start, end = content.find("{"), content.rfind("}")
    result = json.loads(content[start:end + 1])
    paragraph = " ".join(str(result.get("custom_paragraph", "")).split()).strip()
    if not paragraph or len(paragraph) > 700:
        raise ValueError("The acknowledgment agent returned an invalid paragraph")
    forbidden = (
        "we are currently", "we have investigated",
        "we have resolved", "we have escalated", "we have completed",
        "right away", "immediately", "as soon as possible",
    )
    allowed_starts = ("we will begin", "we'll begin", "we will start", "we'll start", "we will review")
    if any(phrase in paragraph.lower() for phrase in forbidden) or not paragraph.lower().startswith(allowed_starts):
        raise ValueError("The acknowledgment paragraph violated the first-touch policy")
    return paragraph

def create_acknowledgment(ticket: dict[str, object]) -> str:
    greeting = "Thank you for contacting Glazed Mind Help Desk."
    closing = "We will contact you as soon as we have an update.\n\nBest regards,\nGlazed Mind Help Desk"
    try:
        body = _custom_paragraph(ticket)
    except Exception as error:
        # A safe acknowledgment is better than leaving a new customer ticket
        # untouched when the local model is temporarily unavailable.
        logger.warning("Acknowledgment model unavailable; using safe fallback: %s", error)
        body = _grounded_fallback(ticket)
    return f"{greeting}\n\n{body}\n\n{closing}"
