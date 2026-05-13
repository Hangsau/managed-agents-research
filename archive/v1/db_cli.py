#!/usr/bin/env python3
"""Safe SQLite CLI wrapper for ma commands."""
import sqlite3, sys, json, os

DB = "/root/managed-agents/sessions.db"

def db_exec(sql, params=(), fetchone=False):
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.execute(sql, params)
    conn.commit()
    row = cur.fetchone() if fetchone else cur.fetchall()
    conn.close()
    return row

def cmd_resume(sid, msg):
    payload = json.dumps({"msg": msg}, ensure_ascii=False)
    db_exec("INSERT INTO events (session_id, type, payload) VALUES (?, 'user_message', ?)", (sid, payload))
    print(f"Inserted user_message for {sid}")

def cmd_events(sid):
    rows = db_exec("SELECT seq, ts, type, payload FROM events WHERE session_id = ? ORDER BY seq", (sid,))
    for r in rows:
        print(f"{r[0]}|{r[1]}|{r[2]}|{r[3]}")

def cmd_status():
    rows = db_exec("""
        SELECT session_id, MAX(ts) as last_ts,
               (SELECT type FROM events e2 WHERE e2.session_id = e.session_id ORDER BY e2.seq DESC LIMIT 1) as last_type,
               COUNT(*) as turns
        FROM events e
        GROUP BY session_id
        ORDER BY last_ts DESC
        LIMIT 20
    """)
    for r in rows:
        print(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}")

def cmd_ls():
    rows = db_exec("""
        SELECT session_id, COUNT(*) as events, MIN(ts) as started, MAX(ts) as updated
        FROM events
        GROUP BY session_id
        ORDER BY updated DESC
    """)
    for r in rows:
        print(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: db_cli.py <command> [args...]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "resume" and len(sys.argv) >= 4:
        cmd_resume(sys.argv[2], sys.argv[3])
    elif cmd == "events" and len(sys.argv) >= 3:
        cmd_events(sys.argv[2])
    elif cmd == "status":
        cmd_status()
    elif cmd == "ls":
        cmd_ls()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
