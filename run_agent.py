#!/usr/bin/env python3
"""Auto-runner: runs turns until completion or max_turns."""
import sys, subprocess, json, time

MAX_TURNS = int(sys.argv[sys.argv.index("--max-turns")+1]) if "--max-turns" in sys.argv else 20
session_id = sys.argv[1]
goal = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None

print(f"=== Agent Run: {session_id} ===")
if goal:
    print(f"Goal: {goal}")

for turn in range(1, MAX_TURNS + 1):
    print(f"\n--- Turn {turn} ---")
    cmd = ["python3", "harness.py", session_id]
    if turn == 1 and goal:
        cmd.append(goal)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.split("\n")
    json_started = False
    json_lines = []
    for line in lines:
        if line.strip() == "--- Turn Result ---":
            json_started = True
            continue
        if json_started:
            json_lines.append(line)
    
    try:
        turn_result = json.loads("\n".join(json_lines))
    except:
        print(result.stdout)
        turn_result = {}
    
    if turn_result.get("status") == "done":
        print(f"\n[OK] COMPLETED: {turn_result.get('summary', 'done')}")
        print(f"Total turns: {turn}")
        break
    elif turn_result.get("status") == "waiting":
        print(f"\n[WAIT] {turn_result.get('question')}")
        break
    elif turn_result.get("status") == "error":
        print(f"\n[ERR] {turn_result}")
        break
    else:
        time.sleep(1)
else:
    print(f"\n[MAX] Reached {MAX_TURNS} turns")
