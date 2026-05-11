#!/usr/bin/env python3
"""
Phase 1: Managed Agents Harness
- Single-brain (OpenRouter free tier)
- SQLite append-only event log
- Wake/resume via session_id
- Micro-task loop: plan → execute → persist → sleep
"""
import os, sys, json, sqlite3, time, subprocess, textwrap
from datetime import datetime

DB_PATH = "/root/managed-agents/sessions.db"
API_KEY = "sk-W4SX3Txqg0Dhdyp29KIV2hgHiHrvqMEct0v2uWLI4800pXURjrjmSGHnAUcvWEdA"
API_URL = "https://opencode.ai/zen/go/v1/chat/completions"
MODEL = "deepseek-v4-flash"  # fast, cheap, high token limit via OpenCode Go

SYSTEM_PROMPT = """You are a planner. Given a goal and past results, decide the single next step.
Output ONLY valid JSON with keys: thought, action, args.
Actions: bash, read_file, write_file, complete, ask_user.
Example: {"thought":"List files","action":"bash","args":{"cmd":"ls -la","workdir":"/tmp"}}

IMPORTANT:
- bash ALREADY runs inside an isolated container. Do NOT prefix commands with 'docker run'.
- Inside bash, the working directory is /workspace/ which maps to the host workdir and PERSISTS.
- To create files that persist, write them to /workspace/ inside bash (e.g., "/workspace/output.txt").
- read_file reads from the HOST filesystem, so use the host path (e.g., "/tmp/output.txt" if workdir was /tmp).
No text outside JSON."""

def db_exec(sql, params=(), fetchone=False):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.execute(sql, params)
    conn.commit()
    row = cur.fetchone() if fetchone else cur.fetchall()
    conn.close()
    return row

def log_event(session_id, etype, payload):
    db_exec("INSERT INTO events (session_id, type, payload) VALUES (?, ?, ?)",
            (session_id, etype, json.dumps(payload, ensure_ascii=False)))

def get_events(session_id, since_seq=0):
    rows = db_exec("SELECT seq, ts, type, payload FROM events WHERE session_id=? AND seq > ? ORDER BY seq",
                   (session_id, since_seq))
    return [{"seq": r[0], "ts": r[1], "type": r[2], "payload": json.loads(r[3])} for r in rows]

def call_llm(messages, max_tokens=1000):
    import urllib.request
    data = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2
    }).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "ManagedAgents-Harness/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            if "choices" in result and result["choices"]:
                msg = result["choices"][0]["message"]
                content = msg.get("content")
                # Handle reasoning models (DeepSeek, Kimi, etc.)
                if not content and msg.get("reasoning_content"):
                    content = msg["reasoning_content"]
                if not content and msg.get("reasoning"):
                    content = msg["reasoning"]
                if not content and msg.get("reasoning_details"):
                    content = msg["reasoning_details"][0].get("text", "")
                if not content:
                    content = json.dumps({"error": "Model returned empty content", "model": result.get("model")})
                return content
            else:
                return json.dumps({"error": result.get("error", "No choices in response")})
    except Exception as e:
        return json.dumps({"error": str(e)})

def execute_action(action, args, session_id="unknown"):
    import subprocess as sp
    
    if action == "bash":
        cmd = args.get("cmd", "")
        # Auto-correct common model mistake: trying to run docker inside docker
        import re
        # Pattern: docker run [flags] image command...
        docker_run_match = re.search(r'docker\s+run\s+(?:--[a-z-]+\s+|\s+)*(?:\S+\s+)(.*)', cmd)
        if docker_run_match:
            cmd = docker_run_match.group(1).strip()
            print(f"[AUTO-CORRECT] Stripped 'docker run' prefix. Running: {cmd}")
        # Also catch simpler forms
        elif cmd.strip().startswith('docker run'):
            parts = cmd.strip().split(None, 3)
            if len(parts) >= 4:
                cmd = parts[3]
                print(f"[AUTO-CORRECT] Stripped 'docker run' prefix. Running: {cmd}")
        # Bash guard
        g = sp.run(["python3", "/root/managed-agents/guards/guard_bash.py", cmd], capture_output=True, text=True)
        guard_result = json.loads(g.stdout) if g.returncode == 0 or g.returncode == 2 else {"blocked": False}
        if guard_result.get("blocked"):
            return {"error": f"BASH GUARD: {guard_result.get('reason')}", "blocked": True}
        # Docker sandbox execution
        workdir = args.get("workdir", "/tmp")
        r = sp.run(["python3", "/root/managed-agents/docker_exec.py", cmd, workdir], capture_output=True, text=True)
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return {"stdout": r.stdout[:4000], "stderr": r.stderr[:2000], "rc": r.returncode}
    
    elif action == "read_file":
        try:
            with open(args["path"]) as f:
                return {"content": f.read()[:8000]}
        except Exception as e:
            return {"error": str(e)}
    
    elif action == "write_file":
        path = args["path"]
        # Path guard
        g = sp.run(["python3", "/root/managed-agents/guards/guard_path.py", path], capture_output=True, text=True)
        guard_result = json.loads(g.stdout) if g.returncode == 0 or g.returncode == 2 else {"blocked": False}
        if guard_result.get("blocked"):
            return {"error": f"PATH GUARD: {guard_result.get('reason')}", "blocked": True}
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(args["content"])
            return {"written": path, "bytes": len(args["content"].encode())}
        except Exception as e:
            return {"error": str(e)}
    
    elif action == "complete":
        # Queue result for auto-relay to Telegram
        import os
        pending_dir = "/root/managed-agents/pending_results"
        os.makedirs(pending_dir, exist_ok=True)
        # LLMs may use different keys for the final answer
        final_result = (
            args.get("result") or
            args.get("summary") or
            args.get("reason") or
            args.get("answer") or
            args.get("output") or
            args.get("content") or
            "done"
        )
        with open(os.path.join(pending_dir, f"{session_id}.json"), "w") as f:
            json.dump({
                "session_id": session_id,
                "result": final_result,
                "summary": final_result,
                "ts": datetime.utcnow().isoformat()
            }, f, ensure_ascii=False)
        return {"status": "completed", "summary": final_result}
    elif action == "ask_user":
        return {"status": "waiting", "question": args.get("question", "?")}
    else:
        return {"error": f"unknown action: {action}"}

