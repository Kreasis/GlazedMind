"""Monday.com adapter for the Glazed Mind ticket board."""

import json
import os
import re
from datetime import date
from urllib.request import Request, urlopen

MONDAY_QUERY = """
query GlazedMindTickets($boardId: [ID!]) {
  boards(ids: $boardId) {
    groups { id title }
    columns { id title type }
    items_page(limit: 500) {
      items {
        id
        name
        group { id title }
        column_values { id text value column { title } }
      }
    }
  }
}
"""

TICKET_UPDATES_QUERY = """
query GlazedMindTicketUpdates($itemIds: [ID!]!) {
  me { id name }
  items(ids: $itemIds) {
    id
    updates(limit: 100) {
      id
      body
      created_at
      creator { id name }
    }
  }
}
"""

CREATE_UPDATE_MUTATION = """
mutation CreateAcknowledgment($itemId: ID!, $body: String!) {
  create_update(item_id: $itemId, body: $body) { id }
}
"""

CHANGE_STATUS_MUTATION = """
mutation ChangeTicketStatus($boardId: ID!, $itemId: ID!, $columnId: String!, $value: String!) {
  change_simple_column_value(board_id: $boardId, item_id: $itemId, column_id: $columnId, value: $value) { id }
}
"""

CREATE_ITEM_MUTATION = """
mutation CreateSupportTicket($boardId: ID!, $groupId: String!, $itemName: String!, $columnValues: JSON!) {
  create_item(board_id: $boardId, group_id: $groupId, item_name: $itemName, column_values: $columnValues) { id name }
}
"""

def _config() -> tuple[str, str, str]:
    token = os.getenv("MONDAY_API_TOKEN", "").strip()
    board_id = os.getenv("MONDAY_BOARD_ID", "").strip()
    endpoint = os.getenv("MONDAY_API_URL", "https://api.monday.com/v2").strip()
    if not token or not board_id:
        raise RuntimeError("MONDAY_API_TOKEN and MONDAY_BOARD_ID must be configured in .env")
    return token, board_id, endpoint

def _column_map(item: dict[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in item.get("column_values", []):
        title = str((value.get("column") or {}).get("title") or value.get("id") or "").strip().lower()
        result[title] = str(value.get("text") or "")
    return result

def _normalize(item: dict[str, object]) -> dict[str, object]:
    columns = _column_map(item)
    ticket_name = str(item.get("name") or "Untitled ticket")
    explicit_number = columns.get("ticket number", "").strip()
    store_match = re.search(r"\bFC\s*[-#]?\s*(\d{2,})\b", f"{explicit_number} {ticket_name}", re.I)
    store_code = f"FC{store_match.group(1)}" if store_match else explicit_number
    return {
        "id": item.get("id"),
        "ticket": ticket_name,
        "group": (item.get("group") or {}).get("title", ""),
        "status": columns.get("status", ""),
        "priority": columns.get("priority", ""),
        "request_type": columns.get("request type", ""),
        "requestor_name": columns.get("requestor name", ""),
        # FCXXXX identifies a store and is intentionally not treated as a
        # unique ticket identifier. Monday's item id is the unique identity.
        "store_code": store_code,
        "ticket_number": store_code,  # Backward-compatible API alias.
        "description": columns.get("description", ""),
        "date": columns.get("date", ""),
        "follow_up_count": columns.get("follow-up count", columns.get("follow up count", "")),
        "columns": columns,
    }

def _request(query: str, variables: dict[str, object]) -> dict[str, object]:
    token, _, endpoint = _config()
    request = Request(endpoint, data=json.dumps({"query": query, "variables": variables}).encode(), headers={"Content-Type": "application/json", "Authorization": token}, method="POST")
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode())
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "Monday API returned an error"))
    return payload

def fetch_board() -> dict[str, object]:
    token, board_id, endpoint = _config()
    payload = _request(MONDAY_QUERY, {"boardId": [board_id]})
    board = (payload.get("data", {}).get("boards") or [None])[0]
    if not board:
        raise RuntimeError(f"Monday board {board_id} was not found")
    items = [_normalize(item) for item in board.get("items_page", {}).get("items", [])]
    groups = [{"id": group["id"], "title": group["title"]} for group in board.get("groups", [])]
    columns = [{"id": column["id"], "title": column["title"], "type": column.get("type", "")} for column in board.get("columns", [])]
    return {"groups": groups, "columns": columns, "items": items}

def fetch_ticket_context(group: str | None = "Open Tickets") -> dict[str, object]:
    """Return tickets plus the Monday user represented by the API token."""
    board = fetch_board()
    items = board["items"]
    if group:
        expected = group.lower()
        items = [item for item in items if str(item.get("group", "")).lower() == expected]
    awaiting = [item for item in items if str(item.get("status") or "").strip().lower() == "awaiting customer"]
    if not awaiting:
        return {"tickets": items, "viewer": {}}
    payload = _request(TICKET_UPDATES_QUERY, {"itemIds": [str(item["id"]) for item in awaiting]})
    data = payload.get("data", {})
    viewer = data.get("me") or {}
    updates_by_item: dict[str, list[dict[str, str]]] = {}
    for raw_item in data.get("items", []):
        updates_by_item[str(raw_item.get("id") or "")] = [
            {
                "id": str(update.get("id") or ""),
                "body": str(update.get("body") or ""),
                "created_at": str(update.get("created_at") or ""),
                "creator_id": str((update.get("creator") or {}).get("id") or ""),
                "creator_name": str((update.get("creator") or {}).get("name") or ""),
            }
            for update in raw_item.get("updates", [])
            if isinstance(update, dict)
        ]
    for item in items:
        item["updates"] = updates_by_item.get(str(item.get("id") or ""), [])
    return {
        "tickets": items,
        "viewer": {"id": str(viewer.get("id") or ""), "name": str(viewer.get("name") or "")},
    }

