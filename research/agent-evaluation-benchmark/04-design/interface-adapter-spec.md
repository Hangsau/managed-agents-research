# Stage 4.8 — Interface Adapter Specification

> Answers DQ-15 (adapter complexity counting). Defines the minimal interface every deployed system must expose through an adapter to be testable, plus 4 worked example adapters (Bare API, CLI, VM-agent, local-agent).

---

## 1. The SystemAdapter contract

Every subject is wrapped by an adapter that implements four methods:

```python
from typing import Protocol

class SystemAdapter(Protocol):
    def identity(self) -> dict:
        """Return the current identity tuple (see system-identity-definition.md §1).
        Must be queryable on demand; the harness re-queries between trials to
        detect self-modification."""
        ...

    def submit(self, task: "TaskSpec") -> "Trace":
        """Submit a task and return a Trace.
        Trace contains: subject_output, tool_invocations, latency_s,
        input_tokens, output_tokens, reasoning_tokens, error_info, raw_log."""
        ...

    def cost(self, trace: "Trace") -> "Cost":
        """Return the cost of producing this trace, in tokens (primary)
        and USD (computed from harness's price table)."""
        ...

    def teardown(self) -> None:
        """Release resources, kill processes, restore filesystem state.
        Idempotent; safe to call multiple times."""
        ...
```

Adapters are short by design (DQ-15 cap ≤100 LOC excluding imports). An adapter that exceeds 100 LOC signals an interface-immaturity problem with the subject system, not a flaw in the harness.

---

## 2. Adapter complexity counting (DQ-15)

