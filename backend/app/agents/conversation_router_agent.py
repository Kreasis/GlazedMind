"""Conversation and support-intent router for the GlazedMind chatbot."""
import re
import unicodedata

from app.services.llm import generate_chat_plan
from app.agents.procedure_scope import resolve_scope
from app.agents.knowledge_retriever import confident_title

GENERIC_TITLE_TERMS = {"ncr", "the", "a", "an", "to", "for", "and", "or", "of", "new"}

def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")

def _language(value: str) -> str:
    # The assistant understands bilingual input, but GlazedMind's operational
    # language is English for every customer-facing response.
    return "en"

def _basic_chat(question: str) -> dict[str, object] | None:
    normalized = _normalize(question).strip(" .,!?")
    language = _language(question)
    responses = {
        "greeting": {
            "es": "¡Hola! Soy GlazedMind, el asistente del Help Desk. ¿En qué puedo ayudarte hoy?",
            "en": "Hello! I’m GlazedMind, the Help Desk assistant. How can I help you today?",
        },
        "identity": {
            "es": "Me llamo GlazedMind. Soy el asistente del Help Desk y trabajo con nuestra documentación técnica verificada.",
            "en": "My name is GlazedMind. I’m the Help Desk assistant and I work with our verified technical documentation.",
        },
        "thanks": {"es": "¡Con gusto! ¿Necesitas ayuda con algo más?", "en": "You’re welcome! Is there anything else I can help with?"},
        "farewell": {"es": "¡Hasta luego! Aquí estaré cuando necesites ayuda.", "en": "Goodbye! I’ll be here whenever you need help."},
        "wellbeing": {"es": "Estoy muy bien y listo para ayudarte. ¿En qué estás trabajando?", "en": "I’m doing well and ready to help. What are you working on?"},
        "capabilities": {
            "es": "Puedo conversar contigo y ayudarte con procedimientos documentados para plataformas como NCR, Acumera, Acuvigil y Scale, además de instalaciones, impresoras, pagos, menús, precios, promociones, pedidos online y escalaciones.",
            "en": "I can chat with you and help with documented procedures for platforms such as NCR, Acumera, Acuvigil, and Scale, including installations, printers, payments, menus, prices, promotions, online ordering, and escalations.",
        },
    }
    patterns = [
        ("greeting", r"^(hola|hello|hi|hey|buenas)$"),
        ("identity", r"(como te llamas|cual es tu nombre|what(?:'s| is) your name|who are you)"),
        ("thanks", r"^(gracias|muchas gracias|thanks|thank you|perfecto)$"),
        ("farewell", r"^(adios|hasta luego|bye|goodbye|see you)$"),
        ("wellbeing", r"(como estas|how are you|how is it going|how's it going)"),
        ("capabilities", r"(que puedes hacer|para que sirves|what can you do|how can you help)"),
    ]
    for intent, pattern in patterns:
        if re.search(pattern, normalized):
            return {"mode": "chat", "language": language, "reply": responses[intent][language], "selected_titles": []}
    return None

def _lexical_fallback(question: str, catalog: list[str]) -> list[str]:
    query_terms = set(re.findall(r"[a-z0-9]+", _normalize(question))) - GENERIC_TITLE_TERMS
    ranked: list[tuple[int, str]] = []
    for title in catalog:
        title_terms = set(re.findall(r"[a-z0-9]+", _normalize(title))) - GENERIC_TITLE_TERMS
        ranked.append((len(query_terms & title_terms), title))
    ranked.sort(reverse=True)
    if ranked and ranked[0][0] >= 2 and (len(ranked) == 1 or ranked[0][0] > ranked[1][0]):
        return [ranked[0][1]]
    return []

def _confident_candidate(candidates: list[dict[str, object]]) -> list[str]:
    title = confident_title(candidates)
    return [title] if title else []

def _history_choice(question: str, history: list[dict[str, str]], catalog: list[str]) -> list[str]:
    normalized = _normalize(question).strip(" .,!?")
    ordinal_map = {"1": 0, "option 1": 0, "opcion 1": 0, "the first one": 0, "la primera": 0, "2": 1, "option 2": 1, "opcion 2": 1, "the second one": 1, "la segunda": 1, "3": 2, "option 3": 2, "opcion 3": 2, "the third one": 2, "la tercera": 2, "4": 3, "option 4": 3, "opcion 4": 3}
    if normalized not in ordinal_map:
        return []
    assistant_messages = [item.get("content", "") for item in history if item.get("role") == "assistant"]
    if not assistant_messages:
        return []
    last_message = assistant_messages[-1]
    mentioned = [title for title in catalog if title in last_message]
    index = ordinal_map[normalized]
    return [mentioned[index]] if index < len(mentioned) else []

def _explicit_procedure_intent(question: str, catalog: list[str]) -> list[str]:
    normalized = _normalize(question)
    terms = set(re.findall(r"[a-z0-9]+", normalized))
    installation_words = {"setup", "install", "installation", "instalar", "instalo", "instalacion", "configurar"}
    new_words = {"new", "nuevo", "nueva"}
    registration_words = {"register", "registration", "registering", "registrar", "registro"}
    installation_title = "NCR - POS complete, installation process"
    registration_title = "NCR - Registering a device for the POS"
    if "pos" in terms and terms & new_words and terms & installation_words and installation_title in catalog:
        return [installation_title]
    if terms & registration_words and terms & {"pos", "device", "dispositivo"} and registration_title in catalog:
        return [registration_title]
    return []

