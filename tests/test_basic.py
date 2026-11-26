from src.ingest.load_jsonl import parse_raw_record
from src.agent.orchestrator import classify_intent
from src.ingest.chunking import chunk_publication


def test_parse_author_key_prefers_orcid():
    pub = parse_raw_record(
        {
            "objectId": "x1",
            "title": "T",
            "year": 2001,
            "abstracts": [{"languageCode": "eng", "content": "Hello"}],
            "keywords": [{"languageCode": "eng", "keywords": ["a b"]}],
            "authors": [
                {
                    "objectId": "a1",
                    "name": "Ada",
                    "lastName": "Lovelace",
                    "orcidId": "0000-0001-2345-6789",
                    "uuid": "UU",
                }
            ],
        }
    )
    assert pub.authors[0].author_key.startswith("orcid:")
    assert "Hello" in pub.primary_abstract()
    both = parse_raw_record(
        {
            "objectId": "x3",
            "title": "Title",
            "year": 2001,
            "abstracts": [
                {"languageCode": "eng", "content": "English abstract"},
                {"languageCode": "pol", "content": "Polski abstrakt"},
            ],
            "keywords": [
                {"languageCode": "eng", "keywords": ["alpha"]},
                {"languageCode": "pol", "keywords": ["beta"]},
            ],
            "authors": [],
        }
    )
    text = both.publication_search_text(max_chars=3200)
    assert "English abstract" in text
    assert "Polski abstrakt" in text
    assert "alpha" in text and "beta" in text
    assert len(both.publication_search_text(max_chars=12)) == 12


def test_chunk_single_for_short_text():
    pub = parse_raw_record(
        {
            "objectId": "x2",
            "title": "Short",
            "year": 2000,
            "abstracts": [{"languageCode": "eng", "content": "Abs"}],
            "keywords": [],
            "authors": [],
        }
    )
    chunks = chunk_publication(pub)
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["object_id"] == "x2"


def test_intent_routing():
    assert classify_intent("Najpopularniejsze tematy w zbiorze") == "trend"
    assert classify_intent("Profil autora Jan Kowalski") == "author"
    assert classify_intent("Współautorzy dla Anna Nowak") == "coauthor"
    assert classify_intent("Papers about sol-gel silica voltammetry") == "semantic"
    assert classify_intent("List topic clusters present in the database") == "trend"
    assert classify_intent("Jakie tematy dominują w publikacjach?") == "trend"
    assert classify_intent("co tam") == "chitchat"
    assert classify_intent("Cześć!") == "chitchat"
    assert classify_intent("hello") == "chitchat"
    assert classify_intent("Who are the authors of that paper?") == "author"
    assert classify_intent("A kto są autorzy tej pracy?") == "author"
    assert classify_intent("Kto publikuje w kierunku neutrino") == "direction_authors"
    assert classify_intent("Who publishes in machine learning?") == "direction_authors"
    assert classify_intent("Jak wygląda wzorzec rozwoju kierunku neutrino") == "trend"
    assert classify_intent("Jaka jest pogoda na jutro?") == "off_topic"
    assert classify_intent("Papers about weather systems") == "semantic"
