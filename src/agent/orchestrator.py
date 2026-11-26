from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from src.analytics.tools import AnalyticsTools
from src.config import get_settings
from src.llm.client import LLMClient


class SupportsSearch(Protocol):
    def search(
        self,
        query: str,
        top_k: int = 10,
        where: Optional[dict] = None,
        **kwargs: Any,
    ) -> list[dict]: ...


SYSTEM_PROMPT = """Jesteś Sci-Pub Agent. Odpowiadasz na pytania o wczytany zbiór publikacji naukowych.

Zasady:
- Odpowiedz na OSTATNIE pytanie. Poprzedni temat zostaw, chyba że użytkownik mówi „ta praca”, „ten autor” albo „to samo”.
- Fakty bierz wyłącznie z listy źródeł i z wyników narzędzi. Nie dopisuj znaczenia, historii ani ocen, których nie ma w źródle.
- Pisz w języku pytania. Najwyżej cztery zdania albo krótka lista tytułów.
- Bez powitania, bez „witaj ponownie” i bez pytania na końcu.
- Cytuj tylko numery z listy, w formie [n] tytuł (rok).
- Gdy pytanie jest o książki, a źródła są artykułami, powiedz to i podaj najbliższe tytuły ze zbioru.
- Gdy tytuły słabo pasują do pytania, napisz to w pierwszym zdaniu. Nie opisuj ich tak, jakby odpowiadały wprost.
- Przy wzorcu rozwoju użyj pola pattern: wzrost, spadek albo podobny poziom. Puste pattern oznacza jeden rok, nie wieloletni trend.
"""

REWRITE_PROMPT = """Na podstawie historii rozmowy i OSTATNIEJ wiadomości użytkownika przygotuj samodzielne zapytanie do systemu publikacji naukowych.

Zwróć WYŁĄCZNIE poprawny JSON (bez markdown):
{"standalone_query": "...", "intent": "semantic|trend|author|coauthor|direction_authors|chitchat|off_topic", "language": "pl|en"}

Reguły intent:
- chitchat — powitanie, small-talk, meta o asystencie bez pytania o dane
- off_topic — pytanie niezwiązane ze zbiorem publikacji
- trend — popularność tematów, trendy w czasie, wzorzec rozwoju, top topics
- author — profil autora LUB lista autorów konkretnej publikacji („kto napisał tę pracę”)
- direction_authors — kto publikuje w danym kierunku
- coauthor — współautorzy / sieć współautorstwa osoby
- semantic — wyszukiwanie / treść / streszczenie publikacji

standalone_query: pełne pytanie bez zaimków.
Jeśli ostatnia wiadomość nazywa nowy temat, zapytanie jest tylko o ten temat. Nie doklejaj poprzedniego.
Poprzedni temat dopisz wyłącznie przy zaimku: ta praca, ten autor, to samo, współautorzy tej osoby.
Zachowaj język użytkownika. Jeśli to tylko powitanie, intent=chitchat i krótkie standalone_query.
"""


@dataclass
class AgentResponse:
    answer: str
    intent: str
    sources: list[dict] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)
    chart: Optional[dict] = None
    rewritten_query: Optional[str] = None


def classify_intent(question: str) -> str:
    """Fast regex router (also used by tests / eval). Prefer LLM rewrite when history exists."""
    q = question.lower().strip()
    if _looks_like_chitchat(q):
        return "chitchat"
    if _looks_off_topic(q):
        return "off_topic"
    if re.search(
        r"kto\s+publikuje|autorzy\s+kierunku|autorzy\s+tematu|"
        r"who\s+publishes|authors?\s+(?:in|of)\s+(?:the\s+)?(?:direction|topic|field)",
        q,
    ):
        return "direction_authors"
    if re.search(r"wsp[oó][lł]autor(?:zy|ów)?", q) or re.search(
        r"co-?authors?\s+of\b", q
    ):
        return "coauthor"
    if re.search(
        r"autor(?:zy|ów)?\s+(?:tej\s+|tej\s+samej\s+)?(?:pracy|publikacji|paper)|"
        r"authors?\s+of\b|who\s+wrote\b|kto\s+(?:napisa[łl]|jest\s+autorem)",
        q,
    ):
        return "author"
    if re.search(
        r"profil autora|author profile|kto (jest|napisa)|publications by|"
        r"profil\s+autora|\bauthor\b.*\bprofile\b",
        q,
    ):
        return "author"
    if re.search(
        r"trend|popularno[sś][cć]|top topic|najpopular|dominuj[aą]c|kierunk|wzorzec",
        q,
    ):
        return "trend"
    if re.search(r"temat|topic|klasyfik|cluster", q) and re.search(
        r"ile|list|top|najcz[eę]|domin", q
    ):
        return "trend"
    return "semantic"


