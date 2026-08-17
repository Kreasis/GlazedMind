"""Customer-facing web support channel backed by Monday tickets."""

from __future__ import annotations

import html
import json
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.acknowledgment import create_acknowledgment
from app.services.activity import append_activity
from app.services.auto_ack import (
    claim_first_touch,
    first_touch_gate,
    record_handled_ticket,
    release_first_touch,
)
from app.services.monday import (
    change_ticket_status,
    create_support_ticket,
    fetch_board,
    fetch_tickets,
    fetch_ticket_updates,
    post_ticket_update,
)
from app.services.ticket_matching import find_matching_ticket


_data_path = Path(__file__).resolve().parent.parent.parent / "data" / "support_cases.json"
_lock = threading.Lock()
_store_pattern = re.compile(r"^FC\d{3,}$", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(_data_path.read_text(encoding="utf-8"))
        cases = payload.get("cases", {}) if isinstance(payload, dict) else {}
        return {str(key): dict(value) for key, value in cases.items() if isinstance(value, dict)}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(cases: dict[str, dict[str, object]]) -> None:
    _data_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _data_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "cases": cases}, indent=2), encoding="utf-8")
    temporary.replace(_data_path)


def _message(role: str, content: str, *, external_id: str = "") -> dict[str, str]:
    return {
        "id": str(uuid4()),
        "role": role,
        "content": content.strip(),
        "channel": "web",
        "created_at": _now(),
        "external_id": external_id,
    }


def _public(case: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in case.items() if key not in {"access_token", "monday_update_ids"}}


def _plain_text(value: object) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _validate_store(value: object) -> str:
    store_code = re.sub(r"[\s-]+", "", str(value or "")).upper()
    if not _store_pattern.fullmatch(store_code):
        raise ValueError("Store number must use the FCXXXX format")
    return store_code


def _find_case(case_id: str, access_token: str) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    cases = _load()
    case = cases.get(str(case_id))
    if not case or not secrets.compare_digest(str(case.get("access_token") or ""), str(access_token or "")):
        raise KeyError("Support case not found")
    return cases, case


def _sync_monday(case: dict[str, object]) -> None:
    item_id = str(case.get("monday_item_id") or "")
    if not item_id:
        return
    known_updates = {str(value) for value in case.get("monday_update_ids", [])}
    known_external = {
        str(message.get("external_id") or "")
        for message in case.get("messages", [])
        if isinstance(message, dict)
    }
    context = fetch_ticket_updates(item_id)
    changed = False
    for update in sorted(context.get("updates", []), key=lambda value: str(value.get("created_at") or "")):
        update_id = str(update.get("id") or "")
        if not update_id or update_id in known_updates or update_id in known_external:
            continue
        content = _plain_text(update.get("body"))
        if not content:
            continue
        message = _message("agent", content, external_id=update_id)
        message["created_at"] = str(update.get("created_at") or message["created_at"])
        case.setdefault("messages", []).append(message)
        known_external.add(update_id)
        changed = True
    board = fetch_board()
    ticket = next((item for item in board.get("items", []) if str(item.get("id") or "") == item_id), None)
    if ticket:
        status = str(ticket.get("status") or case.get("status") or "")
        if status != case.get("status"):
            case["status"] = status
            changed = True
    if changed:
        case["updated_at"] = _now()


