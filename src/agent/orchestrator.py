from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.analytics.tools import AnalyticsTools
from src.config import get_settings
from src.llm.client import LLMClient
from src.retrieve.hybrid import HybridRetriever


SYSTEM_PROMPT = """You are a scientific publications analyst agent.
Answer ONLY using the provided TOOL RESULTS and/or RETRIEVED SOURCES.
If evidence is missing, say you do not know from the current database.
Always cite sources as [title (year)] when using retrieved publications.
Respond in the same language as the user question (Polish or English).
Be concise and factual. Do not invent institutions, citations, or years.
"""


@dataclass
class AgentResponse:
    answer: str
    intent: str
    sources: list[dict] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)
    chart: Optional[dict] = None


def classify_intent(question: str) -> str:
    q = question.lower()
    # Prefer listing coauthors of a person; avoid "who co-authored <paper topic>"
    if re.search(r"wsp[oó][lł]autor(?:zy|ów)?", q) or re.search(
        r"co-?authors?\s+of\b", q
    ):
        return "coauthor"
    if re.search(
        r"profil autora|author profile|kto (jest|napisa)|publications by|"
        r"profil\s+autora|\bauthor\b.*\bprofile\b",
        q,
    ):
        return "author"
    if re.search(r"trend|popularno[sś][cć]|top topic|najpopular|dominuj[aą]c|kierunk", q):
        return "trend"
    if re.search(r"temat|topic|klasyfik|cluster", q) and re.search(
        r"ile|list|top|najcz[eę]|domin", q
    ):
        return "trend"
    return "semantic"


def _extract_year(question: str) -> Optional[int]:
    m = re.search(r"\b(19|20)\d{2}\b", question)
    return int(m.group(0)) if m else None


