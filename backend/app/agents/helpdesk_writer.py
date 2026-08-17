"""Adds Help Desk tone around immutable procedure sections."""

def present(language: str, sections: list[dict[str, object]]) -> dict[str, str]:
    count = sum(len(section.get("steps", [])) for section in sections)
    if language == "es":
        return {
            "answer": f"Encontré el procedimiento verificado en la documentación. A continuación tienes los {count} pasos completos, conservados en su orden original.",
            "follow_up": "Si algún resultado no coincide con la guía, dime en qué paso ocurrió y lo revisamos.",
        }
    return {
        "answer": f"I found the verified procedure in the documentation. Below are all {count} steps, preserved in their original order.",
        "follow_up": "If any result differs from the guide, tell me which step you reached and we’ll review it.",
    }
