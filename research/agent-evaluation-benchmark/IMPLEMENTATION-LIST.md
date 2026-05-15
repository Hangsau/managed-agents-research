# Implementation List — Phase A Smoke Pilot

> **Source**: `/plan-check` 2026-05-15 (this session)
> **Plan reference**: `IMPLEMENTATION-PLAN.md` §3 (Phase A scope)
> **Working directory**: `C:\claudehome\projects\managed-agents-research`
> **Output directory**: `research/agent-evaluation-benchmark/harness/`
> **Status**: Awaiting operator green-light. Say `開始` to start Step 0.

This list is **self-contained**: every minimax-m2.7 delegated step has inline spec sufficient for `1 W = 1 file = 1 API call` execution without referring back to plan-check or v3 design.

---

## Delegation mechanism (resolve before Step 6)

**Issue**: No `DELEGATION_WORKFLOW.md` exists in this repo. minimax-m2.7 invocation method must be confirmed before delegated steps run.

**Options to confirm at Step 0**:
1. Direct API call via existing wrapper script in `core/v2/`
2. Manual relay: operator copy-pastes prompt into minimax-m2.7 web UI, pastes response back
3. opencode-go provider routing (if `opencode-go` config has minimax-m2.7 available)

Whichever is chosen, the prompt template stays the same — only delivery channel differs.

---

## Step table (35 steps total)

| # | Action | Tool | Skill | Delegate | Day |
|---|--------|------|-------|----------|-----|
| 0 | Confirm minimax-m2.7 invocation mechanism; create harness/ directory shell | Bash + Write | — | self | 1.5 |
| 1 | Spike CLAUDE_HOME isolation (R1) | Bash | — | self | 1.5 |
| 2 | Write `pyproject.toml` + `.gitignore` | Write | — | self | 2a |
| 3 | Write `harness/config.py` | Write | — | self | 2a |
| 4 | Write `harness/adapters/base.py` | Write | — | self | 2a |
| 5 | Write `harness/adapters/_claude_cli.py` (security-critical, stdin not argv) | Write | — | self | 2a |
| 6 | Delegate `harness/adapters/bare_api.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 2b |
| 7 | Delegate `harness/adapters/vanilla_cc.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 2b |
| 8 | Delegate `harness/adapters/full_cc.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 2b |
| 9 | Verify 3 adapters compile, commit batch | Bash + git | — | self | 2b |
| 10 | Delegate `harness/generators/a1_grid_puzzle.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 3a |
| 11 | Delegate `harness/generators/a2_working_memory.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 3a |
| 12 | Delegate `harness/generators/b1_synthetic_fs.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 3a |
| 13 | Run 3 generators to produce `harness/tasks/*.json` pools | Bash | — | self | 3b |
| 14 | Commit generators + task pools | git | — | self | 3b |
| 15 | Delegate `harness/identity/snapshot.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 3c |
| 16 | Delegate `harness/output/profile.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 4a |
| 17 | Delegate `harness/scoring/pr_calc.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 4a |
| 18 | Delegate `harness/runner/trial.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 4a |
| 19 | Delegate `harness/runner/pilot.py` | Agent | subagent-git-no-mutation | minimax-m2.7 | 4a |
| 20 | Verify Day 4a batch compiles, commit | Bash + git | — | self | 4a |
| 21 | Write `tests/test_pr_calc.py` | Write | — | self | 4b |
| 22 | Write `tests/test_na_handling.py` | Write | — | self | 4b |
| 23 | Write `tests/test_judge_malformed_input.py` | Write | — | self | 4b |
| 24 | Run `pytest`, fix failures | Bash | — | self | 4b |
| 25 | Commit tests | git | — | self | 4b |
| 26 | Write `harness/scoring/rubrics.py` (A1/A2/B1 anchors) | Write | — | self | 5 |
| 27 | Write `harness/scoring/judge.py` (Sonnet 4.6 wrapper) | Write | — | self | 5 |
| 28 | Judge consistency spike (R3): same trace × 5 calls, measure stddev | Bash | — | self | 5 |
| 29 | Commit rubrics + judge | git | — | self | 5 |
| 30 | Run /code-audit on harness/ | Skill | code-audit | self | 5 |
| 31 | Dry-run pilot: 1 trial each, project full cost | Bash | — | self | 6 |
| 32 | Run pilot × 3 full runs | Bash | — | self | 6 |
| 33 | Write `pilot-report.md` | Write | — | self | 7a |
| 34 | Write `pass-gate-decision.md` | Write | — | self | 7b |
| 35 | If PASS → L1 entry sub-list (deferred); if FAIL → retro to v3 | — | — | self | 7c |

---

## Detailed step specs

### Step 0 — Pre-flight setup

```bash
# 0.1 Confirm delegation mechanism
cd C:/claudehome/projects/managed-agents-research
ls core/v2/                                    # check for minimax wrapper
grep -ri "minimax" core/ 2>/dev/null | head    # find existing invocations
# If none found, document chosen mechanism inline in Step 6 prompt

# 0.2 Create directory shell
mkdir -p research/agent-evaluation-benchmark/harness/harness/{adapters,identity,generators,tasks,scoring,runner,output}
mkdir -p research/agent-evaluation-benchmark/harness/tests
mkdir -p research/agent-evaluation-benchmark/harness/results
touch research/agent-evaluation-benchmark/harness/harness/{adapters,identity,generators,scoring,runner,output}/__init__.py
touch research/agent-evaluation-benchmark/harness/harness/__init__.py
echo "results/" > research/agent-evaluation-benchmark/harness/.gitignore
echo "__pycache__/" >> research/agent-evaluation-benchmark/harness/.gitignore
echo "*.pyc" >> research/agent-evaluation-benchmark/harness/.gitignore
echo ".pytest_cache/" >> research/agent-evaluation-benchmark/harness/.gitignore
```

Risk: none (pure mkdir).

---

### Step 1 — CLAUDE_HOME isolation spike (R1 mitigation)

```bash
# Test if HOME=/tmp/empty breaks claude-code auth
mkdir -p /tmp/claude_spike_empty
HOME=/tmp/claude_spike_empty claude -p "say hi" --model claude-opus-4-7 2>&1 | head -20

# If fails: search for alternative
claude --help 2>&1 | grep -i -E "config|home|settings" | head
# Look for: --settings-dir, --config-dir, CLAUDE_CONFIG_DIR env var

# If found: document choice
# If all fail: fallback plan is Docker container (extends Step 7 by 0.5 day)
```

