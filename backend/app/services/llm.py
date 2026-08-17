"""Grounded OpenAI resolution generation for the hackathon demo."""

import json
import os
from pathlib import Path

from openai import OpenAI

POLICY_PATH = Path(__file__).resolve().parents[2] / "prompts" / "helpdesk_response_policy.md"
ROUTER_POLICY_PATH = Path(__file__).resolve().parents[2] / "prompts" / "chatbot_router_agent.md"

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "before_you_start": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}},
        "verify": {"type": "array", "items": {"type": "string"}},
        "escalation_needed": {"type": "boolean"},
        "escalation_reason": {"type": "string"},
        "draft_response": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["summary", "before_you_start", "steps", "verify", "escalation_needed", "escalation_reason", "draft_response", "confidence"],
    "additionalProperties": False,
}

def generate_resolution(question: str, sources: list[dict[str, object]], contacts: dict[str, str] | None) -> dict[str, object]:
    ollama_url = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    use_ollama = bool(ollama_url)
    api_key = (os.getenv("OLLAMA_API_KEY", "") if use_ollama else os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY or OPENAI_API_KEY is not configured")
    model = os.getenv("OLLAMA_MODEL" if use_ollama else "OPENAI_MODEL", "") or ("llama3.1" if use_ollama else "gpt-5.6")
    context = json.dumps({"ticket": question, "guides": sources, "escalation_contacts": contacts}, ensure_ascii=False)
    policy = POLICY_PATH.read_text(encoding="utf-8") if POLICY_PATH.exists() else ""
    instructions = f"""{policy}

Use the retrieved guides and contacts as the only factual source. Return only the requested JSON object. The `steps` array must contain the complete procedure in one response, with every operational action preserved."""
    client = OpenAI(api_key=api_key, base_url=f"{ollama_url}/v1" if use_ollama and not ollama_url.endswith("/v1") else (ollama_url or None))
    if use_ollama:
        response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": instructions}, {"role": "user", "content": context}], response_format={"type": "json_object"}, temperature=0.2)
        return json.loads(response.choices[0].message.content or "{}")
    response = client.responses.create(model=model, instructions=instructions, input=context, reasoning={"effort": "medium"}, store=False, text={"format": {"type": "json_schema", "name": "glazed_mind_resolution", "strict": True, "schema": OUTPUT_SCHEMA}})
    return json.loads(response.output_text)

def generate_chat_response(question: str, history: list[dict[str, str]], sources: list[dict[str, object]]) -> dict[str, object]:
    """Generate a natural conversational reply grounded in the retrieved guides."""
    ollama_url = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    use_ollama = bool(ollama_url)
    api_key = (os.getenv("OLLAMA_API_KEY", "") if use_ollama else os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("No model API key configured")
    model = os.getenv("OLLAMA_MODEL" if use_ollama else "OPENAI_MODEL", "") or ("gemma4:latest" if use_ollama else "gpt-5.6")
    policy = POLICY_PATH.read_text(encoding="utf-8") if POLICY_PATH.exists() else ""
    context = json.dumps({"conversation": history[-10:], "new_question": question, "retrieved_guides": sources}, ensure_ascii=False)
    instructions = f"""You are the Glazed Mind Help Desk conversational assistant.
{policy}
Have a genuine, helpful conversation: acknowledge what the person said, answer the current question, and ask one short follow-up question when useful. Use only facts from retrieved guides; if the guides do not contain the answer, say so clearly and offer to help find the right procedure. If the user asks how to install, configure, register, or asks for steps, provide the complete documented procedure in the answer, preserving every operational step in order. Never invent a generic unverified installation process and never create a new protocol when a retrieved guide contains the procedure. Terminology is strict: GlazedMind is only the help desk assistant; the POS is NCR/NCR POS; Acumera, Acuvigil, and Scale are separate whitelist/network platforms. Never say “GlazedMind POS” or “GlazedMind (Acumera/Acuvigil/Scale)”. Return only JSON with keys: answer (string), follow_up (string), sources (array of guide titles)."""
    client = OpenAI(api_key=api_key, base_url=f"{ollama_url}/v1" if use_ollama and not ollama_url.endswith("/v1") else (ollama_url or None))
    if use_ollama:
        response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": instructions}, {"role": "user", "content": context}], response_format={"type": "json_object"}, temperature=0.35)
        return json.loads(response.choices[0].message.content or "{}")
    response = client.responses.create(model=model, instructions=instructions, input=context, store=False)
    return json.loads(response.output_text)

def _json_object(value: str) -> dict[str, object]:
    """Parse a JSON object even when a local model wraps it in a code fence."""
    value = value.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end < start:
        raise ValueError("The model did not return a JSON object")
    return json.loads(value[start:end + 1])

def generate_chat_plan(
    question: str,
    history: list[dict[str, str]],
    available_documents: list[str],
    vector_candidates: list[dict[str, object]],
) -> dict[str, object]:
    """Classify the turn and select exact document titles; never generate steps."""
    ollama_url = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    use_ollama = bool(ollama_url)
    api_key = (os.getenv("OLLAMA_API_KEY", "") if use_ollama else os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("No model API key configured")
    model = os.getenv("OLLAMA_MODEL" if use_ollama else "OPENAI_MODEL", "") or ("qwen3.5:4b" if use_ollama else "gpt-5.6")
    policy = ROUTER_POLICY_PATH.read_text(encoding="utf-8")
    payload = json.dumps(
        {
            "conversation": history[-10:],
            "current_message": question,
            "available_documents": available_documents,
            "vector_candidates": [
                {"title": item.get("source"), "score": item.get("score")}
                for item in vector_candidates
            ],
        },
        ensure_ascii=False,
    )
    timeout = float(os.getenv("OLLAMA_ROUTER_TIMEOUT_SECONDS", "12"))
    client = OpenAI(
        api_key=api_key,
        base_url=f"{ollama_url}/v1" if use_ollama and not ollama_url.endswith("/v1") else (ollama_url or None),
        timeout=timeout,
        max_retries=0,
    )
    if use_ollama:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": policy}, {"role": "user", "content": payload}],
            response_format={"type": "json_object"},
            temperature=0.0,
            extra_body={"think": False},
        )
        return _json_object(response.choices[0].message.content or "{}")
    response = client.responses.create(model=model, instructions=policy, input=payload, store=False)
    return _json_object(response.output_text)