def create_case(payload: dict[str, object]) -> dict[str, object]:
    store_code = _validate_store(payload.get("store_code"))
    customer_name = " ".join(str(payload.get("customer_name") or "").split()).strip()
    customer_email = str(payload.get("customer_email") or "").strip().lower()
    subject = " ".join(str(payload.get("subject") or "").split()).strip()
    description = str(payload.get("description") or "").strip()
    if not customer_name or not customer_email or "@" not in customer_email:
        raise ValueError("Customer name and a valid email address are required")
    if len(subject) < 4 or len(description) < 8:
        raise ValueError("Please provide a short subject and enough detail about the request")
    request_type = str(payload.get("request_type") or "Question").strip()
    priority = str(payload.get("priority") or "Medium Priority").strip()
    if request_type not in {"Issue", "Question", "Request"}:
        raise ValueError("Request type must be Issue, Question, or Request")
    if priority not in {"Low Priority", "Medium Priority", "High Priority"}:
        raise ValueError("Priority is not valid")

    ticket_input = {
        "store_code": store_code,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "subject": subject,
        "description": description,
        "request_type": request_type,
        "priority": priority,
    }
    request_text = f"{subject}\n{description}"
    matching_ticket = find_matching_ticket(store_code, request_text, fetch_tickets("Open Tickets"))
    if matching_ticket:
        item_id = str(matching_ticket.get("id") or "")
        case_id = str(uuid4())
        access_token = secrets.token_urlsafe(24)
        created_at = _now()
        linked_message = (
            "We found an open Help Desk case for this same request and linked your message to it. "
            "Our team is already working on it, and updates will appear here."
        )
        monday_body = (
            "Additional customer request received through the GlazedMind Web Support Portal "
            "and linked to this existing case.\n\n"
            f"{customer_name} ({customer_email})\n\n{description}"
        )
        update_id = post_ticket_update(item_id, monday_body)
        current_status = str(matching_ticket.get("status") or "In Progress")
        if current_status.strip().lower() == "awaiting customer":
            change_ticket_status(item_id, "New Reply")
            current_status = "New Reply"
        case = {
            "id": case_id,
            "access_token": access_token,
            "monday_item_id": item_id,
            "store_code": store_code,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "subject": subject,
            "request_type": request_type,
            "priority": priority,
            "status": current_status,
            "created_at": created_at,
            "updated_at": created_at,
            "messages": [_message("customer", description, external_id=update_id), _message("agent", linked_message)],
            "monday_update_ids": [update_id],
            "automation_status": "linked",
            "matched_existing": True,
        }
        append_activity(item_id, "portal_case_linked", "Related portal request linked", f"A new message from {store_code} matched this open ticket and was linked instead of creating a duplicate.")
        with _lock:
            cases = _load()
            cases[case_id] = case
            _save(cases)
        return {**_public(case), "access_token": access_token}

    with first_touch_gate():
        monday_ticket = create_support_ticket(ticket_input)
        item_id = str(monday_ticket["id"])
        first_touch_claimed = claim_first_touch(item_id)
    case_id = str(uuid4())
    access_token = secrets.token_urlsafe(24)
    created_at = _now()
    case: dict[str, object] = {
        "id": case_id,
        "access_token": access_token,
        "monday_item_id": item_id,
        "store_code": store_code,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "subject": subject,
        "request_type": request_type,
        "priority": priority,
        "status": "New Reply",
        "created_at": created_at,
        "updated_at": created_at,
        "messages": [_message("customer", description)],
        "monday_update_ids": [],
        "automation_status": "processing",
    }
    append_activity(item_id, "portal_request_received", "Customer request received", f"{store_code} contacted the Help Desk through the Web Support Portal.")
    append_activity(item_id, "ticket_detected", "Ticket created in Monday", f"{monday_ticket.get('ticket')} entered as New Reply.")
    append_activity(item_id, "request_understood", "Request understood", description[:280])

    try:
        if not first_touch_claimed:
            raise RuntimeError("The automatic first-touch agent is already processing this ticket")
        acknowledgment = create_acknowledgment(monday_ticket)
        update_id = post_ticket_update(item_id, acknowledgment)
        case["monday_update_ids"].append(update_id)
        case["messages"].append(_message("agent", acknowledgment, external_id=update_id))
        record_handled_ticket(item_id, acknowledgment_posted=True, update_id=update_id, message=acknowledgment, processed_at=_now(), status_updated=False, first_touch_processing=True)
        append_activity(item_id, "acknowledgment_posted", "Personalized acknowledgment posted", "The acknowledgment was delivered to Monday and the Web Support Portal.")
        change_ticket_status(item_id, "In Progress")
        record_handled_ticket(item_id, status_updated=True, first_touch_processing=False)
        append_activity(item_id, "status_changed", "Status changed to In Progress", "The web first-touch workflow completed automatically.")
        case.update({"status": "In Progress", "automation_status": "complete"})
    except Exception as error:
        if first_touch_claimed:
            release_first_touch(item_id)
        if not any(message.get("role") == "agent" for message in case["messages"] if isinstance(message, dict)):
            case["messages"].append(_message("agent", "Your request was received. Our Help Desk team is processing it now."))
        case.update({"automation_status": "pending", "automation_note": str(error)})

    with _lock:
        cases = _load()
        cases[case_id] = case
        _save(cases)
    return {**_public(case), "access_token": access_token}


def get_case(case_id: str, access_token: str) -> dict[str, object]:
    with _lock:
        cases, case = _find_case(case_id, access_token)
        try:
            _sync_monday(case)
        except Exception:
            pass
        cases[case_id] = case
        _save(cases)
        return _public(case)


def add_customer_message(case_id: str, access_token: str, content: str) -> dict[str, object]:
    message_text = str(content or "").strip()
    if len(message_text) < 2:
        raise ValueError("Please enter a message")
    if len(message_text) > 4000:
        raise ValueError("The message is too long")
    with _lock:
        cases, case = _find_case(case_id, access_token)
        monday_body = (
            "Customer reply from GlazedMind Web Support Portal\n\n"
            f"{case.get('customer_name')} ({case.get('customer_email')})\n\n{message_text}"
        )
        update_id = post_ticket_update(str(case.get("monday_item_id")), monday_body)
        case.setdefault("monday_update_ids", []).append(update_id)
        case.setdefault("messages", []).append(_message("customer", message_text, external_id=update_id))
        change_ticket_status(str(case.get("monday_item_id")), "New Reply")
        case.update({"status": "New Reply", "updated_at": _now()})
        append_activity(case.get("monday_item_id"), "customer_replied", "Customer response received", "A new customer message arrived through the Web Support Portal.")
        cases[case_id] = case
        _save(cases)
        return _public(case)
