from src.agent.orchestrator import AgentOrchestrator, _cites_source, _grounded_titles
from src.analytics.tools import AnalyticsTools, describe_growth
from src.ingest.store import MetadataStore
from src.retrieve.ranking import ndcg_at_k, recall_at_k
from src.schemas import Author, Publication


def test_describe_growth_labels():
    assert describe_growth([]) is None
    assert describe_growth([{"year": 2000, "count": 4}]) is None
    assert describe_growth(
        [{"year": 2000, "count": 10}, {"year": 2010, "count": 20}]
    ) == "wzrost"
    assert describe_growth(
        [{"year": 2000, "count": 20}, {"year": 2010, "count": 10}]
    ) == "spadek"
    assert describe_growth(
        [{"year": 2000, "count": 10}, {"year": 2010, "count": 11}]
    ) == "podobny poziom"


def test_trend_ignores_years_outside_1900_2026(tmp_path):
    store = MetadataStore(tmp_path / "pubs.db")
    author = Author(name="Ada", last_name="Lovelace", orcid_id="0000-0001-0000-0001")
    years = [-1, 2000, 2010, 2010, 2010, 2916]
    pubs = [
        Publication(
            object_id=str(i),
            title=f"Paper {i}",
            year=year,
            topic_id=1,
            topic_label="neutrino",
            authors=[author],
        )
        for i, year in enumerate(years)
    ]
    store.upsert_publications(pubs)
    tools = AnalyticsTools(store)
    trend = tools.topic_trend("neutrino")
    assert [point["year"] for point in trend["series"]] == [2000, 2010]
    assert trend["series"][0]["count"] == 1
    assert trend["series"][1]["count"] == 3
    assert trend["pattern"] == "wzrost"
    assert all(paper["year"] in {2000, 2010} for paper in trend["publications"])

    people = tools.direction_authors("neutrino")
    assert people["authors"][0]["orcid_id"] == "0000-0001-0000-0001"
    assert people["authors"][0]["n_publications"] == 6
    assert people["total_authors"] == 1


def test_single_year_is_not_called_a_trend(tmp_path):
    store = MetadataStore(tmp_path / "one.db")
    pubs = [
        Publication(
            object_id="a",
            title="A",
            year=2000,
            topic_id=1,
            topic_label="silica",
            authors=[],
        ),
        Publication(
            object_id="b",
            title="B",
            year=2916,
            topic_id=1,
            topic_label="silica",
            authors=[],
        ),
    ]
    store.upsert_publications(pubs)
    trend = AnalyticsTools(store).topic_trend("silica")
    assert trend["pattern"] is None
    assert trend["series"] == [{"year": 2000, "count": 1}]
    assert "jeden rok" in trend["note"]


def test_empty_question_does_not_search():
    class Dummy:
        def search(self, *args, **kwargs):
            raise AssertionError("empty input must not search")

    agent = AgentOrchestrator(Dummy(), None, llm=object())
    result = agent.ask("   ")
    assert result.intent == "off_topic"
    assert "Brakuje treści" in result.answer
    assert result.sources == []


def test_new_topic_is_not_glued_to_the_previous_one():
    called = {"n": 0}

    class Boom:
        def chat(self, *args, **kwargs):
            called["n"] += 1
            raise RuntimeError("rewrite should not run for a new topic")

    agent = AgentOrchestrator(object(), None, llm=Boom())
    history = [
        {"role": "user", "content": "daj jakieś znane książki z matematyki"},
        {"role": "assistant", "content": "Znalazłem prace o historii matematyki."},
    ]
    query, intent = agent._resolve_turn("a historia polski?", history)
    assert "matem" not in query.lower()
    assert "historia" in query.lower()
    assert intent == "semantic"
    refined, _ = agent._resolve_turn("ale do nauki matematyki", history)
    assert refined.lower().startswith("do nauki")
    assert called["n"] == 0

    agent._resolve_turn("a kto napisał tę pracę?", history)
    assert called["n"] == 1


def test_answer_prompt_skips_the_previous_essay():
    agent = AgentOrchestrator(object(), None, llm=object())
    sources = [
        {
            "text": f"abstrakt {i}",
            "metadata": {"title": f"Tytuł {i}", "year": 2000 + i},
        }
        for i in range(1, 11)
    ]
    messages = agent._synthesis_messages(
        "a historia polski?",
        "historia polski",
        "semantic",
        sources,
        {"search_publications": {"n": 10}},
        [
            {"role": "user", "content": "książki z matematyki"},
            {
                "role": "assistant",
                "content": "Witaj ponownie! historia matematyki jest fascynująca.",
            },
        ],
    )
    blob = messages[-1]["content"]
    assert "Witaj ponownie" not in blob
    assert "historia matematyki jest fascynująca" not in blob
    assert "[10] Tytuł 10" in blob
    assert "abstrakt" not in blob


def test_answer_that_ignores_sources_is_replaced_with_titles():
    assert not _cites_source(
        'Co to jest "Euklides" w matematyce?',
        [{"metadata": {"title": "Recepcja polskich szkolnych podręczników do matematyki"}}],
    )
    assert _cites_source(
        "Najbliżej jest Recepcja polskich szkolnych podręczników do matematyki (2017).",
        [{"metadata": {"title": "Recepcja polskich szkolnych podręczników do matematyki"}}],
    )
    listed = _grounded_titles(
        "daj książki z matematyki",
        [{"metadata": {"title": "Recepcja polskich podręczników", "year": 2017}}],
    )
    assert "klasycznych podręczników" in listed
    assert "Recepcja polskich podręczników" in listed


def test_ndcg_rewards_a_higher_rank():
    relevant = ["a", "b"]
    assert ndcg_at_k(["a", "b"], relevant, 10) > ndcg_at_k(["b", "x", "a"], relevant, 10)
    assert recall_at_k(["a", "b", "c"], relevant, 10) == 1.0
    assert recall_at_k(["c"], relevant, 10) == 0.0