def _standalone_shift(question: str) -> Optional[str]:
    """A new subject after „a” or „ale”, searched on its own.

    Pronouns and bare follow-ups („a współautorzy?”, „a kto napisał tę pracę?”)
    still go through the rewrite, because they need the previous turn.
    """
    match = re.match(
        r"^(?:a|ale|i|oraz|and|also)\s+(.+)$",
        question.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    rest = match.group(1).strip(" ?.,!")
    if not rest:
        return None
    if re.fullmatch(r"(?:w\s+)?(?:roku\s+)?(?:19|20)\d{2}", rest, flags=re.IGNORECASE):
        return None
    if re.search(
        r"\b("
        r"tej|tego|ten|ta|to|tamten|tamta|tamto|niej|niego|nim|"
        r"on|ona|jego|jej|ich|"
        r"this|that|those|it|same|"
        r"wsp[oó][lł]autor|co-?author|"
        r"autor(?:zy|ów|a)?|"
        r"prac[aęy]|publikacj"
        r")\b",
        rest,
        flags=re.IGNORECASE,
    ):
        return None
    return rest


def _looks_like_followup(question: str) -> bool:
    q = question.lower().strip()
    if re.match(r"^(a |i |and |also |oraz )\b", q):
        return True
    return bool(
        re.search(
            r"\b("
            r"tej\s+pracy|tej\s+publikacji|tego\s+autora|tych\s+autor|"
            r"tamten|tamta|tamto|"
            r"that\s+paper|this\s+paper|that\s+author|those\s+authors|"
            r"the\s+same|that\s+one|this\s+one"
            r")\b",
            q,
        )
    )


def _looks_off_topic(q: str) -> bool:
    """Questions that are not about the publication collection."""
    if re.search(
        r"\b(publikac|paper|papers|autor|author|kierunk|topic|abstrakt|doi|temat)\b",
        q,
    ):
        return False
    return bool(
        re.search(
            r"pogod|przepis na |opowiedz(?: mi)? żart|tell me a joke|"
            r"what'?s the weather|who won the (?:game|match)|"
            r"stolica francji|capital of france|kurs dolara",
            q,
        )
    )


def _looks_like_chitchat(q: str) -> bool:
    return bool(
        re.fullmatch(
            r"(co\s+tam|cze[sś][cć]|hej|haj|siema|siemka|elo|yo|"
            r"dzie[nń]\s*dobry|dobry\s*wiecz[oó]r|hejka|"
            r"hi|hello|hey|howdy|what'?s\s+up|sup|yo|"
            r"jak\s+si[eę]\s+masz|how\s+are\s+you|"
            r"dzi[eę]kuj[eę]|dzi[eę]ki|thanks|thank\s+you|"
            r"ok|okay|jasne|rozumiem|super|fajnie)\s*[!?.…]*",
            q,
        )
    )


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
    tokens = re.findall(r"[A-ZÁĄĆĘŁŃÓŚŹŻ][\wÁĄĆĘŁŃÓŚŹŻáąćęłńóśźż\-]+", question)
    if tokens:
        return " ".join(tokens[-2:])
    return question.strip()


def _extract_direction_query(question: str) -> str:
    patterns = [
        r"(?:w\s+)?kierunku\s+(.+)$",
        r"(?:w\s+)?kierunkiem\s+(.+)$",
        r"(?:of\s+)?(?:the\s+)?direction\s+(.+)$",
        r"(?:in\s+)?(?:the\s+)?(?:topic|field)\s+(.+)$",
        r"(?:w\s+)?temacie\s+(.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, question, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" ?.,")
    return question.strip(" ?.,")


def _direction_is_explicit(question: str) -> bool:
    name = _extract_direction_query(question).lower()
    return bool(name) and name not in {"tym", "tego", "tej", "this", "that", "it"}


def _extract_topic_query(question: str) -> str:
    m = re.search(
        r"(?:temat(?:u|cie)?|topic|trend(?:y|zie)?(?:\s+dla)?)\s+(.+)$",
        question,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(" ?.,")
    cleaned = re.sub(
        r"\b(jaki|jakie|jak|jest|są|the|what|are|is|trend|trendy|temat|topic)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" ?.,") or question


def _normalize_history(history: Optional[list[dict]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for turn in history or []:
        role = (turn.get("role") or "").strip()
        content = (turn.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        # Strip UI metadata that may have leaked into older sessions
        content = re.sub(r"\n*_intent:\s*`[^`]+`_\s*$", "", content).strip()
        out.append({"role": role, "content": content[:4000]})
    return out[-40:]


def _parse_rewrite_json(raw: str) -> Optional[dict[str, str]]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    intent = str(data.get("intent") or "semantic").lower().strip()
    if intent not in {
        "semantic",
        "trend",
        "author",
        "coauthor",
        "direction_authors",
        "chitchat",
        "off_topic",
    }:
        intent = "semantic"
    query = str(data.get("standalone_query") or "").strip()
    if not query:
        return None
    return {"standalone_query": query, "intent": intent}


def _off_topic_answer(question: str) -> str:
    english = bool(re.search(r"\b(the|what|who|how|weather|joke|capital)\b", question.lower()))
    if english and not re.search(r"[ąćęłńóśźż]", question.lower()):
        return (
            "That question is outside the loaded publication set. "
            "You can ask, for example:\n"
            "- What are the dominant research directions?\n"
            "- How does the number of papers in a direction change over the years?\n"
            "- Author profile by name"
        )
    return (
        "To pytanie nie dotyczy wczytanego zbioru publikacji. "
        "Mogę pomóc na przykład tak:\n"
        "- Jakie kierunki dominują w zbiorze?\n"
        "- Jak zmienia się liczba prac w wybranym kierunku?\n"
        "- Profil autora po imieniu i nazwisku"
    )


def _slim_tools(tool_results: dict) -> dict:
    """Drop paper lists from the prompt. The numbers and titles stay."""
    slim: dict = {}
    for key, value in tool_results.items():
        if not isinstance(value, dict):
            slim[key] = value
            continue
        copy = {
            item_key: item
            for item_key, item in value.items()
            if item_key not in {"publications"}
        }
        authors = copy.get("authors")
        if isinstance(authors, list):
            copy["authors"] = [
                {
                    "name": person.get("name"),
                    "orcid_id": person.get("orcid_id"),
                    "n_publications": person.get("n_publications"),
                }
                for person in authors[:12]
            ]
        matches = copy.get("matches")
        if isinstance(matches, list):
            copy["matches"] = [
                {
                    "name": person.get("name"),
                    "orcid_id": person.get("orcid_id"),
                    "topics": person.get("topics"),
                    "n_publications": len(person.get("publications") or []),
                }
                for person in matches[:5]
            ]
        series = copy.get("series")
        if isinstance(series, list) and len(series) > 8:
            copy["series"] = [series[0], series[-1]]
        slim[key] = copy
    return slim


def _fold(text: str) -> str:
    return (text or "").lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))


def _cites_source(answer: str, sources: list[dict]) -> bool:
    """True when the answer actually names a retrieved title, not a remembered one."""
    folded = _fold(answer)
    for source in sources:
        title = _fold((source.get("metadata") or {}).get("title") or "")
        words = re.findall(r"[a-z0-9]{5,}", title)[:6]
        if len(words) >= 2 and sum(word in folded for word in words[:4]) >= 2:
            return True
    return False


def _grounded_titles(question: str, sources: list[dict]) -> str:
    books = bool(re.search(r"ksi[aą][zż]k|podr[eę]cznik|\bbook", question, re.I))
    lines = [
        "W zbiorze nie ma klasycznych podręczników. Najbliższe publikacje:"
        if books
        else "Najbliższe publikacje:"
    ]
    for i, source in enumerate(sources[:5], start=1):
        meta = source.get("metadata") or {}
        lines.append(f"- [{i}] {meta.get('title')} ({meta.get('year')})")
    return "\n".join(lines)


def _sources_from_papers(papers: list[dict]) -> list[dict]:
    sources = []
    seen: set[str] = set()
    for paper in papers:
        oid = str(paper.get("object_id") or "")
        if oid and oid in seen:
            continue
        if oid:
            seen.add(oid)
        sources.append(
            {
                "id": oid or paper.get("title"),
                "text": "",
                "metadata": {
                    "object_id": oid,
                    "title": paper.get("title"),
                    "year": paper.get("year"),
                    "doi": paper.get("doi") or "",
                    "topic_label": paper.get("topic_label") or "",
                },
            }
        )
    return sources


class AgentOrchestrator:
    def __init__(
        self,
        retriever: SupportsSearch,
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
        on_token=None,
    ) -> AgentResponse:
        if not question or not str(question).strip():
            return AgentResponse(
                answer=(
                    "Brakuje treści. Wpisz pytanie o publikacje, kierunki albo autorów."
                ),
                intent="off_topic",
            )
        if _looks_off_topic(question.lower().strip()):
            return AgentResponse(
                answer=_off_topic_answer(question),
                intent="off_topic",
                rewritten_query=question.strip(),
            )

        top_k = top_k or self.settings.retrieval_top_k
        history = _normalize_history(history)
        year = year or _extract_year(question)

        rewritten, intent = self._resolve_turn(question, history)
        year = year or _extract_year(rewritten)

        tool_results: dict[str, Any] = {}
        sources: list[dict] = []
        chart: Optional[dict] = None

        where = None
        if year is not None:
            where = {"year": {"$eq": year}}

        if intent == "chitchat":
            answer = self._chat_reply(question, history, intent="chitchat", on_token=on_token)
            return AgentResponse(
                answer=answer,
                intent=intent,
                rewritten_query=rewritten,
            )

        if intent == "off_topic":
            return AgentResponse(
                answer=_off_topic_answer(question),
                intent=intent,
                rewritten_query=rewritten,
            )

        if intent == "trend":
            if re.search(r"kierunk|direction", rewritten, re.I):
                topic = _extract_direction_query(rewritten)
            else:
                topic = _extract_topic_query(rewritten)
            broad = re.search(r"top|najpopular|dominuj|popular", rewritten, re.I)
            if broad or not topic:
                tool_results["top_topics"] = self.analytics.top_topics(year=year, n=10)
                listed = tool_results["top_topics"]["topics"]
                chart = {
                    "type": "bar",
                    "title": "Dominujące kierunki",
                    "data": [
                        {"label": t["label"], "count": t["count"]} for t in listed
                    ],
                    "total": tool_results["top_topics"].get("total"),
                    "publications": tool_results["top_topics"].get("publications") or [],
                    "pattern": None,
                }
                sources = _sources_from_papers(
                    tool_results["top_topics"].get("publications") or []
                )[:8]
            else:
                tool_results["topic_trend"] = self.analytics.topic_trend(
                    topic, year_from=None, year_to=None
                )
                trend = tool_results["topic_trend"]
                chart = {
                    "type": "bar",
                    "title": f"Liczebność: {topic}",
                    "data": [
                        {"label": str(p["year"]), "count": p["count"]}
                        for p in trend["series"]
                    ],
                    "total": trend.get("total"),
                    "publications": trend.get("publications") or [],
                    "pattern": trend.get("pattern"),
                    "note": trend.get("note"),
                }
                sources = _sources_from_papers(trend.get("publications") or [])[:8]

        elif intent == "direction_authors":
            name = _extract_direction_query(rewritten)
            tool_results["direction_authors"] = self.analytics.direction_authors(name)
            sources = _sources_from_papers(
                [
                    paper
                    for person in tool_results["direction_authors"].get("authors") or []
                    for paper in person.get("publications") or []
                ]
            )[:8]

        elif intent == "author":
            name = _extract_author_query(rewritten)
            # "authors of <paper>" follow-ups → resolve via retrieval, not author search
            if re.search(
                r"autor(?:zy|ów)?\s+(?:tej\s+)?(?:pracy|publikacji)|authors?\s+of\b|"
                r"kto\s+(?:napisa|jest\s+autorem)|who\s+wrote\b",
                rewritten,
                re.I,
            ) or (
                re.search(r"\b(autorzy|authors)\b", rewritten, re.I)
                and not re.search(r"profil", rewritten, re.I)
            ):
                sources = self.retriever.search(rewritten, top_k=top_k, where=where)
                ids = [s.get("metadata", {}).get("object_id") for s in sources[:3]]
                tool_results["publication_authors"] = self.analytics.publication_authors(
                    [i for i in ids if i]
                )
            else:
                tool_results["author_profile"] = self.analytics.author_profile(name)
                matches = tool_results["author_profile"].get("matches") or []
                if matches:
                    sources = _sources_from_papers(
                        [
                            paper
                            for person in matches
                            for paper in person.get("publications") or []
                        ]
                    )[:8]
                else:
                    # Fallback: maybe the rewrite still points at a paper title
                    sources = self.retriever.search(rewritten, top_k=top_k, where=where)
                    ids = [s.get("metadata", {}).get("object_id") for s in sources[:3]]
                    tool_results["publication_authors"] = (
                        self.analytics.publication_authors([i for i in ids if i])
                    )

        elif intent == "coauthor":
            name = _extract_author_query(rewritten)
            tool_results["coauthor_graph"] = self.analytics.coauthor_graph(name, depth=1)
            sources = []

        else:
            sources = self.retriever.search(rewritten, top_k=top_k, where=where)
            tool_results["search_publications"] = {
                "n": len(sources),
                "ids": [s["metadata"].get("object_id") for s in sources],
                "query": rewritten,
            }

        if intent in {"trend", "author", "direction_authors", "coauthor"}:
            answer = self._fallback_answer(intent, sources, tool_results, error="")
            if on_token:
                on_token(answer)
        elif on_token:
            messages = self._synthesis_messages(
                question, rewritten, intent, sources, tool_results, history
            )
            parts: list[str] = []
            try:
                for tok in self.llm.chat_stream(messages, max_tokens=160):
                    parts.append(tok)
                    on_token(tok)
                answer = "".join(parts).strip()
            except Exception as exc:
                answer = self._fallback_answer(
                    intent, sources, tool_results, error=str(exc)
                )
                on_token(answer)
        else:
            answer = self._synthesize(
                question, rewritten, intent, sources, tool_results, history
            )
        if intent == "semantic" and sources and not _cites_source(answer, sources):
            answer = _grounded_titles(question, sources)
        return AgentResponse(
            answer=answer,
            intent=intent,
            sources=sources,
            tool_results=tool_results,
            chart=chart,
            rewritten_query=rewritten,
        )

    def _resolve_turn(
        self, question: str, history: list[dict[str, str]]
    ) -> tuple[str, str]:
        prior_user = [t for t in history if t["role"] == "user"]
        # Skip extra LLM rewrite on first question (welcome message is not a real turn)
        # and on standalone queries that already have a clear intent.
        direct = classify_intent(question)
        if direct == "off_topic" or (
            direct == "direction_authors" and _direction_is_explicit(question)
        ):
            return question.strip(), direct
        shifted = _standalone_shift(question)
        if shifted:
            return shifted, classify_intent(shifted)
        if (
            not prior_user
            or _looks_like_chitchat(question.lower().strip())
            or not _looks_like_followup(question)
        ):
            return question.strip(), direct

        # Follow-ups only: one short JSON rewrite before retrieval
        try:
            hist_txt = "\n".join(
                f"{t['role'].upper()}: {t['content'][:600]}" for t in history[-6:]
            )
            raw = self.llm.chat(
                [
                    {"role": "system", "content": REWRITE_PROMPT},
                    {
                        "role": "user",
                        "content": f"HISTORY:\n{hist_txt}\n\nLATEST:\n{question}",
                    },
                ],
                temperature=0.0,
                max_tokens=180,
            )
            parsed = _parse_rewrite_json(raw)
            if parsed:
                q = parsed["standalone_query"]
                intent = parsed["intent"]
                regex_intent = classify_intent(q)
                if intent == "semantic" and regex_intent != "semantic":
                    intent = regex_intent
                elif intent == "semantic" and classify_intent(question) != "semantic":
                    intent = classify_intent(question)
                return q, intent
        except Exception:
            pass

        # Fallback: heuristic follow-up expansion
        intent = classify_intent(question)
        rewritten = question.strip()
        if history and re.search(
            r"\b(a |i |to |ta |ten |tego |tej |tamten|tamta|on|ona|jego|jej|"
            r"the same|that|this|those|him|her|it)\b",
            question.lower(),
        ):
            prev_users = [t["content"] for t in history if t["role"] == "user"]
            if prev_users:
                rewritten = f"{prev_users[-1]} — follow-up: {question}"
                ri = classify_intent(rewritten)
                if intent == "semantic" or ri in {"author", "coauthor", "trend"}:
                    intent = ri if ri != "semantic" else intent
        return rewritten, intent

    def _chat_reply(
        self,
        question: str,
        history: list[dict[str, str]],
        intent: str = "chitchat",
        on_token=None,
    ) -> str:
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[-6:])
        messages.append(
            {
                "role": "user",
                "content": (
                    f"{question}\n\n"
                    "(To small-talk / meta. Nie przeszukuj bazy. "
                    "Odpowiedz naturalnie i zaproponuj 2–3 przykładowe pytania o publikacje.)"
                ),
            }
        )
        try:
            if on_token:
                parts: list[str] = []
                for tok in self.llm.chat_stream(messages, max_tokens=80):
                    parts.append(tok)
                    on_token(tok)
                return "".join(parts).strip()
            return self.llm.chat(messages, max_tokens=80)
        except Exception:
            return (
                "Cześć! Jestem Sci-Pub Agent — mogę szukać publikacji, opisywać tematy, "
                "trendy i współautorstwo.\n\n"
                "Przykłady:\n"
                "- Jakie są najpopularniejsze tematy?\n"
                "- Profil autora Paweł Kulesza\n"
                "- Która publikacja dotyczy neutrin?"
            )

    def _synthesis_messages(
        self,
        question: str,
        rewritten: str,
        intent: str,
        sources: list[dict],
        tool_results: dict[str, Any],
        history: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        context_blocks = []
        for i, source in enumerate(sources[:10], start=1):
            meta = source.get("metadata") or {}
            snippet = (source.get("text") or "").replace("\n", " ")[:160]
            block = f"[{i}] {meta.get('title')} ({meta.get('year')})"
            if snippet and intent != "semantic":
                block += f"\n{snippet}"
            context_blocks.append(block)
        context = "\n".join(context_blocks) if context_blocks else "(brak źródeł)"
        if intent == "semantic":
            return [
                {
                    "role": "system",
                    "content": (
                        "Wybierz z listy najwyżej 4 publikacje najbliższe pytaniu. "
                        "Wypisz je jako: - [n] tytuł (rok). "
                        "Potem jedno zdanie, czy są artykułami ze zbioru, czy książkami. "
                        "Nie zadawaj pytań i nie dopisuj tytułów spoza listy."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Pytanie: {question}\n\n{context}",
                },
            ]
        tools_json = json.dumps(_slim_tools(tool_results), ensure_ascii=False)[:1800]
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Ostatnie pytanie: {question}\n"
                    f"Zapytanie do zbioru: {rewritten}\n\n"
                    f"WYNIKI NARZĘDZI:\n{tools_json}\n\n"
                    f"Źródła:\n{context}\n\n"
                    "Odpowiedz tylko na ostatnie pytanie. Bez powitania."
                ),
            },
        ]

    def _synthesize(
        self,
        question: str,
        rewritten: str,
        intent: str,
        sources: list[dict],
        tool_results: dict[str, Any],
        history: list[dict[str, str]],
    ) -> str:
        messages = self._synthesis_messages(
            question, rewritten, intent, sources, tool_results, history
        )
        try:
            return self.llm.chat(messages, max_tokens=160)
        except Exception as exc:
            return self._fallback_answer(intent, sources, tool_results, error=str(exc))

    def _fallback_answer(
        self,
        intent: str,
        sources: list[dict],
        tool_results: dict[str, Any],
        error: str = "",
    ) -> str:
        lines = []
        if error:
            lines.append(
                "(LLM niedostępny — odpowiedź z narzędzi i wyszukiwania.)"
            )
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
            pattern = tr.get("pattern")
            if pattern == "wzrost":
                lines.append("Wzorzec rozwoju: liczba prac rośnie.")
            elif pattern == "spadek":
                lines.append("Wzorzec rozwoju: liczba prac maleje.")
            elif pattern == "podobny poziom":
                lines.append("Wzorzec rozwoju: liczba prac pozostaje na podobnym poziomie.")
            elif tr.get("note"):
                lines.append(tr["note"])
            series = tr.get("series") or []
            if len(series) > 8:
                lines.append(
                    f"{series[0]['year']}: {series[0]['count']}; "
                    f"{series[-1]['year']}: {series[-1]['count']}. "
                    "Pozostałe lata są na wykresie."
                )
            else:
                for point in series:
                    lines.append(f"- {point['year']}: {point['count']}")
        elif intent == "author" and "author_profile" in tool_results:
            matches = tool_results["author_profile"].get("matches") or []
            if not matches:
                lines.append("Nie znaleziono autora.")
            else:
                for m in matches:
                    lines.append(f"Autor: {m['name']}")
                    if m.get("orcid_id"):
                        lines.append(f"ORCID: {m['orcid_id']}")
                    lines.append(f"Liczba publikacji: {len(m['publications'])}")
                    if m.get("topics"):
                        lines.append("Kierunki: " + ", ".join(m["topics"]))
                    for p in m["publications"][:8]:
                        lines.append(f"- {p['title']} ({p['year']})")
                    if m.get("coauthors"):
                        lines.append(
                            "Współautorzy: "
                            + ", ".join(c["name"] for c in m["coauthors"][:8])
                        )
        elif intent == "direction_authors" and "direction_authors" in tool_results:
            found = tool_results["direction_authors"]
            people = found.get("authors") or []
            if not people:
                lines.append(found.get("note") or "Nie znaleziono autorów tego kierunku.")
            else:
                lines.append(f"Kierunek: {found.get('query')}")
                for person in people:
                    orcid = f", ORCID {person['orcid_id']}" if person.get("orcid_id") else ""
                    lines.append(
                        f"- {person['name']} ({person.get('n_publications', 0)} prac{orcid})"
                    )
        elif intent == "author" and "publication_authors" in tool_results:
            papers = tool_results["publication_authors"].get("papers") or []
            if not papers:
                lines.append("Nie znaleziono autorów dla wskazanych publikacji.")
            else:
                for p in papers:
                    lines.append(f"{p['title']} ({p['year']}):")
                    lines.append(", ".join(p.get("authors") or []) or "(brak autorów)")
        elif intent == "coauthor" and "coauthor_graph" in tool_results:
            g = tool_results["coauthor_graph"]
            lines.append(
                f"Węzły: {len(g.get('nodes') or [])}, "
                f"krawędzie: {len(g.get('edges') or [])}"
            )
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
        return "\n".join(lines)
