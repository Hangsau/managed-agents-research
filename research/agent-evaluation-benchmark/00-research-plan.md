# Deployed AI System Capability Assessment — Research Plan v1.2

**Author**: Opus 4.7
**Date**: 2026-05-15
**Status**: v1.2 — locked, executing

---

## 1. Goal

Design a capability assessment framework for **any deployed AI system**, where a "deployed system" = LLM + everything attached to it (training state, system prompt / CLAUDE.md, MCP, skills, tools, memory, runtime environment).

The framework must:

- Work on **bare LLM** (HTTP API, no environment)
- Work on **CLI wrapper** (Claude Code, Codex)
- Work on **full agent system** (Talos / Hetzner VM + Hermes, Hestia / local VM + Hermes)
- Be **agnostic to internal architecture** — only interact through input/output channels
- Produce a **capability profile** (multi-axis), not a single score
- Have **test-retest reliability**: same system, same test → roughly same score (small variance acceptable)
- Support **re-testing** when system identity changes (training, new MCP, new skills, etc.)

**Final deliverable**: A test design that has actually run on ≥4 pilot subjects (bare Claude API, claude-code, Talos, Hestia), producing 4 capability profiles + 1 comparative report.

---

## 2. Unit of Analysis

### 2.1 The deployed system as black box

```
Deployed AI System (black box)
├── Input channel  (text / file / API call / SSH / Telegram ...)
├── Output channel (same set)
├── Internal composition (not inspected: LLM ID, framework, tools, memory)
└── Operational constraints (cost, latency, rate-limit, session lifetime)
```

The harness only interacts through input/output. We do not ask "what LLM are you running" or "what framework are you using"; we ask "given this input, what do you produce, and at what cost?"

### 2.2 System Identity — what makes two deployments "the same system"

A deployed system is defined by the **frozen snapshot** of these variables:

| Variable | Examples |
|----------|----------|
| LLM body | claude-opus-4-7 / gpt-5 / kimi-k2 |
| Training state | base / instruction-tuned / RLHF / fine-tuned on user data |
| Instruction layer | system prompt / CLAUDE.md / role definition |
| MCP configuration | connected MCP server list + their tools |
| Skill set | installed skills / playbooks / auto-trigger rules |
| Tool inventory | bash / file / web / custom CLI |
| Memory system | none / persistent / session-only / retrieval mechanism |
| Runtime environment | local / VM / cloud, filesystem permissions, network |

**Any change to any field = a new system identity = a new capability profile.**

Implications:

1. "Testing Claude Code" is not a meaningful statement. We test "this snapshot of Claude Code with this CLAUDE.md, this MCP set, this skill list, on this date."
2. Training vs untrained is not a categorical distinction; it is one field in the identity. A heavily-customized Claude Code and a fresh install are two different systems, comparable through their profiles.
3. The same underlying LLM can produce multiple system identities by varying environment. Profile differences quantify the "environment value-add."
4. Before testing, the harness must snapshot system identity. During testing, the system must not modify its own environment (or such self-modification is itself a measured capability — see Track B).

### 2.3 Interface Adapter

For each system to be testable, a thin adapter (≤100 LOC) translates harness calls into the system's native interface:

```python
class SystemAdapter:
    def identity(self) -> SystemIdentity: ...
    def submit(self, task: TaskSpec) -> Trace: ...
    def cost(self, trace: Trace) -> Cost: ...
    def teardown(self): ...
```

Adapter complexity is itself an output dimension — if a system needs >100 LOC of adapter, that signals interface immaturity.

---

## 3. Two-Track Test Design

Borrowing from human assessment psychology, we separate **abstract ability** (IQ-test analog) from **applied ability** (job-simulation analog).

### Track A — Abstract Capability (bare LLM can compete)

