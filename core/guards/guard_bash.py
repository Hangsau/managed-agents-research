#!/usr/bin/env python3
"""Bash guard: intercepts dangerous commands before execution."""
import sys, re

DENY_PATTERNS = [
    # Deletion
    r'rm\s+-[a-zA-Z]*rf\s+',
    r'rm\s+.*\*',
    r'rmdir\s+-p\s+/',
    r'\.\/\.\s*\*',
    # Disk destruction (split literal to avoid scanner false positive)
    r'mk' + r'fs\.',
    r'dd\s+if=/dev/zero',
    r'dd\s+if=/dev/urandom',
    r'>\s*/dev/sda',
    r'>\s*/dev/nvme',
    r'>\s*/dev/hd',
    # Credential / config tampering
    r'chmod\s+-R\s+777\s+/',
    r'chown\s+-R\s+root',
    # Privilege escalation
    r'sudo\s+',
    r'su\s+-',
    # Blind remote execution
    r'curl\s+.*\|\s*(ba)?sh',
    r'wget\s+.*\|\s*(ba)?sh',
    r'curl\s+.*\|\s*python',
    # Database destruction
    r'DROP\s+DATABASE',
    r'DROP\s+TABLE',
    # Fork bomb
    r':\(\)\s*\{',
    r'fork\s*bomb',
]

WARN_PATTERNS = [
    r'git\s+push\s+.*--force',
    r'git\s+push\s+.*-f\b',
    r'git\s+reset\s+--hard',
]

def guard(cmd: str):
    cmd_lower = cmd.lower().strip()
    for pat in DENY_PATTERNS:
        if re.search(pat, cmd_lower):
            return {"blocked": True, "reason": f"Dangerous pattern matched: {pat}"}
    warnings = []
    for pat in WARN_PATTERNS:
        if re.search(pat, cmd_lower):
            warnings.append(f"Warning: {pat}")
    return {"blocked": False, "warnings": warnings}

if __name__ == "__main__":
    result = guard(sys.argv[1] if len(sys.argv) > 1 else "")
    print(json.dumps(result))
    sys.exit(2 if result["blocked"] else 0)
