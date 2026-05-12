"""Guard script runner."""
import json, os, subprocess as sp


def check_guard(guard_script: str, args_list: list[str]) -> dict:
    """Run a guard script and return its parsed JSON output.

    Returns {"blocked": bool, "reason": str} on success,
    or {"blocked": False} if the guard is missing, exits abnormally,
    or produces unparsable output.
    """
    guard_path = f"/root/managed-agents/core/guards/{guard_script}"
    if not os.path.exists(guard_path):
        return {"blocked": False}

    result = sp.run(
        ["python3", guard_path] + args_list,
        capture_output=True,
        text=True,
    )

    if result.returncode in (0, 2) and result.stdout.strip():
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            pass

    return {"blocked": False}