def _contextual_follow_up(question: str, history: list[dict[str, str]], catalog: list[str]) -> dict[str, object] | None:
    normalized = _normalize(question).strip(" .,!?")
    assistant_messages = [item.get("content", "") for item in history if item.get("role") == "assistant"]
    if not assistant_messages:
        return None
    last = assistant_messages[-1]
    installation = "NCR - POS complete, installation process"
    registration = "NCR - Registering a device for the POS"
    both_shown = installation in last and registration in last
    if not both_shown:
        return None
    asks_difference = any(phrase in normalized for phrase in {"cual es la diferencia", "que diferencia", "what is the difference", "whats the difference", "difference"})
    only_ncr = normalized in {"ncr", "es ncr", "its ncr", "it is ncr"}
    if asks_difference:
        language = _language(question)
        reply = (
            f"Ambos procedimientos son para NCR, pero tienen objetivos distintos:\n\n"
            f"1. {registration}: se usa cuando el POS ya está configurado y necesitas registrar o vincular el dispositivo con la tienda/servidor NCR.\n"
            f"2. {installation}: se usa para configurar un POS nuevo desde el inicio e incluye el proceso completo de instalación y sus periféricos.\n\n"
            "Como indicaste que es un POS nuevo, corresponde la opción 2. ¿Quieres que te muestre el procedimiento completo?"
            if language == "es"
            else
            f"Both procedures are for NCR, but they serve different purposes:\n\n"
            f"1. {registration}: use this when the POS is already configured and you need to register or link the device to the NCR store/server.\n"
            f"2. {installation}: use this to configure a new POS from the beginning, including the complete installation and peripherals.\n\n"
            "Because you said this is a new POS, option 2 applies. Would you like the complete procedure?"
        )
        return {"mode": "clarify", "language": language, "clarification_question": reply, "selected_titles": []}
    if only_ncr:
        language = _language(" ".join(item.get("content", "") for item in history[-2:]) + " " + question)
        reply = (
            "Ambas opciones son para NCR. Necesito saber el objetivo: ¿vas a configurar un POS nuevo desde cero (opción 2) o registrar un dispositivo ya configurado (opción 1)?"
            if language == "es"
            else "Both options are for NCR. I need the goal: are you setting up a new POS from scratch (option 2), or registering an already configured device (option 1)?"
        )
        return {"mode": "clarify", "language": language, "clarification_question": reply, "selected_titles": []}
    return None

def _ambiguity_question(candidates: list[dict[str, object]], language: str) -> str:
    if len(candidates) < 2:
        return ""
    best_score = float(candidates[0].get("score", 0.0))
    close = [item for item in candidates if best_score - float(item.get("score", 0.0)) <= 0.08 and float(item.get("score", 0.0)) >= 0.45][:4]
    if len(close) < 2:
        return ""
    options = "\n".join(f"{index}. {item['source']}" for index, item in enumerate(close, 1))
    lead = "Encontré varios procedimientos posibles. ¿Cuál necesitas?" if language == "es" else "I found several possible procedures. Which one do you need?"
    return f"{lead}\n\n{options}"

def route(
    question: str,
    history: list[dict[str, str]],
    catalog: list[str],
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    direct = _basic_chat(question)
    if direct:
        return direct
    contextual = _contextual_follow_up(question, history, catalog)
    if contextual:
        return contextual
    history_choice = _history_choice(question, history, catalog)
    if history_choice:
        return {"mode": "support", "language": _language(question + " " + " ".join(item.get("content", "") for item in history[-2:])), "normalized_request": question, "selected_titles": history_choice}
    scoped = resolve_scope(question, catalog, history)
    if scoped and scoped["decision"] == "select":
        return {"mode": "support", "language": "en", "normalized_request": question, "selected_titles": [scoped["title"]], "scope": scoped["scope"]}
    if scoped and scoped["decision"] == "clarify":
        return {"mode": "clarify", "language": "en", "clarification_question": scoped["question"], "selected_titles": [], "scope": scoped["scope"]}
    explicit = _explicit_procedure_intent(question, catalog)
    if explicit:
        return {"mode": "support", "language": _language(question), "normalized_request": question, "selected_titles": explicit}
    confident = _confident_candidate(candidates)
    if confident:
        return {"mode": "support", "language": _language(question), "normalized_request": question, "selected_titles": confident}
    ambiguity = _ambiguity_question(candidates, _language(question))
    if ambiguity:
        return {"mode": "clarify", "language": _language(question), "clarification_question": ambiguity, "selected_titles": []}
    try:
        plan = generate_chat_plan(question, history, catalog, candidates)
        mode = str(plan.get("mode", "clarify")).lower()
        raw_selected = plan.get("selected_titles", [])
        selected = [title for title in raw_selected if title in catalog] if isinstance(raw_selected, list) else []
        if mode == "support" and selected:
            return {**plan, "mode": "support", "selected_titles": selected}
        if mode == "chat" and str(plan.get("reply", "")).strip():
            return {**plan, "mode": "chat", "selected_titles": []}
        question_text = str(plan.get("clarification_question", "")).strip()
        if question_text:
            return {**plan, "mode": "clarify", "selected_titles": []}
    except Exception:
        pass
    selected = _lexical_fallback(question, catalog)
    if selected:
        return {"mode": "support", "language": _language(question), "normalized_request": question, "selected_titles": selected}
    language = _language(question)
    clarification = (
        "Quiero asegurarme de darte el procedimiento correcto. ¿Qué sistema, dispositivo o cambio necesitas realizar?"
        if language == "es"
        else "I want to make sure I give you the correct procedure. Which system, device, or change do you need help with?"
    )
    return {"mode": "clarify", "language": language, "clarification_question": clarification, "selected_titles": []}