def _extract_author_query(question: str) -> str:
    patterns = [
        r"wsp[oó][lł]autor(?:zy|ów)?(?:\s+dla)?\s+(.+)$",
        r"co-?authors?(?:\s+of)?\s+(.+)$",
        r"profil(?:\s+autora)?\s+(.+)$",
        r"author(?:\s+profile)?\s+(.+)$",
        r"publikacje\s+(.+)$",
        r"publications?\s+by\s+(.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, question, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" ?.,")
    # Fallback: last capitalized tokens
    tokens = re.findall(r"[A-ZÁĄĆĘŁŃÓŚŹŻ][\wÁĄĆĘŁŃÓŚŹŻáąćęłńóśźż\-]+", question)
    if tokens:
        return " ".join(tokens[-2:])
    return question.strip()


def _extract_topic_query(question: str) -> str:
    m = re.search(
        r"(?:temat(?:u|cie)?|topic|trend(?:y|zie)?(?:\s+dla)?)\s+(.+)$",
        question,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(" ?.,")
    # strip stopwords-ish
    cleaned = re.sub(
        r"\b(jaki|jakie|jak|jest|są|the|what|are|is|trend|trendy|temat|topic)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" ?.,") or question


class AgentOrchestrator:
    def __init__(
        self,
        retriever: HybridRetriever,
        analytics: AnalyticsTools,
        llm: Optional[LLMClient] = None,
    ):
        self.retriever = retriever
        self.analytics = analytics
        self.llm = llm or LLMClient()
        self.settings = get_settings()

    def ask(
        self,
        question: str,
        top_k: Optional[int] = None,
        year: Optional[int] = None,
        history: Optional[list[dict]] = None,
    ) -> AgentResponse:
        top_k = top_k or self.settings.retrieval_top_k
        intent = classify_intent(question)
        year = year or _extract_year(question)
        tool_results: dict[str, Any] = {}
        sources: list[dict] = []
        chart: Optional[dict] = None

        where = None
        if year is not None:
            where = {"year": {"$eq": year}}

        if intent == "trend":
            topic = _extract_topic_query(question)
            if re.search(r"top|najpopular|dominuj", question, re.I) or not topic:
                tool_results["top_topics"] = self.analytics.top_topics(year=year, n=10)
                chart = {
                    "type": "bar",
                    "title": "Top topics",
                    "data": tool_results["top_topics"]["topics"],
                }
            else:
                tool_results["topic_trend"] = self.analytics.topic_trend(
                    topic, year_from=None, year_to=None
                )
                chart = {
                    "type": "line",
                    "title": f"Trend: {topic}",
                    "data": tool_results["topic_trend"]["series"],
                }
            # Also retrieve a few example pubs for grounding
            sources = self.retriever.search(question, top_k=top_k, where=where)

        elif intent == "author":
            name = _extract_author_query(question)
            tool_results["author_profile"] = self.analytics.author_profile(name)
            sources = self.retriever.search(name, top_k=top_k)

        elif intent == "coauthor":
            name = _extract_author_query(question)
            tool_results["coauthor_graph"] = self.analytics.coauthor_graph(name, depth=1)
            sources = []

        else:
            sources = self.retriever.search(question, top_k=top_k, where=where)
            tool_results["search_publications"] = {
                "n": len(sources),
                "ids": [s["metadata"].get("object_id") for s in sources],
            }

        answer = self._synthesize(question, intent, sources, tool_results, history or [])
        return AgentResponse(
            answer=answer,
            intent=intent,
            sources=sources,
            tool_results=tool_results,
            chart=chart,
        )

    def _synthesize(
        self,
        question: str,
        intent: str,
        sources: list[dict],
        tool_results: dict[str, Any],
        history: list[dict],
    ) -> str:
        context_blocks = []
        for i, s in enumerate(sources, start=1):
            meta = s.get("metadata") or {}
            context_blocks.append(
                f"[{i}] {meta.get('title')} ({meta.get('year')})\n{s.get('text', '')[:1200]}"
            )
        context = "\n\n".join(context_blocks) if context_blocks else "(no retrieved sources)"
        tools_json = json.dumps(tool_results, ensure_ascii=False, indent=2)[:8000]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in history[-6:]:
            messages.append(turn)
        messages.append(
            {
                "role": "user",
                "content": (
                    f"INTENT: {intent}\nQUESTION: {question}\n\n"
                    f"TOOL RESULTS:\n{tools_json}\n\n"
                    f"RETRIEVED SOURCES:\n{context}\n\n"
                    "Write the final answer."
                ),
            }
        )

        try:
            return self.llm.chat(messages)
        except Exception as exc:
            return self._fallback_answer(intent, sources, tool_results, error=str(exc))

    def _fallback_answer(
        self,
        intent: str,
        sources: list[dict],
        tool_results: dict[str, Any],
        error: str = "",
    ) -> str:
        lines = [
            "(LLM niedostępny — odpowiedź deterministyczna z narzędzi/RAG.)",
        ]
        if error:
            lines.append(f"Powód: {error}")
        if intent == "trend" and "top_topics" in tool_results:
            topics = tool_results["top_topics"].get("topics") or []
            if not topics:
                lines.append("Brak tematów w bazie.")
            else:
                lines.append("Najczęstsze tematy:")
                for t in topics:
                    lines.append(f"- {t['label']} (n={t['count']})")
        elif intent == "trend" and "topic_trend" in tool_results:
            tr = tool_results["topic_trend"]
            lines.append(f"Temat: {tr.get('topic')}, łącznie publikacji: {tr.get('total')}")
            if tr.get("note"):
                lines.append(tr["note"])
            for p in tr.get("series") or []:
                lines.append(f"- {p['year']}: {p['count']}")
        elif intent == "author" and "author_profile" in tool_results:
            matches = tool_results["author_profile"].get("matches") or []
            if not matches:
                lines.append("Nie znaleziono autora.")
            else:
                m = matches[0]
                lines.append(f"Autor: {m['name']}")
                lines.append(f"Liczba publikacji: {len(m['publications'])}")
                for p in m["publications"][:8]:
                    lines.append(f"- {p['title']} ({p['year']})")
                if m.get("coauthors"):
                    lines.append("Współautorzy: " + ", ".join(c["name"] for c in m["coauthors"][:8]))
        elif intent == "coauthor" and "coauthor_graph" in tool_results:
            g = tool_results["coauthor_graph"]
            lines.append(f"Węzły: {len(g.get('nodes') or [])}, krawędzie: {len(g.get('edges') or [])}")
            for n in (g.get("nodes") or [])[:15]:
                lines.append(f"- {n['name']}")
        else:
            if not sources:
                lines.append("Brak trafień w indeksie.")
            else:
                lines.append("Najbliższe publikacje:")
                for s in sources[:5]:
                    meta = s.get("metadata") or {}
                    authors = meta.get("author_names") or ""
                    suffix = f" — {authors.replace('|', ', ')}" if authors else ""
                    lines.append(f"- {meta.get('title')} ({meta.get('year')}){suffix}")
                    snippet = (s.get("text") or "")[:280]
                    if snippet:
                        lines.append(f"  {snippet}")
        return "\n".join(lines)
