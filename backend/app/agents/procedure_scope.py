"""Procedure scope metadata and deterministic scope selection."""
import re
import unicodedata

MASTER_INSTALLATION = "NCR - POS complete, installation process"
BASIC_DEVICE_CHECKS = "General Device Troubleshooting - Basic Checks"

# Metadata lives outside the source documents so the DOCX files remain canonical.
PROCEDURE_METADATA: dict[str, dict[str, str]] = {
    BASIC_DEVICE_CHECKS: {
        "document_type": "prerequisite",
        "procedure": "basic_device_checks",
        "scope": "malfunction_only",
    },
    MASTER_INSTALLATION: {
        "document_type": "master",
        "procedure": "full_pos_installation",
        "scope": "complete_installation",
    },
    "NCR - Registering a device for the POS": {"document_type": "standalone", "procedure": "pos_registration", "scope": "isolated_task"},
    "NCR - Configuring a cash drawer": {"document_type": "standalone", "procedure": "cash_drawer", "scope": "isolated_task"},
    "NCR - Configuring the kitchen printer": {"document_type": "standalone", "procedure": "kitchen_printer", "scope": "isolated_task"},
    "NCR - Remove a kitchen printer": {"document_type": "standalone", "procedure": "remove_kitchen_printer", "scope": "isolated_task"},
    "NCR - Configuring the receipt printer": {"document_type": "standalone", "procedure": "receipt_printer", "scope": "isolated_task"},
    "Setting up a Sticky Printer": {"document_type": "standalone", "procedure": "sticky_printer", "scope": "isolated_task"},
    "NCR - Enable or Disable onliner ordering": {"document_type": "standalone", "procedure": "online_ordering", "scope": "isolated_task"},
    "NCR - Price change": {"document_type": "standalone", "procedure": "price_change", "scope": "isolated_task"},
    "NCR - Password reset": {"document_type": "standalone", "procedure": "password_reset", "scope": "isolated_task"},
    "NCR - Configuring date and time": {"document_type": "standalone", "procedure": "date_time", "scope": "isolated_task"},
    "NCR - Check the system version": {"document_type": "standalone", "procedure": "system_version", "scope": "isolated_task"},
    "NCR - Credit processor initiation": {"document_type": "standalone", "procedure": "credit_processor", "scope": "isolated_task"},
    "NCR - Add new Item to the Menu": {"document_type": "standalone", "procedure": "add_menu_item", "scope": "isolated_task"},
    "NCR -Adding or removing item": {"document_type": "standalone", "procedure": "add_remove_item", "scope": "isolated_task"},
}

# The prerequisite is intentionally conservative. It is useful for a device
# that has stopped operating, but it should not be injected into planned work
# such as installations, configuration changes, menu updates, or account work.
MALFUNCTION_PHRASES = {
    "not working", "does not work", "doesnt work", "stopped working",
    "wont turn on", "will not turn on", "no power", "not powering on",
    "not responding", "unresponsive", "offline", "disconnected",
    "keeps disconnecting", "intermittent", "intermittently", "frozen",
    "freezing", "black screen", "blank screen", "not printing",
    "cannot connect", "cant connect", "connection lost",
}
DEVICE_TERMS = {
    "pos", "terminal", "device", "printer", "kds", "boh", "display",
    "screen", "card reader", "scanner", "drawer", "router", "switch",
    "workstation", "tablet", "server",
}
PLANNED_WORK_TERMS = {
    "install", "installation", "setup", "configure", "configuration",
    "register", "registration", "new", "change", "update", "modify",
    "add", "remove", "enable", "disable", "reset", "replace",
    "price", "menu", "promotion", "hours", "password", "access",
    "refund", "double charge",
}

def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()

def should_prepend_basic_checks(question: str) -> bool:
    """Return True only for an existing physical device malfunction."""
    text = _normalized_text(question)
    padded = f" {text} "
    has_failure = any(phrase in text for phrase in MALFUNCTION_PHRASES)
    has_device = any(f" {term} " in padded for term in DEVICE_TERMS)
    is_planned_work = any(f" {term} " in padded for term in PLANNED_WORK_TERMS)
    return has_failure and has_device and not is_planned_work

def prepend_basic_checks(question: str, selected_titles: list[str], catalog: list[str] | None = None) -> list[str]:
    """Place the prerequisite before the chosen procedure without duplication."""
    available = catalog is None or BASIC_DEVICE_CHECKS in catalog
    if not available or not should_prepend_basic_checks(question):
        return selected_titles
    return [BASIC_DEVICE_CHECKS, *[title for title in selected_titles if title != BASIC_DEVICE_CHECKS]]

