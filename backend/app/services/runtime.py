"""Runtime flags exposed to the demo UI and automation services."""

import os


def _enabled(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


def demo_mode() -> bool:
    return _enabled("DEMO_MODE")


def followup_time_unit() -> str:
    """Use accelerated minutes only when the explicit demo flag is enabled."""
    requested = os.getenv("AUTO_FOLLOWUP_TIME_UNIT", "days").strip().lower()
    if demo_mode() and requested in {"minute", "minutes"}:
        return "minutes"
    return "days"


def runtime_summary() -> dict[str, object]:
    return {
        "mode": "demo" if demo_mode() else "standard",
        "demo_mode": demo_mode(),
        "followup_time_unit": followup_time_unit(),
        "auto_ack_enabled": _enabled("AUTO_ACK_ENABLED", default=True),
        "auto_followup_enabled": _enabled("AUTO_FOLLOWUP_ENABLED"),
    }
