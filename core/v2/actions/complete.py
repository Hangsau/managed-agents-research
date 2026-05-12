"""Queue a completion result for relay."""
import json, os, sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def run(args: dict, session_id: str) -> dict:
    pending_dir = "/root/managed-agents/pending_results"
    os.makedirs(pending_dir, exist_ok=True)

    final_result = (
        args.get("result")
        or args.get("summary")
        or args.get("reason")
        or args.get("answer")
        or args.get("output")
        or args.get("content")
        or "done"
    )

    payload = {
        "session_id": session_id,
        "result": final_result,
        "summary": final_result,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    with open(os.path.join(pending_dir, f"{session_id}.json"), "w") as f:
        json.dump(payload, f, ensure_ascii=False)

    return {"status": "completed", "summary": final_result}