SPECIFIC_INTENTS: list[tuple[set[str], str]] = [
    ({"cash", "drawer"}, "NCR - Configuring a cash drawer"),
    ({"kitchen", "printer", "remove"}, "NCR - Remove a kitchen printer"),
    ({"kitchen", "printer"}, "NCR - Configuring the kitchen printer"),
    ({"receipt", "printer"}, "NCR - Configuring the receipt printer"),
    ({"sticky", "printer"}, "Setting up a Sticky Printer"),
    ({"online", "ordering"}, "NCR - Enable or Disable onliner ordering"),
    ({"price", "change"}, "NCR - Price change"),
    ({"password", "reset"}, "NCR - Password reset"),
    ({"date", "time"}, "NCR - Configuring date and time"),
    ({"system", "version"}, "NCR - Check the system version"),
    ({"credit", "processor"}, "NCR - Credit processor initiation"),
]

TERM_MAP = {
    "instalar": "install", "instalo": "install", "instalacion": "installation",
    "configurar": "setup", "configuro": "setup", "nuevo": "new", "nueva": "new",
    "registrar": "register", "registro": "register", "dispositivo": "device",
    "cajon": "drawer", "efectivo": "cash", "impresora": "printer", "cocina": "kitchen",
    "recibo": "receipt", "pegajosa": "sticky", "pedidos": "ordering", "pedido": "ordering",
    "linea": "online", "precio": "price", "cambio": "change", "contrasena": "password",
    "update": "change", "updated": "change", "updating": "change", "modify": "change", "modifying": "change",
    "restablecer": "reset", "fecha": "date", "hora": "time", "sistema": "system",
    "version": "version", "credito": "credit", "procesador": "processor", "remover": "remove",
    "eliminar": "remove",
}

def _terms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"\bset\s+up\b", "setup", normalized)
    return {TERM_MAP.get(word, word) for word in re.findall(r"[a-z0-9]+", normalized)}

def metadata_for(title: str) -> dict[str, str]:
    return PROCEDURE_METADATA.get(title, {"document_type": "standalone", "procedure": "general", "scope": "isolated_task"})

def resolve_scope(question: str, catalog: list[str], history: list[dict[str, str]] | None = None) -> dict[str, str] | None:
    """Resolve master vs standalone intent before semantic document ranking."""
    terms = _terms(question)
    recent_user = " ".join(item.get("content", "") for item in (history or [])[-4:] if item.get("role") == "user")
    context_terms = terms | _terms(recent_user)

    full_words = {"install", "installation", "setup", "complete", "scratch"}
    is_full_install = "pos" in context_terms and bool(context_terms & {"new", "complete", "scratch"}) and bool(context_terms & full_words)
    if is_full_install and MASTER_INSTALLATION in catalog:
        return {"decision": "select", "title": MASTER_INSTALLATION, "scope": "complete_installation"}

    # A clearly described generic device failure can safely start with the
    # prerequisite even when no system-specific procedure is identifiable.
    # Component-specific failures continue below so the chatbot can present
    # Basic Checks first and the matching component guide second.
    has_named_component = any(required <= terms for required, _ in SPECIFIC_INTENTS)
    if should_prepend_basic_checks(question) and not has_named_component and BASIC_DEVICE_CHECKS in catalog:
        return {"decision": "select", "title": BASIC_DEVICE_CHECKS, "scope": "malfunction_only"}

    # A named component is an isolated task unless the user explicitly says it is
    # part of a new/complete POS installation.
    for required, title in SPECIFIC_INTENTS:
        if required <= terms and title in catalog:
            return {"decision": "select", "title": title, "scope": "isolated_task"}

    registration_words = {"register", "registering", "registration"}
    registration_title = "NCR - Registering a device for the POS"
    if terms & registration_words and terms & {"pos", "device"} and registration_title in catalog:
        return {"decision": "select", "title": registration_title, "scope": "isolated_task"}

    # Generic POS setup lacks the information needed to choose between the master
    # runbook and a single component procedure.
    if "pos" in terms and terms & {"setup", "install", "installation", "configuring", "configure"}:
        return {
            "decision": "clarify",
            "question": "Are you setting up a complete new POS from scratch, or do you need help with a specific component or task?",
            "scope": "ambiguous",
        }
    return None
