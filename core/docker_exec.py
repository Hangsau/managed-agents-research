#!/usr/bin/env python3
"""Execute a bash command inside a Docker sandbox."""
import subprocess, sys, os, json

def docker_exec(cmd: str, workdir: str = "/tmp"):
    """Run cmd inside agent-sandbox container, mounting workdir."""
    # Ensure workdir exists on host
    os.makedirs(workdir, exist_ok=True)
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{workdir}:/workspace",
        "-w", "/workspace",
        "-e", "HOME=/workspace",
        "-e", "PATH=/usr/local/bin:/usr/bin:/bin",
        "--network", "bridge",
        "--cap-drop", "ALL",
        "agent-sandbox:latest",
        "sh", "-c", cmd
    ]
    try:
        r = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=60)
        return {"stdout": r.stdout[:4000], "stderr": r.stderr[:2000], "rc": r.returncode}
    except subprocess.TimeoutExpired:
        return {"error": "docker timeout", "stdout": "", "stderr": "", "rc": -1}
    except Exception as e:
        return {"error": str(e), "stdout": "", "stderr": "", "rc": -1}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "echo hello"
    workdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp"
    print(json.dumps(docker_exec(cmd, workdir)))
