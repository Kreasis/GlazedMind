"""Operational activity log and impact metrics for the hackathon demo."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
_activity_path = _data_dir / "activity_log.json"
_ack_path = _data_dir / "acknowledged_ticket_ids.json"
_followup_path = _data_dir / "followup_state.json"
_knowledge_path = Path(__file__).resolve().parent.parent.parent / "knowledge-base"
_lock = threading.Lock()


def _read_json(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def _events() -> list[dict[str, object]]:
    stored = _read_json(_activity_path, {"events": []})
    values = stored.get("events", []) if isinstance(stored, dict) else []
    return [dict(value) for value in values if isinstance(value, dict)]


def _save_events(events: list[dict[str, object]]) -> None:
    _activity_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _activity_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "events": events[-500:]}, indent=2), encoding="utf-8")
    temporary.replace(_activity_path)


def append_activity(
    ticket_id: object,
    event_type: str,
    title: str,
    detail: str,
    *,
    metadata: dict[str, object] | None = None,
    dedupe_key: str | None = None,
) -> dict[str, object]:
    timestamp = datetime.now(timezone.utc).isoformat()
    event_metadata = dict(metadata or {})
    if dedupe_key:
        event_metadata["dedupe_key"] = dedupe_key
        event_metadata["run_count"] = 1
    event = {
        "id": str(uuid4()),
        "ticket_id": str(ticket_id or ""),
        "event_type": event_type,
        "title": title,
        "detail": detail,
        "created_at": timestamp,
        "metadata": event_metadata,
    }
    with _lock:
        events = _events()
        if dedupe_key:
            ticket_key = str(ticket_id or "")
            for existing in events:
                existing_metadata = existing.get("metadata")
                if not isinstance(existing_metadata, dict):
                    continue
                if str(existing.get("ticket_id") or "") != ticket_key or existing_metadata.get("dedupe_key") != dedupe_key:
                    continue
                updated_metadata = dict(existing_metadata)
                updated_metadata.update(event_metadata)
                updated_metadata["run_count"] = int(existing_metadata.get("run_count") or 1) + 1
                updated_metadata["last_run_at"] = timestamp
                existing.update({"title": title, "detail": detail, "metadata": updated_metadata})
                _save_events(events)
                return existing
        events.append(event)
        _save_events(events)
    return event


def compact_activity_log() -> dict[str, int]:
    """Remove legacy empty procedure events and collapse repeated successful runs."""
    with _lock:
        events = _events()
        compacted: list[dict[str, object]] = []
        procedures: dict[tuple[str, str], dict[str, object]] = {}
        for event in events:
            if event.get("event_type") != "knowledge_retrieved":
                compacted.append(event)
                continue
            metadata = dict(event.get("metadata") or {})
            steps = int(metadata.get("steps") or 0)
            if steps <= 0:
                continue
            sources = sorted(str(source) for source in metadata.get("sources", []) if source)
            dedupe_key = str(metadata.get("dedupe_key") or f"procedure:{steps}:{'|'.join(sources)}")
            marker = (str(event.get("ticket_id") or ""), dedupe_key)
            if marker in procedures:
                existing = procedures[marker]
                existing_metadata = dict(existing.get("metadata") or {})
                existing_metadata["run_count"] = int(existing_metadata.get("run_count") or 1) + int(metadata.get("run_count") or 1)
                existing_metadata["last_run_at"] = event.get("created_at")
                existing["metadata"] = existing_metadata
                continue
            metadata.update({"dedupe_key": dedupe_key, "run_count": int(metadata.get("run_count") or 1)})
            event["metadata"] = metadata
            procedures[marker] = event
            compacted.append(event)
        if compacted != events:
            _save_events(compacted)
        return {"before": len(events), "after": len(compacted), "removed": len(events) - len(compacted)}


def _ack_state() -> dict[str, dict[str, object]]:
    stored = _read_json(_ack_path, {"tickets": {}})
    tickets = stored.get("tickets", {}) if isinstance(stored, dict) else {}
    return {str(key): dict(value) for key, value in tickets.items() if isinstance(value, dict)}


def _followup_state() -> dict[str, dict[str, object]]:
    stored = _read_json(_followup_path, {"tickets": {}})
    tickets = stored.get("tickets", {}) if isinstance(stored, dict) else {}
    return {str(key): dict(value) for key, value in tickets.items() if isinstance(value, dict)}


def _synthetic_timeline(ticket_id: str) -> list[dict[str, object]]:
    ack = _ack_state().get(ticket_id, {})
    followup = _followup_state().get(ticket_id, {})
    created_at = str(ack.get("processed_at") or followup.get("last_contact_at") or "")
    result: list[dict[str, object]] = []

    def add(event_type: str, title: str, detail: str, sequence: int) -> None:
        result.append({"id": f"historic-{ticket_id}-{event_type}-{sequence}", "ticket_id": ticket_id,
                       "event_type": event_type, "title": title, "detail": detail,
                       "created_at": created_at, "metadata": {"historic": True, "sequence": sequence}})

    if ack.get("message") or ack.get("update_id"):
        add("ticket_detected", "Ticket detected in Monday", "New Reply entered the automated workflow.", 1)
        message = str(ack.get("message") or "")
        paragraph = message.split("\n\n")[1] if len(message.split("\n\n")) > 1 else "Request context analyzed."
        add("request_understood", "Request understood", paragraph, 2)
        add("acknowledgment_posted", "Personalized acknowledgment posted", "Customer communication was added to the Monday ticket.", 3)
        if ack.get("status_updated"):
            add("status_changed", "Status changed to In Progress", "The first-touch workflow completed automatically.", 4)
    followup_count = int(followup.get("followup_count") or 0)
    for attempt in range(1, followup_count + 1):
        add("followup_sent", f"Follow-up #{attempt} sent", "No customer response was detected before the priority deadline.", 4 + attempt)
        result[-1]["metadata"]["attempt"] = attempt
    if followup.get("resolved"):
        add("ticket_resolved", "Ticket resolved automatically", "Three follow-up attempts were completed without a customer response.", 8)
    return result


def timeline(ticket_id: object) -> list[dict[str, object]]:
    key = str(ticket_id or "")
    live = [event for event in _events() if str(event.get("ticket_id")) == key]
    historic = _synthetic_timeline(key)
    existing = {(str(event.get("event_type")), str((event.get("metadata") or {}).get("attempt", ""))) for event in live}
    for event in historic:
        marker = (str(event.get("event_type")), str((event.get("metadata") or {}).get("attempt", "")))
        if marker not in existing and not any(str(item.get("event_type")) == marker[0] for item in live if marker[0] != "followup_sent"):
            live.append(event)
    return sorted(live, key=lambda event: (str(event.get("created_at") or ""), int((event.get("metadata") or {}).get("sequence", 99))))


def impact_metrics() -> dict[str, object]:
    from app.services.runtime import runtime_summary

    acknowledgments = [value for value in _ack_state().values() if value.get("message") or value.get("update_id")]
    followups = _followup_state()
    followup_messages = sum(int(value.get("followup_count") or 0) for value in followups.values())
    auto_resolved = sum(1 for value in followups.values() if value.get("resolved"))
    status_updates = sum(1 for value in acknowledgments if value.get("status_updated"))
    documents = len(list(_knowledge_path.glob("*.docx"))) if _knowledge_path.exists() else 0
    automated_actions = len(acknowledgments) + status_updates + followup_messages + auto_resolved
    return {
        "tickets_acknowledged": len(acknowledgments),
        "status_updates": status_updates,
        "followups_sent": followup_messages,
        "tickets_auto_resolved": auto_resolved,
        "automated_actions": automated_actions,
        "estimated_minutes_saved": len(acknowledgments) * 4 + status_updates + followup_messages * 3 + auto_resolved * 2,
        "knowledge_documents": documents,
        "activity_events": len(_events()),
        "calculation_note": "Estimate: 4 min per acknowledgment, 1 min per status update, 3 min per follow-up, and 2 min per automatic closure.",
        "runtime": runtime_summary(),
    }
