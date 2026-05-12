#!/usr/bin/env python3
"""
Phase 1: Managed Agents Harness
- Single-brain (OpenRouter free tier)
- SQLite append-only event log
- Wake/resume via session_id
- Micro-task loop: plan → execute → persist → sleep
"""
import os, sys, json, sqlite3, time, subprocess, textwrap
from datetime import datetime, timezone

# Ensure project root is in path for core.* imports
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Load .env if present
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key, val)

DB_PATH = "/root/managed-agents/sessions.db"
API_KEY = os.environ.get("MANAGED_AGENTS_API_KEY", "")
API_URL = os.environ.get("MANAGED_AGENTS_API_URL", "https://opencode.ai/zen/go/v1/chat/completions")
MODEL = os.environ.get("MANAGED_AGENTS_MODEL", "kimi-k2.6")
# Fallback chain if primary model fails
MODEL_FALLBACKS = {
    "kimi-k2.6": "kimi-k2.5",
    "kimi-k2.5": "deepseek-v4-flash",
    "deepseek-v4-flash": "deepseek-v4-pro",
}

SYSTEM_PROMPT = """You are a planner. Given a goal and past results, decide the single next step.
Output ONLY valid JSON with keys: thought, action, args. No markdown, no text outside JSON.
Available actions and their EXACT args format:
- bash: {"cmd": "shell command", "workdir": "/tmp"}
- read_file: {"path": "/absolute/path/to/file"}
- write_file: {"path": "/absolute/path/to/file", "content": "file contents"}
- complete: {"summary": "final answer"}
- ask_user: {"question": "what to ask"}
- web_search: {"query": "search terms", "max_results": 5}
- search_files: {"path": "/directory", "pattern": "*.py"}

Examples:
{"thought":"List files","action":"bash","args":{"cmd":"ls -la","workdir":"/tmp"}}
{"thought":"Read config","action":"read_file","args":{"path":"/root/managed-agents/core/harness.py"}}
{"thought":"Find Python files","action":"search_files","args":{"path":"/root/managed-agents","pattern":"*.py"}}
{"thought":"Search web","action":"web_search","args":{"query":"AI agent trends 2026","max_results":5}}

CRITICAL RULES:
- thought MUST be under 80 characters. Be concise. Do NOT repeat past results.
- If read_file returns content, trust it. Do NOT verify with bash.
- If a tool result is unclear, try a different approach directly. Do NOT analyze discrepancies.
- bash runs inside an isolated container with /workspace/ as working directory. It CANNOT see /root/.
- read_file and search_files read from the HOST filesystem directly. They CAN see /root/.
- When analyzing host code or files, ALWAYS use read_file or search_files. NEVER use bash for this.
- web_search queries DuckDuckGo and returns results. Use when you need external info.
- search_files finds files by pattern (e.g., "*.py") in a directory tree.
- CRITICAL: read_file args MUST use "path" key, NOT "file_path".
- CRITICAL: write_file args MUST use "path" key, NOT "file_path".
- Use absolute paths starting with /root/ or /tmp/ for read_file and search_files."""

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
    events = []
    for r in rows:
        try:
            payload = json.loads(r[3])
        except json.JSONDecodeError:
            payload = {"raw": r[3], "parse_error": True}
        events.append({"seq": r[0], "ts": r[1], "type": r[2], "payload": payload})
    return events

