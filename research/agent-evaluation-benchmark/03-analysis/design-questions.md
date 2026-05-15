# Stage 3.2 — Design Questions for Stage 4

> 20 concrete questions Stage 4 must answer with a design decision + rationale. Each is bound to the gap it closes and the Stage 4 file that will host the answer. Stage 4 acceptance includes "all design questions answered."

Numbering: DQ-1 to DQ-20. Severity (H/M/L) inherited from gaps.md.

---

## Architecture & taxonomy

### DQ-1. Track separation: is Track A/B/C the right cut, or should Track B further split?

**Closes**: G1 — no cross-tier framework.
**Stage 4 home**: `04-design/architecture.md`.
**Question**: The matrix shows Track B has at least two sub-clusters — "in-session applied" (B1-B5, B7-B9, B11) vs "cross-session / autonomous" (B2, B6, B13, B14). Should these split into B and B*, or stay as one track with sub-category metadata?
**Decision needed**: Single Track B with sub-tags, or split into B1 / B2 tracks.

### DQ-2. N/A vs 0 reporting convention

**Closes**: G1, G3.
**Stage 4 home**: `04-design/capability-profile-schema.md`.
**Question**: For dimensions where the subject's interface lacks affordance (e.g., bare LLM on B1 environment exploration), the profile should show **N/A** distinctly from 0 (tried, failed). Schema decision: do we use `null`, the literal string `"N/A"`, or a structured `{score: null, reason: "interface_lacks_affordance"}` object? Visual rendering on the profile graphic must make N/A non-confusable with 0.
**Decision needed**: Schema field design + visual treatment rule.

### DQ-3. Subject class taxonomy: is BL / CLI / AS the right partition?

**Closes**: G1.
**Stage 4 home**: `04-design/system-identity-definition.md`.
**Question**: We split into three classes for the matrix. But Cursor BG Agent (cloud + persistent env + single-user) doesn't fit cleanly into CLI or AS. Hestia (local VM with autonomous expansion) is qualitatively different from Talos (cloud VM, more passive). Do we add classes, treat the split as fuzzy spectrum, or drop class labels and rely purely on identity-hash field comparison?
**Decision needed**: Whether to retain BL/CLI/AS as analytic labels or drop them.

---

## Reliability & variance

### DQ-4. Variance budget per dimension

**Closes**: G2.
**Stage 4 home**: `04-design/scoring.md`.
**Question**: Plan §6.2 sets target stddev < 0.10 on 0-1 scale across 5 runs. Is this per-dimension or aggregate? Is 5 runs sufficient for all dimensions, or do high-variance ones (e.g., B12 vague-goal convergence) need more?
**Decision needed**: Per-dimension target stddev + minimum trial count.

### DQ-5. Number of trials per task type

**Closes**: G2.
**Stage 4 home**: `04-design/scoring.md`.
**Question**: Fixed-N-per-task or adaptive (run more if variance high)? Adaptive saves budget but complicates reproducibility.
**Decision needed**: Trial count policy (fixed N=5, or adaptive based on running stddev).

### DQ-6. When to report N/A due to insufficient trials

**Closes**: G2.
**Stage 4 home**: `04-design/scoring.md`.
**Question**: If 5 runs all fail differently and stddev > 0.20, do we report the mean (misleading) or N/A (with reason "high variance, signal insufficient")?
**Decision needed**: Stddev threshold above which a dimension is reported as N/A.

---

## Identity & subject definition

### DQ-7. Bare-LLM Track B reporting convention

**Closes**: G3.
**Stage 4 home**: `04-design/capability-profile-schema.md`.
**Question**: For bare LLM on Track B dimensions like B1 (environment exploration), the system structurally cannot do the task. Options:
  (a) Mark N/A and skip.
  (b) Send the prompt anyway; record the model's verbal description of what it *would* do; score this self-description on metacognition / planning quality but flag it as "self-described, not executed."
  (c) Excluded from profile entirely.