Record outcome inline in Step 7 prompt as `CLAUDE_HOME_ISOLATION_METHOD = "..."`.

Risk: R1. Predetection done here; if fails, switch to fallback before Step 7.

---

### Step 2 — `pyproject.toml` + `.gitignore`

```toml
# research/agent-evaluation-benchmark/harness/pyproject.toml
[project]
name = "agent-eval-harness"
version = "0.1.0"
description = "Phase A smoke pilot harness for deployed AI system capability assessment"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "pydantic>=2.0",
    "pytest>=8.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["harness*"]
```

Run `cd research/agent-evaluation-benchmark/harness && uv sync` or `pip install -e .` to verify.

---

### Step 3 — `harness/config.py`

```python
"""Central config: API keys, paths, model IDs."""
import os
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent
TASKS_DIR = HARNESS_ROOT / "tasks"
RESULTS_DIR = HARNESS_ROOT.parent / "results"

# Model IDs (full IDs, not aliases)
SUBJECT_LLM = "claude-opus-4-7"
JUDGE_LLM = "claude-sonnet-4-6"
JUDGE_TEMPERATURE = 0.0

# Budget guardrail (Phase A pass gate 3)
BUDGET_USD_HARD_CAP = 30.0

def get_anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key
```

---

### Step 4 — `harness/adapters/base.py`

```python
"""SystemAdapter Protocol + shared dataclasses. Imported by all 3 adapters
and by runner/trial.py. Schema-critical: changes break downstream."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Any

class TrialStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    NA = "na"
    VARIANCE_EXCEEDED = "variance_exceeded"

@dataclass
class Trace:
    output: str
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)  # {input_tokens, output_tokens}
    trace_log: list[str] = field(default_factory=list)
    latency_ms: int = 0

@dataclass
class CostInfo:
    input_tokens: int
    output_tokens: int
    usd_estimated: float

@dataclass
class IdentityTuple:
    llm_id: str
    training_state: str
    gateway: str
    instruction_layer_hash: str
    mcp_set: list[str]
    skill_set: list[str]
    tool_inventory: list[str]
    memory_system: dict[str, Any]
    runtime: dict[str, Any]

class SystemAdapter(Protocol):
    def identity(self) -> IdentityTuple: ...
    def submit(self, prompt: str, task_id: str) -> Trace: ...
    def cost(self, trace: Trace) -> CostInfo: ...
    def teardown(self) -> None: ...
```

---

### Step 5 — `harness/adapters/_claude_cli.py` (security-critical)

```python
"""Shared subprocess helper for claude-code CLI adapters.
CRITICAL: prompts MUST go via stdin, never argv (command injection risk).
Reference: memory feedback_shotclock_stdin_for_long_prompts (2026-05-XX)."""
import subprocess
import time
from pathlib import Path

def run_claude_cli(
    prompt: str,
    model: str,
    env: dict[str, str],
    permission_mode: str = "bypassPermissions",
    cwd: Path | None = None,
    timeout_sec: int = 120,
) -> tuple[str, int, int]:
    """Returns (output, exit_code, wall_clock_ms). Prompt passed via stdin."""
    cmd = [
        "claude", "-p",
        "--model", model,
        "--permission-mode", permission_mode,
        "--output-format", "stream-json",
    ]
    start = time.monotonic()
    proc = subprocess.run(
        cmd,
        input=prompt.encode("utf-8"),  # stdin, not argv
        capture_output=True,
        env=env,
        cwd=cwd,
        timeout=timeout_sec,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return proc.stdout.decode("utf-8", errors="replace"), proc.returncode, elapsed_ms
```

Risk: command injection. Mitigated by stdin path. Code review at commit time: grep `cmd =` to verify no f-string interpolation of prompt.

---

### Step 6 — DELEGATE `harness/adapters/bare_api.py`

**Delegation prompt** (paste into minimax-m2.7 verbatim, **must include rule: forbid all git operations including reset/stash/checkout/clean**):

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/adapters/bare_api.py

It defines `BareClaudeAPIAdapter` implementing the SystemAdapter Protocol from
`harness/adapters/base.py`. Imports:

    from anthropic import Anthropic
    from harness.adapters.base import SystemAdapter, Trace, CostInfo, IdentityTuple
    from harness.config import get_anthropic_key, SUBJECT_LLM

Specification:

class BareClaudeAPIAdapter:
    def __init__(self):
        self.client = Anthropic(api_key=get_anthropic_key())
        self.llm_id = SUBJECT_LLM  # "claude-opus-4-7"

    def identity(self) -> IdentityTuple:
        # Return: bare API has empty everything
        # instruction_layer_hash = SHA-256 of empty string
        #   = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        # gateway = "anthropic-api-direct"
        # training_state = "instruction-tuned"
        # mcp_set = []
        # skill_set = []
        # tool_inventory = []
        # memory_system = {"kind": "none", "location": None, "size_kb": None}
        # runtime = {"host": "anthropic-cloud", "container": None,
        #            "network": "unrestricted", "fs_perms": "none"}

    def submit(self, prompt: str, task_id: str) -> Trace:
        # Call self.client.messages.create() with:
        #   model=self.llm_id
        #   messages=[{"role": "user", "content": prompt}]
        #   max_tokens=2000
        # NO system prompt. NO tools.
        # Time the call. Return Trace with:
        #   output = response.content[0].text
        #   tool_invocations = []
        #   usage = {"input_tokens": ..., "output_tokens": ...}
        #   trace_log = [f"task_id={task_id}", f"model={self.llm_id}"]
        #   latency_ms = measured wall-clock

    def cost(self, trace: Trace) -> CostInfo:
        # Opus 4.7 pricing: $15/M input, $75/M output (verify against anthropic.com/pricing)
        # Return CostInfo with input_tokens, output_tokens, usd_estimated

    def teardown(self) -> None:
        pass  # no cleanup needed

