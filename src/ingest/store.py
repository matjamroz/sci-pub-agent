from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from src.schemas import Publication


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS publications (
    object_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER,
    doi TEXT,
    abstract TEXT,
    keywords TEXT,
    topic_id INTEGER,
    topic_label TEXT
);

CREATE TABLE IF NOT EXISTS authors (
    author_key TEXT PRIMARY KEY,
    name TEXT,
    last_name TEXT,
    orcid_id TEXT,
    uuid TEXT,
    object_id TEXT
);

CREATE TABLE IF NOT EXISTS authorships (
    object_id TEXT NOT NULL,
    author_key TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (object_id, author_key),
    FOREIGN KEY (object_id) REFERENCES publications(object_id),
    FOREIGN KEY (author_key) REFERENCES authors(author_key)
);

CREATE TABLE IF NOT EXISTS topics (
    topic_id INTEGER PRIMARY KEY,
    label TEXT NOT NULL,
    keywords TEXT
);

CREATE INDEX IF NOT EXISTS idx_pubs_year ON publications(year);
CREATE INDEX IF NOT EXISTS idx_pubs_topic ON publications(topic_id);
CREATE INDEX IF NOT EXISTS idx_authorships_author ON authorships(author_key);
"""


class MetadataStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def reset(self) -> None:
        self._conn.executescript(
            """
            DELETE FROM authorships;
            DELETE FROM authors;
            DELETE FROM publications;
            DELETE FROM topics;
            """
        )
        self._conn.commit()

    def upsert_publications(self, pubs: Iterable[Publication]) -> int:
        count = 0
        for pub in pubs:
            keywords = " | ".join(pub.keyword_list())
            self._conn.execute(
                """
                INSERT INTO publications(object_id, title, year, doi, abstract, keywords, topic_id, topic_label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(object_id) DO UPDATE SET
                    title=excluded.title,
                    year=excluded.year,
                    doi=excluded.doi,
                    abstract=excluded.abstract,
                    keywords=excluded.keywords,
                    topic_id=excluded.topic_id,
                    topic_label=excluded.topic_label
                """,
                (
                    pub.object_id,
                    pub.title,
                    pub.year,
                    pub.doi,
                    pub.primary_abstract(),
                    keywords,
                    pub.topic_id,
                    pub.topic_label,
                ),
            )
            self._conn.execute("DELETE FROM authorships WHERE object_id = ?", (pub.object_id,))
            for pos, author in enumerate(pub.authors):
                self._conn.execute(
                    """
                    INSERT INTO authors(author_key, name, last_name, orcid_id, uuid, object_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(author_key) DO UPDATE SET
                        name=excluded.name,
                        last_name=excluded.last_name,
                        orcid_id=COALESCE(excluded.orcid_id, authors.orcid_id),
                        uuid=COALESCE(excluded.uuid, authors.uuid),
                        object_id=COALESCE(excluded.object_id, authors.object_id)
                    """,
                    (
                        author.author_key,
                        author.name,
                        author.last_name,
                        author.orcid_id,
                        author.uuid,
                        author.object_id,
                    ),
                )
                self._conn.execute(
                    """
                    INSERT INTO authorships(object_id, author_key, position)
                    VALUES (?, ?, ?)
                    """,
                    (pub.object_id, author.author_key, pos),
                )
            count += 1
        self._conn.commit()
        return count

    def upsert_topics(self, topics: dict[int, dict]) -> None:
        for topic_id, info in topics.items():
            self._conn.execute(
                """
                INSERT INTO topics(topic_id, label, keywords)
                VALUES (?, ?, ?)
                ON CONFLICT(topic_id) DO UPDATE SET
                    label=excluded.label,
                    keywords=excluded.keywords
                """,
                (topic_id, info.get("label", f"topic_{topic_id}"), info.get("keywords", "")),
            )
        self._conn.commit()

    def count_publications(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM publications").fetchone()
        return int(row["c"])

    def year_span(self) -> tuple[Optional[int], Optional[int]]:
        row = self._conn.execute(
            "SELECT MIN(year) AS mn, MAX(year) AS mx FROM publications WHERE year IS NOT NULL"
        ).fetchone()
        return row["mn"], row["mx"]

    def fetch_publication(self, object_id: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM publications WHERE object_id = ?", (object_id,)
        ).fetchone()

    def search_authors(self, query: str, limit: int = 10) -> list[sqlite3.Row]:
        q = f"%{query.strip()}%"
        return list(
            self._conn.execute(
                """
                SELECT * FROM authors
                WHERE name LIKE ? OR last_name LIKE ? OR (name || ' ' || last_name) LIKE ?
                   OR (last_name || ' ' || name) LIKE ?
                LIMIT ?
                """,
                (q, q, q, q, limit),
            )
        )

    def connection(self) -> sqlite3.Connection:
        return self._conn
