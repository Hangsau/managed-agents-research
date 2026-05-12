#!/usr/bin/env python3
"""Phase 2: Modular Managed Agents Harness (v2)."""
import json, sys

from . import config, db
from .turn_loop import run_turn
from .dispatcher import submit_batch, dispatch_loop, wait_batch, collect_results


def _cmd_single():
    session_id = sys.argv[2]
    goal = sys.argv[3] if len(sys.argv) > 3 else None
    db.ensure_schema()
    if not config.API_KEY:
        print("ERROR: API_KEY not set. Check .env or environment.")
        sys.exit(1)
    result = run_turn(session_id, goal)
    print("\n--- Turn Result ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _cmd_batch():
    """Submit a batch: harness_v2.py batch <playbook_name> <vars_json> [count]"""
    if len(sys.argv) < 4:
        print("Usage: python -m core.v2.harness_v2 batch <playbook_name> <vars_json> [count]")
        print('  vars_json: {"topic":"blockchain","angle":"finance"}')
        sys.exit(1)

    playbook_name = sys.argv[2]
    vars_dict = json.loads(sys.argv[3])
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    db.ensure_schema()
    db.ensure_queue_schema()

    tasks = []
    for i in range(count):
        tasks.append({
            "session_id": None,  # auto-generated
            "playbook_name": playbook_name,
            "vars": vars_dict,
        })

    batch_id = submit_batch(tasks)
    print(f"Batch submitted: {batch_id} ({count} tasks)")


def _cmd_dispatch():
    """Run dispatcher: harness_v2.py dispatch [max_tasks]"""
    max_tasks = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    db.ensure_schema()
    db.ensure_queue_schema()
    if not config.API_KEY:
        print("ERROR: API_KEY not set. Check .env or environment.")
        sys.exit(1)
    dispatch_loop(max_tasks=max_tasks)


def _cmd_status():
    """Check batch status: harness_v2.py status <batch_id>"""
    if len(sys.argv) < 3:
        print("Usage: python -m core.v2.harness_v2 status <batch_id>")
        sys.exit(1)
    batch_id = sys.argv[2]
    db.ensure_schema()
    db.ensure_queue_schema()
    status = db.get_batch_status(batch_id)
    print(json.dumps(status, ensure_ascii=False, indent=2))


def _cmd_results():
    """Collect results: harness_v2.py results <batch_id>"""
    if len(sys.argv) < 3:
        print("Usage: python -m core.v2.harness_v2 results <batch_id>")
        sys.exit(1)
    batch_id = sys.argv[2]
    db.ensure_schema()
    db.ensure_queue_schema()
    results = collect_results(batch_id)
    print(json.dumps(results, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m core.v2.harness_v2 <command> [args...]")
        print("")
        print("Commands:")
        print("  single <session_id> [goal]     Run a single session (default)")
        print("  batch <playbook> <vars> [n]    Submit n tasks to queue")
        print("  dispatch [max_tasks]           Run dispatcher loop")
        print("  status <batch_id>              Check batch status")
        print("  results <batch_id>             Collect batch results")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd in ("single", "s"):
        _cmd_single()
    elif cmd == "batch":
        _cmd_batch()
    elif cmd in ("dispatch", "d"):
        _cmd_dispatch()
    elif cmd == "status":
        _cmd_status()
    elif cmd == "results":
        _cmd_results()
    else:
        # Default: treat as session_id for backward compat
        sys.argv.insert(1, "single")
        _cmd_single()


if __name__ == "__main__":
    main()
