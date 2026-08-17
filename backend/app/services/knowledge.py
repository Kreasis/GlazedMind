"""Verified Knowledge Base retrieval backed by PostgreSQL and pgvector."""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

STOP_WORDS = {"the", "and", "for", "with", "from", "this", "that", "into", "cannot", "not", "a", "an", "at", "to", "of", "in", "on"}

@lru_cache(maxsize=1)
def _documents() -> list[dict[str, str]]:
    try:
        from app.services.vector_store import documents
        return documents()
    except Exception:
        return []

def _terms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    return {term for term in re.findall(r"[a-z0-9]{3,}", normalized) if term not in STOP_WORDS}

def search(query: str, limit: int = 3) -> list[dict[str, str]]:
    """Return the best matching guide excerpts with filenames for source display."""
    try:
        from app.services.vector_store import search_vector
        vector_results = search_vector(query, limit)
        if vector_results:
            return vector_results
    except Exception:
        # Exact-term retrieval keeps the demo usable if embeddings are temporarily offline.
        pass
    query_terms = _terms(query)
    generic_terms = {"how", "create", "make", "change", "documentation", "document", "guide", "process", "procedure", "issue", "problem"}
    if not (query_terms - generic_terms):
        return []
    pos_terms = {"pos", "payment", "credit", "card", "terminal", "processor", "ncr", "printer", "server", "device"}
    matches = []
    for document in _documents():
        if document["title"].lower() in {"complete guide - pos most common tbs", "ncr - pos complete, installation process"} and not (query_terms & pos_terms):
            continue
        searchable = f"{document['title']} {document['content']}".lower()
        title_score = sum(document["title"].lower().count(term) for term in query_terms) * 100
        score = title_score + sum(document["content"].lower().count(term) for term in query_terms)
        if not score:
            continue
        position = min((searchable.find(term) for term in query_terms if term in searchable), default=0)
        excerpt = document["content"][max(0, position - 130): position + 420].strip()
        # PDF extraction also captures the repeated Shipley banner on each
        # page (page-*-1.jpg). It is branding, not a troubleshooting screen,
        # so exclude it before aligning screenshots with the procedure.
        images = [image for image in document.get("images", []) if not image.lower().endswith("-1.jpg")]
        matches.append({"source": document["title"], "filename": document["filename"], "excerpt": excerpt, "steps": document.get("steps", []), "images": images[:100], "score": score})
    return sorted(matches, key=lambda item: item["score"], reverse=True)[:limit]

def _numbered_steps(content: str) -> list[str]:
    """Recover numbered PDF steps when the extractor could not build a list."""
    pattern = re.compile(r"(?<!\w)(\d{1,2})\.\s+(.*?)(?=\s+\d{1,2}\.\s+|$)", re.S)
    steps: list[str] = []
    for number, text in pattern.findall(content):
        index = int(number)
        cleaned = " ".join(text.split()).strip()
        # PDF page headers are interleaved between numbered instructions.
        cleaned = cleaned.split("Shipley Do-Nuts: Knowledge Base Troubleshooting for common issues", 1)[0].strip()
        if cleaned:
            steps.append(cleaned)
    return steps

def _align_images(steps: list[str], images: list[str]) -> list[str | None]:
    """Attach screenshots conservatively; known text-only setup steps stay blank."""
    aligned: list[str | None] = []
    image_index = 0
    text_only = ("open the app and begin", "edit the time and choose")
    for step in steps:
        if any(step.lower().startswith(prefix) for prefix in text_only):
            aligned.append(None)
            continue
        aligned.append(images[image_index] if image_index < len(images) else None)
        image_index += 1
    return aligned

def _clean_steps(steps: list[str]) -> list[str]:
    """Remove document metadata and customer-dialogue prompts from procedures."""
    if not steps:
        return []
    first_instruction = next(
        (index for index, step in enumerate(steps)
         if re.match(r"^(?:step\s+\d+|\d+[.)])", step.strip(), re.I)),
        0,
    )
    cleaned: list[str] = []
    for step in steps[first_instruction:]:
        raw = step.get("text", "") if isinstance(step, dict) else step
        text = " ".join(str(raw).split()).strip()
        if not text or re.match(r"^(?:version|purpose|standard operating procedure|shipley do-nuts)$", text, re.I):
            continue
        if "please provide me with the list of items" in text.lower():
            continue
        cleaned.append(text)
    # Runbooks in DOCX often store a section heading and its actions as
    # separate extracted entries. Keep the heading with its instructions so
    # the UI does not render a meaningless "Step 1" followed by "Step 2".
    if any(re.match(r"^step\s+\d+", item, re.I) for item in cleaned):
        merged: list[str] = []
        for item in cleaned:
            if re.match(r"^step\s+\d+", item, re.I):
                merged.append(item)
            elif merged:
                merged[-1] = f"{merged[-1]} {item}"
            else:
                merged.append(item)
        return merged
    return cleaned

