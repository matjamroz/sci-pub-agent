from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="Sci-Pub Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

WELCOME = (
    "Witaj. Jestem **Sci-Pub Agent** — asystent RAG do analizy publikacji naukowych.\n\n"
    "Pytaj o tematy, trendy, współautorstwo i treść prac. Pamiętam kontekst rozmowy, "
    "więc możesz dopytywać (np. *„a kto są autorzy tej pracy?”*).\n\n"
    "Przykłady:\n"
    "- *Jakie są najpopularniejsze tematy w zbiorze?*\n"
    "- *Która publikacja dotyczy neutrin?*\n"
    "- *Profil autora Paweł Kulesza*"
)


def inject_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:ital,wght@0,500;0,600;1,500&display=swap');

:root {
  --bg-0: #06101c;
  --bg-1: #0a1628;
  --bg-2: #0f2138;
  --panel: rgba(12, 28, 48, 0.72);
  --line: rgba(120, 190, 255, 0.14);
  --text: #e8eef7;
  --muted: #8fa3bc;
  --cyan: #4ec7ff;
  --cyan-dim: #2a8fbf;
  --glow: rgba(78, 199, 255, 0.35);
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg-0) !important;
  color: var(--text) !important;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif !important;
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1200px 600px at 12% -10%, rgba(46, 140, 220, 0.22), transparent 55%),
    radial-gradient(900px 500px at 88% 8%, rgba(90, 70, 180, 0.12), transparent 50%),
    radial-gradient(700px 420px at 70% 95%, rgba(40, 170, 210, 0.10), transparent 55%),
    linear-gradient(180deg, #07111f 0%, #06101c 45%, #050d18 100%) !important;
}

[data-testid="stAppViewContainer"]::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: 0.45;
  background-image:
    linear-gradient(rgba(100, 180, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(100, 180, 255, 0.045) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at 50% 30%, black 20%, transparent 75%);
}

[data-testid="stHeader"] {
  background: transparent !important;
}
[data-testid="stToolbar"] { display: none !important; }

.block-container {
  padding-top: 1.4rem !important;
  padding-bottom: 6rem !important;
  max-width: 1280px !important;
  position: relative;
  z-index: 1;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #071525 0%, #06101c 100%) !important;
  border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebar"] * {
  color: var(--text) !important;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stCaption {
  color: var(--muted) !important;
}
[data-testid="stSidebar"] hr {
  border-color: var(--line) !important;
}

/* Brand */
.sp-brand {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1.25rem;
  padding: 0.25rem 0 1rem;
  border-bottom: 1px solid var(--line);
}
.sp-brand-mark {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
}
.sp-logo {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  background:
    radial-gradient(circle at 30% 30%, #9ae2ff, #2ea8e0 55%, #164a78 100%);
  box-shadow: 0 0 18px var(--glow);
  position: relative;
}
.sp-logo::after {
  content: "";
  position: absolute;
  inset: 7px;
  border: 1.5px solid rgba(255,255,255,0.75);
  border-radius: 3px;
  transform: rotate(45deg);
}
.sp-brand h1 {
  margin: 0 !important;
  font-family: "IBM Plex Serif", Georgia, serif !important;
  font-weight: 600 !important;
  font-size: 1.85rem !important;
  letter-spacing: -0.02em;
  color: var(--text) !important;
  line-height: 1.15 !important;
}
.sp-brand p {
  margin: 0 !important;
  color: var(--muted) !important;
  font-size: 0.95rem !important;
  max-width: 42rem;
  line-height: 1.45;
}
.sp-kicker {
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--cyan) !important;
  font-weight: 500;
}

/* Panels */
.sp-panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 1rem 1.05rem;
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
}
.sp-panel h3 {
  margin: 0 0 0.75rem 0 !important;
  font-family: "IBM Plex Serif", Georgia, serif !important;
  font-size: 1.05rem !important;
  font-weight: 600 !important;
  color: var(--text) !important;
}
.sp-empty {
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.45;
}
.sp-source {
  padding: 0.65rem 0;
  border-bottom: 1px solid var(--line);
}
.sp-source:last-child { border-bottom: none; }
.sp-source-title {
  font-weight: 600;
  color: var(--text);
  font-size: 0.92rem;
  line-height: 1.35;
}
.sp-source-meta {
  color: var(--cyan-dim);
  font-size: 0.78rem;
  margin-top: 0.2rem;
}
.sp-source-snip {
  color: var(--muted);
  font-size: 0.82rem;
  margin-top: 0.35rem;
  line-height: 1.4;
}

