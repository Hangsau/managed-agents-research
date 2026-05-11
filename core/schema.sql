-- Phase 1: Single-table append-only event log
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
    type TEXT NOT NULL,  -- 'user_goal', 'planner_decision', 'tool_call', 'tool_result', 'completion', 'error'
    payload TEXT NOT NULL  -- JSON
);

CREATE INDEX IF NOT EXISTS idx_session ON events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_type ON events(type);