def _clean_step_records(steps: list[object]) -> list[dict[str, object]]:
    """Clean procedure entries while preserving their position-bound images."""
    raw_records = [
        {
            "text": " ".join(str(step.get("text", "") if isinstance(step, dict) else step).split()).strip(),
            "images": list(step.get("images", [])) if isinstance(step, dict) else [],
            "section": str(step.get("section", "")) if isinstance(step, dict) else "",
            "kind": str(step.get("kind", "step")) if isinstance(step, dict) else "step",
        }
        for step in steps
    ]
    first_instruction = next(
        (index for index, record in enumerate(raw_records)
         if re.match(r"^(?:step\s+\d+|\d+[.)])", str(record["text"]), re.I)),
        0,
    )
    cleaned: list[dict[str, object]] = []
    for record in raw_records[first_instruction:]:
        text = str(record["text"])
        if not text or re.match(r"^(?:version|purpose|standard operating procedure|shipley do-nuts)$", text, re.I):
            continue
        if "please provide me with the list of items" in text.lower():
            continue
        cleaned.append(record)
    if any(re.match(r"^step\s+\d+", str(record["text"]), re.I) for record in cleaned):
        merged: list[dict[str, object]] = []
        for record in cleaned:
            if re.match(r"^step\s+\d+", str(record["text"]), re.I):
                merged.append({"text": record["text"], "images": list(record["images"])})
            elif merged:
                merged[-1]["text"] = f"{merged[-1]['text']} {record['text']}"
                merged[-1]["images"].extend(record["images"])
            else:
                merged.append(record)
        return merged
    return cleaned

def document_by_title(title: str) -> dict[str, object] | None:
    """Return one exact persisted document from the Knowledge Base."""
    return next((document for document in _documents() if document["title"] == title), None)

def document_steps(document: dict[str, object]) -> list[str]:
    """Recover every documented step without summarizing or deduplicating it."""
    stored_steps = list(document.get("steps") or [])
    if stored_steps:
        return [str(record["text"]) for record in _clean_step_records(stored_steps)]
    return _clean_steps(_numbered_steps(str(document.get("content", ""))))

def document_step_records(document: dict[str, object]) -> list[dict[str, object]]:
    """Return complete steps with only screenshots structurally attached in DOCX."""
    stored_steps = list(document.get("steps") or [])
    if stored_steps:
        return _clean_step_records(stored_steps)
    return [{"text": step, "images": []} for step in _clean_steps(_numbered_steps(str(document.get("content", ""))))]

def escalation_contacts(query: str = "") -> dict[str, str] | None:
    for document in _documents():
        if "point of contacts" in document["title"].lower():
            content = document["content"]
            terms = _terms(query)
            sections = [
                ({"pos", "ncr", "payment", "credit", "card", "terminal"}, "NCR/ ALOHA CLOUD/ PAYMENTS SUPPORT"),
                ({"olo", "menu", "online", "ordering"}, "OLO HELP/ MENU RELATED"),
                ({"network", "firewall", "internet"}, "Scale Computing Support"),
                ({"drive", "headset", "timer", "camera"}, "DTiQ Drive Thru Support"),
                ({"doordash", "refund"}, "Doordash"),
            ]
            start = 0
            for keywords, heading in sections:
                if terms & keywords:
                    start = content.lower().find(heading.lower())
                    break
            return {"source": document["title"], "excerpt": content[max(0, start): max(0, start) + 650]}
    return None

