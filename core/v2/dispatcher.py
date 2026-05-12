"""Task queue dispatcher: claim pending tasks and run them via harness."""
import json, os, sys, time, uuid
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from . import config, db
from .playbook import Playbook, load_playbook, run_playbook
from .turn_loop import run_turn

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RESULT_DIR = os.environ.get("BATCH_RESULTS_DIR", os.path.join(_PROJECT_ROOT, "results"))


def _ensure_result_dir():
    os.makedirs(_RESULT_DIR, exist_ok=True)
    return _RESULT_DIR


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
    results_dir = _ensure_result_dir()
    result_path = os.path.join(results_dir, f"{session_id}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result_path


def _run_one_task_wrapped(task: dict) -> tuple:
    """Run a single task. Returns (task_id, result_path, error)."""
    try:
        result_path = run_one_task(task)
        return task["id"], result_path, None
    except Exception as e:
        return task["id"], None, str(e)


def dispatch_loop(max_tasks: int = 0, max_workers: int = 3, poll_interval: float = 2.0):
    """Poll queue and run tasks concurrently until no more pending (or max_tasks reached)."""
    db.ensure_schema()
    db.ensure_queue_schema()

    task_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        while True:
            # Submit new tasks while we have capacity
            while len(futures) < max_workers:
                if max_tasks > 0 and task_count >= max_tasks:
                    break
                task = db.claim_next_pending()
                if task is None:
                    break
                task_count += 1
                print(f"[{task_count}] Submitted task {task['id']} (session={task['session_id']}, playbook={task['playbook_name']})")
                future = executor.submit(_run_one_task_wrapped, task)
                futures[future] = task["id"]

            # If nothing is running and no new tasks, we're done
            if not futures:
                print("No pending tasks. Dispatcher idle.")
                break

            # Wait for at least one to complete
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                task_id = futures.pop(future)
                _, result_path, error = future.result()
                if error:
                    retried = db.complete_task(task_id, error=error)
                    if retried:
                        print(f"    -> Retry scheduled: task {task_id} | {error}")
                    else:
                        print(f"    -> Failed: task {task_id} | {error}")
                else:
                    db.complete_task(task_id, result_path=result_path)
                    print(f"    -> Done: task {task_id} | {result_path}")

            # Stop if we've reached max_tasks and drained all futures
            if max_tasks > 0 and task_count >= max_tasks and not futures:
                print(f"Reached max_tasks={max_tasks}. Stopping.")
                break


def submit_batch(tasks: list[dict], max_retries: int = 0) -> str:
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
            vars=t.get("vars", {}),
            max_retries=max_retries
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


def collect_results(batch_id: str, merge: bool = False) -> list[dict] | dict:
    """Read result files for a completed batch. If merge=True, return a merged dict."""
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

    if not merge:
        return results

    # Merge mode: aggregate all results into a single summary dict
    merged = {}
    errors = []
    for r in results:
        sid = r.get("session_id", "unknown")
        if "result" in r:
            merged[sid] = r["result"]
        elif "error" in r:
            errors.append({"session_id": sid, "error": r["error"]})

    return {
        "results": merged,
        "errors": errors,
        "total": len(results),
        "success": len(merged),
        "failed": len(errors),
    }
