# Stage 4.9 — Pilot Targets

> The five (+1 optional) pilot subjects, with their identity snapshots. Same-LLM-different-environment trio (subjects 1, 2, 3) is the framework's central demonstration.

---

## Subject 1 — Bare Claude API

**Display name**: `bare-claude-api`

**Identity snapshot**:

```json
{
  "llm_id": "claude-opus-4-7",
  "training_state": "instruction-tuned",
  "gateway": "anthropic-api-direct",
  "instruction_layer_hash": "sha256:e3b0c44298fc...",
  "mcp_set": [],
  "skill_set": [],
  "tool_inventory": [],
  "memory_system": {"kind": "none", "location": null,
                    "size_kb": null, "retrieval_mechanism": null},
  "runtime": {"host": "anthropic-cloud", "container": null,
              "network": "unrestricted", "fs_perms": "none"}
}
```

(`e3b0c44298fc...` is the SHA-256 of the empty string — bare API has no system prompt.)

**Predicted profile** (qualitative): Track A clean across all dimensions; Track B almost all N/A with self-described attempts; Track C lowest cost per task, lowest latency.

**Adapter**: `BareClaudeAPIAdapter` from interface-adapter-spec.md §3.

---

## Subject 2 — Claude Code (vanilla)

**Display name**: `claude-code-vanilla`

**Identity snapshot**:

```json
{
  "llm_id": "claude-opus-4-7",
  "training_state": "instruction-tuned",
  "gateway": "anthropic-api-direct",
  "instruction_layer_hash": "sha256:<hash_of_claude_code_default_system_prompt>",
  "mcp_set": [],
  "skill_set": [],
  "tool_inventory": ["bash", "file_read", "file_write", "edit", "glob", "grep", "web_fetch"],
  "memory_system": {"kind": "session_only", "location": null,
                    "size_kb": null, "retrieval_mechanism": null},
  "runtime": {"host": "windows-11", "container": null,
              "network": "unrestricted", "fs_perms": "sandbox-rw"}
}
```

