from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Sci-Pub Agent", page_icon="📚", layout="wide")

API_URL = st.sidebar.text_input("API URL", value="http://127.0.0.1:8000")
top_k = st.sidebar.slider("top_k", 1, 15, 5)
year_filter = st.sidebar.number_input("Filtr roku (0 = brak)", min_value=0, max_value=2100, value=0)

st.title("Sci-Pub Agent")
st.caption(
    "Pytania o trendy, tematy i zależności współautorstwa w publikacjach naukowych (RAG)."
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_chart" not in st.session_state:
    st.session_state.last_chart = None
if "last_sources" not in st.session_state:
    st.session_state.last_sources = []

col_chat, col_side = st.columns([2, 1])

with col_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Zadaj pytanie…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        payload = {
            "question": prompt,
            "top_k": top_k,
            "year": year_filter or None,
            "history": [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1]
                if m["role"] in {"user", "assistant"}
            ][-6:],
        }
        try:
            resp = requests.post(f"{API_URL.rstrip('/')}/ask", json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "")
            st.session_state.last_sources = data.get("sources") or []
            st.session_state.last_chart = data.get("chart")
            meta = f"\n\n_intent: `{data.get('intent')}`_"
            full = answer + meta
        except Exception as exc:
            full = f"Błąd API: {exc}"
            st.session_state.last_sources = []
            st.session_state.last_chart = None

        st.session_state.messages.append({"role": "assistant", "content": full})
        with st.chat_message("assistant"):
            st.markdown(full)

with col_side:
    st.subheader("Źródła")
    sources = st.session_state.last_sources or []
    if not sources:
        st.write("Brak źródeł dla ostatniej odpowiedzi.")
    for s in sources:
        meta = s.get("metadata") or {}
        title = meta.get("title") or s.get("id")
        year = meta.get("year")
        doi = meta.get("doi") or ""
        score = s.get("rrf_score") or s.get("score")
        st.markdown(f"**{title}** ({year})")
        if doi:
            st.markdown(f"[DOI](https://doi.org/{doi})")
        if score is not None:
            st.caption(f"score={score:.4f}" if isinstance(score, float) else f"score={score}")
        st.write((s.get("text") or "")[:400] + "…")
        st.divider()

    st.subheader("Wykres")
    chart = st.session_state.last_chart
    if not chart:
        st.write("Brak danych wykresu.")
    else:
        data = chart.get("data") or []
        if chart.get("type") == "bar" and data:
            fig = px.bar(
                data,
                x="label",
                y="count",
                title=chart.get("title") or "Topics",
            )
            st.plotly_chart(fig, use_container_width=True)
        elif chart.get("type") == "line" and data:
            fig = px.line(
                data,
                x="year",
                y="count",
                markers=True,
                title=chart.get("title") or "Trend",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.json(chart)

if st.sidebar.button("Health check"):
    try:
        r = requests.get(f"{API_URL.rstrip('/')}/health", timeout=10)
        st.sidebar.json(r.json())
    except Exception as exc:
        st.sidebar.error(str(exc))
