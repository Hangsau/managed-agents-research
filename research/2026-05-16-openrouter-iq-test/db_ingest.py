"""Import all JSONL data into SQLite database.

Run after each round to keep data/results.db in sync.
Usage: python db_ingest.py
"""

import json
import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent / "data"
DB = BASE / "results.db"


def init_db(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS samples (
        id         INTEGER PRIMARY KEY,
        provider   TEXT NOT NULL,
        model      TEXT NOT NULL,
        probe      TEXT NOT NULL,
        sample_idx INTEGER,
        temperature REAL,
        round      INTEGER,
        ok         INTEGER,
        content    TEXT,
        content_len INTEGER,
        error      TEXT,
        model_id   TEXT,
        source_file TEXT
    );

    CREATE UNIQUE INDEX IF NOT EXISTS uq_samples
        ON samples(provider, model, probe, sample_idx, source_file);

    CREATE TABLE IF NOT EXISTS scores (
        id         INTEGER PRIMARY KEY,
        provider   TEXT NOT NULL,
        model      TEXT NOT NULL,
        probe      TEXT NOT NULL,
        sample_idx INTEGER,
        score      REAL
    );

    CREATE UNIQUE INDEX IF NOT EXISTS uq_scores
        ON scores(provider, model, probe, sample_idx);
    """)
    conn.commit()


def ingest_samples(conn, jsonl_path: Path, source_name: str):
    inserted = 0
    skipped = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO samples
                        (provider, model, probe, sample_idx, temperature, round,
                         ok, content, content_len, error, model_id, source_file)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    r.get("provider", "unknown"),
                    r.get("model", ""),
                    r.get("probe", ""),
                    r.get("sample"),
                    r.get("temperature"),
                    r.get("round"),
                    1 if r.get("ok") else 0,
                    (r.get("content") or "")[:10000],
                    len(r.get("content") or ""),
                    r.get("error"),
                    r.get("model_id"),
                    source_name,
                ))
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"  warn: {e} on {r.get('model')} {r.get('probe')}")
    conn.commit()
    print(f"  {source_name}: +{inserted} inserted, {skipped} already existed")


def ingest_scores(conn, scored_path: Path):
    inserted = 0
    with open(scored_path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("score") is None:
                continue
            conn.execute("""
                INSERT OR REPLACE INTO scores
                    (provider, model, probe, sample_idx, score)
                VALUES (?,?,?,?,?)
            """, (
                r.get("provider", "unknown"),
                r.get("model", ""),
                r.get("probe", ""),
                r.get("sample"),
                r.get("score"),
            ))
            inserted += 1
    conn.commit()
    print(f"  scores: {inserted} records upserted")


def print_summary(conn):
    print("\n=== DB Summary ===")
    rows = conn.execute("""
        SELECT provider, model, COUNT(*) as n,
               SUM(CASE WHEN ok=1 AND content != '' THEN 1 ELSE 0 END) as valid
        FROM samples
        GROUP BY provider, model
        ORDER BY provider, model
    """).fetchall()
    for prov, model, n, valid in rows:
        short = model.split("/")[-1][:40]
        print(f"  [{prov:10s}] {short:42s} total={n} valid={valid}")

    # Score summary
    print("\n=== Score Averages ===")
    rows = conn.execute("""
        SELECT provider, model,
               AVG(score) as mean_score,
               COUNT(*) as n
        FROM scores
        GROUP BY provider, model
        ORDER BY mean_score DESC
    """).fetchall()
    for prov, model, mean, n in rows:
        short = model.split("/")[-1][:40]
        print(f"  [{prov:10s}] {short:42s} mean={mean:.3f} (n={n})")


def main():
    conn = sqlite3.connect(DB)
    init_db(conn)

    sources = [
        (BASE / "consistency.jsonl", "consistency"),
        (BASE / "nvidia.jsonl", "nvidia"),
    ]
    for path, name in sources:
        if path.exists():
            print(f"Ingesting {name}...")
            ingest_samples(conn, path, name)

    scored = BASE / "scored.jsonl"
    if scored.exists():
        print("Ingesting scores...")
        ingest_scores(conn, scored)

    print_summary(conn)
    conn.close()
    print(f"\nDB: {DB}")


if __name__ == "__main__":
    main()
