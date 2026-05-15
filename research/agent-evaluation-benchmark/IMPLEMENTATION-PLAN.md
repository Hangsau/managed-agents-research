# Implementation Plan — Deployed AI System Capability Assessment

> Companion to v3 design lock. v3 is the academic-rigor specification (what the framework would need to look like under peer-review standards). This document is the operational plan for actually building it under realistic constraints (single operator, Opus quota, no external reviewers initially).
>
> **Status**: Plan v1.0 (2026-05-15). Awaiting operator sign-off before Phase A starts.

---

## 1. Strategy: three-tier ladder with hard gates

We commit to a **staged public-release ladder**, not a binary "publish vs internal" choice:

| Tier | What it is | Trigger to enter | Time / Cost |
|------|-----------|------------------|-------------|
| **Phase A** | Internal smoke pilot, 3 subjects, 3 dimensions, PR-based ranking | Operator green-light (this document) | 1 week, ~$15 API |
| **L1** | Open-source harness on GitHub, no leaderboard | Phase A pass gate (§3.4) | 1-2 days |
| **L2** | Public submission portal + normative sample + leaderboard | L1 signal gate (§5.1) | 6-12 months |
| **L3** | Authoritative benchmark with academic / industry partner | L2 traction gate (§6) | Indefinite |

Each tier has hard pass gates. **No tier is entered without its gate firing.** This prevents the "investment ratchet" trap where the next phase feels obligatory because the previous finished.

---

## 2. What we simplify from v3 and why

v3 borrows from psychometrics: test-retest reliability coefficients, multi-judge consensus with inter-rater reliability, IRT difficulty calibration, construct validity claims. These are **the machinery to justify extrapolation** — claiming your score on subject X predicts behavior on similar subjects you didn't test.

For Phase A and L1, we make **no extrapolation claims**. We compare a fixed pool of subjects against each other. The final deliverable in psychometrics is the **percentile rank (PR)** — the validation machinery exists to legitimize PR as extrapolatable. Without extrapolation, PR alone is sufficient.

