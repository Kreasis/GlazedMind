from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.router import api_router
from app.services.auto_ack import start_auto_ack, stop_auto_ack
from app.services.auto_followup import start_auto_followup, stop_auto_followup
from app.services.vector_store import ensure_schema
from app.services.runtime import runtime_summary

app = FastAPI(title="Glazed Mind API", version="0.1.0", description="AI Help Desk Copilot API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix="/api/v1")
knowledge_images = Path(__file__).resolve().parent.parent / "data" / "knowledge_images"
knowledge_images.mkdir(parents=True, exist_ok=True)
app.mount("/knowledge-images", StaticFiles(directory=knowledge_images), name="knowledge-images")

@app.on_event("startup")
def start_background_services() -> None:
    start_auto_ack()
    start_auto_followup()
    ensure_schema()

@app.on_event("shutdown")
def stop_background_services() -> None:
    stop_auto_ack()
    stop_auto_followup()

@app.get("/health")
def health_check() -> dict[str, object]:
    return {"status": "ok", "service": "glazed-mind-api", "runtime": runtime_summary()}
