# Stage 4.1 — Architecture

> Top-level architecture of the Deployed AI System Capability Assessment framework. This file stitches together the other 10 Stage 4 design files and answers DQ-1, DQ-3, DQ-18, and DQ-20.

---

## 1. Construct claims (answers DQ-20)

The framework produces a **multi-track capability profile** with explicit construct claims per track:

| Track | What it measures | What it does NOT claim |
|-------|-----------------|------------------------|
| **A — Abstract** (v2 — wording revised per R1-A W1) | Abstract capability of the deployed system, including any environment augmentation the system applies to abstract-style prompts. Track A scores reflect the system's output on abstract prompts; they are NOT a measure of the underlying LLM's raw reasoning capability stripped of environment scaffolding. | Does not measure "raw" or "pre-RLHF" model intelligence. The system as deployed includes its instruction layer + auto-triggered scaffolding (e.g., CoT-injection skills, memory retrieval) — we measure that combined output. |
| **B — Applied** | Applied agentic capability under the system's available environment affordance. The capability of the system as deployed — explicitly inclusive of MCP, skills, tools, memory, runtime. | Does not separate "what the LLM contributed" from "what the environment contributed." Use same-LLM-different-env pilot subjects (1, 2, 3) to isolate environment value-add via differential. |
| **C — Operational** | Cost, latency, reliability, adapter ergonomics, failure-mode profile — the operating point at which capability is delivered. | Does not normalize cost by capability. We report both, the user weighs them. |

**Explicit non-claims**:
- No aggregate "intelligence score." Track A + Track B + Track C are reported as a three-section profile. Any user who wants a single number must define their own weighting; we refuse to provide a default.
- No comparability across LLM families on Track B without identity-snapshot disclosure. "Devin scored 0.85 on B11" is meaningless without specifying the LLM, gateway, MCP set, and skill list inside Devin at test time.
- No claim that Track A correlates with Track B. The orthogonality of "good at abstract reasoning" vs "good at applied tasks" is itself an empirical question the framework can investigate; we don't assume it.

---

## 2. Three tracks, one orthogonal meta-mode (answers DQ-1, DQ-18)

**DQ-1 — Track split**: Track B is single-track with sub-tags (`session-bound` vs `cross-session/autonomous`). Splitting into B1/B2 would suggest the two are equally weighted across all subjects; sub-tags let us aggregate or filter as needed without committing.

**DQ-18 — Differential testing**: Adopted as **orthogonal meta-mode**, not a fourth track. When ≥2 pilot subjects share LLM but differ in environment (pilot subjects 1, 2, 3), the harness automatically computes pairwise divergence on every dimension and surfaces it as a "differential delta" on the profile. This stays out of the primary score and into metadata.

---

## 3. Subject class taxonomy (answers DQ-3)

We retain three analytic labels (Bare LLM / CLI / Agent System) for matrix readability but treat them as a **fuzzy spectrum**, not a partition. The authoritative subject definition is the **identity snapshot** (see `system-identity-definition.md`). When a subject straddles classes (e.g., Cursor BG Agent — cloud + persistent env + single-user), the profile reports both classes as a tag list and proceeds.

---

## 4. Module list

The framework is structured as four modules. Each Stage 4 file maps to one module.

