"""Read a file with path mapping and size limits."""
import os, sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from ..guard import check_guard
from ..config import MAX_READ_FILE_BYTES


def run(args: dict, session_id: str) -> dict:
    path = args.get("path", "")

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
        total_lines = sum(
            1 for _ in open(path, "r", encoding="utf-8", errors="ignore")
        )

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        truncated = len(content) > MAX_READ_FILE_BYTES
        content = content[:MAX_READ_FILE_BYTES]

        return {
            "content": content,
            "lines": total_lines,
            "bytes": total_bytes,
            "truncated": truncated,
        }
    except Exception as e:
        return {"error": str(e)}