def run_turn(session_id, goal=None):
    # Load history
    history = get_events(session_id)
    
    # If new session and goal provided, log it
    if goal and not history:
        log_event(session_id, "user_goal", {"goal": goal})
        history = [{"seq": 1, "type": "user_goal", "payload": {"goal": goal}}]
    
    def attempt_call(correction=""):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for ev in history[-15:]:
            if ev["type"] == "user_goal":
                messages.append({"role": "user", "content": f"GOAL: {ev['payload']['goal']}"})
            elif ev["type"] == "planner_decision":
                raw_decision = ev['payload'].get('raw', '')
                if raw_decision and not raw_decision.startswith('{'):
                    continue  # Skip unparseable decisions from history
                messages.append({"role": "assistant", "content": raw_decision})
            elif ev["type"] == "tool_result":
                content = json.dumps(ev['payload'], ensure_ascii=False)[:1500]
                messages.append({"role": "user", "content": f"RESULT: {content}"})
            elif ev["type"] == "error":
                messages.append({"role": "user", "content": f"ERROR: {ev['payload'].get('msg','')}"})
        if correction:
            messages.append({"role": "user", "content": correction})
        
        print(f"[{session_id}] Calling planner...")
        raw = call_llm(messages)
        if raw is None:
            log_event(session_id, "error", {"msg": "LLM returned None (likely API failure)"})
            return None, {"error": "llm timeout or failure"}
        
        # Parse JSON
        decision = None
        try:
            decision = json.loads(raw)
        except json.JSONDecodeError:
            import re
            m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
            if m:
                try:
                    decision = json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
            if decision is None:
                # Try to find any JSON object
                m2 = re.search(r'(\{.*\})', raw, re.DOTALL)
                if m2:
                    try:
                        decision = json.loads(m2.group(1))
                    except json.JSONDecodeError:
                        pass
        return raw, decision
    
    raw, decision = attempt_call()
    if raw is None:
        return decision  # error dict
    
    if decision is None:
        # Retry once with correction
        raw2, decision = attempt_call("Your previous response was not valid JSON. Output ONLY valid JSON. No text before or after.")
        if decision is None:
            log_event(session_id, "error", {"msg": "Failed to parse planner output after retry", "raw": raw})
            return {"error": "parse failed", "raw": raw}
        raw = raw2
    
    log_event(session_id, "planner_decision", {"raw": raw, "ts": datetime.utcnow().isoformat()})
    
    action = decision.get("action")
    args = decision.get("args", {})
    
    print(f"[{session_id}] Action: {action} | Args: {list(args.keys())}")
    
    # Execute
    result = execute_action(action, args, session_id)
    log_event(session_id, "tool_result", {"action": action, "args": args, "result": result})
    
    if action == "complete":
        return {"status": "done", "summary": result.get("summary", "done")}
    elif action == "ask_user":
        return {"status": "waiting", "question": result.get("question")}
    else:
        return {"status": "continue", "action": action, "result_preview": str(result)[:200]}

def main():
    if len(sys.argv) < 2:
        print("Usage: python harness.py <session_id> [goal]")
        print("  If goal provided, starts new session.")
        print("  If no goal, resumes existing session.")
        sys.exit(1)
    
    session_id = sys.argv[1]
    goal = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not API_KEY:
        print("ERROR: API_KEY not set in harness.py")
        sys.exit(1)
    
    result = run_turn(session_id, goal)
    print("\n--- Turn Result ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
