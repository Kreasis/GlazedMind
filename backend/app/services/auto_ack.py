"""Background Monday monitor for automatic ticket acknowledgments."""

import logging
import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.services.acknowledgment import create_acknowledgment
from app.services.monday import change_ticket_status, fetch_tickets, post_ticket_update
from app.services.activity import append_activity

logger = logging.getLogger(__name__)
_stop = threading.Event()
_thread: threading.Thread | None = None
_default_state_path = Path(__file__).resolve().parent.parent.parent / "data" / "acknowledged_ticket_ids.json"
_state_path = _default_state_path
_state_lock = threading.Lock()
_first_touch_gate = threading.RLock()

def _load_state() -> dict[str, dict[str, object]]:
    try:
        stored = json.loads(_state_path.read_text(encoding="utf-8"))
        if isinstance(stored, list):
            # Migrate the original completed-ID list without reprocessing tickets.
            return {str(item_id): {"acknowledgment_posted": True, "status_updated": True} for item_id in stored}
        tickets = stored.get("tickets", {}) if isinstance(stored, dict) else {}
        return {str(item_id): dict(state) for item_id, state in tickets.items() if isinstance(state, dict)}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_state(state: dict[str, dict[str, object]]) -> None:
    _state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 2, "tickets": state}, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(_state_path)


def record_handled_ticket(item_id: str, **progress: object) -> None:
    """Record first-touch work completed outside the polling loop."""
    with _state_lock:
        state = _load_state()
        current = state.setdefault(str(item_id), {})
        current.update(progress)
        _save_state(state)


@contextmanager
def first_touch_gate():
    """Serialize ticket creation/claiming with the background monitor."""
    with _first_touch_gate:
        yield


def claim_first_touch(item_id: str) -> bool:
    """Atomically claim acknowledgment work for one Monday item."""
    with _state_lock:
        state = _load_state()
        current = state.setdefault(str(item_id), {})
        if current.get("status_updated") or current.get("first_touch_processing"):
            return False
        current["first_touch_processing"] = True
        _save_state(state)
        return True


def release_first_touch(item_id: str) -> None:
    """Release an incomplete claim so a later poll can safely retry it."""
    record_handled_ticket(item_id, first_touch_processing=False)


def _ticket_progress(item_id: str) -> dict[str, object]:
    with _state_lock:
        return dict(_load_state().get(str(item_id), {}))


def _poll() -> None:
    interval = max(10, int(os.getenv("AUTO_ACK_INTERVAL_SECONDS", "30")))
    while not _stop.is_set():
        try:
            tickets = fetch_tickets("Open Tickets")
            # On first startup, preserve the existing board history. Only
            # tickets created after this monitor is initialized are eligible.
            if not _state_path.exists():
                with _state_lock:
                    state = {
                        str(ticket.get("id")): {"acknowledgment_posted": True, "status_updated": True}
                        for ticket in tickets if ticket.get("id")
                    }
                    _save_state(state)
            for ticket in tickets:
                if str(ticket.get("status", "")).strip().lower() != "new reply":
                    continue
                item_id = str(ticket.get("id") or "")
                if not item_id:
                    continue
                with first_touch_gate():
                    if not claim_first_touch(item_id):
                        continue
                try:
                    progress = _ticket_progress(item_id)
                    if not progress.get("detected_at"):
                        detected_at = datetime.now(timezone.utc).isoformat()
                        record_handled_ticket(item_id, detected_at=detected_at, first_touch_processing=True)
                        progress["detected_at"] = detected_at
                        if _state_path == _default_state_path:
                            append_activity(item_id, "ticket_detected", "Ticket detected in Monday", f"{ticket.get('ticket') or 'New ticket'} entered as New Reply.")
                    if not progress.get("acknowledgment_posted"):
                        message = create_acknowledgment(ticket)
                        if _state_path == _default_state_path:
                            request = str(ticket.get("description") or ticket.get("ticket") or "Request context analyzed.").strip()
                            append_activity(item_id, "request_understood", "Request understood", request[:280])
                        update_id = post_ticket_update(item_id, message)
                        record_handled_ticket(
                            item_id,
                            acknowledgment_posted=True,
                            update_id=update_id,
                            message=message,
                            processed_at=datetime.now(timezone.utc).isoformat(),
                            first_touch_processing=True,
                        )
                        if _state_path == _default_state_path:
                            append_activity(item_id, "acknowledgment_posted", "Personalized acknowledgment posted", "A customer-specific response was added to the Monday ticket.")
                    change_ticket_status(item_id, "In Progress")
                    record_handled_ticket(item_id, status_updated=True, first_touch_processing=False)
                    if _state_path == _default_state_path:
                        append_activity(item_id, "status_changed", "Status changed to In Progress", "The first-touch workflow completed automatically.")
                    logger.info("Automatic acknowledgment posted for Monday item %s", item_id)
                except Exception:
                    release_first_touch(item_id)
                    raise
        except Exception as error:  # Keep the monitor alive if Monday is temporarily unavailable.
            logger.warning("Automatic Monday acknowledgment check failed: %s", error)
        _stop.wait(interval)


def start_auto_ack() -> None:
    global _thread
    if os.getenv("AUTO_ACK_ENABLED", "true").strip().lower() in {"0", "false", "no"}:
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_poll, name="monday-auto-ack", daemon=True)
    _thread.start()


def stop_auto_ack() -> None:
    _stop.set()