/* Chat */
[data-testid="stChatMessage"] {
  background: rgba(10, 24, 42, 0.55) !important;
  border: 1px solid var(--line) !important;
  border-radius: 14px !important;
  padding: 0.85rem 1rem !important;
  margin-bottom: 0.65rem !important;
  backdrop-filter: blur(8px);
}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li {
  color: var(--text) !important;
  font-size: 0.98rem;
  line-height: 1.55;
}
.sp-meta {
  color: var(--muted) !important;
  font-size: 0.75rem !important;
  margin-top: 0.45rem;
  letter-spacing: 0.02em;
}
.sp-meta code {
  background: rgba(78, 199, 255, 0.12) !important;
  color: var(--cyan) !important;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  font-size: 0.72rem;
}

/* Inputs / widgets */
.stTextInput input, .stNumberInput input, textarea {
  background: rgba(8, 20, 36, 0.9) !important;
  color: var(--text) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
}
.stSlider label, .stTextInput label, .stNumberInput label {
  color: var(--muted) !important;
}
div[data-testid="stChatInput"] textarea {
  background: rgba(8, 20, 36, 0.95) !important;
  color: var(--text) !important;
  border: 1px solid rgba(78, 199, 255, 0.28) !important;
  border-radius: 14px !important;
  box-shadow: 0 0 0 1px rgba(78, 199, 255, 0.08), 0 8px 28px rgba(0,0,0,0.35);
}
div[data-testid="stChatInput"] {
  background: transparent !important;
}

