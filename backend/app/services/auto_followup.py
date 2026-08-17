"""Background scheduler for unanswered Monday customer follow-ups."""

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.agents.monday_followup_agent import create_followup, interval_days
from app.services.monday import change_ticket_status, fetch_ticket_context, post_ticket_update
from app.services.activity import append_activity
from app.services.runtime import followup_time_unit

logger = logging.getLogger(__name__)
_stop = threading.Event()
_thread: threading.Thread | None = None
_default_state_path = Path(__file__).resolve().parent.parent.parent / "data" / "followup_state.json"
_state_path = _default_state_path
_state_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except ValueError:
        return None


def _load_state() -> dict[str, dict[str, object]]:
    try:
        stored = json.loads(_state_path.read_text(encoding="utf-8"))
        tickets = stored.get("tickets", {}) if isinstance(stored, dict) else {}
        return {str(item_id): dict(value) for item_id, value in tickets.items() if isinstance(value, dict)}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, dict[str, object]]) -> None:
    _state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "tickets": state}, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(_state_path)


def _due_delta(priority: object) -> timedelta:
    amount = interval_days(priority)
    unit = followup_time_unit()
    return timedelta(minutes=amount) if unit in {"minute", "minutes"} else timedelta(days=amount)


def _latest_agent_update(ticket: dict[str, object], agent_user_id: str) -> dict[str, object] | None:
    matches = [
        update for update in ticket.get("updates", [])
        if str(update.get("creator_id") or "") == agent_user_id and _parse_date(update.get("created_at"))
    ]
    return max(matches, key=lambda update: _parse_date(update.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc), default=None)


def _customer_replied(ticket: dict[str, object], agent_user_id: str, since: datetime) -> bool:
    return any(
        str(update.get("creator_id") or "") != agent_user_id
        and (_parse_date(update.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)) > since
        for update in ticket.get("updates", [])
    )


def process_once(now: datetime | None = None, initialize_baseline: bool = True) -> list[dict[str, object]]:
    """Run one deterministic scheduler pass; exposed for tests and manual checks."""
    current = (now or _now()).astimezone(timezone.utc)
    context = fetch_ticket_context("Open Tickets")
    agent_user_id = str((context.get("viewer") or {}).get("id") or "")
    if not agent_user_id:
        raise RuntimeError("Monday did not identify the API user; update authors cannot be distinguished safely")
    with _state_lock:
        state = _load_state()
    actions: list[dict[str, object]] = []
    tickets = list(context.get("tickets", []))

    # Establish a safe boundary so existing board history is never enrolled.
    if initialize_baseline and not _state_path.exists():
        state = {
            str(ticket["id"]): {"eligible": False, "baseline": True}
            for ticket in tickets if ticket.get("id")
        }
        with _state_lock:
            _save_state(state)
        return [{"action": "baseline_initialized", "tickets": len(state)}]

    for ticket in tickets:
        item_id = str(ticket.get("id") or "")
        if not item_id:
            continue
        if item_id not in state:
            state[item_id] = {"eligible": True, "followup_count": 0}
        progress = state[item_id]
        status = str(ticket.get("status") or "").strip().lower()
        if status != "awaiting customer":
            if progress.get("followup_count"):
                progress.update({"cancelled": True, "cancelled_status": status})
            continue
        if not progress.get("eligible") or progress.get("resolved") or progress.get("cancelled"):
            continue

        latest_agent = _latest_agent_update(ticket, agent_user_id)
        stored_contact = _parse_date(progress.get("last_contact_at"))
        last_contact = stored_contact or current

        if _customer_replied(ticket, agent_user_id, last_contact):
            state.pop(item_id, None)
            actions.append({"item_id": item_id, "action": "customer_replied"})
            if _state_path == _default_state_path:
                append_activity(item_id, "customer_replied", "Customer response detected", "Automatic follow-ups were cancelled because the customer replied.")
            continue

        if not stored_contact:
            progress["last_contact_at"] = last_contact.isoformat()

        due_at = last_contact + _due_delta(ticket.get("priority"))
        if current < due_at:
            continue

        attempt = int(progress.get("followup_count") or 0) + 1
        message = create_followup(ticket, attempt)
        update_id = post_ticket_update(item_id, message)
        progress.update({
            "followup_count": attempt,
            "last_contact_at": current.isoformat(),
            "last_update_id": update_id,
        })
        if _state_path == _default_state_path:
            append_activity(item_id, "followup_sent", f"Follow-up #{attempt} sent", "No customer response was detected before the priority deadline.", metadata={"attempt": attempt})
        action = "followup"
        if attempt >= 3:
            change_ticket_status(item_id, "Resolved")
            progress["resolved"] = True
            action = "resolved"
            if _state_path == _default_state_path:
                append_activity(item_id, "ticket_resolved", "Ticket resolved automatically", "Three follow-up attempts were completed without a customer response.")
        actions.append({"item_id": item_id, "action": action, "attempt": attempt})

    with _state_lock:
        _save_state(state)
    return actions


def _poll() -> None:
    interval = max(5, int(os.getenv("AUTO_FOLLOWUP_INTERVAL_SECONDS", "300")))
    while not _stop.is_set():
        try:
            for action in process_once():
                logger.info("Automatic Monday follow-up action: %s", action)
        except Exception as error:
            logger.warning("Automatic Monday follow-up check failed: %s", error)
        _stop.wait(interval)


def start_auto_followup() -> None:
    global _thread
    if os.getenv("AUTO_FOLLOWUP_ENABLED", "false").strip().lower() not in {"1", "true", "yes"}:
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_poll, name="monday-auto-followup", daemon=True)
    _thread.start()


def stop_auto_followup() -> None:
    _stop.set()
