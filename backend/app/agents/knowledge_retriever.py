"""Hybrid Knowledge Base retrieval. Candidates are evidence, not final selections."""
import re
import unicodedata

from app.services.knowledge import _documents, search
from app.agents.procedure_scope import metadata_for

TERM_MAP = {
    "instalo": "installation", "instalar": "installation", "instalacion": "installation", "intalacion": "installation", "install": "installation",
    "setup": "installation", "setups": "installation",
    "configuro": "configuring", "configurar": "configuring", "configure": "configuring",
    "registro": "registering", "registrar": "registering", "register": "registering",
    "nuevo": "new", "nueva": "new", "precio": "price", "precios": "price", "cambiar": "change", "cambio": "change", "cambios": "change",
    "update": "change", "updated": "change", "updating": "change", "modify": "change", "modifying": "change",
    "impresora": "printer", "impresoras": "printer", "cocina": "kitchen", "recibo": "receipt", "recibos": "receipt",
    "procesador": "processor", "credito": "credit", "cajon": "drawer", "efectivo": "cash",
    "horario": "hours", "horarios": "hours", "horas": "hours", "tienda": "store",
    "agregar": "add", "anadir": "add", "eliminar": "remove", "remover": "remove", "removed": "remove", "removing": "remove",
    "articulo": "item", "articulos": "item", "producto": "item", "productos": "item",
    "contrasena": "password", "restablecer": "reset", "fecha": "date", "hora": "time",
    "pedidos": "ordering", "pedido": "ordering", "onliner": "online", "promocion": "promotions", "promociones": "promotions",
    "dispositivo": "device", "dispositivos": "device", "red": "network", "lista": "whitelist", "blanca": "whitelist",
}
STOP_TERMS = {"a", "an", "the", "to", "for", "of", "in", "on", "and", "or", "how", "do", "i", "my", "is", "not", "working", "como", "se", "un", "una", "el", "la", "los", "las", "de", "en", "quiero", "necesito", "hacer", "tengo", "ayuda", "con"}

def _terms(value: str) -> set[str]:
    # Uploaded guides often arrive with filenames such as
    # ``HandlingRefunds&Voids.docx``. Split CamelCase before lowercasing so a
    # new document can be matched without adding its title to a static map.
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    normalized = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[a-z0-9]+", normalized)
    terms: set[str] = set()
    for word in words:
        if word in STOP_TERMS:
            continue
        mapped = TERM_MAP.get(word, word)
        terms.add(mapped)
        # Keep lightweight singular aliases for filenames/headings. This is
        # intentionally additive: the original term remains available.
        if len(mapped) > 3 and mapped.endswith("s") and not mapped.endswith("ss"):
            terms.add(mapped[:-1])
    return terms

def retrieve(question: str, limit: int = 6) -> dict[str, object]:
    documents = _documents()
    vector_results = search(question, limit)
    vector_scores = {str(item["source"]): float(item.get("score", 0)) for item in vector_results}
    query_terms = _terms(question)
    ranked: list[dict[str, object]] = []
    for document in documents:
        title = str(document["title"])
        title_terms = _terms(title)
        content_terms = _terms(str(document.get("content", "")))
        denominator = max(len(query_terms), 1)
        title_coverage = len(query_terms & title_terms) / denominator
        content_coverage = len(query_terms & content_terms) / denominator
        vector_score = max(vector_scores.get(title, 0.0), 0.0)
        combined = (0.58 * title_coverage) + (0.27 * content_coverage) + (0.15 * vector_score)
        ranked.append({
            "source": title,
            **metadata_for(title),
            "score": round(combined, 4),
            "title_coverage": round(title_coverage, 4),
            "content_coverage": round(content_coverage, 4),
            "vector_score": round(vector_score, 4),
        })
    ranked.sort(key=lambda item: float(item["score"]), reverse=True)
    return {
        "query": question,
        "catalog": [str(document["title"]) for document in documents],
        "candidates": ranked[:limit],
    }


def confident_title(candidates: list[dict[str, object]]) -> str | None:
    """Return one clearly dominant dynamic result for every consumer.

    Chatbot and Workspace must not apply different confidence thresholds to
    the same pgvector retrieval. A result is accepted only when it has strong
    lexical/semantic evidence and a clear lead over the next candidate.
    """
    if not candidates:
        return None
    best = candidates[0]
    best_score = float(best.get("score", 0.0))
    second_score = float(candidates[1].get("score", 0.0)) if len(candidates) > 1 else 0.0
    margin = best_score - second_score
    title_coverage = float(best.get("title_coverage", 0.0))
    content_coverage = float(best.get("content_coverage", 0.0))
    vector_score = float(best.get("vector_score", 0.0))

    high_combined_confidence = best_score >= 0.50 and margin >= 0.12
    corroborated_dynamic_match = (
        title_coverage >= 0.34
        and content_coverage >= 0.34
        and vector_score >= 0.55
        and margin >= 0.12
    )
    if high_combined_confidence or corroborated_dynamic_match:
        return str(best["source"])
    return None
