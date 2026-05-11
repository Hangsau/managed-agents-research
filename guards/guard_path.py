#!/usr/bin/env python3
"""Path guard: prevents writes outside allowed directories."""
import os, sys

# Directories that are OFF LIMITS for writes (absolute paths)
FORBIDDEN_ROOTS = [
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/opt",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
    "/run",
    "/var/log",
    "/var/lib/systemd",
    "/root/.ssh",
    "/root/.bashrc",
    "/root/.profile",
    "/root/.hermes",
    "/root/managed-agents/sessions.db",
    "/root/managed-agents/sessions.db-wal",
    "/root/managed-agents/sessions.db-shm",
]

# Allowed write roots (everything else under here is okay)
ALLOWED_ROOTS = [
    "/tmp",
    "/root/hermes-novel-project",
    "/root/managed-agents/logs",
    "/root/managed-agents/tools",
    os.path.expanduser("~/workspace"),
]

def resolve(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))

def guard_write(path: str):
    abspath = resolve(path)
    # Check forbidden
    for forbidden in FORBIDDEN_ROOTS:
        if abspath == forbidden or abspath.startswith(forbidden + "/"):
            return {"blocked": True, "reason": f"Write to forbidden path: {forbidden}"}
    # Check if in any allowed root
    for allowed in ALLOWED_ROOTS:
        if abspath.startswith(allowed + "/") or abspath == allowed:
            return {"blocked": False}
    # Default deny for anything else under /root or /home that isn't explicitly allowed
    if abspath.startswith("/root/") or abspath.startswith("/home/"):
        return {"blocked": True, "reason": f"Write outside allowed workspace: {abspath}"}
    return {"blocked": False}

if __name__ == "__main__":
    result = guard_write(sys.argv[1] if len(sys.argv) > 1 else "")
    print(json.dumps(result))
    sys.exit(2 if result["blocked"] else 0)
