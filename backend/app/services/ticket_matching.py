"""Deterministic intent matching for open tickets from the same store."""

from __future__ import annotations

import re


_STOP_WORDS = {
    "a", "an", "and", "are", "can", "for", "from", "got", "have", "help", "i", "in",
    "is", "it", "me", "my", "need", "new", "of", "on", "please", "the", "to", "with",
}


def _normalized(text: object) -> str:
    value = re.sub(r"\bFC\s*[-#]?\s*\d+\b", " ", str(text or ""), flags=re.I).lower()
    value = value.replace("point of sale", "pos")
    replacements = {
        "installation": "install", "installing": "install", "installed": "install",
        "setting up": "setup", "set up": "setup", "registering": "register",
        "registered": "register", "configuration": "configure", "configuring": "configure",
        "changing": "change", "updated": "update", "updating": "update",
        "removing": "remove", "removed": "remove", "adding": "add",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def topic_signature(text: object) -> str:
    value = _normalized(text)
    words = set(value.split())
    has = lambda *options: any(option in words for option in options)

    if "pos" in words and has("install", "setup", "register", "configure"):
        return "new_pos_installation"
    if has("price", "pricing") and has("change", "update", "increase", "decrease"):
        return "price_change"
    if "cash" in words and "drawer" in words:
        return "cash_drawer"
    if "sticky" in words and "printer" in words:
        return "sticky_printer"
    if "kitchen" in words and "printer" in words:
        return "kitchen_printer"
    if "receipt" in words and "printer" in words:
        return "receipt_printer"
    if has("refund", "void", "chargeback"):
        return "refund_or_void"
    if has("password", "login") and has("reset", "forgot", "access"):
        return "password_reset"
    if "online" in words and has("order", "ordering"):
        return "online_ordering"
    if has("promotion", "promo", "discount"):
        return "promotion"
    if "menu" in words and has("add", "remove", "item"):
        return "menu_item"
    if has("date", "time", "timezone") and has("change", "configure", "wrong"):
        return "date_and_time"
    return ""


def same_support_topic(left: object, right: object) -> bool:
    """Return true only when two requests are confidently about the same work."""
    left_value = _normalized(left)
    right_value = _normalized(right)
    left_signature = topic_signature(left_value)
    right_signature = topic_signature(right_value)
    if left_signature or right_signature:
        return bool(left_signature and left_signature == right_signature)

    left_tokens = {word for word in left_value.split() if word not in _STOP_WORDS and len(word) > 2}
    right_tokens = {word for word in right_value.split() if word not in _STOP_WORDS and len(word) > 2}
    overlap = left_tokens & right_tokens
    if len(overlap) < 2:
        return False
    return len(overlap) / max(1, min(len(left_tokens), len(right_tokens))) >= 0.7


def find_matching_ticket(store_code: str, request_text: str, tickets: list[dict[str, object]]) -> dict[str, object] | None:
    expected_store = str(store_code or "").strip().upper()
    for ticket in tickets:
        if str(ticket.get("store_code") or "").strip().upper() != expected_store:
            continue
        if str(ticket.get("status") or "").strip().lower() == "resolved":
            continue
        candidate = f"{ticket.get('ticket') or ''}\n{ticket.get('description') or ''}"
        if same_support_topic(request_text, candidate):
            return ticket
    return None
