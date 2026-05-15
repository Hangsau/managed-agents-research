# Stage 3.1 — Gap Analysis

> What existing work (per Stage 1) covers, where it stops short, and where the deployed-system framing forces new territory. Each gap is named, evidenced from Stage 1, and explicitly linked to a Stage 4 design-question that must close it.

---

## G1. No prior framework evaluates bare LLM + CLI + agent system on commensurable axes

**Evidence**: Across S1.1, S1.4, and S1.9, every existing benchmark and eval module operates within one tier of the deployed-system spectrum.

- LLM benchmarks (S1.6: MMLU, ARC-AGI, GSM8K, HumanEval, GPQA) test the bare model. Cannot accommodate environment-using systems without redesign.
- Agent benchmarks (S1.1: SWE-bench, OSWorld, WebArena, TAU-bench) presume an environment. Bare LLM scores 0 or is excluded — not "N/A interface lacks affordance," literally not runnable.
- Framework-built evals (S1.4: LangSmith, AgentEval, CrewAI test) are framework-internal.

**Inspect-AI** (S1.4, S1.6) is the only framework-agnostic exception. It supports plugging in heterogeneous solvers (claude-code, Codex CLI, Gemini CLI) but does not (a) split abstract vs applied capability cleanly, (b) handle bare LLM as a first-class subject distinct from CLI, or (c) report test-retest variance natively.

**Closes**: DQ-1 (track separation), DQ-2 (N/A vs 0 reporting), DQ-3 (subject class taxonomy).

---

## G2. Test-retest reliability is universally absent from agent evaluation

