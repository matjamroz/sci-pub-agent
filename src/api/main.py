from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import get_settings
from src.pipeline import build_index, get_runtime

app = FastAPI(
    title="Sci-Pub Agent API",
    description="RAG agent for trends and dependencies in scientific publications",
    version="0.1.0",
)

_runtime = None


def runtime():
    global _runtime
    if _runtime is None:
        _runtime = get_runtime()
    return _runtime


class AskRequest(BaseModel):
    question: str
    top_k: Optional[int] = None
    year: Optional[int] = None
    history: list[dict[str, str]] = Field(default_factory=list)


class IngestRequest(BaseModel):
    jsonl_path: Optional[str] = None
    reset: bool = True
    n_clusters: Optional[int] = None


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    try:
        rt = runtime()
        n = rt.store.count_publications()
        span = rt.store.year_span()
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)}
    return {
        "status": "ok",
        "publications": n,
        "year_span": span,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
    }


@app.post("/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    rt = runtime()
    result = rt.agent.ask(
        req.question,
        top_k=req.top_k,
        year=req.year,
        history=req.history,
    )
    return {
        "answer": result.answer,
        "intent": result.intent,
        "sources": result.sources,
        "tool_results": result.tool_results,
        "chart": result.chart,
    }


@app.post("/ingest")
def ingest(req: IngestRequest) -> dict[str, Any]:
    global _runtime
    path = Path(req.jsonl_path) if req.jsonl_path else None
    try:
        summary = build_index(
            jsonl_path=path,
            reset=req.reset,
            n_clusters=req.n_clusters,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _runtime = None  # reload on next request
    return {"status": "ok", "summary": summary}