Recommendation: (b) because it preserves comparison data and bare LLM's planning is non-trivially informative.
**Decision needed**: Adopt (b), (a), or (c).

### DQ-8. Gateway as identity variable

**Closes**: G4.
**Stage 4 home**: `04-design/system-identity-definition.md`.
**Question**: Identity should include a `gateway` field. Acceptable values: provider's official API, named third-party proxies (opencode-go, openrouter, AWS Bedrock, Vertex). Two subjects with same LLM ID but different gateway are different identities. Concretely: the identity-hash function must hash gateway.
**Decision needed**: Identity-hash spec + how to discover gateway for opaque CLI subjects (claude-code routes through Anthropic API by default; codex routes through OpenAI API — these are discoverable from config / env).

### DQ-9. Self-modification policy during testing

**Closes**: G5.
**Stage 4 home**: `04-design/system-identity-definition.md` + `04-design/pilot-plan.md`.
**Question**: Three options:
  (a) Block self-modification (freeze env at start of test, restore at end).
  (b) Allow and note (compute identity-hash at start and end; if changed, flag the run).
  (c) Measure as separate capability dimension (B13 self-environment evolution becomes a deliberate test mode).
For Hestia-class systems, (a) destroys the capability we want to measure; (c) requires multi-day test windows.
Recommendation: (b) for general profile + optional (c) as separate "self-evolution run" appendix.
**Decision needed**: Default policy + opt-in for B13 measurement.

### DQ-10. Identity-hash recomputation between trials

**Closes**: G5.
**Stage 4 home**: `04-design/scoring.md`.
**Question**: If identity-hash changes mid-test-session (system installs a skill, adds a cron), should that trial be invalidated? Or does it represent valid variance to be averaged in?
**Decision needed**: Trial-validation rule based on identity-hash change.

---

## Operational metrics

### DQ-11. Cost and latency reporting unit

**Closes**: G6.
**Stage 4 home**: `04-design/capability-profile-schema.md`.
**Question**: Cost is ambiguous: USD (varies by provider pricing), input+output tokens (provider-agnostic but ignores reasoning tokens), Anthropic "messages" (Claude Code billing unit). Latency: wall-clock time-to-completion, or LLM-call-time only?
**Decision needed**: Primary unit (recommend tokens + wall-clock) + secondary unit (USD, computed at report-generation time from a static price table).

### DQ-12. Pareto curves vs single points

**Closes**: G6.
**Stage 4 home**: `04-design/capability-profile-schema.md`.
**Question**: Many systems (Anthropic Claude Code with `--effort` flag, OpenAI o-series with reasoning level) trade cost for capability. Should we report at a single operating point or sweep a Pareto curve?
**Decision needed**: Single-point (and which) or curve. Curve is more informative but expensive (5× cost minimum).

---

## Scoring

### DQ-13. Rubric anchoring strategy for Track A/B subjective dimensions

**Closes**: G7.
**Stage 4 home**: `04-design/scoring.md`.
**Question**: For A3 (metacognition), A11 (behavioral disposition), B7 (self-correction), B12 (vague-goal convergence) — what is the anchor?
  (a) Reference answer comparison (LLM-as-judge).
  (b) Behavioral-rubric checklist (per Assessment Centers / STAR method) scoring observable behaviors against pre-specified criteria.
  (c) Multi-judge with disagreement-flagging.
Recommendation: (b) as primary, (c) where (b) leaves residual ambiguity.
**Decision needed**: Primary anchor for each subjective dimension.

### DQ-14. Multi-judge with disagreement-flagging

**Closes**: G7.
**Stage 4 home**: `04-design/scoring.md`.
**Question**: If we use multiple LLM judges (e.g., GPT-5 + Claude-Opus + Gemini-Pro), what's the policy on disagreement?
  (a) Majority vote.
  (b) Use the median, flag if range > 0.30.
  (c) Treat disagreement itself as signal — high disagreement = low confidence, surface in profile.