**Evidence**: Of the 13 agent benchmarks in S1.1 and the 10 vendor self-evals in S1.9, **zero** report test-retest reliability. A few (TAU-bench's pass^k metric, Anthropic's 5-run averaging on OSWorld) compute aggregate over multiple trials but never publish stddev. By contrast, every human assessment in S1.7 publishes test-retest as a precondition for validity claims (WAIS-5 r ≥ 0.88, Raven's APM r ≥ 0.85, NEO-PI r ≥ 0.80 over 8 weeks).

**Why it matters**: Without variance estimates, any reported difference between two systems could be sampling noise. Devin's 13.86% on SWE-bench is presented as a fact; whether the true rate is 12-16% or 8-20% is unknown publicly.

**User explicit requirement** ("same system, same test → small variance acceptable") makes this gap non-negotiable for our framework.

**Closes**: DQ-4 (variance budget per dimension), DQ-5 (number of trials per task), DQ-6 (when to report N/A due to insufficient trials).

---

## G3. Bare-LLM scores on Track B are uncomputed, not just unreported

**Evidence**: When papers report SWE-bench numbers, they list models (GPT-4, Claude, Llama) *with* an agent scaffold (SWE-Agent, Devin, etc.). The "bare model SWE-bench" number does not exist in the literature because the model alone cannot interact with a repository. Industry surveys (S1.5, S1.9) similarly compare *configured systems*, not the underlying LLM.

**Why it matters**: Our framework's central claim ("same LLM + different environment = different profile, environment value-add quantified") requires bare-LLM Track B measurement, even if the result is "N/A on most dimensions." Without it, the same-LLM-different-env trio comparison (pilot subjects 1-2-3) cannot be presented.

**Closes**: DQ-7 (bare-LLM Track B reporting convention — silence, N/A, or "self-described attempt").

---

## G4. Same model ID across different gateways is treated as the same model

**Evidence**: Memory record 2026-05-12 and matching observation in S1.5: NVIDIA NIM hosting of Kimi K2 behaves materially differently from opencode-go hosting of the same nominal model ID. System prompt interpretation, refusal calibration, token streaming all diverge.

**Why it matters**: Two pilot subjects could both report LLM = "claude-opus-4-7" but route through different intermediate stacks (Anthropic API direct, AWS Bedrock, Vertex AI, opencode-go proxy). If we treat these as identical identity, test-retest reliability across runs is violated by an uncontrolled variable.

**Existing work**: Vendor model cards (S1.3) name the LLM but rarely the gateway. SWE-bench leaderboards have no gateway field.

**Closes**: DQ-8 (gateway as identity variable).

---

## G5. No protocol exists for testing self-modifying systems

**Evidence**: S1.9's vendor surveys treat all agent systems as static once shipped. Devin's "self-healing" (S1.9), MultiOn's "self-healing capabilities," Hestia's autonomous cron expansion (memory 2026-05-14) violate this assumption. None of S1.1's agent benchmarks have a protocol for what happens if the subject modifies itself between trial 1 and trial 2.

**Implications**: For Hestia-class systems, test-retest reliability is structurally violated unless we freeze the subject. But freezing it eliminates the capability we want to measure (self-improvement). This is a genuine tension, not a measurement bug.

**Closes**: DQ-9 (self-modification policy: freeze, allow-and-note, or measure as separate dimension), DQ-10 (identity-hash recomputation between trials).

---

## G6. Cost and latency are inconsistently first-class axes

**Evidence**: HELM (S1.6) and Cursor's CursorBench (S1.3) treat efficiency as a primary axis. Most other benchmarks (S1.1, S1.9) report cost as a footnote or omit. Devin's annual review (S1.5) emphasizes ACU (Agent Compute Unit) efficiency, but the metric is proprietary and not comparable cross-vendor. Bolt.new's 20M tokens to debug one auth issue (S1.5) is documented in a third-party review, not in vendor materials.

**Why it matters**: A deployed system that solves task X in $0.10 / 12s is operationally different from one that solves it in $80 / 6 hours. Capability is not separable from operating point.

**Closes**: DQ-11 (cost and latency reporting unit), DQ-12 (whether to report Pareto-frontier curves or single points).

---

## G7. Multi-rater consensus is unused in AI benchmarking

**Evidence**: S1.7 documents Assessment Centers' multi-rater consensus achieving inter-rater reliability r = 0.70-0.85, with predictive validity r = 0.55 vs r = 0.10 for unstructured single-rater judgment. STAR-method structured interviews similarly use 2-4 independent raters. No agent benchmark in S1.1 or S1.9 uses multi-rater consensus on subjective scoring (LLM-as-judge is single-LLM-as-judge, not multi-judge with calibration meeting).

**Why it matters**: Track A dimensions A3 (metacognition), A5 (refusal calibration), A11 (behavioral disposition) and Track B B7 (self-correction), B12 (vague-goal convergence) have no automatic ground truth. Without multi-rater consensus or behavioral-rubric anchoring, scoring drifts.

**Closes**: DQ-13 (rubric anchoring strategy), DQ-14 (whether to use multiple LLM-judges with disagreement-flagging).

---

## G8. Adapter complexity has no analog metric in any prior work

**Evidence**: No benchmark in Stage 1 measures or reports "how hard is it to connect this benchmark to a new system." Inspect-AI's external-solver list (Claude Code, Codex CLI, Gemini CLI) implies effort but does not quantify. Vendor framework evals (S1.4) presume their own framework primitives.

**Why this matters**: A deployed system that requires a 500-line adapter to be testable is operationally less useful than one that takes 30 lines. Adapter complexity is a property of the system's interface maturity. It belongs in the profile.

**Risk**: If we score adapter complexity, we might disincentivize support for hard-to-adapt systems (researchers won't bother). Mitigation: report it as metadata, not subtract from score.

**Closes**: DQ-15 (adapter complexity definition and counting rule).

---

## G9. Contamination handling is fragmented and reactive

**Evidence**: GPQA uses canary strings (S1.6). ARC-AGI uses private hold-out (S1.1). Most benchmarks address contamination only after evidence of leakage (MMLU had 6.5% error rate including contamination; MMLU-Pro re-curated). Bloom (S1.3) generates new scenarios per run — the strongest contamination posture, but only for behavioral evals.

**Why it matters**: For Track A dimensions, public ARC-AGI / HumanEval / MMLU sets are likely in the training data of any frontier LLM. Without procedural generation, repeat measurement is dominated by memorization signal.

**But**: procedural generation introduces variance (each run sees different items), which directly fights test-retest reliability (G2). Two opposing design constraints.

**Closes**: DQ-16 (procedural-vs-static task pool balance), DQ-17 (item-difficulty calibration when items are generated fresh).

---

## G10. No prior framework supports differential testing as a primary axis

**Evidence**: Differential testing (S1.8) — "run same input through N implementations, compare divergence" — is well-established in SE for tasks lacking perfect oracles. It is mentioned nowhere in S1.1-S1.6 as an agent-eval primitive. AnthropicEval, OpenAIEval, AgentBench all rely on either oracle (unit tests, exact match) or LLM-as-judge.

**Why it matters**: Our pilot includes same-LLM-different-environment subjects (1, 2, 3) and same-framework-different-deployment subjects (4, 5). Differential testing across these is the natural way to isolate environment contribution. It is also the only way to handle Track B tasks where there is no unique correct answer (vague-goal convergence, environment exploration).

**Closes**: DQ-18 (whether differential testing is a separate Track or a meta-mode applied to existing tracks).

---

## G11. The perception-reality gap is itself an unmeasured capability

**Evidence**: METR's RCT (S1.5) showed developers expecting 24% speedup, perceiving 20% speedup, actually slowing 19%. This is a capability of the **deployed agent + user pair**, not of either alone. No benchmark in Stage 1 measures user-system co-performance under perception bias.

**Stretch goal**: A "with-user vs without-user" comparison axis. For now, out of scope — pilots are agent-only, no human-in-loop measurement. But the gap is real and worth flagging for v2 or future work.

**Closes**: nothing in v1; noted as future work.

---

## G12. Failure-mode profiling is verbal, not structured

**Evidence**: S1.9 documents vendor failure-mode vocabulary: "ambiguous projects" (Devin), "complex interfaces" (OpenAI), "vague requirements" (Cursor), "scope creep mid-task" (Devin). These are useful descriptors but unstructured — cannot be quantified, compared, or accumulated across systems. No benchmark in S1.1 categorizes failure modes systematically.

**Closes**: DQ-19 (taxonomy of failure modes worth tracking + scoring convention).

---

## G13. The construct "intelligence" or "capability" itself is unsettled

**Evidence**: ARC-AGI / Chollet (S1.6): intelligence as skill-acquisition efficiency. HumanEval: functional correctness. MMLU: knowledge recall. GAIA: open-ended task completion. ADEPTS: six user-facing capabilities. MontyCloud: four pillars. CHC theory: three-stratum hierarchy. Each is internally coherent; none agree.

**Implication for our work**: We must explicitly name the construct(s) we target. Stage 4 architecture document should say: "Track A measures fluid reasoning + linguistic competence + knowledge recall. Track B measures applied agentic capability under environment affordance. Track C measures operational efficiency. We do NOT measure a single 'intelligence' value, and reject any user request to collapse the tracks into one."

**Closes**: DQ-20 (construct claims for each track).

---

## Summary table — gap × closing design-question

| Gap | Severity | Closes design questions |
|-----|----------|------------------------|
| G1 — No cross-tier framework | High | DQ-1, DQ-2, DQ-3 |
| G2 — Test-retest unreported | High | DQ-4, DQ-5, DQ-6 |
| G3 — Bare-LLM Track B uncomputed | High | DQ-7 |
| G4 — Gateway as hidden identity | High | DQ-8 |
| G5 — Self-modifying systems unhandled | Medium | DQ-9, DQ-10 |
| G6 — Cost/latency inconsistent | High | DQ-11, DQ-12 |
| G7 — No multi-rater consensus | Medium | DQ-13, DQ-14 |
| G8 — Adapter complexity unmeasured | Medium | DQ-15 |
| G9 — Contamination vs reliability tension | High | DQ-16, DQ-17 |
| G10 — Differential testing absent | Medium | DQ-18 |
| G11 — Perception-reality gap | Low (future) | — |
| G12 — Failure modes unstructured | Medium | DQ-19 |
| G13 — Construct claim unsettled | High | DQ-20 |

20 design questions total, traced back to 12 closing gaps and 1 future-work gap. Each design question maps to a Stage 4 deliverable.
