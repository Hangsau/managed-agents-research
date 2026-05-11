#!/usr/bin/env python3
"""Dispatcher: launch a background agent run and return immediately."""
import subprocess, sys, uuid, json, os

LOG_DIR = "/root/managed-agents/logs"

def dispatch(goal: str, max_turns: int = 20):
    sid = f"bg-{uuid.uuid4().hex[:6]}"
    log_path = os.path.join(LOG_DIR, f"{sid}.log")
    os.makedirs(LOG_DIR, exist_ok=True)

    cmd = [
        "python3", "run_agent.py", sid, goal, f"--max-turns={max_turns}"
    ]

    with open(log_path, "w") as logf:
        proc = subprocess.Popen(
            cmd,
            stdout=logf,
            stderr=subprocess.STDOUT,
            cwd="/root/managed-agents"
        )

    return {
        "session_id": sid,
        "pid": proc.pid,
        "log": log_path,
        "status": "running"
    }

if __name__ == "__main__":
    goal = sys.argv[1] if len(sys.argv) > 1 else "echo hello"
    max_turns = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    result = dispatch(goal, max_turns)
    print(json.dumps(result, ensure_ascii=False))
