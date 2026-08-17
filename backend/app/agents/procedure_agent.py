"""Builds immutable, complete procedures from exact selected documents."""
from app.services.knowledge import document_by_title, document_step_records

def assemble(selected_titles: list[str]) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    for title in selected_titles:
        document = document_by_title(title)
        if not document:
            continue
        records = document_step_records(document)
        if not records:
            continue
        if any(record.get("section") for record in records):
            grouped: dict[str, dict[str, object]] = {}
            for record in records:
                section_title = str(record.get("section") or "Procedure")
                section = grouped.setdefault(section_title, {"title": section_title, "source": title, "steps": [], "step_images": [], "notices": []})
                if str(record.get("kind", "step")) == "step":
                    section["steps"].append(str(record["text"]))
                    section["step_images"].append(list(record.get("images", [])))
                else:
                    section["notices"].append({"kind": str(record.get("kind")), "text": str(record["text"])})
            sections.extend(section for section in grouped.values() if section["steps"] or section["notices"])
        else:
            sections.append({
                "title": title,
                "source": title,
                "steps": [str(record["text"]) for record in records],
                "step_images": [list(record.get("images", [])) for record in records],
                "notices": [],
            })
    return sections
