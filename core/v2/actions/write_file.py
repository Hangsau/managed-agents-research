"""Write a file with path mapping and guard checks."""
import os, sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from ..guard import check_guard


def run(args: dict, session_id: str) -> dict:
    path = args.get("path", "")
    content = args.get("content", "")

    # Map sandbox paths to host paths
    if path.startswith("/workspace/managed-agents"):
        path = path.replace("/workspace/managed-agents", "/root/managed-agents", 1)

    guard_result = check_guard("guard_path.py", [path])
    if guard_result.get("blocked"):
        return {"error": f"PATH GUARD: {guard_result.get('reason')}", "blocked": True}

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"written": path, "bytes": len(content.encode("utf-8"))}
    except Exception as e:
        return {"error": str(e)}