def _call_single_model(model, messages, max_tokens):
    """Single model call with error handling. Returns (content, error)."""
    import urllib.request
    data = json.dumps({
        "model": model,
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
            if "error" in result:
                return None, result["error"]
            if "choices" in result and result["choices"]:
                msg = result["choices"][0]["message"]
                content = msg.get("content")
                if not content and msg.get("reasoning_content"):
                    content = msg["reasoning_content"]
                if not content and msg.get("reasoning"):
                    content = msg["reasoning"]
                if not content and msg.get("reasoning_details"):
                    content = msg["reasoning_details"][0].get("text", "")
                if content:
                    return content, None
                return None, "Model returned empty content"
            return None, "No choices in response"
    except Exception as e:
        return None, str(e)

def call_llm(messages, max_tokens=1000):
    """Call LLM with fallback chain."""
    # Try primary model
    content, err = _call_single_model(MODEL, messages, max_tokens)
    if content is not None:
        return content
    print(f"[LLM] Primary model {MODEL} failed: {err}")
    
    # Try fallbacks
    fallback = MODEL_FALLBACKS.get(MODEL)
    while fallback:
        content, err = _call_single_model(fallback, messages, max_tokens)
        if content is not None:
            print(f"[LLM] Fallback to {fallback} succeeded")
            return content
        print(f"[LLM] Fallback {fallback} failed: {err}")
        fallback = MODEL_FALLBACKS.get(fallback)
    
    # All failed
    print(f"[LLM] All models failed. Last error: {err}")
    return None

def check_guard(guard_script, args_list):
    import subprocess as sp, os, json
    guard_path = f"/root/managed-agents/core/guards/{guard_script}"
    if not os.path.exists(guard_path):
        return {"blocked": False}
    g = sp.run(["python3", guard_path] + args_list, capture_output=True, text=True)
    if g.returncode in (0, 2) and g.stdout.strip():
        try:
            return json.loads(g.stdout)
        except json.JSONDecodeError:
            return {"blocked": False}
    return {"blocked": False}

def execute_action(action, args, session_id="unknown"):
    import subprocess as sp, os
    
    if action == "bash":
        cmd = args.get("cmd", "")
        workdir = args.get("workdir", "/tmp")
        # Auto-correct common model mistake: trying to run docker inside docker
        import re
        docker_run_match = re.search(r'docker\s+run\s+(?:--[a-z-]+\s+|\s+)*(?:\S+\s+)(.*)', cmd)
        if docker_run_match:
            cmd = docker_run_match.group(1).strip()
            print(f"[AUTO-CORRECT] Stripped 'docker run' prefix. Running: {cmd}")
        elif cmd.strip().startswith('docker run'):
            parts = cmd.strip().split(None, 3)
            if len(parts) >= 4:
                cmd = parts[3]
                print(f"[AUTO-CORRECT] Stripped 'docker run' prefix. Running: {cmd}")
        # Bash guard
        g = sp.run(["python3", "/root/managed-agents/core/guards/guard_bash.py", cmd], capture_output=True, text=True)
        guard_result = json.loads(g.stdout) if g.returncode == 0 or g.returncode == 2 else {"blocked": False}
        if guard_result.get("blocked"):
            return {"error": f"BASH GUARD: {guard_result.get('reason')}", "blocked": True}
        # If command accesses managed-agents paths, run on host directly (not sandboxed)
        # This preserves isolation for untrusted commands while allowing project scripts to run
        if "/managed-agents" in cmd or "/managed-agents" in workdir:
            r = sp.run(cmd, shell=True, capture_output=True, text=True, cwd=workdir.replace("/workspace", "/root"), timeout=60)
            return {"stdout": r.stdout[:4000], "stderr": r.stderr[:2000], "rc": r.returncode}
        # Docker sandbox execution for isolated commands
        r = sp.run(["python3", "/root/managed-agents/core/docker_exec.py", cmd, workdir], capture_output=True, text=True)
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return {"stdout": r.stdout[:4000], "stderr": r.stderr[:2000], "rc": r.returncode}
    
    elif action == "read_file":
        path = args["path"]
        # Map sandbox paths to host paths
        if path.startswith("/workspace/managed-agents"):
            path = path.replace("/workspace/managed-agents", "/root/managed-agents", 1)
        guard_result = check_guard("guard_path.py", [path])
        if guard_result.get("blocked"):
            return {"error": f"PATH GUARD: {guard_result.get('reason')}", "blocked": True}
        try:
            if not os.path.exists(path):
                return {"error": f"File not found: {path}"}
            total_bytes = os.path.getsize(path)
            total_lines = sum(1 for _ in open(path, 'r', encoding='utf-8', errors='ignore'))
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            truncated = len(content) > 8000
            content = content[:8000]
            return {
                "content": content,
                "lines": total_lines,
                "bytes": total_bytes,
                "truncated": truncated
            }
        except Exception as e:
            return {"error": str(e)}
    
    elif action == "write_file":
        path = args["path"]
        if path.startswith("/workspace/managed-agents"):
            path = path.replace("/workspace/managed-agents", "/root/managed-agents", 1)
        guard_result = check_guard("guard_path.py", [path])
        if guard_result.get("blocked"):
            return {"error": f"PATH GUARD: {guard_result.get('reason')}", "blocked": True}
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(args["content"])
            return {"written": path, "bytes": len(args["content"].encode("utf-8"))}
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
                "ts": datetime.now(timezone.utc).isoformat()
            }, f, ensure_ascii=False)
        return {"status": "completed", "summary": final_result}
    elif action == "ask_user":
        return {"status": "waiting", "question": args.get("question", "?")}
    
    elif action == "web_search":
        query = args.get("query", "")
        max_results = args.get("max_results", 5)
        try:
            from core import web_search
            return web_search.search(query, max_results)
        except Exception as e:
            return {"error": str(e)}
    
    elif action == "search_files":
        path = args.get("path", "/tmp")
        pattern = args.get("pattern", "")
        try:
            import fnmatch
            matches = []
            for root, dirs, files in os.walk(path):
                for name in files:
                    if fnmatch.fnmatch(name.lower(), pattern.lower()) or fnmatch.fnmatch(name, pattern):
                        full = os.path.join(root, name)
                        matches.append(full)
                # Limit to avoid huge scans
                if len(matches) > 100:
                    matches.append("... (truncated at 100)")
                    break
            return {"matches": matches[:100], "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}
    
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
                payload = ev['payload']
                action = payload.get('action', '')
                result = payload.get('result', {})
                # Smart summary for read_file to avoid flooding context
                if action == 'read_file' and isinstance(result, dict) and 'content' in result:
                    truncated = result.get('truncated', False)
                    summary = {
                        'action': 'read_file',
                        'path': payload.get('args', {}).get('path', 'unknown'),
                        'lines': result.get('lines', '?'),
                        'bytes': result.get('bytes', '?'),
                        'truncated': truncated,
                        'note': 'COMPLETE FILE - no more content' if not truncated else 'TRUNCATED - use bash for full content',
                        'preview': result['content'][:100] + '...' if len(result['content']) > 100 else result['content']
                    }
                    content = json.dumps(summary, ensure_ascii=False)
                else:
                    content = json.dumps(payload, ensure_ascii=False)[:500]
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
    
    log_event(session_id, "planner_decision", {"raw": raw, "ts": datetime.now(timezone.utc).isoformat()})
    
    action = decision.get("action")
    args = decision.get("args", {})
    
    # Detect repetitive commands (stuck loop)
    recent_tools = [e for e in history if e["type"] == "tool_result"][-4:]
    current_sig = json.dumps({"action": action, "args": args}, sort_keys=True)
    dup_count = sum(1 for e in recent_tools 
                    if json.dumps({"action": e["payload"].get("action"), 
                                   "args": e["payload"].get("args")}, sort_keys=True) == current_sig)
    # Also detect same-file access via different commands (only for read/write, not bash execution)
    def extract_path(a, ar):
        if a in ('read_file', 'write_file') and 'path' in ar:
            return ar['path']
        return None
    current_path = extract_path(action, args)
    if current_path:
        path_dups = sum(1 for e in recent_tools if extract_path(e["payload"].get("action"), e["payload"].get("args", {})) == current_path)
        if path_dups >= 2:
            log_event(session_id, "error", {"msg": f"Planner stuck: repeated access to {current_path} too many times", "raw": raw})
            return {"error": "stuck loop", "msg": f"Repeated access to {current_path}"}
    if dup_count >= 2:
        log_event(session_id, "error", {"msg": f"Planner stuck: repeated {action} {list(args.keys())} too many times", "raw": raw})
        return {"error": "stuck loop", "msg": f"Repeated {action} too many times"}
    
    print(f"[{session_id}] Action: {action} | Args: {list(args.keys())}")
    
    # Execute with retry (exponential backoff) for transient failures
    result = None
    max_retries = 2
    for attempt in range(max_retries + 1):
        result = execute_action(action, args, session_id)
        if "error" not in result or attempt == max_retries:
            break
        # Don't retry on guard blocks or stuck loops
        if result.get("blocked") or result.get("error") == "stuck loop":
            break
        wait = 2 ** attempt
        print(f"[{session_id}] Action {action} failed (attempt {attempt+1}/{max_retries+1}), retrying in {wait}s...")
        time.sleep(wait)
    
    log_event(session_id, "tool_result", {"action": action, "args": args, "result": result})
    
    if action == "complete":
        return {"status": "done", "summary": result.get("summary", "done")}
    elif action == "ask_user":
        return {"status": "error", "message": "ask_user is not available in autonomous mode. Continue with best effort using available tools."}
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
