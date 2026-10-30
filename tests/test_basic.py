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