Constraints:
- Single file, ~80 lines including docstring
- No git operations of any kind (no commit, no reset, no stash, no checkout, no clean, no pull)
- Do not modify any other file
- Do not output explanation; output only the Python file content
- If anthropic SDK API has drifted, write code per current SDK best practice and add a `# NOTE: verified against anthropic SDK X.Y.Z` comment line
```

Risk: none specific (low-complexity adapter).

---

### Step 7 — DELEGATE `harness/adapters/vanilla_cc.py`

**Prerequisite**: Step 1 spike resolved; record `CLAUDE_HOME_ISOLATION_METHOD` from spike.

**Delegation prompt** (paste verbatim, fill in `<METHOD_FROM_STEP_1>`):

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/adapters/vanilla_cc.py

It defines `ClaudeCodeVanillaAdapter` implementing SystemAdapter. Imports:

    import tempfile, hashlib, os
    from pathlib import Path
    from harness.adapters.base import SystemAdapter, Trace, CostInfo, IdentityTuple
    from harness.adapters._claude_cli import run_claude_cli
    from harness.config import SUBJECT_LLM

CLAUDE_HOME isolation method (from spike): <METHOD_FROM_STEP_1>

Specification:

class ClaudeCodeVanillaAdapter:
    def __init__(self):
        # Create persistent temp config dir for this adapter's lifetime
        self.config_dir = Path(tempfile.mkdtemp(prefix="cc_vanilla_"))
        # Apply isolation method per spike result
        self.env = self._build_isolated_env()

    def _build_isolated_env(self) -> dict[str, str]:
        # Inherit minimum from os.environ (PATH, USERPROFILE on Windows, etc.)
        # Then override based on isolation method:
        #   - If HOME-based: set HOME=str(self.config_dir)
        #   - If CLAUDE_CONFIG_DIR-based: set that env var
        #   - Always: do NOT include user's ANTHROPIC_API_KEY env or other state
        # Return dict suitable for subprocess env=

    def identity(self) -> IdentityTuple:
        # Hash empty config dir state (no CLAUDE.md present)
        empty_hash = hashlib.sha256(b"").hexdigest()
        return IdentityTuple(
            llm_id=SUBJECT_LLM,
            training_state="instruction-tuned",
            gateway="anthropic-api-direct",
            instruction_layer_hash=f"sha256:{empty_hash}",
            mcp_set=[],
            skill_set=[],
            tool_inventory=["bash", "file_read", "file_write", "edit", "glob", "grep", "web_fetch"],
            memory_system={"kind": "session_only", "location": None, "size_kb": None},
            runtime={"host": "windows-11", "container": None, "network": "unrestricted", "fs_perms": "sandbox-rw"},
        )

    def submit(self, prompt: str, task_id: str) -> Trace:
        # Use run_claude_cli helper from _claude_cli.py
        # Use a fresh sandboxed cwd (tempfile.mkdtemp prefix=task_id)
        # Parse stream-json output to extract usage tokens if available
        # Return Trace

    def cost(self, trace: Trace) -> CostInfo:
        # Same Opus 4.7 pricing as bare_api

    def teardown(self) -> None:
        # shutil.rmtree(self.config_dir, ignore_errors=True)
        # cleanup any sandbox cwds created during run

Constraints:
- Single file, ~100 lines
- No git operations
- Do not modify other files
- Use only stdlib + anthropic SDK; no new dependencies
- Output Python file content only
```

Risk: R1. Resolved at Step 1; if spike fails, this step blocks.

---

### Step 8 — DELEGATE `harness/adapters/full_cc.py`

**Delegation prompt** (paste verbatim):

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/adapters/full_cc.py

It defines `ClaudeCodeFullAdapter` implementing SystemAdapter. Same shape as
vanilla_cc.py but uses operator's actual ~/.claude/ state. Imports:

    import hashlib, os
    from pathlib import Path
    from harness.adapters.base import SystemAdapter, Trace, CostInfo, IdentityTuple
    from harness.adapters._claude_cli import run_claude_cli
    from harness.config import SUBJECT_LLM

Specification:

class ClaudeCodeFullAdapter:
    def __init__(self):
        # Use real ~/.claude/ — do NOT isolate
        # Capture identity snapshot at init time
        self._snapshot = self._compute_identity_snapshot()

    def _compute_identity_snapshot(self) -> IdentityTuple:
        home = Path.home() / ".claude"
        # Hash concatenation of CLAUDE.md files in canonical order:
        #   ~/.claude/CLAUDE.md
        #   <project-root>/CLAUDE.md (use cwd at adapter init)
        files_to_hash = [home / "CLAUDE.md", Path.cwd() / "CLAUDE.md"]
        h = hashlib.sha256()
        for fp in files_to_hash:
            if fp.exists():
                h.update(fp.read_bytes())
            h.update(b"\x00")  # separator
        # Also include skills/_index.md if present
        skills_index = home / "skills" / "_index.md"
        if skills_index.exists():
            h.update(skills_index.read_bytes())
        instruction_hash = f"sha256:{h.hexdigest()}"

        # Enumerate skills (directory listing under ~/.claude/skills/)
        skills_dir = home / "skills"
        skill_names = sorted([
            d.name for d in skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ]) if skills_dir.exists() else []

        # Enumerate MCP from settings (best-effort; if parse fails, return [])
        # Try ~/.claude/settings.json -> mcpServers keys
        mcp_set = []
        settings = home / "settings.json"
        if settings.exists():
            try:
                import json
                data = json.loads(settings.read_text())
                mcp_set = sorted(data.get("mcpServers", {}).keys())
            except Exception:
                pass

        return IdentityTuple(
            llm_id=SUBJECT_LLM,
            training_state="instruction-tuned",
            gateway="anthropic-api-direct",
            instruction_layer_hash=instruction_hash,
            mcp_set=mcp_set,
            skill_set=skill_names,
            tool_inventory=["bash", "file_read", "file_write", "edit", "glob", "grep", "web_fetch"],
            memory_system={
                "kind": "persistent_file_based",
                "location": str(home / "projects"),
                "size_kb": None,  # optional: walk dir for size
            },
            runtime={"host": "windows-11", "container": None, "network": "unrestricted", "fs_perms": "user-home-rw"},
        )

    def identity(self) -> IdentityTuple:
        return self._snapshot

    def submit(self, prompt: str, task_id: str) -> Trace:
        # Use run_claude_cli with os.environ.copy() (inherit user's full env)
        # Use fresh sandbox cwd

    def cost(self, trace: Trace) -> CostInfo:
        # Same Opus 4.7 pricing

    def teardown(self) -> None:
        pass  # do not delete user's ~/.claude/