**Counted LOC**:
- Method bodies, control flow, parsing logic, error handling.
- Configuration constants specific to this adapter (e.g., subject's CLI flag patterns).

**Not counted**:
- Standard imports (`import json`, `import subprocess`).
- Type hints and docstrings.
- Test code (test files are not adapter files).
- External dependencies (calling a 1000-line library is fine; the adapter is the wrapper, not the library).

**External dependency count** (`external_deps_count` in profile C4): number of non-stdlib pip packages the adapter directly imports. This is reported separately from LOC.

**100-LOC cap rationale**: If your adapter needs more than 100 lines to wrap a subject's interface, the subject's interface is too idiosyncratic for routine evaluation. The framework reports this in C4 (adapter complexity) and proceeds; it does not refuse to evaluate.

---

## 3. Example Adapter 1 — Bare Claude API

```python
import anthropic

class BareClaudeAPIAdapter:
    """Adapter for bare Claude API (no system prompt, no tools, no memory)."""

    def __init__(self, model_id="claude-opus-4-7", gateway="anthropic-api-direct"):
        self._model_id = model_id
        self._gateway = gateway
        self._client = anthropic.Anthropic()

    def identity(self) -> dict:
        return {
            "llm_id": self._model_id,
            "training_state": "instruction-tuned",
            "gateway": self._gateway,
            "instruction_layer_hash": _hash(""),
            "mcp_set": [],
            "skill_set": [],
            "tool_inventory": [],
            "memory_system": {"kind": "none"},
            "runtime": {"host": "anthropic-cloud", "container": None,
                        "network": "unrestricted", "fs_perms": "none"},
        }

    def submit(self, task) -> "Trace":
        start = time.monotonic()
        response = self._client.messages.create(
            model=self._model_id,
            max_tokens=4096,
            messages=[{"role": "user", "content": task.prompt}],
        )
        return Trace(
            output=response.content[0].text,
            tool_invocations=[],
            latency_s=time.monotonic() - start,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            reasoning_tokens=0,
            raw_log=response.model_dump_json(),
        )

    def cost(self, trace) -> "Cost":
        return Cost.from_tokens(self._model_id, trace.input_tokens,
                                trace.output_tokens, trace.reasoning_tokens)

    def teardown(self):
        pass  # nothing to clean up
```

**LOC**: ~30. **External deps**: 1 (`anthropic`).

---

## 4. Example Adapter 2 — Claude Code CLI

```python
class ClaudeCodeCLIAdapter:
    """Adapter for claude-code CLI; wraps `claude -p` invocations."""

    def __init__(self, workdir, claude_path="claude", model="claude-opus-4-7"):
        self._workdir = workdir
        self._claude = claude_path
        self._model = model
        self._claude_md_hash = _hash_file(workdir / "CLAUDE.md") if (workdir / "CLAUDE.md").exists() else _hash("")
        self._mcp_set = _read_mcp_registry(workdir)
        self._skill_set = _read_skills_index(workdir)

    def identity(self) -> dict:
        return {
            "llm_id": self._model,
            "training_state": "instruction-tuned",
            "gateway": "anthropic-api-direct",
            "instruction_layer_hash": self._claude_md_hash,
            "mcp_set": sorted(self._mcp_set),
            "skill_set": sorted(self._skill_set),
            "tool_inventory": ["bash", "file_read", "file_write", "edit", "glob", "grep", "web_fetch"],
            "memory_system": {"kind": "session_only"},
            "runtime": {"host": "windows-11", "container": None,
                        "network": "unrestricted", "fs_perms": "user-home-rw"},
        }

    def submit(self, task) -> "Trace":
        """v2 fix (response to R1-B #3): prompt is passed via either argv OR stdin,
        never both. v1 had a silent double-pass bug when prompt length > 8000."""
        start = time.monotonic()
        use_stdin = len(task.prompt) > 8000
        cmd = [self._claude, "-p", "--model", self._model,
               "--permission-mode", "bypassPermissions"]
        if not use_stdin:
            cmd.insert(2, task.prompt)  # pass as argv positional
        proc = subprocess.run(
            cmd,
            cwd=task.workspace.path if task.workspace else self._workdir,
            capture_output=True, text=True, timeout=task.timeout_s,
            input=task.prompt if use_stdin else None,
        )
        return Trace(
            output=proc.stdout,
            tool_invocations=_parse_tool_log(proc.stdout),
            latency_s=time.monotonic() - start,
            input_tokens=_extract_token_count(proc.stdout, "input"),
            output_tokens=_extract_token_count(proc.stdout, "output"),
            reasoning_tokens=_extract_token_count(proc.stdout, "reasoning"),
            raw_log=proc.stdout + proc.stderr,
        )

    def cost(self, trace) -> "Cost":
        return Cost.from_tokens(self._model, trace.input_tokens,
                                trace.output_tokens, trace.reasoning_tokens)

    def teardown(self):
        pass
```

**LOC**: ~45. **External deps**: 0 (stdlib only).

---

## 5. Example Adapter 3 — Talos (VM agent via SSH)

```python
class TalosVMAdapter:
    """Adapter for Talos (Hetzner VM running Hermes + Claude)."""

    def __init__(self, ssh_host="talos.hetzner", ssh_user="hermes"):
        self._ssh_host = ssh_host
        self._ssh_user = ssh_user
        self._identity_cache = None

    def identity(self) -> dict:
        """v2 fix (response to R1-B #7): always re-query, no caching.
        Talos can self-modify (Hermes is an active framework); cached
        identity hides drift. Matches Hestia adapter's pattern."""
        return self._query_remote_identity()

    def _query_remote_identity(self):
        """v2 fix (response to R1-B #7, #8): always re-query (no cache); add timeout."""
        result = subprocess.check_output(
            ["ssh", "-o", "ConnectTimeout=10",
             f"{self._ssh_user}@{self._ssh_host}",
             "curl", "-s", "--max-time", "10",
             "http://localhost:8642/identity"],
            text=True, timeout=30,
        )
        return json.loads(result)

    def submit(self, task) -> "Trace":
        start = time.monotonic()
        payload = json.dumps({"prompt": task.prompt, "task_id": str(task.id)})
        result = subprocess.check_output(
            ["ssh", f"{self._ssh_user}@{self._ssh_host}",
             "curl", "-s", "-X", "POST", "-d", "@-",
             "http://localhost:8642/submit"],
            input=payload, text=True, timeout=task.timeout_s,
        )
        response = json.loads(result)
        # Re-query identity in case of self-modification
        self._identity_cache = None
        return Trace(
            output=response["output"],
            tool_invocations=response.get("tool_invocations", []),
            latency_s=time.monotonic() - start,
            input_tokens=response["usage"]["input_tokens"],
            output_tokens=response["usage"]["output_tokens"],
            reasoning_tokens=response["usage"].get("reasoning_tokens", 0),
            raw_log=response.get("trace_log", ""),
        )

    def cost(self, trace) -> "Cost":
        identity = self.identity()
        return Cost.from_tokens(identity["llm_id"], trace.input_tokens,
                                trace.output_tokens, trace.reasoning_tokens)

    def teardown(self):
        # Optionally instruct Talos to roll back identity changes; not by default
        pass
```

**LOC**: ~55. **External deps**: 0 (stdlib only). **Assumption**: Talos exposes `/identity` and `/submit` endpoints — this is a standardization the agent-system class must commit to in order to be evaluable. Specifying this endpoint pair is the framework's contract with agent-system implementers.

---

## 6. Example Adapter 4 — Hestia (local VM via SSH + drift handling)

```python
class HestiaVMAdapter:
    """Adapter for Hestia (local VirtualBox VM with autonomous expansion)."""

    def __init__(self, vm_host="hestia.local", ssh_user="hermes"):
        self._vm = vm_host
        self._user = ssh_user
        self._identity_cache = None
        self._last_hash = None

    def identity(self) -> dict:
        # Always query fresh — Hestia self-modifies actively
        result = subprocess.check_output(
            ["ssh", f"{self._user}@{self._vm}",
             "curl", "-s", "http://localhost:8642/identity"],
            text=True, timeout=10,
        )
        identity = json.loads(result)
        self._identity_cache = identity
        return identity

    def submit(self, task) -> "Trace":
        pre_hash = _identity_hash(self.identity())
        start = time.monotonic()
        payload = json.dumps({"prompt": task.prompt, "task_id": str(task.id)})
        result = subprocess.check_output(
            ["ssh", f"{self._user}@{self._vm}",
             "curl", "-s", "-X", "POST", "-d", "@-",
             "http://localhost:8642/submit"],
            input=payload, text=True, timeout=task.timeout_s,
        )
        response = json.loads(result)
        post_hash = _identity_hash(self.identity())
        return Trace(
            output=response["output"],
            tool_invocations=response.get("tool_invocations", []),
            latency_s=time.monotonic() - start,
            input_tokens=response["usage"]["input_tokens"],
            output_tokens=response["usage"]["output_tokens"],
            reasoning_tokens=response["usage"].get("reasoning_tokens", 0),
            identity_drift=(pre_hash != post_hash),
            raw_log=response.get("trace_log", ""),
        )

    def cost(self, trace):
        return Cost.from_tokens(self.identity()["llm_id"], trace.input_tokens,
                                trace.output_tokens, trace.reasoning_tokens)

    def teardown(self):
        pass
```

**LOC**: ~60. **External deps**: 0. **Differences from Talos adapter**: identity caching is disabled (Hestia self-modifies, so every trial re-queries); Trace carries explicit `identity_drift` flag.

---

## 7. Adapter testing matrix

Every adapter must pass a 3-task smoke suite before the framework will use it for full evaluation:

| Smoke task | Purpose |
|-----------|---------|
| `identity_consistency`: call `identity()` 3 times; assert same hash | Detects nondeterministic identity reporting |
| `simple_echo`: submit `"Echo back the word HELLO."`; assert output contains "HELLO" | Verifies submit pipeline works end-to-end |
| `latency_sanity`: same as echo but assert `latency_s` field is populated and > 0 | Verifies timing instrumentation |

If smoke suite fails, the adapter is rejected with an error. The subject cannot be evaluated.

---

## 8. DQ closure

| DQ | Resolved in this file |
|----|----------------------|
| DQ-15 | §2 — LOC counting rules; 100-LOC cap as warning not block; external deps reported separately |

---

## 9. Open standards we depend on

For agent-system class subjects to be evaluable, they must expose a minimal HTTP/SSH endpoint pair:
- `GET /identity` — returns the identity tuple.
- `POST /submit` — accepts `{prompt, task_id}` and returns `{output, tool_invocations, usage, trace_log}`.

This is a **standardization the framework imposes**. Existing systems (Hermes, Devin, Cursor BG) do not all expose this. Adopting the framework requires either implementing the endpoints or writing a heavier adapter. We document this trade-off explicitly because it affects which systems can be evaluated.
