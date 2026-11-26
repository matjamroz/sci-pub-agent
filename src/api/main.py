from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import get_settings
from src.pipeline import build_index, get_runtime

app = FastAPI(
    title="Sci-Pub Agent API",
    description="RAG agent for trends and dependencies in scientific publications",
    version="0.1.0",
)


def _warm_search() -> None:
    """Load the vector model before the first question, so that question is not the one that pays for it."""
    try:
        rt = runtime()
        from src.embeddings import embed_texts

        embed_texts(["warmup"])
        # Load the language model at the context size used for answers,
        # so the first question is not the one that reloads it.
        rt.agent.llm.chat(
            [{"role": "user", "content": "ok"}],
            max_tokens=1,
        )
    except Exception:
        return


@app.on_event("startup")
def warm_search_on_startup() -> None:
    threading.Thread(target=_warm_search, daemon=True).start()

_runtime = None
_runtime_lock = threading.Lock()


def runtime():
    global _runtime
    if _runtime is None:
        with _runtime_lock:
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
        trend_span = rt.store.trend_year_span()
        directions = rt.store.count_directions()
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)}
    return {
        "status": "ok",
        "publications": n,
        "year_span": span,
        "trend_year_span": trend_span,
        "directions": directions,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
    }


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    def generate():
        box: dict[str, Any] = {}
        tokens: queue.Queue = queue.Queue()

        def worker() -> None:
            try:
                box["result"] = runtime().agent.ask(
                    req.question,
                    top_k=req.top_k,
                    year=req.year,
                    history=req.history,
                    on_token=tokens.put,
                )
            except Exception as exc:
                box["error"] = str(exc)
            tokens.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = tokens.get()
            if item is None:
                break
            yield json.dumps({"type": "token", "text": item}, ensure_ascii=False) + "\n"
        if box.get("error"):
            yield json.dumps(
                {"type": "error", "text": box["error"]}, ensure_ascii=False
            ) + "\n"
            return
        result = box["result"]
        yield json.dumps(
            {
                "type": "done",
                "answer": result.answer,
                "intent": result.intent,
                "sources": result.sources,
                "tool_results": result.tool_results,
                "chart": result.chart,
                "rewritten_query": result.rewritten_query,
            },
            ensure_ascii=False,
        ) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.post("/ask")
def ask(req: AskRequest) -> dict[str, Any]:
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
        "rewritten_query": result.rewritten_query,
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