def answer_ticket(question: str, use_llm: bool = True) -> dict[str, object]:
    """Create a concise, source-grounded troubleshooting response for the demo."""
    sources = search(question)
    if not sources:
        return {"answer": "I could not find a matching guide in the verified Knowledge Base.", "steps": ["Confirm the affected system and collect the store/FC number.", "Escalate using the contacts guide if the incident is urgent."], "sources": []}

    primary = sources[0]
    terms = _terms(question)
    primary_document = next((doc for doc in _documents() if doc["title"] == primary["source"]), None)
    complete_steps = _clean_steps(list(primary.get("steps") or []))
    if not complete_steps and primary_document:
        complete_steps = _clean_steps(_numbered_steps(primary_document.get("content", "")))
    install_request = bool(terms & {"install", "installation", "instalacion", "intalacion", "instalar", "instalo", "registro", "registrar", "register", "setup", "configurar"}) and bool(terms & {"pos", "device", "terminal", "ncr", "dispositivo"})
    if install_request:
        # The whitelist procedure and the POS registration procedure are
        # stored as separate guides. Always include the whitelist guide for
        # a new POS, even when vector similarity ranks registration first.
        whitelist_doc = next((doc for doc in _documents() if "pos complete, installation" in doc["title"].lower()), None)
        if whitelist_doc and not any(source["source"] == whitelist_doc["title"] for source in sources):
            whitelist_images = [image for image in whitelist_doc.get("images", []) if not image.lower().endswith("-1.jpg")]
            sources.insert(0, {"source": whitelist_doc["title"], "filename": whitelist_doc["filename"], "excerpt": whitelist_doc["content"][:550], "steps": whitelist_doc.get("steps", []), "images": whitelist_images[:100], "score": 1.0})
    if install_request:
        installation = next((source for source in sources if "pos complete, installation" in source["source"].lower()), None)
        if installation:
            primary = installation
            primary["steps"] = _clean_steps(_numbered_steps(next((doc["content"] for doc in _documents() if doc["title"] == installation["source"]), "")))
            sources = [primary] + [source for source in sources if source is not primary]
            complete_steps = primary["steps"]
    contacts = escalation_contacts(question)
    if not use_llm:
        return {"answer": "", "steps": complete_steps, "step_images": _align_images(complete_steps, primary.get("images", [])), "sources": sources, "escalation": contacts}
    try:
        from app.services.llm import generate_resolution
        generated = generate_resolution(question, sources, contacts)
        if generated.get("steps"):
            raw_steps = generated["steps"]
            if isinstance(raw_steps, str):
                raw_steps = re.split(r"(?=\*{0,2}Step\s+\d+)", raw_steps, flags=re.I)
            generated["steps"] = _clean_steps([str(step).replace("**", "").replace("* ", "") for step in raw_steps])
        if not generated.get("steps") and complete_steps:
            generated["steps"] = complete_steps
        if not generated.get("summary") and not generated.get("answer"):
            generated["answer"] = "I reviewed the relevant Glazed Mind Help Desk documentation and organized the complete procedure below. Please follow the steps in order, and let us know if any result differs from what is described."
        if not generated.get("verify"):
            generated["verify"] = ["Confirm the requested change or installation works as expected before closing the ticket."]
        if not generated.get("draft_response"):
            generated["draft_response"] = "We reviewed the documented procedure and outlined the required steps above. Please let us know if you need help with any step or if the expected result does not occur."
        generated["step_images"] = _align_images(generated.get("steps", []), primary.get("images", []))
        return {**generated, "sources": sources, "escalation": contacts}
    except Exception:
        # Keep the local demo usable when the API key or model is unavailable.
        pass
    if complete_steps:
        steps = complete_steps
    elif terms & {"pos", "payment", "credit", "card", "terminal", "processor"}:
        steps = [
            "Confirm the store/FC number, the affected POS device, and whether other devices are impacted.",
            "On the POS, tap the cloud icon in the upper-right corner and check Host, Server, and Credit Processor status.",
            "Check the power socket and power cable, then verify the Ethernet cable is securely connected to the LAN port (not the COM port).",
            "If the Credit Processor is offline or not initialized, follow the credit processor procedure and use the Payments/NCR escalation contact if needed.",
        ]
    elif terms & {"printer", "receipt", "kitchen", "sticky"}:
        steps = ["Confirm the exact printer and location affected.", "Check power, cabling, paper, and network connection.", "Follow the matching printer configuration guide below.", "Document the outcome and escalate if the device is physically damaged or still unreachable."]
    else:
        steps = [
            "Confirm the store/FC number and identify the exact system or device affected.",
            f"Open the guide '{primary['source']}' and follow its documented procedure.",
            "Validate the fix with the store before closing the ticket.",
        ]
    return {"answer": "I reviewed the relevant Glazed Mind Help Desk documentation and organized the complete procedure below. Please follow the steps in order, and let us know if any result differs from what is described.", "steps": steps, "step_images": _align_images(steps, primary.get("images", [])), "verify": ["Confirm the requested change or installation works as expected before closing the ticket."], "draft_response": "We reviewed the documented procedure and outlined the required steps above. Please let us know if you need help with any step or if the expected result does not occur.", "sources": sources, "escalation": contacts}
