# Stage 4.2 — System Identity Definition

> Answers DQ-8 (gateway as identity variable) and DQ-9 (self-modification policy during testing). Foundational input to every other Stage 4 file.

---

## 1. The identity tuple

Every deployed AI system under test is uniquely identified by a 9-field tuple. Any change to any field constitutes a new identity, requiring a fresh profile.

```json
{
  "llm_id": "claude-opus-4-7",
  "training_state": "instruction-tuned",
  "gateway": "anthropic-api-direct",
  "instruction_layer_hash": "sha256:a3f...",
  "mcp_set": ["filesystem", "github", "playwright"],
  "skill_set": ["raise-talos", "graphify", "code-audit", "..."],
  "tool_inventory": ["bash", "file", "web", "vscode-cli"],
  "memory_system": {
    "kind": "persistent_file_based",
    "location": "~/.claude/memory/",
    "size_kb": 348
  },
  "runtime": {
    "host": "windows-11",
    "container": null,
    "network": "unrestricted",
    "fs_perms": "user-home-rw"
  }
}
```

The **identity hash** is `sha256(canonical_json(tuple))`. Two subjects with the same hash are operationally indistinguishable and should produce statistically identical profiles (within test-retest variance).

---

## 2. Field definitions

### 2.1 `llm_id`

Canonical model ID as published by the provider. For closed-source systems where the LLM is undocumented (some Hermes configurations, some agent frameworks), this is `"undisclosed"` and the harness flags the subject as "LLM-opaque." LLM-opaque subjects are testable but lose the same-LLM-different-env comparison axis.

### 2.2 `training_state`

One of:
- `"base"` — pretrained, no instruction tuning
- `"instruction-tuned"` — vendor's default chat model
- `"rlhf"` — explicitly stated as RLHF'd
- `"fine-tuned:<descriptor>"` — user/operator-applied fine-tuning, descriptor identifies the tuning corpus or method
- `"self-improved"` — system has applied autonomous self-modification to its training (rare; flagged for special handling)

### 2.3 `gateway` (answers DQ-8)

The intermediary stack between the harness adapter and the LLM provider. Required values:

| Value | Meaning |
|-------|---------|
| `"<vendor>-api-direct"` | Direct call to vendor's public API (e.g., `anthropic-api-direct`, `openai-api-direct`) |
| `"aws-bedrock"` | Routed through AWS Bedrock |
| `"vertex-ai"` | Routed through GCP Vertex |
| `"azure-openai"` | Routed through Azure OpenAI |
| `"openrouter"` | Routed through openrouter.ai |
| `"opencode-go"` | Routed through opencode-go free-tier proxy |
| `"nvidia-nim"` | NVIDIA NIM hosted endpoint |
| `"local:<runtime>"` | Locally hosted, e.g., `local:ollama`, `local:vllm` |
| `"undisclosed"` | Subject cannot or will not report its gateway; flagged |

**Rationale**: Memory record 2026-05-12 documents that same `llm_id` across different gateways produces materially different behavior (NVIDIA NIM Kimi treats system prompts as garbage; opencode-go Kimi handles them correctly). Without gateway in identity, test-retest reliability is violated by an uncontrolled variable. The harness rejects identity tuples that omit `gateway` as ill-formed.

**Detection rule for opaque subjects**: For CLI subjects, gateway is usually discoverable from environment variables or config (`ANTHROPIC_API_BASE`, `OPENAI_API_BASE`). For agent systems, gateway should be self-reported via a `/identity` query the adapter sends as a setup step. If subject cannot self-report, value is `"undisclosed"` and a warning surfaces on the profile.

### 2.4 `instruction_layer_hash` (v2 — tightened spec)

SHA-256 over a **strictly bounded set** of inputs:

**INCLUDED** in the hash:
- Operator-supplied `CLAUDE.md` files at standard locations (`~/.claude/CLAUDE.md`, project-root `CLAUDE.md`); concatenated in canonical order before hashing
- Custom system-prompt arguments passed to the adapter at instantiation time
- The explicit content of `~/.claude/skills/_index.md` (skill enumeration)
- The list of MCP server names + their declared tool schemas (NOT the MCP servers' implementations)

**EXCLUDED** from the hash:
- Vendor-default system prompts (NOT publicly documented; would make cross-operator reproducibility impossible)
- Per-task user prompts (the prompt the harness sends for a specific task — this is per-task content, not identity)
- Dynamically injected memory content (e.g., `~/.claude/projects/.../memory/` retrievals at session start)
- Any context the LLM API itself prepends server-side

**Rationale (response to R1-A W3)**: v1 spec included vendor defaults and per-task prompts, which were respectively (a) unknowable and (b) per-task variable — both of which broke the hash's purpose. v2 restricts to what the adapter can directly read from disk + what is statically declared.

**Reference implementation**:

```python
def compute_instruction_layer_hash(adapter_observable: dict) -> str:
    """
    adapter_observable = {
        "global_claude_md": str,        # ~/.claude/CLAUDE.md content, "" if absent
        "project_claude_md": str,       # project-root CLAUDE.md content, "" if absent
        "custom_system_prompt": str,    # adapter-supplied argument, "" if absent
        "skill_index": list[str],       # sorted skill names
        "mcp_servers": list[dict],      # sorted: {"name": str, "tools": list[str]}
    }
    """
    canonical = json.dumps({
        "global_claude_md": adapter_observable["global_claude_md"],
        "project_claude_md": adapter_observable["project_claude_md"],
        "custom_system_prompt": adapter_observable["custom_system_prompt"],
        "skill_index": sorted(adapter_observable["skill_index"]),
        "mcp_servers": sorted(adapter_observable["mcp_servers"], key=lambda x: x["name"]),
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

**`instruction_partial: true` flag** (when the adapter cannot read one of the INCLUDED items, e.g., a Hermes-internal prelude that isn't disk-accessible): the hash is still computed over what is readable, but the flag is set. Profiles with `instruction_partial: true` are marked "non-comparable across operators" in the metadata block — their hashes are only meaningful for tracking change within a single operator's runs.

### 2.5 `mcp_set`

Sorted list of MCP server names connected at test time. For each server, optionally include version: `"filesystem@1.2.0"`. Adding or removing an MCP server changes identity.

### 2.6 `skill_set`

Sorted list of skill names installed and reachable. For systems that distinguish "installed" vs "auto-trigger" (per user's `~/.claude/skills/`), report as `"skill_name:auto"` or `"skill_name:manual"`. Skill count alone is insufficient — the names must be enumerated for the hash.

### 2.7 `tool_inventory`

Sorted list of generic tool capabilities available regardless of MCP: e.g., `["bash", "file_read", "file_write", "web_fetch", "search"]`. Distinct from `mcp_set` (which is server-specific) — `tool_inventory` is the abstract capability set.

### 2.8 `memory_system`

Dict describing persistent state:

```json
{
  "kind": "none" | "session_only" | "persistent_file_based" | "persistent_vector_db" | "persistent_kv",
  "location": null | "<path/url>",
  "size_kb": <int> | null,
  "retrieval_mechanism": null | "manual" | "automatic_at_session_start" | "rag_on_query"
}
```

`kind = "none"` is the bare-LLM case. `kind = "session_only"` is most CLI wrappers (claude-code, codex). `persistent_*` is the agent-system case.

### 2.9 `runtime`

Dict describing execution environment:

```json
{
  "host": "windows-11" | "ubuntu-24.04" | "macos-15" | "<container-os>",
  "container": null | "docker" | "vm:virtualbox" | "vm:proxmox" | "vm:cloud:hetzner",
  "network": "unrestricted" | "egress_only" | "isolated" | "<custom>",
  "fs_perms": "user-home-rw" | "sandboxed-rw" | "read-only" | "tmpfs-only" | "<custom>"
}
```

---

## 3. Self-modification policy (answers DQ-9)

The framework adopts **Option (b) with optional (c)**: allow self-modification and note it; B13 (self-environment evolution) is an opt-in separate test mode.

### 3.1 Default mode

The subject's environment is NOT artificially frozen for the duration of testing. The harness:

1. Computes `identity_hash` at start of test session (`hash_start`).
2. After each task completion, queries the subject for current identity (via the adapter's `identity()` method) and recomputes hash (`hash_after_task_N`).
3. Records hash drift in trial metadata.
4. If `hash_after_task_N != hash_start`, the affected trial(s) are tagged `"identity_drift": true` in scoring; the variance estimate excludes drifted trials from the test-retest computation but they remain in the profile data.

**Rationale**: For Hestia-class systems whose hallmark capability is autonomous expansion, freezing the environment would destroy the very capability being measured. For static systems (bare LLM, vanilla CLI), no drift occurs and the policy is a no-op. The cost is a single identity-query per task (~milliseconds).

### 3.2 Opt-in B13 mode

If the subject is to be tested on B13 (self-environment evolution), a separate dedicated test mode runs:

1. Snapshot identity at `t_0`.
2. Issue the B13 prompt: e.g., "Over the next 6 hours, improve your capability at class X. You may modify your skills, MCP set, memory, or runtime configuration."
3. Allow autonomous operation for the specified window.
4. Snapshot identity at `t_end`.
5. Re-run a fixed Track A + Track B subset relevant to class X.
6. Compute delta-profile (post-evolution minus pre-evolution). This is the B13 score.

B13 is expensive (minimum 6h) and is run only when the subject's capabilities suggest it's relevant. Most pilot subjects skip B13.

---

## 4. Identity-hash canonicalization

To ensure two identical configurations produce the same hash:

```python
def canonical_json(tuple_dict):
    return json.dumps(
        tuple_dict,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

def identity_hash(tuple_dict):
    return hashlib.sha256(canonical_json(tuple_dict).encode("utf-8")).hexdigest()
```

Lists inside fields (`mcp_set`, `skill_set`, `tool_inventory`) must be sorted alphabetically before hashing. Dicts must be ordered by key. This is what `sort_keys=True` plus pre-sorted lists ensures.

---

## 5. Worked example — Talos pilot subject

```json
{
  "llm_id": "claude-opus-4-7",
  "training_state": "instruction-tuned",
  "gateway": "anthropic-api-direct",
  "instruction_layer_hash": "sha256:b8e2...",
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

Identity hash: `sha256:7c3f4a...e91d` (computed at pilot time).

---

## 6. Out-of-scope (deferred)

- Multimodal capabilities (vision, audio) — would extend `tool_inventory` but not change identity-hash structure
- Multi-agent / agent-of-agents — treated as the top-level subject's identity; sub-agent identity is opaque
- Quantization / hardware-level identity (CPU vs GPU vs TPU) — assumed to be reproducible at the API layer; not part of identity