| v3 machinery | Phase A / L1 replacement | Restore at L2/L3 |
|--------------|--------------------------|------------------|
| Test-retest reliability r ≥ 0.85 with N=5 trials | N=3 runs, report PR rank, flag if rank flips (Kendall's τ) | Yes |
| Multi-judge median (3 LLMs) + Cohen's kappa | Single Sonnet 4.6 judge | Yes |
| IRT difficulty calibration | Static difficulty=3 tasks, one band | Yes |
| Construct validity (convergent + discriminant) | Skipped — name the dimension and proceed | Yes |
| 9-field identity tuple → hash | Keep as version label, not statistical control | Unchanged |
| Procedural task generation + 70/30 held-out | Static 10-task pool per dimension | Yes |
| External expert review | Skipped | Yes (L2 entry blocker) |

**What we do NOT simplify**: identity snapshot (always recorded), per-dimension scoring, differential trio comparison (Subjects 1/2/3 share LLM — the framework's central demonstration).

---

## 3. Phase A — Internal smoke pilot

**Goal**: Answer one question — does the same LLM in different environments produce statistically distinguishable capability profiles?

If yes → framework core claim holds → L1 release warranted.
If no → framework design assumption is wrong → return to v3 for rework before any release.

### 3.1 Scope

| Item | Value |
|------|-------|
| Subjects | 3 (Talos/Hestia deferred to L2 — no Hermes endpoint work needed for Phase A) |
| Subject 1 | Bare Claude API (Opus 4.7, no system prompt, no tools) |
| Subject 2 | Claude Code vanilla (Opus 4.7, no CLAUDE.md, no MCP, no skills) |
| Subject 3 | Claude Code full setup (Opus 4.7, operator's `~/.claude/CLAUDE.md` + MCP + skills + memory) |
| Dimensions | 3 (A1 abstract reasoning, A2 working memory, B1 environment exploration) |
| A1 | Grid-puzzle generator (procedural rules, fixed seed) |
| A2 | Tracking-task generator (n-back style state tracking) |
| B1 | Synthetic filesystem with hidden inconsistencies |
| Trials per task | N=3 |
| Total | 3 subjects × 3 dimensions × 3 trials = 27 trials |
| Judge | Sonnet 4.6, single judge |
| Difficulty | Fixed at 3/5 |
| Task pool | 10 static tasks per dimension |
| Output | JSON profile + PR ranking table per dimension |

### 3.2 Timeline (1 week)

| Day | Work | Who |
|-----|------|-----|
| 1 | `plan-check` (Opus) → implementation list to file/line specificity | Opus 4.7 |
| 2 | `SystemAdapter` Python protocol + 3 adapters | minimax-m2.7 (4 calls, 1 W = 1 file) |
| 3 | 3 task generators (A1 grid, A2 tracking, B1 FS) | minimax-m2.7 (3 calls) |
| 4 | Trial runner + JSON emitter + PR-rank calculator | minimax-m2.7 (1-2 calls) |
| 5 | Scoring rubrics (behavioral anchoring, locked) | **Opus self** — judgment work |
| 6 | Run pilot, collect data | Manual + Sonnet orchestration |
| 7 | Smoke pilot report + L1 gate decision | **Opus self** — synthesis |

### 3.3 Delegation summary

~70% engineering volume → minimax-m2.7 (single-file verbatim spec, no architectural judgment). Opus retains rubric design, prompt template, data interpretation, report writing.

### 3.4 Phase A pass gate (→ proceed to L1 iff all three hold)

1. **Rank stability**: Across 3 runs, PR ranking within each dimension flips at most once (Kendall's τ ≥ 0.67 across runs)
2. **Differentiation signal**: At least 1 dimension shows non-trivial PR spread among subjects (max PR − min PR ≥ 50 percentile points)
3. **Cost discipline**: Total Phase A spend ≤ $30 API + ≤ 2 weeks elapsed time

Any fail → halt L1 plan, return to v3 design for rework.

---

## 4. L1 — Open source release

### 4.1 Trigger
Phase A pass gate (§3.4) fires.

### 4.2 Scope
- Push harness to `managed-agents-research/research/agent-evaluation-benchmark/harness/`
- README: adapter authoring guide, how to run, how to interpret PR
- 3 example adapters from Phase A
- 3 task generators from Phase A
- LICENSE: MIT (decide at L1 entry)
- Disclaimer: `v0.1 — not for cross-organization comparison`

### 4.3 What L1 explicitly does NOT promise
- No leaderboard
- No accepting submissions
- No anti-contamination beyond static pool
- No claim that scores generalize beyond pilot subjects
- No SLA on bug fixes or API stability

### 4.4 Maintenance
- Issues: 7-day best-effort response
- No backwards-compat guarantee until v1.0
- Operator decides version bumps

### 4.5 Effort
1-2 days after Phase A.

---

## 5. L2 — public submission portal (evaluation gate, NOT commitment)

L2 is a 6-12 month full project. **NOT a default next step.** Re-evaluate only when signals appear.

### 5.1 L2 signal gate

L2 evaluation begins (not L2 execution) when **any two** of:

1. **External adapters**: ≥ 5 contributed by non-operator
2. **Substantive engagement**: ≥ 3 Issues/PRs identifying generator bugs, judge bias, or design flaws
3. **Authoritative interest**: AISI / Anthropic eval team / academic group publicly references or uses L1
4. **Operator pull**: framework purpose shifts from "personal tool" to "ecosystem contribution"

Gate fires → start L2 planning (separate document).
Gate does not fire → L1 stays L1 indefinitely. **L1 forever is an acceptable final state.**

### 5.2 What L2 planning would require

1. **Anti-contamination redesign**: procedural generation, 70/30 held-out, quarterly rotation. Without this, leaderboard dies in 12-18 months
2. **Human reviewers**:
   - Psychometrician: reliability claims, power analysis, IRT calibration
   - ML eval engineer: generator collapse, judge prompt leakage, self-selection bias
3. **Authoritative co-signature**: at least one named lab/researcher endorsing. Without this, submissions don't come (chicken-and-egg)
4. **Infrastructure**: hosted submission portal, sandbox execution, identity-snapshot verification, audit trail
5. **Governance**: disputed scores, gaming, vendor pressure, withdrawn submissions

L2 entry restoration of v3 machinery is the bulk of the work — not the infrastructure.

---

## 6. L3 — authoritative benchmark (deferred)

Reached only if L2 has traction. Likely requires academic publication, Anthropic/AISI institutional sponsorship, funded full-time maintainer. Not planned here.

---

## 7. Decisions committed in this plan

These are decisions, not questions. Operator can override before Phase A starts; no override = implementation proceeds with these:

1. **Judge model**: Sonnet 4.6 throughout. Strictly weaker than Subject 1's Opus 4.7, but judge bias affects all subjects equally — doesn't distort rank ordering. Cost-efficient for many judge calls
2. **Identity snapshot date**: Day 1 of Phase A. `~/.claude/skills/_index.md` and `~/.claude/CLAUDE.md` hashed at that moment, frozen for the run
3. **Permission mode**: `bypassPermissions` uniform across Subjects 2 and 3
4. **Code location**: `research/agent-evaluation-benchmark/harness/` inside `managed-agents-research`. Co-located with research artifacts
5. **Judge consistency**: Same Sonnet 4.6 prompt across all subjects and dimensions. Judge prompt locked at Day 5 and not modified mid-pilot
6. **Subject 3 setup snapshot**: Operator's actual `~/.claude/` state on Phase A Day 1, not a curated subset. The whole point is to measure the deployed system as deployed

---

## 8. Acceptance

This plan supersedes v3's `pilot-plan.md` for Phase A scope only. v3 remains authoritative for L2 entry.

Next step on approval: **plan-check (Opus session)** detailing Phase A implementation to file/line specificity, then **implement** per §3.2-3.3 delegation breakdown.
