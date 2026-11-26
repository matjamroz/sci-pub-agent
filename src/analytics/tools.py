from __future__ import annotations

from typing import Any, Optional

from src.ingest.store import MetadataStore

# Years outside this range stay in the database and out of trend counts.
TREND_YEAR_MIN = 1900
TREND_YEAR_MAX = 2026


def describe_growth(series: list[dict[str, Any]]) -> Optional[str]:
    """Rise, fall, or a similar level. One year is not a multi-year trend."""
    if len(series) < 2:
        return None
    first = int(series[0]["count"])
    last = int(series[-1]["count"])
    if first <= 0:
        if last > 0:
            return "wzrost"
        return "podobny poziom"
    change = (last - first) / first
    if change > 0.1:
        return "wzrost"
    if change < -0.1:
        return "spadek"
    return "podobny poziom"


class AnalyticsTools:
    def __init__(self, store: MetadataStore):
        self.store = store

    def topic_trend(
        self,
        topic: str,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> dict[str, Any]:
        conn = self.store.connection()
        topic_ids = self._topic_ids(topic)
        if not topic_ids:
            clause, id_params = "0", []
        else:
            clause, id_params = self._topic_clause(topic_ids)
        sql = f"""
            SELECT year, COUNT(*) AS n
            FROM publications
            WHERE {clause}
              AND year >= ? AND year <= ?
        """
        params: list[Any] = [*id_params, TREND_YEAR_MIN, TREND_YEAR_MAX]
        if year_from is not None:
            sql += " AND year >= ?"
            params.append(year_from)
        if year_to is not None:
            sql += " AND year <= ?"
            params.append(year_to)
        sql += " GROUP BY year ORDER BY year"
        rows = list(conn.execute(sql, params))
        series = [{"year": r["year"], "count": r["n"]} for r in rows]
        mn, mx = self.store.trend_year_span(TREND_YEAR_MIN, TREND_YEAR_MAX)
        total = sum(p["count"] for p in series)
        pattern = describe_growth(series)
        note = None
        if not series:
            note = (
                f"Brak lat z zakresu {TREND_YEAR_MIN}–{TREND_YEAR_MAX} "
                "dla tego kierunku."
            )
        elif pattern is None:
            year = series[0]["year"]
            note = (
                f"W danych jest jeden rok ({year}). Podaję liczebność za ten rok "
                "i nie opisuję tego jako wieloletniego trendu."
            )
        publications = self._matching_publications(
            topic, year=None, trend_only=True, limit=8
        )
        return {
            "topic": topic,
            "series": series,
            "total": total,
            "year_span": [mn, mx],
            "pattern": pattern,
            "note": note,
            "publications": publications,
        }

    def top_topics(self, year: Optional[int] = None, n: int = 10) -> dict[str, Any]:
        conn = self.store.connection()
        stored = conn.execute("SELECT topic_id, label FROM topics").fetchall()
        if stored:
            counted = []
            for row in stored:
                if year is None:
                    count = conn.execute(
                        "SELECT COUNT(*) AS n FROM publications WHERE topic_id = ?",
                        (int(row["topic_id"]),),
                    ).fetchone()["n"]
                else:
                    count = conn.execute(
                        """
                        SELECT COUNT(*) AS n FROM publications
                        WHERE topic_id = ? AND year = ?
                        """,
                        (int(row["topic_id"]), year),
                    ).fetchone()["n"]
                counted.append(
                    {
                        "topic_id": int(row["topic_id"]),
                        "label": row["label"],
                        "count": int(count),
                    }
                )
            counted.sort(key=lambda item: item["count"], reverse=True)
            total = sum(item["count"] for item in counted)
            topics = counted[:n]
        elif year is None:
            rows = conn.execute(
                """
                SELECT topic_id, topic_label, COUNT(*) AS n
                FROM publications
                WHERE topic_id IS NOT NULL
                GROUP BY topic_id, topic_label
                ORDER BY n DESC
                LIMIT ?
                """,
                (n,),
            ).fetchall()
            topics = [
                {
                    "topic_id": r["topic_id"],
                    "label": r["topic_label"],
                    "count": r["n"],
                }
                for r in rows
            ]
            total = self._counted_publications(year=year)
        else:
            rows = conn.execute(
                """
                SELECT topic_id, topic_label, COUNT(*) AS n
                FROM publications
                WHERE topic_id IS NOT NULL AND year = ?
                GROUP BY topic_id, topic_label
                ORDER BY n DESC
                LIMIT ?
                """,
                (year, n),
            ).fetchall()
            topics = [
                {
                    "topic_id": r["topic_id"],
                    "label": r["topic_label"],
                    "count": r["n"],
                }
                for r in rows
            ]
            total = self._counted_publications(year=year)
        return {
            "year": year,
            "topics": topics,
            "total": total,
            "publications": self._publications_for_topics(
                [t["topic_id"] for t in topics], year=year, limit=8
            ),
        }

    def author_profile(self, name: str) -> dict[str, Any]:
        authors = self.store.search_authors(name, limit=5)
        if not authors:
            return {"query": name, "matches": [], "note": "No author found."}
        conn = self.store.connection()
        profiles = []
        for author in authors:
            pubs = conn.execute(
                """
                SELECT p.object_id, p.title, p.year, p.topic_label
                FROM publications p
                JOIN authorships a ON a.object_id = p.object_id
                WHERE a.author_key = ?
                ORDER BY p.year, p.title
                """,
                (author["author_key"],),
            ).fetchall()
            coauthors = conn.execute(
                """
                SELECT au.name, au.last_name, COUNT(*) AS collabs
                FROM authorships a1
                JOIN authorships a2 ON a1.object_id = a2.object_id
                  AND a1.author_key != a2.author_key
                JOIN authors au ON au.author_key = a2.author_key
                WHERE a1.author_key = ?
                GROUP BY au.author_key
                ORDER BY collabs DESC, au.last_name
                LIMIT 20
                """,
                (author["author_key"],),
            ).fetchall()
            topics = sorted(
                {
                    p["topic_label"]
                    for p in pubs
                    if p["topic_label"]
                }
            )
            profiles.append(
                {
                    "author_key": author["author_key"],
                    "name": f"{author['name']} {author['last_name']}".strip(),
                    "orcid_id": author["orcid_id"],
                    "publications": [dict(p) for p in pubs],
                    "topics": topics,
                    "coauthors": [
                        {
                            "name": f"{c['name']} {c['last_name']}".strip(),
                            "collaborations": c["collabs"],
                        }
                        for c in coauthors
                    ],
                }
            )
        return {"query": name, "matches": profiles}

    def publication_authors(self, object_ids: list[str]) -> dict[str, Any]:
        """Authors for one or more publications (follow-ups like 'who wrote that paper')."""
        conn = self.store.connection()
        papers = []
        for oid in object_ids:
            if not oid:
                continue
            pub = conn.execute(
                "SELECT object_id, title, year FROM publications WHERE object_id = ?",
                (oid,),
            ).fetchone()
            if not pub:
                continue
            authors = conn.execute(
                """
                SELECT au.name, au.last_name, a.position
                FROM authorships a
                JOIN authors au ON au.author_key = a.author_key
                WHERE a.object_id = ?
                ORDER BY a.position
                """,
                (oid,),
            ).fetchall()
            papers.append(
                {
                    "object_id": pub["object_id"],
                    "title": pub["title"],
                    "year": pub["year"],
                    "authors": [
                        f"{r['name']} {r['last_name']}".strip() for r in authors
                    ],
                }
            )
        return {"object_ids": object_ids, "papers": papers}

    def direction_authors(
        self, direction: str, limit_authors: int = 20, limit_papers: int = 8
    ) -> dict[str, Any]:
        """Authors whose papers were classified into this direction."""
        conn = self.store.connection()
        topic_ids = self._topic_ids(direction)
        if not topic_ids:
            return {
                "query": direction,
                "authors": [],
                "total_authors": 0,
                "note": "Nie znaleziono takiego kierunku w zbiorze.",
            }
        clause, id_params = self._topic_clause(topic_ids)
        total_row = conn.execute(
            f"SELECT COUNT(*) AS n FROM publications WHERE {clause}",
            id_params,
        ).fetchone()
        if int(total_row["n"]) == 0:
            return {
                "query": direction,
                "authors": [],
                "total_authors": 0,
                "note": "Nie znaleziono takiego kierunku w zbiorze.",
            }
        author_rows = conn.execute(
            f"""
            SELECT au.author_key, au.name, au.last_name, au.orcid_id,
                   COUNT(DISTINCT p.object_id) AS n
            FROM publications p
            JOIN authorships a ON a.object_id = p.object_id
            JOIN authors au ON au.author_key = a.author_key
            WHERE p.{clause}
            GROUP BY au.author_key
            ORDER BY n DESC, au.last_name
            LIMIT ?
            """,
            [*id_params, limit_authors],
        ).fetchall()
        total_authors = conn.execute(
            f"""
            SELECT COUNT(DISTINCT a.author_key) AS n
            FROM publications p
            JOIN authorships a ON a.object_id = p.object_id
            WHERE p.{clause}
            """,
            id_params,
        ).fetchone()
        authors = []
        for row in author_rows:
            papers = conn.execute(
                f"""
                SELECT p.object_id, p.title, p.year, p.topic_label, p.doi
                FROM publications p
                JOIN authorships a ON a.object_id = p.object_id
                WHERE a.author_key = ?
                  AND p.{clause}
                ORDER BY p.year, p.title
                LIMIT ?
                """,
                [row["author_key"], *id_params, limit_papers],
            ).fetchall()
            authors.append(
                {
                    "author_key": row["author_key"],
                    "name": f"{row['name']} {row['last_name']}".strip(),
                    "orcid_id": row["orcid_id"],
                    "n_publications": int(row["n"]),
                    "topics": sorted(
                        {p["topic_label"] for p in papers if p["topic_label"]}
                    ),
                    "publications": [dict(p) for p in papers],
                }
            )
        return {
            "query": direction,
            "authors": authors,
            "total_authors": int(total_authors["n"]),
            "note": None,
        }

    def _topic_ids(self, direction: str) -> list[int]:
        """Match a direction name to topic ids. Six stored labels, not a text scan."""
        needle = (direction or "").strip().lower()
        if not needle:
            return []
        conn = self.store.connection()
        rows = conn.execute("SELECT topic_id, label FROM topics").fetchall()
        if not rows:
            rows = conn.execute(
                """
                SELECT topic_id, topic_label AS label
                FROM publications
                WHERE topic_id IS NOT NULL
                GROUP BY topic_id, topic_label
                """
            ).fetchall()
        found: list[int] = []
        for row in rows:
            label = (row["label"] or "").lower()
            if needle == str(row["topic_id"]) or needle in label:
                found.append(int(row["topic_id"]))
        return found

    def _topic_clause(self, topic_ids: list[int]) -> tuple[str, list[Any]]:
        marks = ",".join("?" for _ in topic_ids)
        return f"topic_id IN ({marks})", [int(i) for i in topic_ids]

    def _matching_publications(
        self,
        topic: str,
        year: Optional[int],
        trend_only: bool,
        limit: int,
    ) -> list[dict[str, Any]]:
        topic_ids = self._topic_ids(topic)
        if not topic_ids:
            return []
        clause, params = self._topic_clause(topic_ids)
        sql = f"""
            SELECT object_id, title, year, topic_label, doi
            FROM publications
            WHERE {clause}
        """
        if year is not None:
            sql += " AND year = ?"
            params.append(year)
        if trend_only:
            sql += " AND year >= ? AND year <= ?"
            params.extend([TREND_YEAR_MIN, TREND_YEAR_MAX])
        # Index lookup stops after LIMIT. Sorting every title in the direction
        # would read the whole topic just to show a short source list.
        sql += " LIMIT ?"
        params.append(limit)
        rows = self.store.connection().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _counted_publications(self, year: Optional[int]) -> int:
        sql = "SELECT COUNT(*) AS n FROM publications WHERE topic_id IS NOT NULL"
        params: list[Any] = []
        if year is not None:
            sql += " AND year = ?"
            params.append(year)
        row = self.store.connection().execute(sql, params).fetchone()
        return int(row["n"])

    def _publications_for_topics(
        self,
        topic_ids: list[int],
        year: Optional[int],
        limit: int,
    ) -> list[dict[str, Any]]:
        ids = [int(i) for i in topic_ids if i is not None]
        if not ids:
            return []
        marks = ",".join("?" for _ in ids)
        sql = f"""
            SELECT object_id, title, year, topic_label, doi
            FROM publications
            WHERE topic_id IN ({marks})
        """
        params: list[Any] = list(ids)
        if year is not None:
            sql += " AND year = ?"
            params.append(year)
        sql += " LIMIT ?"
        params.append(limit)
        rows = self.store.connection().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def coauthor_graph(self, author: str, depth: int = 1) -> dict[str, Any]:
        depth = max(1, min(int(depth), 2))
        authors = self.store.search_authors(author, limit=1)
        if not authors:
            return {"query": author, "nodes": [], "edges": [], "note": "No author found."}
        seed = authors[0]["author_key"]
        conn = self.store.connection()
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        frontier = {seed}
        visited: set[str] = set()
        for _ in range(depth):
            next_frontier: set[str] = set()
            for ak in frontier:
                if ak in visited:
                    continue
                visited.add(ak)
                row = conn.execute(
                    "SELECT * FROM authors WHERE author_key = ?", (ak,)
                ).fetchone()
                if row:
                    nodes[ak] = {
                        "author_key": ak,
                        "name": f"{row['name']} {row['last_name']}".strip(),
                    }
                neighbors = conn.execute(
                    """
                    SELECT a2.author_key AS neighbor, COUNT(*) AS w
                    FROM authorships a1
                    JOIN authorships a2 ON a1.object_id = a2.object_id
                      AND a1.author_key != a2.author_key
                    WHERE a1.author_key = ?
                    GROUP BY a2.author_key
                    """,
                    (ak,),
                ).fetchall()
                for nb in neighbors:
                    nk = nb["neighbor"]
                    edges.append(
                        {"source": ak, "target": nk, "weight": nb["w"]}
                    )
                    next_frontier.add(nk)
                    nrow = conn.execute(
                        "SELECT * FROM authors WHERE author_key = ?", (nk,)
                    ).fetchone()
                    if nrow:
                        nodes[nk] = {
                            "author_key": nk,
                            "name": f"{nrow['name']} {nrow['last_name']}".strip(),
                        }
            frontier = next_frontier - visited
        # Deduplicate undirected edges
        seen = set()
        uniq_edges = []
        for e in edges:
            a, b = sorted([e["source"], e["target"]])
            key = (a, b)
            if key in seen:
                continue
            seen.add(key)
            uniq_edges.append({"source": a, "target": b, "weight": e["weight"]})
        return {
            "query": author,
            "seed": seed,
            "depth": depth,
            "nodes": list(nodes.values()),
            "edges": uniq_edges,
        }
