#!/usr/bin/env python3
"""
Swarm Research Runner
Wraps researcher.py + deep_dive.py for the Managed Agents harness.
Writes structured results to event log so the swarm can track progress.
"""
import os, sys, json, sqlite3, subprocess, datetime

DB_PATH = "/root/managed-agents/sessions.db"
SESSION_ID = os.environ.get("SWARM_SESSION_ID", "unknown")

def log_event(etype, payload):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "INSERT INTO events (session_id, type, payload) VALUES (?, ?, ?)",
        (SESSION_ID, etype, json.dumps(payload, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

def main():
    log_event("research_start", {"ts": datetime.datetime.utcnow().isoformat()})
    
    os.chdir("/root/managed-agents/research")
    
    # Phase 1: Trending scrape
    log_event("research_phase", {"phase": "scrape", "status": "running"})
    r1 = subprocess.run(
        ["python3", "researcher.py"],
        capture_output=True, text=True, timeout=600
    )
    log_event("research_result", {
        "phase": "scrape",
        "rc": r1.returncode,
        "stdout": r1.stdout[-3000:],
        "stderr": r1.stderr[-1000:]
    })
    
    if r1.returncode != 0:
        log_event("research_error", {"phase": "scrape", "msg": r1.stderr})
        print(json.dumps({"status": "error", "phase": "scrape"}))
        sys.exit(1)
    
    # Phase 2: Deep dive (already called by researcher.py in latest version,
    # but keep explicit call for backward compatibility)
    log_event("research_phase", {"phase": "deep_dive", "status": "running"})
    r2 = subprocess.run(
        ["python3", "-c", "import deep_dive; deep_dive.main()"],
        capture_output=True, text=True, timeout=600
    )
    log_event("research_result", {
        "phase": "deep_dive",
        "rc": r2.returncode,
        "stdout": r2.stdout[-3000:],
        "stderr": r2.stderr[-1000:]
    })
    
    # Collect outputs
    reports = sorted([f for f in os.listdir("reports") if f.endswith(".md")], reverse=True)
    drafts = sorted([f for f in os.listdir("skills-drafts") if f.endswith(".md")], reverse=True)
    queue = sorted([f for f in os.listdir("skills-queue") if f.endswith(".json")])
    
    summary = {
        "reports": reports[:3],
        "drafts": drafts[:5],
        "queue_size": len(queue),
        "git_pushed": "Pushed" in r1.stdout or "nothing to commit" in r1.stdout
    }
    
    log_event("research_complete", summary)
    
    # Write pending result for relay
    pending_dir = "/root/managed-agents/pending_results"
    os.makedirs(pending_dir, exist_ok=True)
    with open(os.path.join(pending_dir, f"{SESSION_ID}.json"), "w") as f:
        json.dump({
            "session_id": SESSION_ID,
            "result": f"Daily research done. {len(drafts)} drafts, {len(reports)} reports.",
            "summary": summary,
            "ts": datetime.datetime.utcnow().isoformat()
        }, f, ensure_ascii=False)
    
    print(json.dumps({"status": "done", "summary": summary}, ensure_ascii=False))

if __name__ == "__main__":
    main()