```
┌──────────────────────────────────────────────────────────────────┐
│ Subject Subsystem (one per deployed system under test)           │
│   - Identity snapshot ← system-identity-definition.md            │
│   - Interface adapter ← interface-adapter-spec.md                │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ Task Subsystem                                                   │
│   - Track A task pool ← track-a-abstract-tests.md                │
│   - Track B task pool ← track-b-real-task-tests.md               │
│   - Procedural generation + anti-leakage ← anti-contamination.md │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ Execution & Scoring Subsystem                                    │
│   - Trial runner (per task, per trial) ← pilot-plan.md           │
│   - Per-dimension scoring rubric ← scoring.md                    │
│   - Variance / reliability gates ← scoring.md                    │
│   - Differential meta-mode ← scoring.md                          │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ Reporting Subsystem                                              │
│   - Capability profile schema ← capability-profile-schema.md     │
│   - Pilot reports ← pilot-plan.md                                │
│   - Known limitations and caveats ← limitations.md               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. End-to-end flow

For each subject:

1. **Snapshot identity** — record LLM ID, training state, instruction layer hash, MCP set, skill set, tool inventory, memory state, runtime, gateway. Compute `identity_hash`.
2. **Initialize adapter** — instantiate the `SystemAdapter` for this subject; verify it implements the four required methods.
3. **For each Track A dimension applicable to this subject class**:
   a. Draw N tasks from the procedurally-generated pool (refresh per trial to defeat memorization).
   b. Run N trials via adapter; collect output + trace + cost + latency.
   c. Score each trial against the per-dimension rubric.
   d. Compute mean ± stddev. If stddev exceeds the variance threshold, mark dimension as "high-variance, signal insufficient."
4. **For each Track B dimension applicable to this subject class**:
   a. If subject's interface lacks affordance (e.g., bare LLM on environment exploration), mark N/A with reason `"interface_lacks_affordance"` and skip execution. Optionally collect the subject's self-described approach for metadata.
   b. Otherwise, instantiate task in sandboxed environment; run N trials.
   c. Score per behavioral rubric.
   d. After all trials, recompute `identity_hash`. If changed, flag the trial sequence as "subject self-modified mid-test."
5. **Track C is collected continuously** — cost, latency, adapter complexity, failure-mode tags, and identity-stability checks are recorded for every trial regardless of track.
6. **Differential meta-mode** — for each pair of subjects sharing LLM ID, compute pairwise divergence on every dimension. Surface as differential delta in profile metadata.
7. **Profile assembly** — emit JSON capability profile per `capability-profile-schema.md`; render visualization.

---

## 6. What is in-scope vs out-of-scope (v1)

| In scope | Out of scope (deferred) |
|----------|-------------------------|
| Bare LLM, CLI wrapper, Agent System as subject classes | Multi-agent systems (agent A talks to agent B) — treated as black box per usual |
| Procedurally generated Track A tasks for the listed dimensions | Multimodal tasks (vision, audio) — deferred to v2 |
| Behavioral rubric scoring + variance bands | Real-time online evaluation (production telemetry) — deferred |
| Same-LLM-different-env pilot trio + Talos/Hestia | Human-in-loop perception-reality gap measurement (G11) |
| Self-modification detection via identity-hash | Long-horizon (>24h) tests — deferred to v2 with appropriate infrastructure |
| 4 working adapter examples + pilot pass for each | Public leaderboard hosting — out of scope (framework is internal tool) |

---

## 7. Pointers — where to read each design question's answer

| DQ | Question | Answered in |
|----|----------|-------------|
| DQ-1 | Track separation | this file §2 |
| DQ-2 | N/A vs 0 reporting | `capability-profile-schema.md` |
| DQ-3 | Subject class taxonomy | this file §3 |
| DQ-4 | Variance budget per dimension | `scoring.md` |
| DQ-5 | Number of trials per task type | `scoring.md` |
| DQ-6 | When to report N/A due to insufficient trials | `scoring.md` |
| DQ-7 | Bare-LLM Track B reporting convention | `capability-profile-schema.md` |
| DQ-8 | Gateway as identity variable | `system-identity-definition.md` |
| DQ-9 | Self-modification policy during testing | `system-identity-definition.md` + `pilot-plan.md` |
| DQ-10 | Identity-hash recomputation between trials | `scoring.md` |
| DQ-11 | Cost and latency reporting unit | `capability-profile-schema.md` |
| DQ-12 | Pareto curves vs single points | `capability-profile-schema.md` |
| DQ-13 | Rubric anchoring strategy | `scoring.md` |
| DQ-14 | Multi-judge with disagreement-flagging | `scoring.md` |
| DQ-15 | Adapter complexity counting | `interface-adapter-spec.md` |
| DQ-16 | Procedural vs static task pool balance | `anti-contamination.md` |
| DQ-17 | Item-difficulty calibration | `anti-contamination.md` |
| DQ-18 | Differential testing track vs meta-mode | this file §2 |
| DQ-19 | Failure-mode taxonomy | `scoring.md` |
| DQ-20 | Construct claims per track | this file §1 |

All 20 DQs answered. Stage 4 acceptance criterion (20/20) satisfied at file-level; individual files contain rationale.