.stButton > button {
  background: linear-gradient(180deg, #1a6fa0 0%, #145a84 100%) !important;
  color: #f4fbff !important;
  border: 1px solid rgba(120, 210, 255, 0.35) !important;
  border-radius: 10px !important;
  font-weight: 500 !important;
  box-shadow: 0 0 16px rgba(78, 199, 255, 0.15);
}
.stButton > button:hover {
  border-color: var(--cyan) !important;
  box-shadow: 0 0 22px rgba(78, 199, 255, 0.28);
}
.stExpander {
  background: rgba(8, 20, 36, 0.55) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
}
hr { border-color: var(--line) !important; }

a { color: var(--cyan) !important; }
</style>
        """,
        unsafe_allow_html=True,
    )


def themed_fig(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,20,36,0.35)",
        font=dict(family="IBM Plex Sans, sans-serif", color="#c9d7e8", size=12),
        title=dict(font=dict(family="IBM Plex Serif, serif", size=14, color="#e8eef7")),
        margin=dict(l=40, r=16, t=48, b=40),
        colorway=["#4ec7ff", "#7aa2ff", "#3dd6c3"],
    )
    fig.update_xaxes(gridcolor="rgba(120,190,255,0.12)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(120,190,255,0.12)", zeroline=False)
    return fig


def render_sources_html(sources: list[dict]) -> str:
    if not sources:
        return '<div class="sp-empty">Brak źródeł dla ostatniej odpowiedzi.</div>'
    parts = []
    for s in sources:
        meta = s.get("metadata") or {}
        title = meta.get("title") or s.get("id") or "—"
        year = meta.get("year")
        doi = meta.get("doi") or ""
        score = s.get("rrf_score") or s.get("score")
        snip = ((s.get("text") or "")[:280] + "…") if s.get("text") else ""
        meta_line = f"{year}" if year is not None else ""
        if score is not None:
            try:
                meta_line += f" · score {float(score):.3f}"
            except (TypeError, ValueError):
                meta_line += f" · score {score}"
        doi_html = (
            f'<div class="sp-source-meta"><a href="https://doi.org/{doi}" target="_blank">DOI</a></div>'
            if doi
            else ""
        )
        parts.append(
            f'<div class="sp-source">'
            f'<div class="sp-source-title">{title}</div>'
            f'<div class="sp-source-meta">{meta_line}</div>'
            f"{doi_html}"
            f'<div class="sp-source-snip">{snip}</div>'
            f"</div>"
        )
    return "".join(parts)


def _welcome(text: Optional[str] = None) -> dict:
    return {
        "role": "assistant",
        "content": text or WELCOME,
        "sources": [],
        "chart": None,
        "intent": "chitchat",
        "rewritten_query": None,
        "tool_results": {},
    }


def _make_chat(name: str, parent_id: Optional[str] = None) -> dict:
    return {
        "id": uuid.uuid4().hex,
        "name": (name or "").strip() or "Rozmowa",
        "parent_id": parent_id,
        "messages": [_welcome()],
    }


def _chat_by_id(chat_id: Optional[str]) -> Optional[dict]:
    for chat in st.session_state.get("chats") or []:
        if chat["id"] == chat_id:
            return chat
    return None


def _activate(chat_id: str) -> None:
    chat = _chat_by_id(chat_id)
    if chat is None:
        return
    st.session_state.active_chat_id = chat_id
    st.session_state.messages = chat["messages"]


def _turns(messages: list[dict], limit: int) -> list[dict[str, str]]:
    turns = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in {"user", "assistant"} and m.get("content")
    ]
    return turns[-limit:]


def _dataset_info(api_url: str) -> dict:
    now = time.time()
    cached = st.session_state.get("dataset_info") or {}
    if cached.get("url") == api_url and now - cached.get("at", 0) < 60:
        return cached.get("data") or {}
    try:
        response = requests.get(f"{api_url.rstrip('/')}/health", timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        data = {"error": str(exc)}
    if "error" not in data:
        st.session_state["dataset_info"] = {"url": api_url, "at": now, "data": data}
    return data


def _render_person_cards(people: list[dict]) -> None:
    for person in people:
        publications = person.get("publications") or []
        count = person.get("n_publications", len(publications))
        topics = person.get("topics") or sorted(
            {p.get("topic_label") for p in publications if p.get("topic_label")}
        )
        st.markdown(f"**{person.get('name') or '—'}**")
        meta = f"{count} publikacji"
        if person.get("orcid_id"):
            meta += f" · ORCID {person['orcid_id']}"
        st.caption(meta)
        if topics:
            st.markdown(" ".join(f"`{topic}`" for topic in topics))
        rows = [
            {
                "tytuł": paper.get("title"),
                "rok": paper.get("year"),
                "kierunek": paper.get("topic_label") or "",
            }
            for paper in publications[:30]
        ]
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        st.divider()


def init_state() -> None:
    if "chats" not in st.session_state:
        first = _make_chat("Rozmowa 1")
        st.session_state.chats = [first]
        st.session_state.active_chat_id = first["id"]
        st.session_state.messages = first["messages"]
        st.session_state.show_new_chat = False
    elif "messages" not in st.session_state:
        _activate(st.session_state.active_chat_id)


inject_theme()
pio.templates.default = "plotly_dark"
init_state()

with st.sidebar:
    st.markdown(
        '<div class="sp-kicker">Kontrola sesji</div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Parametry")
    API_URL = st.text_input("Endpoint API", value="http://127.0.0.1:8000")
    info = _dataset_info(API_URL)
    if info.get("error"):
        st.caption(f"Zbiór: {info['error']}")
    elif info.get("status") == "ok":
        span = info.get("trend_year_span") or info.get("year_span") or [None, None]
        st.markdown(
            f"**Publikacje:** {info.get('publications', '—')}  \n"
            f"**Zakres lat:** {span[0]}–{span[1]}  \n"
            f"**Kierunki:** {info.get('directions', '—')}"
        )
    st.divider()
    if st.button("Nowy czat", use_container_width=True):
        st.session_state.show_new_chat = True
    if st.session_state.get("show_new_chat"):
        chat_name = st.text_input("Nazwa rozmowy", value=f"Rozmowa {len(st.session_state.chats) + 1}")
        attach = st.radio("Kontekst innego czatu", ["Nie", "Tak"], horizontal=True)
        parent_id = None
        if attach == "Tak" and st.session_state.chats:
            labels = {chat["name"]: chat["id"] for chat in st.session_state.chats}
            chosen = st.selectbox("Czat źródłowy", list(labels))
            parent_id = labels[chosen]
        if st.button("Utwórz czat", use_container_width=True):
            created = _make_chat(chat_name, parent_id)
            if parent_id:
                source = _chat_by_id(parent_id)
                source_name = source["name"] if source else "innego czatu"
                created["messages"] = [
                    _welcome(
                        f"Nowa rozmowa **{created['name']}**. "
                        f"Widzę też historię czatu **{source_name}**."
                    )
                ]
            st.session_state.chats.append(created)
            st.session_state.show_new_chat = False
            _activate(created["id"])
            st.rerun()
    st.markdown("### Czaty")
    for chat in st.session_state.chats:
        label = chat["name"]
        source = _chat_by_id(chat.get("parent_id"))
        if source:
            label = f"{label} · {source['name']}"
        selected = chat["id"] == st.session_state.active_chat_id
        if st.button(
            label,
            key=f"chat-{chat['id']}",
            use_container_width=True,
            type="primary" if selected else "secondary",
        ):
            _activate(chat["id"])
            st.rerun()
    st.divider()
    top_k = st.slider("Retrieval top-k", 1, 15, 10)
    year_filter = st.number_input(
        "Filtr roku (0 = brak)", min_value=0, max_value=2100, value=0
    )
    history_turns = st.slider("Głębokość historii", 4, 40, 20, step=2)
    if st.button("Status systemu", use_container_width=True):
        try:
            r = requests.get(f"{API_URL.rstrip('/')}/health", timeout=10)
            st.json(r.json())
        except Exception as exc:
            st.error(str(exc))
    st.caption("Model: Ollama · Indeks: Chroma + SQLite")

st.markdown(
    """
<div class="sp-brand">
  <div class="sp-kicker">Scientific publications · RAG agent</div>
  <div class="sp-brand-mark">
    <div class="sp-logo"></div>
    <h1>Sci-Pub Agent</h1>
  </div>
  <p>Konwersacyjna analiza trendów, tematów i zależności współautorstwa w literaturze naukowej.</p>
</div>
""",
    unsafe_allow_html=True,
)

active = _chat_by_id(st.session_state.active_chat_id)
source_chat = _chat_by_id(active.get("parent_id") if active else None)
if active:
    context = f" · kontekst: {source_chat['name']}" if source_chat else ""
    st.markdown(f"### {active['name']}{context}")

col_chat, col_side = st.columns([1.7, 1], gap="large")

def _source_line(source: dict) -> str:
    meta = source.get("metadata") or {}
    title = meta.get("title") or source.get("id") or "—"
    year = meta.get("year")
    doi = meta.get("doi") or ""
    line = f"- {title}"
    if year not in (None, "", -1):
        line += f" ({year})"
    if doi:
        line += f" · [DOI](https://doi.org/{doi})"
    return line


with col_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            source_lines = [_source_line(s) for s in (msg.get("sources") or [])]
            if source_lines:
                st.markdown("**Źródła**\n\n" + "\n".join(source_lines))

    prompt = st.chat_input("Zadaj pytanie o publikacje…")
    if prompt:
        st.session_state.messages.append(
            {"role": "user", "content": prompt, "sources": [], "chart": None}
        )
        st.session_state.pending_chat_id = st.session_state.active_chat_id
        st.rerun()

    pending = (
        st.session_state.get("pending_chat_id") == st.session_state.active_chat_id
        and st.session_state.messages
        and st.session_state.messages[-1].get("role") == "user"
    )
    if pending:
        question = st.session_state.messages[-1]["content"]
        parent_turns = _turns(source_chat["messages"], 12) if source_chat else []
        current_turns = _turns(st.session_state.messages[:-1], history_turns)
        payload = {
            "question": question,
            "top_k": top_k,
            "year": year_filter or None,
            "history": (parent_turns + current_turns)[-40:],
        }
        parts: list[str] = []
        done = None
        error = None
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("Szukam w zbiorze…")
            try:
                with requests.post(
                    f"{API_URL.rstrip('/')}/ask/stream",
                    json=payload,
                    stream=True,
                    timeout=180,
                ) as resp:
                    resp.raise_for_status()
                    for raw in resp.iter_lines(decode_unicode=True):
                        if not raw:
                            continue
                        event = json.loads(raw)
                        if event.get("type") == "token":
                            parts.append(event.get("text") or "")
                            placeholder.markdown("".join(parts))
                        elif event.get("type") == "done":
                            done = event
                        elif event.get("type") == "error":
                            error = event.get("text") or "Błąd odpowiedzi."
            except Exception as exc:
                error = str(exc)
        if done:
            answer = done.get("answer") or "".join(parts)
            sources = done.get("sources") or []
            chart = done.get("chart")
            intent = done.get("intent")
            rewritten = done.get("rewritten_query")
            tool_results = done.get("tool_results") or {}
        else:
            answer = f"Błąd połączenia z API: {error}" if error else "".join(parts)
            sources, chart, intent, rewritten = [], None, "error", None
            tool_results = {}
        st.session_state.pending_chat_id = None
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "chart": chart,
                "intent": intent,
                "rewritten_query": rewritten,
                "tool_results": tool_results,
                "_user_q": question,
            }
        )
        st.rerun()

with col_side:
    last_assistant = next(
        (
            m
            for m in reversed(st.session_state.messages)
            if m["role"] == "assistant"
        ),
        None,
    )
    chart = (last_assistant or {}).get("chart")

    st.markdown('<div class="sp-panel">', unsafe_allow_html=True)
    st.markdown("### Analiza")
    if not chart:
        st.markdown(
            '<div class="sp-empty">Wykres pojawi się przy pytaniach o trendy i tematy.</div>',
            unsafe_allow_html=True,
        )
    else:
        data = chart.get("data") or []
        if chart.get("type") == "bar" and data:
            fig = px.bar(
                data,
                x="label",
                y="count",
                title=chart.get("title") or "Top topics",
            )
            st.plotly_chart(themed_fig(fig), use_container_width=True)
        elif chart.get("type") == "line" and data:
            fig = px.line(
                data,
                x="year",
                y="count",
                markers=True,
                title=chart.get("title") or "Trend",
            )
            st.plotly_chart(themed_fig(fig), use_container_width=True)
        else:
            st.json(chart)
        if chart.get("total") is not None:
            st.caption(f"Policzono z {chart['total']} publikacji.")
        if chart.get("pattern") == "wzrost":
            st.caption("Wzorzec rozwoju: liczba prac rośnie.")
        elif chart.get("pattern") == "spadek":
            st.caption("Wzorzec rozwoju: liczba prac maleje.")
        elif chart.get("pattern") == "podobny poziom":
            st.caption("Wzorzec rozwoju: liczba prac pozostaje na podobnym poziomie.")
        elif chart.get("note"):
            st.caption(chart["note"])
        listed = chart.get("publications") or []
        if listed:
            with st.expander("Lista publikacji"):
                for paper in listed:
                    doi = paper.get("doi") or ""
                    doi_bit = f" · [{doi}](https://doi.org/{doi})" if doi else ""
                    st.markdown(
                        f"- {paper.get('title')} ({paper.get('year')}){doi_bit}"
                    )
    st.markdown("</div>", unsafe_allow_html=True)

    tools = (last_assistant or {}).get("tool_results") or {}
    profile = (tools.get("author_profile") or {}).get("matches") or []
    direction_people = (tools.get("direction_authors") or {}).get("authors") or []
    if profile or direction_people:
        st.markdown("<div style='height:0.85rem'></div>", unsafe_allow_html=True)
        st.markdown('<div class="sp-panel">', unsafe_allow_html=True)
        st.markdown("### Osoby")
        _render_person_cards(profile or direction_people)
        st.markdown("</div>", unsafe_allow_html=True)