**Setup** (v2 — permission mode resolved per R1-B #18): Fresh install of claude-code; no CLAUDE.md; no MCP servers connected; no skills installed; **permission mode = `bypassPermissions` uniformly across all subjects** to keep permission state constant across the differential trio. The framework executes in a freshly created temp working directory.

**Predicted profile**: Track A scores close to Subject 1 (within ±0.05); Track B B1 / B6 / B9 / B11 measurable; cost per task slightly higher (token overhead of CLI scaffolding); Track C C4 adapter ~45 LOC.

**Adapter**: `ClaudeCodeCLIAdapter` from interface-adapter-spec.md §4.

---

## Subject 3 — Claude Code (operator's full setup)

**Display name**: `claude-code-full`

**Identity snapshot**:

```json
{
  "llm_id": "claude-opus-4-7",
  "training_state": "instruction-tuned",
  "gateway": "anthropic-api-direct",
  "instruction_layer_hash": "sha256:<hash_of_~/.claude/CLAUDE.md + C:/claudehome/CLAUDE.md>",
  "mcp_set": [
    "playwright@latest",
    "filesystem@latest",
    "claude_ai_Gmail",
    "claude_ai_Google_Calendar",
    "claude_ai_Google_Drive"
  ],
  "skill_set": [
    "graphify:manual",
    "raise-talos:manual",
    "code-audit:manual",
    "evolve:manual",
    "implement:manual",
    "plan-check:manual",
    "..." (47 total — sorted alphabetically for hashing)
  ],
  "tool_inventory": ["bash", "file_read", "file_write", "edit", "glob",
                     "grep", "web_fetch", "web_search", "task_create",
                     "task_update", "schedule_wakeup", "...", "agent"],
  "memory_system": {
    "kind": "persistent_file_based",
    "location": "C:/Users/hangs/.claude/projects/.../memory/",
    "size_kb": 348,
    "retrieval_mechanism": "automatic_at_session_start"
  },
  "runtime": {"host": "windows-11", "container": null,
              "network": "unrestricted", "fs_perms": "user-home-rw"}
}
```

**Setup**: Operator's actual working setup. Captured at test time; allowed to drift (per identity-stability policy from system-identity-definition.md §3).

**Predicted profile**: Track A scores ≈ Subjects 1 and 2 (within ±0.05) — if they diverge significantly, our environment-isolation hypothesis is wrong. Track B B11 (multi-file mutation), B7 (self-correction), B12 (vague-goal convergence) score higher than Subject 2 due to skills + memory + MCP. Track C C1 cost higher (more tokens for scaffolding), C2 latency higher (extra LLM calls for skill invocation), C5 failure modes shift toward `cost_overrun` and `scope_creep_mid_task`.

**Differential delta** vs Subject 2: positive on B-track skill-dependent dimensions; near-zero on Track A (validates environment isolation).

**Adapter**: `ClaudeCodeCLIAdapter` with operator's `workdir = C:/claudehome` and the operator's `CLAUDE.md` / MCP registry pre-loaded.

---

## Subject 4 — Talos (Hetzner VM + Hermes)

**Display name**: `talos`

**Identity snapshot** (worked example from system-identity-definition.md §5):

```json
{
  "llm_id": "claude-opus-4-7",
  "training_state": "instruction-tuned",
  "gateway": "anthropic-api-direct",
  "instruction_layer_hash": "sha256:b8e2c1...",
  "mcp_set": [
    "filesystem@hermes-builtin",
    "telegram@2.0",
    "git@1.4"
  ],
  "skill_set": [
    "babysit-hold-socratic:auto",
    "raise-talos:manual",
    "talos-verify-claims:auto"
  ],
  "tool_inventory": [
    "bash", "file_read", "file_write", "git_op", "ssh", "tg_send"
  ],
  "memory_system": {
    "kind": "persistent_file_based",
    "location": "/home/hermes/.claude-talos/memory/",
    "size_kb": 412,
    "retrieval_mechanism": "automatic_at_session_start"
  },
  "runtime": {
    "host": "ubuntu-24.04",
    "container": "vm:cloud:hetzner-cx23",
    "network": "unrestricted",
    "fs_perms": "user-home-rw"
  }
}
```

**Setup**: Talos VM up and running, Hermes gateway listening on port 8642, `/identity` and `/submit` endpoints implemented per interface-adapter-spec.md §9.

**Predicted profile**: Track A scores ≈ Subject 3 (same LLM family, similar training); Track B fully measurable, B6 (cross-session) and B14 (async) high; B13 (self-evolution) opt-in. Track C C2 latency higher (network + SSH overhead), C5 failure modes may include `tool_error_not_recovered` (SSH/network blips).

**Adapter**: `TalosVMAdapter` from interface-adapter-spec.md §5.

---

## Subject 5 — Hestia (local VirtualBox + Hermes)

**Display name**: `hestia`

**Identity snapshot** (v2 — TBD fields resolved per R1-B #17):

```json
{
  "llm_id": "deepseek-v3",
  "training_state": "instruction-tuned",
  "gateway": "deepseek-api-direct",
  "instruction_layer_hash": "sha256:<from-hestia-SOUL.md>",
  "mcp_set": ["filesystem@hermes-builtin"],
  "skill_set": ["...self-built skills..."],
  "tool_inventory": ["bash", "file_read", "file_write", "git_op", "self_cron_mutation"],
  "memory_system": {
    "kind": "persistent_file_based",
    "location": "/home/hermes/.hestia-memory/",
    "size_kb": 600,
    "retrieval_mechanism": "automatic_at_session_start"
  },
  "runtime": {
    "host": "ubuntu-24.04",
    "container": "vm:virtualbox-local",
    "network": "unrestricted",
    "fs_perms": "user-home-rw"
  }
}
```

**Setup**: Hestia VM up and running locally; same `/identity` and `/submit` endpoint protocol as Talos. **Identity is queried fresh each trial** (Hestia is the canonical self-modifying subject; the adapter never caches).

**Predicted profile**: Track A scores may differ from Talos if gateway differs (e.g., DeepSeek vs Claude — gateway changes identity). Track B13 (self-environment evolution) is the headline measurement for Hestia — opt-in mode runs ≥6h window with delta-profile output. Identity-drift count expected non-zero across a full pilot run.

**Adapter**: `HestiaVMAdapter` from interface-adapter-spec.md §6.

---

## Subject 6 (optional) — GPT-based CLI (cross-LLM-family contrast)

**Display name**: `codex-cli` or `cursor-cli`

**Identity snapshot** (skeleton):

```json
{
  "llm_id": "gpt-5",
  "training_state": "instruction-tuned",
  "gateway": "openai-api-direct",
  "instruction_layer_hash": "sha256:<hash_of_codex_default>",
  "mcp_set": [],
  "skill_set": [],
  "tool_inventory": ["bash", "file_read", "file_write", "edit"],
  "memory_system": {"kind": "session_only"},
  "runtime": {"host": "windows-11", "container": null,
              "network": "unrestricted", "fs_perms": "sandbox-rw"}
}
```

**Purpose**: Cross-LLM-family contrast. Subjects 1-5 share Claude family (and 1-3 share specific model). Adding GPT-based CLI lets us check whether Track A correctly differentiates LLM families (predicted: yes — different training distribution = different fluid reasoning profile).

**Adapter**: A 4th example adapter (Codex/cursor-cli) — not written in interface-adapter-spec.md yet; would be a near-clone of `ClaudeCodeCLIAdapter` with different command + tokenization.

**Inclusion criterion for the v1 pilot**: only include if Subject 6 setup costs < 1 hour. Otherwise defer to v2.

---

## Pilot run order

Recommended run order to minimize cost and maximize early-error detection:

1. Subject 1 (bare API) — cheapest, fastest, validates Track A pipeline.
2. Subject 2 (vanilla CLI) — validates CLI adapter pipeline; differential to Subject 1 reveals scaffolding noise on Track A.
3. Subject 3 (full setup) — validates Track B pipeline on a known subject; differential to Subjects 1, 2 quantifies environment value-add.
4. Subject 4 (Talos) — validates VM adapter and SSH-based endpoint.
5. Subject 5 (Hestia) — validates identity-drift handling and B13 opt-in mode.
6. Subject 6 (if included) — cross-family contrast.

---

## Acceptance for pilot stage

A pilot is considered complete when:

- All 5 mandatory subjects have produced at least 1 trial per applicable dimension (≥1 trial; not the full N=5 — that's a full run, not a pilot).
- Differential block populated for at least one shared-LLM pair (Subject 1-2, 1-3, or 2-3).
- At least one Track B dimension yields a non-N/A score on Subjects 2, 3, 4, 5.
- A comparative report (`pilot-plan.md` §6) is generated comparing the five profiles.

These criteria are loose enough to allow rapid pilot iteration; full evaluation (N=5 per dimension, all dimensions, full procedural pool) is a v1.1 deliverable.