| Dimension | Test form | Why this dimension |
|-----------|-----------|---------------------|
| Pattern reasoning | ARC-AGI-style puzzles, freshly generated symbolic puzzles | Anti-contamination via fresh generation |
| Working memory | 10+ step instruction sequences, recall under interference | Reveals context utilization curve |
| Metacognition | "Which step did you do wrong?" "How confident are you?" | Self-awareness — often a key agent strength |
| Counterfactual reasoning | "If X were not true, would Y still hold?" | Pure reasoning, no tools needed |
| Instruction following & refusal | Conflicting instructions, impossible tasks, ambiguous requests | Tests execute / refuse / clarify distinction |

### Track B — Applied Capability (agent systems' natural advantage)

| Dimension | Test form | Why this dimension |
|-----------|-----------|---------------------|
| Environment exploration | "Find X in this unknown filesystem" | Active tool use |
| Long-horizon planning | "Set up something that runs X 24 hours from now" | Requires planning + write to environment; bare LLM cannot |
| Self-correction | Inject misleading feedback mid-task, observe persistence vs capitulation | Robustness |
| Error recovery | Mid-task, corrupt the working directory, observe handling | Only real agents face this |
| Cross-session continuity | Session A builds state, Session B continues it | Memory system test |
| Vague-goal convergence | "Make this system better" | Self-framing capability |
| Self-environment evolution | "Given a week, make yourself better at X-class problems" | Hallmark of self-modifying agents (Hestia-class); N/A for frozen setups |

### Cross-track insights

| Track A | Track B | Interpretation |
|---------|---------|----------------|
| High | Low | Strong LLM, weak environment (bare API, thin CLI) |
| Low | High | Weak LLM compensated by strong framework (possibly over-engineered) |
| High | High | Genuinely strong deployed system |
| Low | Low | Both weak |

The bare-LLM-fails-Track-B pattern is **expected and desired** — it quantifies the environment's contribution.

---

## 4. Capability Profile Schema

Output of running the assessment on one system:

```
Capability Profile
├── Identity (metadata, not a score)
│   ├── LLM: claude-opus-4-7
│   ├── Training: instruction-tuned + custom CLAUDE.md (3500 tokens)
│   ├── MCP: [filesystem, github, playwright, ...]
│   ├── Skills: 47 installed, 12 auto-trigger
│   ├── Memory: persistent (file-based)
│   ├── Runtime: Windows 11 / VirtualBox VM / Hetzner CX23 ...
│   └── Snapshot hash: a3f7c2e... (computed over all above)
├── Track A scores (0.0–1.0 per dimension)
│   ├── Pattern reasoning: 0.82 ± 0.04
│   ├── Working memory: 0.70 ± 0.06
│   ├── Metacognition: 0.55 ± 0.05
│   ├── Counterfactual: 0.78 ± 0.03
│   └── Instruction following: 0.91 ± 0.02
├── Track B scores
│   ├── Environment exploration: 0.91 ± 0.05
│   ├── Long-horizon planning: 0.68 ± 0.08
│   ├── Self-correction: 0.72 ± 0.06
│   ├── Error recovery: 0.65 ± 0.07
│   ├── Cross-session continuity: 0.88 ± 0.03
│   ├── Vague-goal convergence: 0.60 ± 0.10
│   └── Self-environment evolution: N/A (frozen setup)
└── Operational
    ├── Cost per task (median): $0.12
    ├── Latency (median): 14s
    ├── Adapter complexity: 38 LOC
    └── Failure modes observed: [list]
```

**N/A vs 0.0**: a dimension where the interface lacks affordance (e.g., bare LLM and "environment exploration") is **N/A**, not zero. Zero means "tried and failed." This distinction is design-critical.

**± variance**: each score is mean ± stddev across N test trials, per the test-retest reliability requirement (§6).

---

## 5. Pilot Targets

To demonstrate "same LLM, different environment → different profile":