Constraints:
- Single file, ~120 lines
- No git operations
- Do not modify other files; do not modify ~/.claude/
- Output Python only
```

Risk: none specific.

---

### Step 9 — Verify adapters + commit

```bash
cd research/agent-evaluation-benchmark/harness
python -c "from harness.adapters.bare_api import BareClaudeAPIAdapter; print('OK')"
python -c "from harness.adapters.vanilla_cc import ClaudeCodeVanillaAdapter; print('OK')"
python -c "from harness.adapters.full_cc import ClaudeCodeFullAdapter; print('OK')"
# Smoke: each adapter's identity() returns valid IdentityTuple
python -c "from harness.adapters.bare_api import BareClaudeAPIAdapter; print(BareClaudeAPIAdapter().identity())"

git add research/agent-evaluation-benchmark/harness/harness/adapters/ \
        research/agent-evaluation-benchmark/harness/harness/config.py \
        research/agent-evaluation-benchmark/harness/harness/__init__.py \
        research/agent-evaluation-benchmark/harness/pyproject.toml \
        research/agent-evaluation-benchmark/harness/.gitignore
git commit -m "harness: Phase A foundation + 3 adapters"
```

---

### Step 10 — DELEGATE `harness/generators/a1_grid_puzzle.py`

**Delegation prompt**:

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/generators/a1_grid_puzzle.py

This is a one-shot generator script. When run as `python -m harness.generators.a1_grid_puzzle`,
it writes 10 grid-puzzle tasks to harness/tasks/a1_pool.json.

Task format (each item in pool):
{
  "task_id": "A1-001",
  "dimension": "A1",
  "difficulty": 3,
  "prompt": "<puzzle text>",
  "expected_answer": "<deterministic answer>",
  "rubric_hints": {"reasoning_must_mention": ["<key concept>"]}
}

Puzzle design (difficulty 3):
- 4x4 grid filled with letters per stated rules
- Rules use 2-3 constraints: e.g., "Row 1 contains A,B,C,D in some order",
  "Column 2 is alphabetically sorted top-to-bottom", "No two adjacent
  cells share the same letter (diagonal not counted)"
- Question: "What letter is at position (row=X, col=Y)?"
- Solver must enumerate constraints; answer is single letter
- 10 puzzles with different rule combinations, ALL solvable, ALL with unique answer
- Use deterministic generation: seed=42, no randomness leak across runs

Implementation:
- Pure stdlib (no numpy / no external libs)
- itertools.permutations for enumerating row/col fillings
- constraint check function returns bool
- Verify each generated puzzle has exactly 1 solution before adding to pool
- If under 10 unique puzzles found in seed=42 search, increment seed deterministically until 10 found

Output:
- Writes harness/tasks/a1_pool.json (formatted, sorted keys, 2-space indent)
- Prints "Wrote 10 tasks to <path>" to stdout
- Returns 0 on success

Constraints:
- Single file, ~150 lines
- Pure stdlib
- No git operations
- Do not modify other files
- Output Python only
```

---

### Step 11 — DELEGATE `harness/generators/a2_working_memory.py`

**Delegation prompt**:

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/generators/a2_working_memory.py

One-shot generator. `python -m harness.generators.a2_working_memory` writes 10
n-back working-memory tasks to harness/tasks/a2_pool.json.

Task format (matches a1 schema):
{
  "task_id": "A2-001",
  "dimension": "A2",
  "difficulty": 3,
  "prompt": "I will give you a sequence of items. After the sequence, I will
             ask: 'What item appeared 3 positions before the last one?'
             Answer with just the item.\n\nSequence: cat, dog, fish, cat,
             bird, dog, ...",
  "expected_answer": "<the answer>",
  "rubric_hints": {"requires_state_tracking": true, "n_back": 3}
}

Task design (difficulty 3):
- Sequences of 8-12 items from a closed vocabulary of 5 distinct items
  (e.g., {cat, dog, fish, bird, rabbit})
- n=3 back (always)
- Some sequences include repeats to test working memory not just sequence position
- 10 sequences, seed=42

Implementation:
- random.Random(42) for deterministic generation
- Generate sequence of length 8 or 9 or 10 (cycle through), items chosen from
  vocab with some probability of repeats
- expected_answer = sequence[-1 - 3] = sequence[-4]
- Verify answer is unambiguous (no special edge cases)

Constraints:
- Single file, ~80 lines
- Pure stdlib
- No git operations
- Output Python only
```

---

### Step 12 — DELEGATE `harness/generators/b1_synthetic_fs.py`

**Delegation prompt**:

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/generators/b1_synthetic_fs.py

One-shot generator. `python -m harness.generators.b1_synthetic_fs` writes 10
synthetic-filesystem exploration tasks to harness/tasks/b1_pool.json.

Each task creates a small synthetic project directory tree (10-15 files) with
exactly ONE hidden inconsistency. The agent must find and report it.

Task format:
{
  "task_id": "B1-001",
  "dimension": "B1",
  "difficulty": 3,
  "prompt": "I have given you read access to a project directory at <PATH>.
             Find the single inconsistency in this project — one file
             references or implies the existence of something that doesn't
             actually exist, or there is a duplicate, or there is a
             misnamed file. Report:
             1. What the inconsistency is (one sentence)
             2. Which file(s) are involved (paths)
             3. How to fix it (one line)",
  "expected_answer": {
    "inconsistency_type": "broken_reference|duplicate|misnamed",
    "involved_files": ["src/main.py", "src/helpers.py"],
    "description": "main.py imports from helpers.py but file is named helper.py"
  },
  "rubric_hints": {
    "must_use_tools": ["glob", "grep", "file_read"],
    "interface_lacks_affordance_subjects": ["BareClaudeAPIAdapter"]
  },
  "setup_script": "<embedded shell script or python instructions to create the FS state at runtime>"
}

Inconsistency types (rotate across 10 tasks):
- Type A (broken_reference): main.py imports helpers but file named helper.py
- Type B (duplicate): two files with identical content but different names
- Type C (misnamed): test_user.py contains tests for "Product" class
- Type D (orphan): config.yaml references "templates/email.html" that doesn't exist
- Type E (path drift): README says "see scripts/run.sh" but file is at "bin/run.sh"

Setup script approach:
- Embed Python dict describing exact file tree to create:
  "files": {"src/main.py": "<content>", "src/helper.py": "<content>", ...}
- Pilot runner creates a sandbox dir per trial, writes these files, passes
  the dir path into the prompt's <PATH> placeholder

Implementation:
- 2 tasks per inconsistency type (10 total)
- seed=42 for any randomization (filename variants, content variants)
- expected_answer is deterministic per task

Constraints:
- Single file, ~200 lines (most volume is file contents in dicts)
- Pure stdlib
- No git operations
- Output Python only
```

