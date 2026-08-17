"""Agent responsible for first-touch Monday ticket handling."""
from app.services.acknowledgment import create_acknowledgment
from app.services.monday import acknowledge_ticket

def handle_new_ticket(ticket: dict[str, object]) -> dict[str, object]:
    item_id = str(ticket.get("id") or "")
    if not item_id:
        raise ValueError("Monday ticket is missing its item id")
    return acknowledge_ticket(item_id, create_acknowledgment(ticket), "In Progress")