def fetch_tickets(group: str | None = "Open Tickets") -> list[dict[str, object]]:
    items = fetch_board()["items"]
    if not group:
        return items
    expected = group.lower()
    return [item for item in items if str(item.get("group", "")).lower() == expected]


def fetch_ticket_updates(item_id: str) -> dict[str, object]:
    """Return the update stream for one item and the API user's identity."""
    payload = _request(TICKET_UPDATES_QUERY, {"itemIds": [str(item_id)]})
    data = payload.get("data", {})
    viewer = data.get("me") or {}
    items = data.get("items") or []
    updates = []
    if items:
        updates = [
            {
                "id": str(update.get("id") or ""),
                "body": str(update.get("body") or ""),
                "created_at": str(update.get("created_at") or ""),
                "creator_id": str((update.get("creator") or {}).get("id") or ""),
                "creator_name": str((update.get("creator") or {}).get("name") or ""),
            }
            for update in items[0].get("updates", [])
            if isinstance(update, dict)
        ]
    return {"viewer": {"id": str(viewer.get("id") or ""), "name": str(viewer.get("name") or "")}, "updates": updates}


def create_support_ticket(ticket: dict[str, object]) -> dict[str, object]:
    """Create an Open Tickets item using the board's visible column names."""
    _, board_id, _ = _config()
    board = fetch_board()
    group = next((group for group in board["groups"] if str(group["title"]).strip().lower() == "open tickets"), None)
    if not group:
        raise RuntimeError("Could not find the Open Tickets group on the Monday board")
    column_ids = {str(column["title"]).strip().lower(): str(column["id"]) for column in board["columns"]}
    values: dict[str, object] = {}

    def set_text(titles: tuple[str, ...], value: object) -> None:
        column_id = next((column_ids[title] for title in titles if title in column_ids), "")
        if column_id and str(value or "").strip():
            values[column_id] = str(value).strip()

    def set_label(titles: tuple[str, ...], value: object) -> None:
        column_id = next((column_ids[title] for title in titles if title in column_ids), "")
        if column_id and str(value or "").strip():
            values[column_id] = {"label": str(value).strip()}

    store_code = str(ticket.get("store_code") or "").strip().upper()
    subject = str(ticket.get("subject") or ticket.get("description") or "Support request").strip()
    item_name = f"{store_code} - {subject[:90]}" if store_code else subject[:100]
    set_label(("status",), "New Reply")
    set_label(("priority",), ticket.get("priority") or "Medium Priority")
    set_label(("request type",), ticket.get("request_type") or "Question")
    set_text(("requestor name", "requester name"), ticket.get("customer_name"))
    set_text(("requestor email", "requester email", "email"), ticket.get("customer_email"))
    set_text(("ticket number",), store_code)
    set_text(("description",), ticket.get("description"))
    date_column = next((column_ids[title] for title in ("date", "created date") if title in column_ids), "")
    if date_column:
        values[date_column] = {"date": date.today().isoformat()}
    payload = _request(CREATE_ITEM_MUTATION, {
        "boardId": board_id,
        "groupId": str(group["id"]),
        "itemName": item_name,
        "columnValues": json.dumps(values),
    })
    created = payload.get("data", {}).get("create_item") or {}
    item_id = str(created.get("id") or "")
    if not item_id:
        raise RuntimeError("Monday did not return the new support ticket id")
    return {"id": item_id, "ticket": str(created.get("name") or item_name), "status": "New Reply", **ticket}

def change_ticket_status(item_id: str, status: str) -> None:
    """Change a Monday status using its visible label."""
    _, board_id, _ = _config()
    board = fetch_board()
    status_column = next((column for column in board["columns"] if str(column["title"]).lower() == "status"), None)
    if not status_column:
        raise RuntimeError("Could not find a Status column on the Monday board")
    _request(CHANGE_STATUS_MUTATION, {"boardId": board_id, "itemId": item_id, "columnId": status_column["id"], "value": status})

def post_ticket_update(item_id: str, message: str) -> str:
    """Post the acknowledgment separately so status retries cannot duplicate it."""
    payload = _request(CREATE_UPDATE_MUTATION, {"itemId": item_id, "body": message})
    update = payload.get("data", {}).get("create_update") or {}
    update_id = str(update.get("id") or "")
    if not update_id:
        raise RuntimeError("Monday did not return an acknowledgment update id")
    return update_id

def acknowledge_ticket(item_id: str, message: str, target_status: str = "In Progress") -> dict[str, object]:
    """Post one acknowledgment and move the item to the target status."""
    post_ticket_update(item_id, message)
    change_ticket_status(item_id, target_status)
    return {"item_id": item_id, "status": target_status, "message": message}