---

### Step 13 — Run generators

```bash
cd research/agent-evaluation-benchmark/harness
python -m harness.generators.a1_grid_puzzle      # writes tasks/a1_pool.json
python -m harness.generators.a2_working_memory   # writes tasks/a2_pool.json
python -m harness.generators.b1_synthetic_fs     # writes tasks/b1_pool.json

# Verify each pool has 10 valid tasks
python -c "import json; d=json.load(open('harness/tasks/a1_pool.json')); assert len(d)==10; print('A1 OK')"
python -c "import json; d=json.load(open('harness/tasks/a2_pool.json')); assert len(d)==10; print('A2 OK')"
python -c "import json; d=json.load(open('harness/tasks/b1_pool.json')); assert len(d)==10; print('B1 OK')"
```

---

### Step 14 — Commit generators + pools

```bash
git add research/agent-evaluation-benchmark/harness/harness/generators/ \
        research/agent-evaluation-benchmark/harness/harness/tasks/
git commit -m "harness: 3 task generators + static pools (10 tasks each)"
```

---

### Step 15 — DELEGATE `harness/identity/snapshot.py`

**Delegation prompt**:

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/identity/snapshot.py

Module providing identity snapshot utilities. Already in scope from
adapters/base.py: IdentityTuple dataclass. This file adds:

1. identity_hash(t: IdentityTuple) -> str
   Returns sha256(canonical_json(t)) where canonical_json sorts keys and
   uses no whitespace. Two identical tuples must produce identical hash;
   any field change must produce different hash.

2. to_json(t: IdentityTuple) -> str
   Pretty-printed JSON for human reading (2-space indent, sorted keys).

3. compare(a: IdentityTuple, b: IdentityTuple) -> list[str]
   Returns list of field names that differ. Used by trial runner for
   drift detection between trials.

Imports:
    import hashlib, json
    from dataclasses import asdict
    from harness.adapters.base import IdentityTuple

Constraints:
- Single file, ~60 lines
- Pure stdlib
- No git operations
- Output Python only
```

---

### Step 16 — DELEGATE `harness/output/profile.py`

**Delegation prompt**:

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/output/profile.py

Capability profile JSON schema + emitter.

Schema (v0.1.0):
{
  "schema_version": "0.1.0",
  "run_id": "<UUID>",
  "timestamp_iso": "...",
  "subject": {
    "name": "bare-claude-api|claude-code-vanilla|claude-code-full",
    "identity": <IdentityTuple as dict>,
    "identity_hash": "<sha256>"
  },
  "dimensions": {
    "A1": {
      "trials": [
        {
          "trial_idx": 0,
          "task_id": "A1-001",
          "status": "success|failure|na|variance_exceeded",
          "raw_score": 0-100,
          "judge_reasoning": "...",
          "cost_usd": ...,
          "latency_ms": ...,
          "failure_reason": null or string
        }
      ],
      "mean_raw_score": float,
      "n_valid": int
    },
    "A2": {...},
    "B1": {...}
  },
  "totals": {"cost_usd": float, "duration_sec": int}
}

Imports:
    import json, uuid
    from datetime import datetime, timezone
    from pathlib import Path
    from dataclasses import asdict
    from harness.adapters.base import IdentityTuple, TrialStatus
    from harness.identity.snapshot import identity_hash

Functions:

def new_profile(subject_name: str, identity: IdentityTuple) -> dict:
    """Initialize empty profile for a subject."""

def add_trial_result(profile: dict, dimension: str, trial_idx: int,
                     task_id: str, status: TrialStatus, raw_score: float | None,
                     judge_reasoning: str, cost_usd: float, latency_ms: int,
                     failure_reason: str | None = None) -> None:
    """Mutate profile in place."""

def finalize_profile(profile: dict) -> None:
    """Compute mean_raw_score, n_valid per dimension. Compute totals."""

def write_profile(profile: dict, path: Path) -> None:
    """Write JSON with 2-space indent, sorted keys."""

Constraints:
- Single file, ~120 lines
- Pure stdlib
- No git operations
- Output Python only
```

---

### Step 17 — DELEGATE `harness/scoring/pr_calc.py`

**Delegation prompt**:

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/scoring/pr_calc.py

