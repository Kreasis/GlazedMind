"""Selects validated Knowledge Base documents for the current turn."""
from app.agents.conversation_router_agent import route
from app.agents.knowledge_retriever import retrieve

def select(question: str, history: list[dict[str, str]]) -> dict[str, object]:
    retrieved = retrieve(question)
    plan = route(question, history, retrieved["catalog"], retrieved["candidates"])
    return {**plan, "candidates": retrieved["candidates"]}
