import sqlite3

uri = "file:C:/Users/matja/Projects/sci-pub-agent/data/processed/chroma/chroma.sqlite3?mode=ro"
conn = sqlite3.connect(uri, uri=True, timeout=3)
tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables", tables)
for name in tables:
    if name.startswith("sqlite_"):
        continue
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    except sqlite3.Error as exc:
        print(name, "err", exc)
        continue
    print(name, count)
