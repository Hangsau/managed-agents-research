"""Run shell commands with guard checks (no sandbox)."""
import json, os, re, subprocess as sp, sys

# Ensure imports resolve
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from ..guard import check_guard


def run(args: dict, session_id: str) -> dict:
    cmd = args.get("cmd", "")
    workdir = args.get("workdir", "/tmp")

    # Bash guard
    guard_result = check_guard("guard_bash.py", [cmd])
    if guard_result.get("blocked"):
        return {"error": f"BASH GUARD: {guard_result.get('reason')}", "blocked": True}

    # Run directly on host
    r = sp.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=workdir,
        timeout=60,
    )
    return {
        "stdout": r.stdout[:4000],
        "stderr": r.stderr[:2000],
        "rc": r.returncode,
    }
