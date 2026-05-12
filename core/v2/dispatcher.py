"""Task queue dispatcher: claim pending tasks and run them via harness."""
import json, os, sys, time, uuid

from . import config, db
from .playbook import Playbook, load_playbook, run_playbook
from .turn_loop import run_turn

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RESULTS_DIR = os.environ.get("BATCH_RESULTS_DIR", os.path.join(_PROJECT_ROOT, "results"))


def _ensure_results_dir():
    os.makedirs(_RESULTS_DIR, exist_ok=True)
    return _RESULTS_DIR


def run_one_task(task: dict) -> str:
    """Run a single task. Returns result_path or raises."""
    task_id = task["id"]
    session_id = task["session_id"]
    playbook_name = task["playbook_name"]
    vars_dict = task["vars"]

    # Load playbook
    pb = load_playbook(playbook_name)
    if pb is None:
        raise RuntimeError(f"Playbook not found: {playbook_name}")

    # Inject vars
    pb = pb.with_vars(vars_dict)

    # Build goal from first step description
    goal = pb.description or f"Run playbook {playbook_name}"

    # Run the session harness
    result = run_turn(session_id, goal=goal)

    # Save result to file
    results_dir = _ensure_results_dir()
    result_path = os.path.join(results_dir, f"{session_id}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result_path


def dispatch_loop(max_tasks: int = 0, poll_interval: float = 2.0):
    """Poll queue and run tasks until no more pending (or max_tasks reached)."""
    db.ensure_schema()
    db.ensure_queue_schema()

    task_count = 0
    while True:
        task = db.claim_next_pending()
        if task is None:
            print("No pending tasks. Dispatcher idle.")
            break

        task_count += 1
        print(f"[{task_count}] Running task {task['id']} (session={task['session_id']}, playbook={task['playbook_name']})")

        try:
            result_path = run_one_task(task)
            db.complete_task(task["id"], result_path=result_path)
            print(f"    -> Done: {result_path}")
        except Exception as e:
            db.complete_task(task["id"], error=str(e))
            print(f"    -> Failed: {e}")

        if max_tasks > 0 and task_count >= max_tasks:
            print(f"Reached max_tasks={max_tasks}. Stopping.")
            break

        time.sleep(poll_interval)


def submit_batch(tasks: list[dict]) -> str:
    """Submit a batch of tasks. Returns batch_id.
    tasks: [{session_id, playbook_name, vars}, ...]
    """
    db.ensure_schema()
    db.ensure_queue_schema()
    batch_id = f"batch_{uuid.uuid4().hex[:8]}"
    for t in tasks:
        sid = t.get("session_id") or f"{batch_id}_{uuid.uuid4().hex[:6]}"
        db.enqueue(
            batch_id=batch_id,
            session_id=sid,
            playbook_name=t["playbook_name"],
            vars=t.get("vars", {})
        )
    return batch_id


def wait_batch(batch_id: str, timeout: float = 300.0, poll_interval: float = 3.0) -> dict:
    """Wait until batch has no pending/running tasks, then return status."""
    start = time.time()
    while True:
        status = db.get_batch_status(batch_id)
        remaining = status["pending"] + status["running"]
        if remaining == 0:
            return status
        if time.time() - start > timeout:
            return {**status, "timed_out": True}
        time.sleep(poll_interval)


def collect_results(batch_id: str) -> list[dict]:
    """Read result files for a completed batch."""
    status = db.get_batch_status(batch_id)
    results = []
    for t in status["tasks"]:
        if t["status"] == "done" and t["result_path"] and os.path.exists(t["result_path"]):
            with open(t["result_path"], "r", encoding="utf-8") as f:
                results.append({
                    "session_id": t["session_id"],
                    "playbook_name": t["playbook_name"],
                    "result": json.load(f)
                })
        elif t["status"] == "failed":
            results.append({
                "session_id": t["session_id"],
                "playbook_name": t["playbook_name"],
                "error": t["error"]
            })
    return results
