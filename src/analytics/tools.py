from __future__ import annotations

from typing import Any, Optional

from src.ingest.store import MetadataStore


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
        sql = """
            SELECT year, COUNT(*) AS n
            FROM publications
            WHERE (topic_label LIKE ? OR CAST(topic_id AS TEXT) = ?)
              AND year IS NOT NULL
        """
        params: list[Any] = [f"%{topic}%", topic]
        if year_from is not None:
            sql += " AND year >= ?"
            params.append(year_from)
        if year_to is not None:
            sql += " AND year <= ?"
            params.append(year_to)
        sql += " GROUP BY year ORDER BY year"
        rows = list(conn.execute(sql, params))
        series = [{"year": r["year"], "count": r["n"]} for r in rows]
        mn, mx = self.store.year_span()
        note = None
        if mn is not None and mx is not None and mn == mx:
            note = (
                f"Dataset spans a single year ({mn}); temporal trend analysis "
                "is not meaningful until multi-year data is loaded."
            )
        return {
            "topic": topic,
            "series": series,
            "total": sum(p["count"] for p in series),
            "year_span": [mn, mx],
            "note": note,
        }

    def top_topics(self, year: Optional[int] = None, n: int = 10) -> dict[str, Any]:
        conn = self.store.connection()
        if year is None:
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
        return {
            "year": year,
            "topics": [
                {
                    "topic_id": r["topic_id"],
                    "label": r["topic_label"],
                    "count": r["n"],
                }
                for r in rows
            ],
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
