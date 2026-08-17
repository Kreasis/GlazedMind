"""Safe incremental DOCX ingestion for the dynamic Knowledge Base."""

import os
import re
import tempfile
from pathlib import Path

from fastapi import UploadFile

from app.services.knowledge import _documents
from app.services.vector_store import documents, upsert_document
from scripts.build_knowledge_index import extract_docx

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge-base"
IMAGE_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_images"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _safe_filename(filename: str) -> str:
    name = Path(filename or "").name.strip()
    if not name.lower().endswith(".docx"):
        raise ValueError("Only DOCX documents are supported.")
    if name.lower() == ".docx":
        raise ValueError("The document needs a valid filename.")
    stem = re.sub(r"[^A-Za-z0-9 _&().,'+-]", "", Path(name).stem).strip(" .")
    if not stem or not re.search(r"[A-Za-z0-9]", stem):
        raise ValueError("The document needs a valid filename.")
    return f"{stem}.docx"


async def ingest(upload: UploadFile) -> dict[str, object]:
    filename = _safe_filename(upload.filename or "")
    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise ValueError("The selected DOCX is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("The DOCX exceeds the 25 MB upload limit.")
    if not content.startswith(b"PK"):
        raise ValueError("The uploaded file is not a valid DOCX document.")

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    destination = KNOWLEDGE_DIR / filename
    # The Knowledge Base is a Docker bind mount while the system temp folder
    # lives on the container filesystem. ``os.replace`` cannot move a file
    # atomically across those filesystems (EXDEV / Errno 18). Keep the staging
    # directory beside the destination so validation and the final replace
    # always happen on the same filesystem.
    with tempfile.TemporaryDirectory(dir=KNOWLEDGE_DIR, prefix=".upload-") as temporary_directory:
        temporary_path = Path(temporary_directory) / filename
        temporary_path.write_bytes(content)
        try:
            raw_text, steps, images = extract_docx(temporary_path, IMAGE_DIR)
        except Exception as error:
            raise ValueError("The DOCX could not be read. Verify that it opens correctly in Word.") from error
        normalized_text = " ".join(raw_text.split())
        if not normalized_text or not steps:
            raise ValueError("The DOCX does not contain readable procedural content.")
        record = {
            "title": Path(filename).stem,
            "filename": filename,
            "content": normalized_text,
            "steps": steps,
            "images": images,
        }
        upsert_document(record)
        os.replace(temporary_path, destination)

    _documents.cache_clear()
    return {
        "title": record["title"],
        "filename": filename,
        "steps": len(steps),
        "images": len(images),
        "status": "indexed",
    }


def catalog() -> list[dict[str, object]]:
    return [
        {
            "title": str(document["title"]),
            "filename": str(document["filename"]),
            "steps": len(document.get("steps") or []),
            "images": len(document.get("images") or []),
        }
        for document in documents()
    ]
