"""SQLite event log."""
import json, sqlite3, threading
from .config import DB_PATH

_local = threading.local()

def _conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 2000")
        _local.conn = conn
    return conn

def ensure_schema():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                ts TEXT DEFAULT CURRENT_TIMESTAMP,
                type TEXT NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON events(session_id, seq)")
        conn.commit()

def log_event(session_id: str, etype: str, payload: dict):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO events (session_id, type, payload) VALUES (?, ?, ?)",
            (session_id, etype, json.dumps(payload, ensure_ascii=False))
        )
        conn.commit()

def get_events(session_id: str, since_seq: int = 0, limit: int = 0) -> list:
    with _conn() as conn:
        sql = "SELECT seq, ts, type, payload FROM events WHERE session_id=? AND seq > ? ORDER BY seq"
        params = [session_id, since_seq]
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    events = []
    for r in rows:
        try:
            payload = json.loads(r[3])
        except json.JSONDecodeError:
            payload = {"raw": r[3], "parse_error": True}
        events.append({"seq": r[0], "ts": r[1], "type": r[2], "payload": payload})
    return events

def get_recent_tool_results(session_id: str, n: int = 4) -> list:
    """Return last n tool_result events (oldest first)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT seq, payload FROM events WHERE session_id=? AND type='tool_result' ORDER BY seq DESC LIMIT ?",
            (session_id, n)
        ).fetchall()
    out = []
    for r in reversed(rows):
        try:
            out.append(json.loads(r[1]))
        except json.JSONDecodeError:
            pass
    return out


# ── Task Queue ──

def ensure_queue_schema():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                playbook_name TEXT NOT NULL,
                vars TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result_path TEXT,
                error TEXT,
                retries INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_batch ON task_queue(batch_id, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON task_queue(status)")
        conn.commit()
    _migrate_queue_schema()

def _migrate_queue_schema():
    """Add missing columns to existing task_queue table."""
    with _conn() as conn:
        cursor = conn.execute("PRAGMA table_info(task_queue)")
        columns = [row[1] for row in cursor.fetchall()]
        if "retries" not in columns:
            conn.execute("ALTER TABLE task_queue ADD COLUMN retries INTEGER DEFAULT 0")
        if "max_retries" not in columns:
            conn.execute("ALTER TABLE task_queue ADD COLUMN max_retries INTEGER DEFAULT 0")
        conn.commit()

def enqueue(batch_id: str, session_id: str, playbook_name: str, vars: dict, max_retries: int = 0) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO task_queue (batch_id, session_id, playbook_name, vars, max_retries) VALUES (?, ?, ?, ?, ?)",
            (batch_id, session_id, playbook_name, json.dumps(vars, ensure_ascii=False), max_retries)
        )
        conn.commit()
        return cur.lastrowid

def complete_task(task_id: int, result_path: str | None = None, error: str | None = None) -> bool:
    """Complete a task. Returns True if task was retried."""
    with _conn() as conn:
        if error:
            row = conn.execute(
                "SELECT retries, max_retries FROM task_queue WHERE id=?",
                (task_id,)
            ).fetchone()
            if row and row[0] < row[1]:
                conn.execute(
                    "UPDATE task_queue SET status='pending', retries=?, error=NULL, started_at=NULL WHERE id=?",
                    (row[0] + 1, task_id)
                )
                conn.commit()
                return True
            conn.execute(
                "UPDATE task_queue SET status='failed', error=?, completed_at=datetime('now') WHERE id=?",
                (error, task_id)
            )
        else:
            conn.execute(
                "UPDATE task_queue SET status='done', result_path=?, completed_at=datetime('now') WHERE id=?",
                (result_path, task_id)
            )
        conn.commit()
        return False

def claim_next_pending() -> dict | None:
    """Atomically claim one pending task. Returns task dict or None."""
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, batch_id, session_id, playbook_name, vars, retries, max_retries FROM task_queue WHERE status='pending' ORDER BY id LIMIT 1"
        ).fetchone()
        if not row:
            conn.commit()
            return None
        task_id = row[0]
        conn.execute(
            "UPDATE task_queue SET status='running', started_at=datetime('now') WHERE id=?",
            (task_id,)
        )
        conn.commit()
        return {
            "id": task_id,
            "batch_id": row[1],
            "session_id": row[2],
            "playbook_name": row[3],
            "vars": json.loads(row[4]) if row[4] else {},
            "retries": row[5],
            "max_retries": row[6],
        }

def get_batch_status(batch_id: str) -> dict:
    """Return {total, pending, running, done, failed, tasks: [...]}."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, session_id, playbook_name, status, result_path, error, created_at FROM task_queue WHERE batch_id=? ORDER BY id",
            (batch_id,)
        ).fetchall()
    tasks = []
    counts = {"total": 0, "pending": 0, "running": 0, "done": 0, "failed": 0}
    for r in rows:
        counts["total"] += 1
        status = r[3]
        counts[status] = counts.get(status, 0) + 1
        tasks.append({
            "id": r[0], "session_id": r[1], "playbook_name": r[2],
            "status": status, "result_path": r[4], "error": r[5],
            "created_at": r[6]
        })
    return {**counts, "tasks": tasks}