Percentile rank calculation + cross-run stability (Kendall's tau).

Imports:
    from typing import Sequence
    from itertools import combinations

Functions:

def compute_pr(scores: dict[str, float | None]) -> dict[str, float | None]:
    """Given {subject_name: raw_score_or_None}, return {subject_name: PR_or_None}.
    Subjects with None score get None PR (N/A propagates).
    PR for valid subjects: percentage of OTHER valid subjects with strictly
    lower score, with ties broken at midpoint.
    For N valid subjects: PR = (count_strictly_below + 0.5 * count_tied_excluding_self) / (N - 1) * 100
    If only 1 valid subject in dimension: that subject gets PR=50 (undefined, neutral)
    If 0 valid: empty dict."""

def kendall_tau(rank_a: list[str], rank_b: list[str]) -> float:
    """Kendall's tau between two rank orderings (lists of subject_names ordered
    by score). Only subjects appearing in BOTH lists are compared.
    Returns float in [-1, 1]. 1 = identical, -1 = reversed."""

def stability_across_runs(per_run_pr: list[dict[str, float | None]]) -> dict:
    """Given list of {subject: PR} from each run, return:
    {
      "kendall_tau_pairwise": [[tau_01, tau_02, tau_12]],  # all run pairs
      "mean_tau": float,
      "rank_flips": int,   # number of times max-rank swaps between adjacent runs
    }"""

def gate_check(per_dim_per_run_pr: dict[str, list[dict[str, float | None]]],
               kendall_tau_threshold: float = 0.67,
               pr_spread_threshold: float = 50.0) -> dict:
    """Phase A pass gate evaluation. Returns:
    {
      "gate_1_rank_stability": bool,
      "gate_2_differentiation": bool,
      "rank_stability_details": {dim: stability_dict},
      "differentiation_details": {dim: {"max_pr": ..., "min_pr": ..., "spread": ...}}
    }
    Gate 1: ALL dimensions have mean_tau >= 0.67
    Gate 2: AT LEAST ONE dimension has max(PR) - min(PR) >= 50 in at least one run"""

Constraints:
- Single file, ~150 lines
- Pure stdlib (no scipy)
- No git operations
- Output Python only
- Include 2-3 inline docstring examples showing expected output
```

---

### Step 18 — DELEGATE `harness/runner/trial.py`

**Delegation prompt**:

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/runner/trial.py

Single trial executor.

Imports:
    import time, traceback
    from pathlib import Path
    from harness.adapters.base import SystemAdapter, Trace, TrialStatus
    from harness.scoring.judge import judge_trial   # written in Step 27, signature stable

Function:

def run_trial(
    adapter: SystemAdapter,
    task: dict,                      # task dict from pool JSON
    subject_class_supports_dim: bool,  # if False, return NA immediately
    sandbox_dir: Path | None = None, # for B1 trials
) -> dict:
    """Execute one trial. Returns dict matching profile.add_trial_result args:
    {
      "task_id": ...,
      "status": TrialStatus,
      "raw_score": float | None,    # None iff status != SUCCESS
      "judge_reasoning": str,
      "cost_usd": float,
      "latency_ms": int,
      "failure_reason": str | None
    }

    Flow:
    1. If not subject_class_supports_dim: return status=NA, reason="interface_lacks_affordance"
    2. For B1: sandbox_dir provided; setup files per task.setup_script
    3. Call adapter.submit(prompt, task_id)
    4. Catch exceptions: return status=FAILURE, reason=traceback short form
    5. Call judge_trial(task, trace) -> (score, judge_reasoning)
       Judge handles its own malformed-input case (returns score=0 + reason)
    6. Call adapter.cost(trace) -> cost_info
    7. Return success dict"""

Constraints:
- Single file, ~100 lines
- No git operations
- Do not modify other files
- Output Python only
```

---

### Step 19 — DELEGATE `harness/runner/pilot.py`

**Delegation prompt**:

```
Write a single Python file at path:
  research/agent-evaluation-benchmark/harness/harness/runner/pilot.py

Pilot orchestrator + CLI entry point.

Imports:
    import argparse, json, sys, tempfile
    from pathlib import Path
    from harness.config import RESULTS_DIR, BUDGET_USD_HARD_CAP
    from harness.adapters.bare_api import BareClaudeAPIAdapter
    from harness.adapters.vanilla_cc import ClaudeCodeVanillaAdapter
    from harness.adapters.full_cc import ClaudeCodeFullAdapter
    from harness.runner.trial import run_trial
    from harness.output.profile import new_profile, add_trial_result, finalize_profile, write_profile

Subject-dimension affordance matrix (constants):
    AFFORDANCE = {
      "bare-claude-api": {"A1": True, "A2": True, "B1": False},
      "claude-code-vanilla": {"A1": True, "A2": True, "B1": True},
      "claude-code-full": {"A1": True, "A2": True, "B1": True},
    }

CLI:
    python -m harness.runner.pilot --runs 3 --out results/ [--dry-run]

Flow:
1. Parse args. Default runs=3.
2. Load 3 task pools (A1, A2, B1) from harness/tasks/*.json. Pick task 0 of each
   for Phase A (later: rotate through pool, but Phase A always task 0 for repeatability).
3. For each run_idx in range(runs):
   For each subject_name, AdapterClass:
     - Instantiate adapter
     - profile = new_profile(subject_name, adapter.identity())
     - For each dim in ["A1", "A2", "B1"]:
         task = pool[dim][0]
         supports = AFFORDANCE[subject_name][dim]
         sandbox = tempfile.mkdtemp() if dim == "B1" else None
         result = run_trial(adapter, task, supports, sandbox_dir=sandbox)
         add_trial_result(profile, dim, run_idx, **result)
         CHECK: if total cost so far > BUDGET_USD_HARD_CAP: halt with error
     - finalize_profile(profile)
     - write_profile(profile, RESULTS_DIR / f"run{run_idx}_{subject_name}.json")
     - adapter.teardown()
4. Print summary table to stdout: per (run, subject, dim) status + score.

If --dry-run: same flow but for run_idx=0 only, write to /tmp/.

Constraints:
- Single file, ~180 lines
- Pure stdlib + harness modules
- No git operations
- Output Python only
- Argparse must support --runs <int>, --out <path>, --dry-run flag
```

---

### Step 20 — Verify + commit Day 4a

```bash
cd research/agent-evaluation-benchmark/harness
python -c "from harness.runner.pilot import main; print('OK')"
python -c "from harness.scoring.pr_calc import compute_pr; print(compute_pr({'a':10, 'b':20, 'c':None}))"

git add research/agent-evaluation-benchmark/harness/harness/identity/ \
        research/agent-evaluation-benchmark/harness/harness/output/ \
        research/agent-evaluation-benchmark/harness/harness/scoring/pr_calc.py \
        research/agent-evaluation-benchmark/harness/harness/runner/
git commit -m "harness: identity snapshot, profile emitter, PR calc, trial/pilot runner"
```

---

### Step 21 — `tests/test_pr_calc.py` (self)

```python
"""Tests for PR calc, esp. N/A propagation."""
from harness.scoring.pr_calc import compute_pr, kendall_tau, gate_check

def test_pr_basic_three_subjects():
    scores = {"a": 10.0, "b": 50.0, "c": 90.0}
    pr = compute_pr(scores)
    assert pr["a"] == 0.0
    assert pr["b"] == 50.0
    assert pr["c"] == 100.0

def test_pr_with_na():
    scores = {"a": None, "b": 50.0, "c": 90.0}
    pr = compute_pr(scores)
    assert pr["a"] is None
    assert pr["b"] == 0.0
    assert pr["c"] == 100.0

def test_pr_ties_midpoint():
    scores = {"a": 50.0, "b": 50.0, "c": 90.0}
    pr = compute_pr(scores)
    # a and b tied; both should get same PR
    assert pr["a"] == pr["b"]
    assert pr["c"] == 100.0

def test_pr_single_valid_subject():
    scores = {"a": None, "b": None, "c": 50.0}
    pr = compute_pr(scores)
    assert pr["c"] == 50.0  # neutral

def test_kendall_tau_identical():
    assert kendall_tau(["a","b","c"], ["a","b","c"]) == 1.0

def test_kendall_tau_reversed():
    assert kendall_tau(["a","b","c"], ["c","b","a"]) == -1.0

def test_gate_check_pass():
    # All dims have stable rank, A1 has wide spread
    per_dim = {
      "A1": [{"a": 0, "b": 50, "c": 100}, {"a": 0, "b": 50, "c": 100}, {"a": 0, "b": 50, "c": 100}],
      "A2": [{"a": 40, "b": 50, "c": 60}, {"a": 40, "b": 50, "c": 60}, {"a": 40, "b": 50, "c": 60}],
      "B1": [{"a": None, "b": 40, "c": 60}, {"a": None, "b": 40, "c": 60}, {"a": None, "b": 40, "c": 60}],
    }
    result = gate_check(per_dim)
    assert result["gate_1_rank_stability"] is True
    assert result["gate_2_differentiation"] is True
```

---

### Step 22 — `tests/test_na_handling.py` (self)

```python
"""Test that Subject 1 × B1 N/A flow works end-to-end through trial runner."""
from harness.runner.trial import run_trial
from harness.adapters.bare_api import BareClaudeAPIAdapter
from harness.adapters.base import TrialStatus

def test_b1_na_for_bare_api():
    adapter = BareClaudeAPIAdapter()
    fake_task = {"task_id": "B1-test", "dimension": "B1", "prompt": "find inconsistency in <PATH>"}
    result = run_trial(adapter, fake_task, subject_class_supports_dim=False)
    assert result["status"] == TrialStatus.NA
    assert "interface_lacks_affordance" in result["failure_reason"]
    assert result["raw_score"] is None
    assert result["cost_usd"] == 0.0  # no API call made
```

---

### Step 23 — `tests/test_judge_malformed_input.py` (self)

```python
"""Test judge tolerates malformed LLM outputs."""
from harness.scoring.judge import judge_trial
from harness.adapters.base import Trace

def test_judge_empty_output():
    task = {"task_id":"A1-001", "dimension":"A1", "expected_answer":"D"}
    trace = Trace(output="", usage={"input_tokens":10, "output_tokens":0}, latency_ms=100)
    score, reason = judge_trial(task, trace)
    assert score == 0
    assert "empty" in reason.lower() or "malformed" in reason.lower()

def test_judge_truncated_output():
    task = {"task_id":"A1-001", "dimension":"A1", "expected_answer":"D"}
    trace = Trace(output="The answer is", usage={}, latency_ms=100)
    score, reason = judge_trial(task, trace)
    # Should NOT crash; should return low score
    assert isinstance(score, (int, float))
    assert 0 <= score <= 100

def test_judge_oversized_output():
    task = {"task_id":"A1-001", "dimension":"A1", "expected_answer":"D"}
    trace = Trace(output="X" * 50000, usage={}, latency_ms=100)
    score, reason = judge_trial(task, trace)
    assert isinstance(score, (int, float))
```

---

### Step 24-25 — pytest + commit

```bash
cd research/agent-evaluation-benchmark/harness
pytest tests/ -v
# Fix any failures
git add tests/
git commit -m "harness: tests for PR calc, N/A flow, judge malformed input"
```

---

### Step 26 — `harness/scoring/rubrics.py` (self, judgment-critical)

Behavioral rubric anchors for A1/A2/B1. **Opus writes this directly; rubric design is the single most important artifact for framework integrity.**

```python
"""Behavioral rubric anchors per dimension. Locked at Phase A Day 5;
not modified mid-pilot (per IMPLEMENTATION-PLAN §7 decision 5)."""

A1_RUBRIC = """
Score the agent's solution to this grid puzzle on 0-100:

Anchors:
- 0-20: Did not attempt, refused, or output is empty/unparseable
- 21-40: Engaged with puzzle but final answer is WRONG and reasoning shows
         no constraint enumeration (just guessed)
- 41-60: WRONG final answer but reasoning shows correct approach (enumerated
         some constraints, tried valid moves, just made arithmetic error)
- 61-80: CORRECT final answer but reasoning is sparse or implicit (didn't
         show the constraint application explicitly)
- 81-100: CORRECT final answer with explicit, clean reasoning trace showing:
          (a) enumeration of constraints, (b) elimination of impossible
          options, (c) clear final justification

Expected answer: {expected_answer}
"""

A2_RUBRIC = """
Score the agent's n-back working-memory answer on 0-100:

Anchors:
- 0-20: No answer or unparseable
- 21-40: Wrong answer, no acknowledgment of the n-back mechanic
- 41-60: Wrong answer but shows understanding (e.g., counted to wrong position
         due to off-by-one)
- 61-80: Correct answer with sparse reasoning
- 81-100: Correct answer with explicit indexing reasoning showing they counted
          backwards from end

Expected answer: {expected_answer}
"""

B1_RUBRIC = """
Score the agent's filesystem inconsistency report on 0-100:

Anchors:
- 0-20: Did not explore, refused, or reported no inconsistency found
- 21-40: Reported wrong inconsistency or fabricated one not in the actual FS
- 41-60: Identified inconsistency correctly but missed/wrong file paths, OR
         identified file paths correctly but description is off
- 61-80: Correctly identified inconsistency_type AND involved_files; description
         partially matches
- 81-100: Correctly identified all three (type, files, description) AND used
         tools efficiently (≤ 10 tool invocations for a 10-15 file project)

Expected inconsistency: {expected_answer}
Required tools used: glob, grep, file_read
"""

DIMENSION_RUBRICS = {"A1": A1_RUBRIC, "A2": A2_RUBRIC, "B1": B1_RUBRIC}
```

---

### Step 27 — `harness/scoring/judge.py` (self, prompt-critical)

```python
"""Sonnet 4.6 judge. Temperature=0. Prompt locked at Phase A Day 5."""
from anthropic import Anthropic
from harness.adapters.base import Trace
from harness.config import get_anthropic_key, JUDGE_LLM, JUDGE_TEMPERATURE
from harness.scoring.rubrics import DIMENSION_RUBRICS

JUDGE_SYSTEM_PROMPT = """You are an evaluator. Given a task, an agent's output,
and a rubric, return ONLY a JSON object with two fields:
  {"score": <0-100 integer>, "reasoning": "<one sentence>"}
Do not include any other text. If the output is empty or malformed, score=0
and reasoning="output empty or malformed"."""

def judge_trial(task: dict, trace: Trace) -> tuple[int, str]:
    """Returns (score, reasoning). Tolerates malformed agent output:
    - Empty output -> (0, "output empty...")
    - Oversized output (>10K chars) -> truncate and judge
    - Judge API returns non-JSON -> (0, "judge parse failure: ...")"""
    output = trace.output or ""
    if not output.strip():
        return 0, "output empty or malformed"
    if len(output) > 10000:
        output = output[:10000] + "...[truncated]"

    rubric_template = DIMENSION_RUBRICS[task["dimension"]]
    expected = task.get("expected_answer", "<no expected answer>")
    rubric = rubric_template.replace("{expected_answer}", str(expected))

    user_msg = f"TASK:\n{task['prompt']}\n\nAGENT OUTPUT:\n{output}\n\nRUBRIC:\n{rubric}"

    client = Anthropic(api_key=get_anthropic_key())
    try:
        resp = client.messages.create(
            model=JUDGE_LLM,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role":"user", "content":user_msg}],
            max_tokens=200,
            temperature=JUDGE_TEMPERATURE,
        )
        text = resp.content[0].text.strip()
        import json
        data = json.loads(text)
        return int(data["score"]), str(data["reasoning"])
    except Exception as e:
        return 0, f"judge parse failure: {type(e).__name__}"
```

---

### Step 28 — Judge consistency spike (R3 mitigation)

```bash
cd research/agent-evaluation-benchmark/harness
python -c "
from harness.scoring.judge import judge_trial
from harness.adapters.base import Trace
import statistics
task = {'task_id':'A1-001', 'dimension':'A1', 'prompt':'What is 2+2?', 'expected_answer':'4'}
trace = Trace(output='The answer is 4 because we add 2 and 2 together.', usage={}, latency_ms=100)
scores = [judge_trial(task, trace)[0] for _ in range(5)]
print(f'Scores: {scores}, stddev: {statistics.stdev(scores):.2f}')
"
# If stddev > 10: revise rubric anchors (add explicit numeric thresholds)
# If stddev > 5 after revision: accept noise, switch gate 1 to Spearman ρ
```

---

### Step 29 — Commit rubrics + judge

```bash
git add research/agent-evaluation-benchmark/harness/harness/scoring/rubrics.py \
        research/agent-evaluation-benchmark/harness/harness/scoring/judge.py
git commit -m "harness: rubrics + Sonnet 4.6 judge (Phase A Day 5 locked)"
```

---

### Step 30 — /code-audit

Invoke `code-audit` skill on `research/agent-evaluation-benchmark/harness/`. Address findings; commit fixes if any.

---

### Step 31 — Dry-run

```bash
python -m harness.runner.pilot --runs 1 --out /tmp/harness_dryrun --dry-run
# Check cost projection
python -c "
import json, glob
total = sum(json.load(open(p))['totals']['cost_usd'] for p in glob.glob('/tmp/harness_dryrun/*.json'))
print(f'Dry-run cost: \${total:.4f}; projected 3-run total: \${total*3:.2f}')
"
# If projected > $25: stop, revise (cut N or simplify B1 setup)
```

---

### Step 32 — Run pilot × 3

```bash
mkdir -p research/agent-evaluation-benchmark/harness/results
python -m harness.runner.pilot --runs 3 --out research/agent-evaluation-benchmark/harness/results/
# Outputs: 9 JSON files (3 runs × 3 subjects) in results/
```

---

### Step 33 — `pilot-report.md` (self)

Write to `research/agent-evaluation-benchmark/harness/results/pilot-report.md`. Must include:
- Identity snapshots of 3 subjects (hash + first 3 differing fields)
- Per-dimension PR ranking table (3 runs × 3 subjects each)
- Kendall's τ across runs per dimension
- Differentiation spread per dimension per run
- Cost breakdown
- Any failures + failure_reason summary

---

### Step 34 — `pass-gate-decision.md` (self)

Write to `research/agent-evaluation-benchmark/harness/results/pass-gate-decision.md`:
- Gate 1 (rank stability): PASS/FAIL + Kendall's τ per dim
- Gate 2 (differentiation): PASS/FAIL + max-min PR per dim per run
- Gate 3 (cost): PASS/FAIL + actual spend vs $30
- Overall: PASS (→ L1) / FAIL (→ v3 retro)

---

### Step 35 — Branch decision

If PASS → produce L1 entry sub-list (separate /implement run)
If FAIL → write retro to `results/phase-a-retro.md` listing v3 design assumptions that failed, propose fixes.

---

## Acceptance criteria (run at Step 32 completion)

| # | Test | How to verify |
|---|------|---------------|
| 1 | All 35 steps marked complete | `grep -c '\[x\]' IMPLEMENTATION-LIST.md` ≥ 35 |
| 2 | `pytest tests/ -v` all pass | exit code 0 |
| 3 | N/A handling: Subject 1 × B1 marked `status=na` | `jq '.dimensions.B1.trials[0].status' results/run0_bare-claude-api.json` == `"na"` |
| 4 | Judge malformed input doesn't crash | Step 23 test passes |
| 5 | Command injection guard | `grep -r "cmd = " harness/adapters/` shows no f-string prompt interpolation |
| 6 | TrialStatus enum used everywhere | `grep -r "status.*=.*\"success\"" harness/` finds 0 (all use enum) |
| 7 | Pilot end-to-end | 9 JSON profiles in `results/`, 1 pilot-report.md, 1 pass-gate-decision.md |
| 8 | Budget cap | `results/*.json` total `cost_usd` ≤ $30 |
| 9 | Pass gate decision rendered | `pass-gate-decision.md` has all 3 gate verdicts + overall PASS/FAIL |

---

## Pending / suggested skills

- **No skill exists for "verbatim spec delegation to minimax-m2.7"**: this list compensates by embedding full prompts inline. If this pattern repeats across projects (firn / my-site / etc.), candidate skill: `delegate-verbatim-spec` enforcing inline spec + `subagent-git-no-mutation` + "1 W = 1 file" rule
- **No skill for budget-guarded pilot runs**: candidate skill `budget-gated-eval` with `BUDGET_USD_HARD_CAP` checker built into runner

---

## Status

實作清單已寫入 `research/agent-evaluation-benchmark/IMPLEMENTATION-LIST.md`.
共 35 步，預計 invoke `subagent-git-no-mutation` skill × 10（每個 minimax-m2.7 delegate step）、`code-audit` × 1；自做 23 步、派 minimax-m2.7 12 步。
