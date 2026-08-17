"""PostgreSQL/pgvector persistence for the dynamic Knowledge Base."""

import os

import psycopg
from psycopg.types.json import Jsonb
from openai import OpenAI

def _dsn() -> str:
    return os.getenv("DATABASE_URL", "postgresql://glazed:glazed@postgres:5432/glazed_mind").replace("postgresql+psycopg://", "postgresql://")

def _client() -> OpenAI:
    base = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError("OLLAMA_BASE_URL is required for local embeddings")
    return OpenAI(api_key=os.getenv("OLLAMA_API_KEY", "ollama"), base_url=f"{base}/v1" if not base.endswith("/v1") else base, timeout=20.0, max_retries=0)

def ensure_schema() -> None:
    with psycopg.connect(_dsn()) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                steps JSONB NOT NULL DEFAULT '[]'::jsonb,
                images JSONB NOT NULL DEFAULT '[]'::jsonb,
                embedding vector
            )
        """)
        connection.commit()

def _embed(text: str) -> list[float]:
    model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    response = _client().embeddings.create(model=model, input=text)
    return response.data[0].embedding

def search_vector(query: str, limit: int = 3) -> list[dict[str, object]]:
    ensure_schema()
    embedding = _embed(query)
    with psycopg.connect(_dsn()) as connection:
        rows = connection.execute(
            "SELECT title, filename, content, steps, images, (embedding <=> %s::vector) AS distance FROM knowledge_chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT %s",
            (embedding, embedding, limit),
        ).fetchall()
    return [{"source": row[0], "filename": row[1], "excerpt": row[2][:550], "steps": row[3], "images": row[4], "score": round(1 - float(row[5]), 4)} for row in rows]

def documents() -> list[dict[str, object]]:
    """Return the persisted knowledge documents without a file fallback."""
    ensure_schema()
    with psycopg.connect(_dsn()) as connection:
        rows = connection.execute("SELECT title, filename, content, steps, images FROM knowledge_chunks ORDER BY id").fetchall()
    return [{"title": row[0], "filename": row[1], "content": row[2], "steps": row[3], "images": row[4]} for row in rows]

def replace_documents(documents_to_store: list[dict[str, object]]) -> int:
    """Atomically replace the persisted Knowledge Base after all embeddings succeed."""
    ensure_schema()
    prepared: list[tuple[object, ...]] = []
    for document in documents_to_store:
        embedding = _embed(f"{document['title']}\n{document['content']}")
        prepared.append((
            document["title"],
            document["filename"],
            document["content"],
            Jsonb(document.get("steps", [])),
            Jsonb(document.get("images", [])),
            embedding,
        ))
    with psycopg.connect(_dsn()) as connection:
        connection.execute("DELETE FROM knowledge_chunks")
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO knowledge_chunks (title, filename, content, steps, images, embedding) VALUES (%s, %s, %s, %s, %s, %s::vector)",
                prepared,
            )
        connection.commit()
    return len(prepared)

def upsert_document(document: dict[str, object]) -> None:
    """Embed and replace one document without rebuilding the remaining Knowledge Base."""
    ensure_schema()
    embedding = _embed(f"{document['title']}\n{document['content']}")
    with psycopg.connect(_dsn()) as connection:
        connection.execute(
            "DELETE FROM knowledge_chunks WHERE filename = %s OR title = %s",
            (document["filename"], document["title"]),
        )
        connection.execute(
            "INSERT INTO knowledge_chunks (title, filename, content, steps, images, embedding) VALUES (%s, %s, %s, %s, %s, %s::vector)",
            (
                document["title"], document["filename"], document["content"],
                Jsonb(document.get("steps", [])), Jsonb(document.get("images", [])), embedding,
            ),
        )
        connection.commit()
