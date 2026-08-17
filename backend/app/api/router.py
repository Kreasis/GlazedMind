from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.knowledge import search
from app.services.monday import fetch_board, fetch_tickets
from app.services.monday import acknowledge_ticket
from app.services.acknowledgment import create_acknowledgment
from app.agents.chatbot_agent import answer as chatbot_answer
from app.agents.workspace_ticket_agent import troubleshoot as workspace_troubleshoot
from app.services.knowledge_upload import catalog as knowledge_catalog, ingest as ingest_knowledge
from app.services.activity import append_activity, impact_metrics, timeline
from app.services.support_portal import add_customer_message, create_case, get_case
from app.services.runtime import runtime_summary

api_router = APIRouter()

class KnowledgeQuestion(BaseModel):
    question: str
    history: list[dict[str, str]] = Field(default_factory=list)
    ticket_id: str | None = None

class AcknowledgmentInput(BaseModel):
    item_id: str
    ticket: dict[str, object]

class SupportCaseInput(BaseModel):
    store_code: str
    customer_name: str
    customer_email: str
    subject: str
    description: str
    request_type: str = "Question"
    priority: str = "Medium Priority"

class SupportMessageInput(BaseModel):
    access_token: str
    message: str

@api_router.get("/modules")
def list_modules() -> dict[str, object]:
    """Describe the modules that are actually available in this build."""
    return {
        "runtime": runtime_summary(),
        "modules": [
            {"name": "Monday Intake & Acknowledgment", "status": "active"},
            {"name": "Workspace Troubleshooting", "status": "active"},
            {"name": "Documentation Chatbot", "status": "active"},
            {"name": "Dynamic Knowledge Base", "status": "active"},
            {"name": "Priority Follow-up Automation", "status": "active"},
            {"name": "Customer Portal", "status": "active"},
            {"name": "Onboarding & Skill Gaps", "status": "active-demo"},
            {"name": "Escalation Directory", "status": "active"},
            {"name": "Impact Dashboard", "status": "active-demo"},
            {"name": "Similar Resolved Cases", "status": "planned"},
            {"name": "Knowledge Learning Loop", "status": "planned"},
        ],
    }

@api_router.get("/tickets")
def monday_tickets(group: str = "Open Tickets") -> dict[str, object]:
    try:
        board = fetch_board()
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    items = [item for item in board["items"] if str(item.get("group", "")).lower() == group.lower()]
    return {"source": "monday", "group": group, "groups": board["groups"], "tickets": items}

@api_router.post("/tickets/acknowledge")
def acknowledge(input: AcknowledgmentInput) -> dict[str, object]:
    try:
        message = create_acknowledgment(input.ticket)
        return acknowledge_ticket(input.item_id, message, "In Progress")
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

@api_router.get("/knowledge/search")
def knowledge_search(query: str) -> dict[str, object]:
    return {"query": query, "results": search(query)}

@api_router.get("/knowledge/documents")
def list_knowledge_documents() -> dict[str, object]:
    try:
        return {"documents": knowledge_catalog()}
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

@api_router.post("/knowledge/documents")
async def upload_knowledge_document(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        return await ingest_knowledge(file)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"The document could not be indexed: {error}") from error

@api_router.post("/chatbot/ask")
def ask_chatbot(input: KnowledgeQuestion) -> dict[str, object]:
    return chatbot_answer(input.question, input.history)

@api_router.post("/workspace/troubleshoot")
def troubleshoot_workspace_ticket(input: KnowledgeQuestion) -> dict[str, object]:
    result = workspace_troubleshoot(input.question)
    if input.ticket_id:
        sections = list(result.get("sections", []))
        sources = [str(source) for source in result.get("sources", [])]
        step_count = sum(len(section.get("steps", [])) for section in sections if isinstance(section, dict))
        if step_count > 0:
            procedure_key = f"procedure:{step_count}:{'|'.join(sorted(sources))}"
            append_activity(
                input.ticket_id,
                "knowledge_retrieved",
                "Verified procedure prepared",
                f"{step_count} documented steps retrieved from {', '.join(sources) if sources else 'the Knowledge Base'}.",
                metadata={"steps": step_count, "sources": sources},
                dedupe_key=procedure_key,
            )
        else:
            append_activity(
                input.ticket_id,
                "no_procedure_match",
                "No documented procedure matched",
                "The Knowledge Base did not return a verified procedure for this request.",
                metadata={"steps": 0, "sources": []},
                dedupe_key="no-procedure-match",
            )
    return result

@api_router.get("/operations/activity")
def ticket_activity(ticket_id: str) -> dict[str, object]:
    return {"ticket_id": ticket_id, "events": timeline(ticket_id)}

@api_router.get("/operations/metrics")
def operations_metrics() -> dict[str, object]:
    return impact_metrics()

@api_router.post("/support/cases")
def create_support_case(input: SupportCaseInput) -> dict[str, object]:
    try:
        return create_case(input.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"The support request could not be created: {error}") from error

@api_router.get("/support/cases/{case_id}")
def read_support_case(case_id: str, access_token: str) -> dict[str, object]:
    try:
        return get_case(case_id, access_token)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

@api_router.post("/support/cases/{case_id}/messages")
def post_support_message(case_id: str, input: SupportMessageInput) -> dict[str, object]:
    try:
        return add_customer_message(case_id, input.access_token, input.message)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"The message could not be delivered: {error}") from error