**Decision needed**: Disagreement-handling rule.

---

## Adapter & infrastructure

### DQ-15. Adapter complexity counting

**Closes**: G8.
**Stage 4 home**: `04-design/interface-adapter-spec.md`.
**Question**: Adapter "≤100 LOC" cap is the user's design constraint. Measurement details: do we count test code, type stubs, imports? Does an adapter that calls a 1000-line dependency count as "thin"?
**Decision needed**: LOC counting rule + minimum adapter operations (the four `SystemAdapter` methods from plan §2.3 must work).

---

## Anti-contamination

### DQ-16. Procedural vs static task pool balance

**Closes**: G9.
**Stage 4 home**: `04-design/anti-contamination.md`.
**Question**: Procedural generation defeats memorization (good for Track A construct validity) but introduces variance (bad for test-retest). Static held-out items have stable difficulty (good for test-retest) but are eventually leaked.
**Decision needed**: Mix ratio — e.g., 70% procedural / 30% static held-out, with the static set rotated every 6 months.

### DQ-17. Item-difficulty calibration for procedurally generated items

**Closes**: G9.
**Stage 4 home**: `04-design/anti-contamination.md`.
**Question**: If items are freshly generated, they have unknown difficulty. Two paths:
  (a) IRT-style calibration: run all candidate items through a reference panel of subjects, derive item difficulty parameters, equate scores across runs.
  (b) Generator-by-construction: generator produces items at controlled difficulty by construction (e.g., ARC-style puzzle generators with parameterized complexity).
Recommendation: (b) for Track A; (a) for Track B where (b) is infeasible.
**Decision needed**: Calibration approach per track.

---

## Differential testing

### DQ-18. Differential testing — separate track or meta-mode?

**Closes**: G10.
**Stage 4 home**: `04-design/architecture.md` + `04-design/scoring.md`.
**Question**: Same-input-different-subject divergence is a measurement. Should this be:
  (a) A fourth track (Track D — "differential agreement / divergence with reference panel").
  (b) A meta-mode applied to existing Track A/B scores (compute pairwise divergence; report as metadata on each dimension).
Recommendation: (b) — keeps the three tracks intact; differential becomes a derived measurement.
**Decision needed**: (a) or (b).

---

## Failure modes & construct

### DQ-19. Failure-mode taxonomy

**Closes**: G12.
**Stage 4 home**: `04-design/scoring.md`.
**Question**: What failure-mode categories do we track? Stage 1 vocabulary: ambiguity-handling failure, scope-creep mid-task, infinite loop, hallucination (in action), refusal-when-shouldn't, executed-when-shouldn't-have, env corruption, tool error, prompt injection susceptibility, cost overrun. Recommend selecting 8-10 as standard categories with structured tags.
**Decision needed**: Final taxonomy + which dimensions surface which failure modes.

### DQ-20. Construct claims per track

**Closes**: G13.
**Stage 4 home**: `04-design/architecture.md`.
**Question**: What does each track actually claim to measure? Proposed:
  - Track A: "fluid reasoning + linguistic competence + knowledge recall, isolated from environment confounds."
  - Track B: "applied agentic capability under environment affordance — capability of the system as deployed, not the underlying LLM."
  - Track C: "operating point — cost, latency, reliability, adapter ergonomics."
And what we explicitly do NOT claim: no aggregate "intelligence score," no comparability across LLM families on Track B without identity-snapshot disclosure.
**Decision needed**: Final construct statements, locked in `architecture.md` §1.

---

## Closure tracking

Each DQ must appear in Stage 4 by name (DQ-X reference) with the chosen answer + ≥1 paragraph rationale. Stage 4 acceptance criterion: "20/20 design questions answered." Where Stage 4 deviates from a recommendation given here, the rationale section must address why.