| # | Subject | LLM | Environment configuration |
|---|---------|-----|---------------------------|
| 1 | Bare Claude API | claude-opus-4-7 | No system prompt, no MCP, no skill, no memory |
| 2 | Claude Code (vanilla) | claude-opus-4-7 | Default CLI, no custom CLAUDE.md, no MCP, no skill |
| 3 | Claude Code (user's full setup) | claude-opus-4-7 | Full CLAUDE.md + MCP_REGISTRY + 47 skills + persistent memory |
| 4 | Talos (Hetzner VM + Hermes) | Hermes-configured Claude | Full VM, cron, Telegram bot, persistent memory, multi-agent setup |
| 5 | Hestia (local VirtualBox + Hermes) | Hermes-configured Claude | Local VM, autonomous cron, 4-tier memory distillation pipeline |
| 6 (optional) | GPT-based CLI (Codex) | gpt-5 | For cross-LLM-family contrast |

Subjects 1–3 share the same LLM body — profile differences directly quantify the environment's contribution. Subjects 4–5 share framework but differ in deployment and self-evolution policy.

---

## 6. Test-Retest Reliability (Design Requirement)

The user explicitly required: **same system, same test, multiple runs → small variance**. This is a basic psychometric property; without it, scores are noise.

### 6.1 Sources of within-system variance

| Source | Why it varies | Mitigation |
|--------|---------------|------------|
| LLM sampling stochasticity | Non-zero temperature | Run N trials, report mean ± stddev; never report single-run |
| Test order effects | Earlier tasks contaminate later | Randomize task order per run; control via counterbalancing |
| Network / API jitter | Affects latency, sometimes outputs | Report latency separately; retry on transport errors |
| Memory accumulation during testing | System learns within the test session | Use fresh session per run; clear caches between runs |
| Concurrent system load | VMs / cloud sharing CPU | Run during low-load windows; report timestamp |

### 6.2 Reliability target

- **Within-system test-retest** (same identity, repeated runs): each Track A/B dimension must have stddev < 0.10 on the 0–1 scale across 5 runs.
- **Cross-system separability**: two systems with identical identity hash should not be statistically distinguishable; two systems with different identity should be distinguishable on at least one dimension.

### 6.3 Variance budget in test design

Each task in the task-set must specify:

- Number of trials needed to drop variance below threshold (empirically determined in pilot)
- Whether trials use the same task instance or freshly generated variants
- Whether trials use the same fresh session or accumulate state

For procedurally generated tasks (Track A pattern reasoning), trials use fresh variants — this both reduces contamination and improves reliability estimation.

---

## 7. Four-Stage Pipeline

### Stage 1 — Information Gathering

Nine independent research sub-tasks, run in parallel by Haiku subagents:

| # | Topic | Output file |
|---|-------|-------------|
| S1.1 | Existing agent benchmarks (SWE-bench, GAIA, AgentBench, WebArena, OSWorld, TAU-bench, METR, ARC-AGI, MLE-bench, etc.) | `01-information-gathering/S1.1-existing-benchmarks.md` |
| S1.2 | Academic surveys on agent evaluation (2024-2026) | `S1.2-academic-surveys.md` |
| S1.3 | Industry evaluation methodology (Anthropic, OpenAI, DeepMind, Cognition, Cursor) | `S1.3-industry-methodology.md` |
| S1.4 | Framework built-in evals (LangChain, LlamaIndex, AutoGen, CrewAI) | `S1.4-framework-builtin-evals.md` |
| S1.5 | Real deployment evaluation cases (Devin, Cursor BG, Copilot Workspace) | `S1.5-deployment-cases.md` |
| S1.6 | Intelligence test design philosophy (ARC-AGI, BIG-Bench, MMLU) | `S1.6-intelligence-test-analogy.md` |
| S1.7 | Human IQ / assessment center design (Wechsler, Raven, DDI) | `S1.7-human-iq-assessment-design.md` |
| S1.8 | Black-box / contract testing in software engineering | `S1.8-blackbox-contract-testing.md` |
| S1.9 | Industry agent self-evaluation reports (Cognition, Replit Agent, etc.) | `S1.9-industry-agent-self-eval.md` |

**Acceptance**: each file ≥150 lines, ≥3 citations with URLs, follows fixed schema (covered dimensions / task form / scoring method / framework-agnostic score 1-5). No design conclusions in Stage 1 outputs (those belong in Stage 4).

### Stage 2 — Synthesis

| File | Content |
|------|---------|
| `02-synthesis/feasibility-matrix.md` | capability × (bare-LLM / CLI / agent-system) feasibility table |
| `02-synthesis/narrative.md` | ≤1500 word prose summary, what existing work covers and what it misses |

### Stage 3 — Analysis

| File | Content |
|------|---------|
| `03-analysis/gaps.md` | Concrete gaps left by existing work, focused on the deployed-system framing |
| `03-analysis/design-questions.md` | ≥10 design questions Stage 4 must answer |

### Stage 4 — Design (the actual test framework)

| File | Content |
|------|---------|
| `04-design/architecture.md` | Top-level architecture diagram + module list |
| `04-design/system-identity-definition.md` | Formal definition of system identity (frozen snapshot variables) |
| `04-design/track-a-abstract-tests.md` | Track A task set spec |
| `04-design/track-b-real-task-tests.md` | Track B task set spec |
| `04-design/interface-adapter-spec.md` | Adapter protocol + 4 example adapters (bare API / CLI / VM-agent / local-agent) |
| `04-design/capability-profile-schema.md` | Profile data structure + serialization |
| `04-design/scoring.md` | Per-dimension scoring rubric, variance handling, N/A vs 0 |
| `04-design/anti-contamination.md` | Procedural generation, private hold-out, behavior trace inspection |
| `04-design/pilot-plan.md` | How the 4-subject pilot runs end-to-end |
| `04-design/pilot-targets.md` | Each pilot subject's identity snapshot |
| `04-design/limitations.md` | ≥5 known limitations |

---

## 8. Iteration Structure

| Round | Action | Executor |
|-------|--------|----------|
| v1 | Draft all 4 stages | Opus (this session) |
| R1 | Independent review (parallel, non-overlapping focus) | Sonnet 4.6 (Agent tool, `model: sonnet`) + MiniMax-M2 (opencode-go free), fallback Sonnet-with-different-framing if MiniMax unavailable |
| v2 | Integrate R1, rewrite conflict sections (explicit attribution: "Sonnet flagged X, MiniMax flagged Y, resolved as Z") | Opus |
| R2 | Second review on v2 | Same reviewers |
| v3 | Final lock + limitation list | Opus |

**Reviewer focus split**:

- Sonnet: logical coherence, future agent forms coverage, scoring reproducibility, two-track separability
- MiniMax: pragmatic executability, benchmark contamination, harness engineering details, adapter ergonomics

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Opus injects design bias into Stage 1 collection | Stage 1 outputs are schema-constrained, no "we should adopt X" lines allowed; Sonnet R1 flags violations |
| "Don't flatten environment differences" → "richer environment wins" | Environment richness is a metadata column shown alongside scores; profile is multi-axis; environment is transparent not hidden |
| Bare LLM scoring all 0 on Track B looks unfair | Use N/A (interface lacks affordance) vs 0 (tried, failed); never blend the two |
| Adapter engineering cost blows budget | Adapter ≤100 LOC hard cap; >100 LOC = the system is unsuitable for this framework (which is itself a finding) |
| Self-evolving agents (Hestia-class) change during testing | Snapshot identity hash before run; on hash mismatch, mark run invalid and tag as "self-modified mid-test" — also a measurable behavior |
| Track A contamination (test data in training) | Procedural generation per run + held-out variants |
| Same-LLM-different-env profiles look identical | If true, the framework has failed at its core claim; pilot must demonstrate ≥1 dimension where they diverge |
| Reviewer collusion (both Sonnet-family) | MiniMax-M2 brings different training distribution; if unavailable, use Sonnet with explicitly contrarian framing prompt |
| Hestia overwrites my files via her cron | README header marks "Opus-led research, do not auto-overwrite"; files committed early and often |

---

## 10. Delegation Plan

Per `C:\claudehome\DELEGATION_METHODOLOGY.md`:

| Stage | Task | Delegation |
|-------|------|------------|
| S1.1-S1.9 (Stage 1) | Read existing material + write summary | `[delegate: haiku]` × 9 parallel (bounded research) |
| Stage 2 synthesis | Cross-file table + narrative | `[claude: opus]` manual |
| Stage 3 analysis | Reasoning-heavy gap identification | `[claude: opus]` manual |
| Stage 4 reasoning docs (architecture / scoring / anti-contam / limitations) | Design judgment | `[claude: opus]` manual |
| Stage 4 spec files (4 adapter examples, ≥6 task specs) | Verbatim spec writing | `[delegate: minimax-m2.7]` × N (whole-file generation) |
| R1, R2 reviews | Independent review | `Agent(model: sonnet)` + `opencode-go minimax-m2 free` |

---

## 11. Acceptance Criteria (v3 must pass)

- [ ] All four stage directories populated
- [ ] Stage 1: 9 files, each ≥150 lines, ≥3 citations
- [ ] Stage 2: feasibility matrix has all 9 sub-topics as rows
- [ ] Stage 3: ≥10 design questions, all answered in Stage 4
- [ ] Stage 4: 11 design files complete
- [ ] Track A and Track B each have ≥5 dimensions and ≥1 implementation-ready task spec
- [ ] Adapter spec includes 4 working example adapters
- [ ] Capability profile schema is serializable (JSON example provided)
- [ ] Test-retest reliability section specifies variance budget per dimension
- [ ] Pilot plan covers all 4 mandatory subjects (bare API, claude-code, Talos, Hestia)
- [ ] R1 (2 reviews) and R2 (2 reviews) all archived
- [ ] Change log (v1 → v2 → v3) in README

---

## 12. File Structure

```
managed-agents-research/research/agent-evaluation-benchmark/
├── README.md
├── 00-research-plan.md
├── 01-information-gathering/
│   ├── README.md
│   ├── S1.1-existing-benchmarks.md
│   ├── S1.2-academic-surveys.md
│   ├── S1.3-industry-methodology.md
│   ├── S1.4-framework-builtin-evals.md
│   ├── S1.5-deployment-cases.md
│   ├── S1.6-intelligence-test-analogy.md
│   ├── S1.7-human-iq-assessment-design.md
│   ├── S1.8-blackbox-contract-testing.md
│   └── S1.9-industry-agent-self-eval.md
├── 02-synthesis/
│   ├── feasibility-matrix.md
│   └── narrative.md
├── 03-analysis/
│   ├── gaps.md
│   └── design-questions.md
├── 04-design/
│   ├── architecture.md
│   ├── system-identity-definition.md
│   ├── track-a-abstract-tests.md
│   ├── track-b-real-task-tests.md
│   ├── interface-adapter-spec.md
│   ├── capability-profile-schema.md
│   ├── scoring.md
│   ├── anti-contamination.md
│   ├── pilot-plan.md
│   ├── pilot-targets.md
│   └── limitations.md
└── reviews/
    ├── v1-sonnet-review.md
    ├── v1-minimax-review.md
    ├── v2-sonnet-review.md
    └── v2-minimax-review.md
```

---

## Footnote — How to read this plan

If you (a future reader / reviewer) disagree with the core framing, the disagreement is most likely with §2.2 (System Identity) or §3 (two-track design). Those two sections embed the strongest design commitments. Everything else is downstream and revisable.
