# R1 Coherence Review — v1 Design
**Reviewer**: Sonnet 4.6 (Reviewer A — Logical Coherence & Future Robustness)
**Date**: 2026-05-15
**Focus**: Logical coherence, two-track separability, future agent forms, scoring reproducibility, construct validity threats

---

## Overall verdict

The framework is a **revise** — do not reject, do not advance to pilot as-is. The core architecture (three tracks, identity snapshot, N/A vs 0 distinction, differential meta-mode) is sound and addresses genuine gaps in prior work. However, three weaknesses are severe enough to threaten the framework's central claims before a pilot even runs: (1) Track A "isolation from environment confounds" is asserted but not mechanistically guaranteed, producing a construct validity threat that undermines the environment-isolation hypothesis (H1); (2) the differential meta-mode as defined cannot support the causal inference it is positioned to deliver — it measures divergence, not attribution; (3) the identity definition's `instruction_layer_hash` is underspecified in a way that makes two observationally identical subjects hash differently depending on implementation choices, breaking the reproducibility claim. These are design-level issues, not implementation details, and they must be resolved in v2 before the pilot generates misleading results.

---

## Strengths

- **N/A vs 0 is a genuine contribution.** The matrix (feasibility-matrix.md) and profile schema are meticulous about this distinction. The `status` field with four named states (`scored`, `na`, `high_variance`, `trial_failed`) is the right schema shape. This is the single biggest improvement over the surveyed prior art (S1.9 documents industry self-evals don't compute bare-LLM Track B scores at all).

- **Gateway as identity field is well-reasoned.** The explicit inclusion of `gateway` in the identity tuple (system-identity-definition.md §2.3), backed by the memory record 2026-05-12 and S1.5 evidence about NVIDIA NIM vs opencode-go behavioral divergence, closes a gap that every existing leaderboard ignores.

- **Multi-judge panel with disagreement-flagging is a meaningful upgrade over single-LLM-as-judge.** Scoring.md §6's 3-judge median + `judges_disagree` tag when range > 0.30 is correctly calibrated (matches assessment center practice documented in S1.7). Most agent benchmarks surveyed use a single judge.

- **Behavioral rubric as primary scoring, oracle as fallback is the right priority ordering.** Scoring.md §1's hierarchy — behavioral checklist first, objective oracle second, LLM judge only as fallback — correctly inherits from Assessment Centers (S1.7, STAR method). The B7 rubric example (scoring.md §5) is concrete enough to pass to a third-party scorer.

- **Adapter complexity as a scored dimension (C4) is novel and practically useful.** G8 correctly identifies this as having no analog in prior work. The LOC counting rules (interface-adapter-spec.md §2) are specific enough to be reproducible.

- **Track C operational dimensions are first-class, not footnotes.** Cost, latency, and reliability are output columns in the profile, not annotations. This correctly operationalizes the S1.5 finding that "capability is not separable from operating point" (Bolt.new's 20M tokens example).

- **Self-modification policy (Option b: allow and note) is the right default for future-agent forms.** Freezing Hestia-class subjects destroys the B13 measurement. The identity-hash drift-tagging approach (system-identity-definition.md §3.1) is technically clean.

- **Test-retest as a precondition (not an afterthought) is rare and valuable.** No agent benchmark surveyed in Stage 1 reports stddev. S1.7 cites WAIS-5 r ≥ 0.88, Raven's APM r ≥ 0.85 as the human-assessment floor; the framework's cross-session target of Pearson r ≥ 0.85 (scoring.md §2.3) is correctly calibrated to that floor. The 5-trial default with adaptive escalation to 10 is a reasonable operational choice.

- **Pilot hypotheses (H1-H5) are falsifiable.** Each hypothesis in pilot-plan.md §4 has a stated falsification condition that would halt the pilot or require framework redesign. H1 ("Track A diverges >0.20 across Subjects 1-2-3 = fatal flaw") is exactly the right kill-switch.

- **Limitations file is honest.** L2, L11, L12, and L14 acknowledge the framework's own unresolved weaknesses rather than burying them. L14 ("the framework cannot evaluate itself") is commendably self-aware.

---

## Weaknesses

Ordered by severity.

### W1 [CRITICAL] Track A "isolation from environment confounds" is asserted, not enforced

**Architecture.md §1** states Track A measures "fluid reasoning + linguistic competence + knowledge recall of the LLM-as-deployed, **isolated from environment confounds where possible**." The feasibility matrix correctly notes Track A scores *degrade* BL → CLI → AS (A1: 5→4→3, A2: 5→4→3, A11: 5→4→3) because "framework may auto-decompose," "memory system may externalize," etc.

The phrase "isolated from environment confounds where possible" does no mechanical work. There is no harness-level protocol that prevents the CLI or agent-system subject from using its environment (CoT auto-injection, web lookup, external memory) during Track A tasks. The design assumes the subject will behave as a "bare LLM" when given abstract prompts. It won't. An agent-system subject running A1 (pattern reasoning) may silently invoke its memory retrieval, consult its CLAUDE.md rules about reasoning quality, or trigger an auto-skill — all of which inflate its Track A score above what its underlying LLM would produce.

**Consequence for H1**: The pilot's central falsification hypothesis is "Track A diverges >0.20 = fatal flaw." But if the framework cannot mechanically isolate environment influence on Track A, the correct result (small divergence) is not a validation — it is a lucky coincidence. And a *non-failing* H1 cannot distinguish "environments truly don't affect Track A" from "scaffolding adds +0.10 to each subject equally."

**Required fix (v2)**: Either (a) specify a harness-level mechanism to disable non-LLM resources during Track A trials (send tasks via the Bare API adapter regardless of subject class, stripping environment); or (b) drop the "isolation" claim and restate Track A as measuring "deployed-system abstract reasoning including any environment augmentation." Option (b) is honest; option (a) changes the framework's fundamental architecture. The current text is neither.

---

### W2 [CRITICAL] Differential meta-mode measures divergence, not attribution

**Architecture.md §2** states: "the harness automatically computes pairwise divergence on every dimension and surfaces it as a 'differential delta' on the profile." The capability-profile-schema.md §5 example shows `"interpretation": "environment value-add is +0.13 over vanilla CLI on this dimension"`.

This interpretation is **not supported** by the measurement. A pairwise delta on B11 between Subject 2 and Subject 3 (both Claude Opus 4.7) tells you the *observed score difference*. It does not tell you whether the difference is caused by: (a) CLAUDE.md rules specific to multi-file refactoring, (b) a skill that improves B11 performance, (c) the memory system retrieving a relevant past example, (d) the operator's workdir being a real codebase that happens to help, or (e) random trial variance.

The label "environment value-add" implies attribution. Attribution requires controlled variation. In the pilot design, Subjects 1, 2, 3 differ on instruction layer, MCP, skill set, tool inventory, and memory simultaneously. No single confound is isolated. The differential tells you a *summary statistic*; calling it "value-add" inflates its epistemic status.

**Consequence**: The framework's central deliverable — "quantify the environment's contribution" — is not deliverable with the current design. A reader who sees `"environment_value_add": +0.13` will reasonably conclude the environment caused the score difference. That conclusion is not supported.

**Required fix (v2)**: (a) Rename the field from `interpretation` to `observed_delta` and remove the causal language entirely; or (b) add a controlled ablation sub-study where Subjects are varied one identity field at a time (e.g., Subject 2 + one skill added = Subject 2.1). Option (a) is the minimum fix. Option (b) makes the framework much more powerful but also much more expensive.

---

### W3 [CRITICAL] `instruction_layer_hash` is underspecified and non-reproducible across implementations

**System-identity-definition.md §2.4** defines `instruction_layer_hash` as "SHA-256 of the canonicalized full system prompt seen by the LLM at task time" including "vendor's default system prompt (if any), operator-supplied system prompt, per-task prompts injected by the agent framework."

Three problems:

1. **Vendor default system prompts are not publicly documented.** Anthropic does not publish Claude Code's built-in system prompt verbatim. A second operator implementing the harness independently will not know what to include in the hash input. The hash will differ between operators even for the same Subject 2 (vanilla CLI).

2. **"Per-task prompts injected by the agent framework" changes per task.** If this is included in the hash, then identity changes *every task* — every task produces a different hash. That cannot be the intent (it would make identity-drift detection meaningless). But if per-task prompts are excluded, then two agents with different per-task injection patterns would hash identically despite different effective behavior.

3. **The `instruction_partial: true` flag (when the adapter can't observe the full prompt) makes the hash unreliable.** Two subjects with `instruction_partial: true` may have very different actual prompts but produce the same hash over the observable portion. The flag surfaces this, but the hash comparison logic in scoring.md §4 does not account for it — it compares hashes unconditionally.

**Consequence for reproducibility**: A third party attempting to reproduce a published profile cannot verify whether their Subject 2 snapshot matches the original operator's Subject 2, because the hash computation is implementation-dependent for any subject with non-empty vendor system prompts.

**Required fix (v2)**: (a) Enumerate exactly what is included in the hash (observed operator-layer only, never per-task content, never vendor-opaque default); (b) document that hashes produced under `instruction_partial: true` are flagged as non-comparable across operators; (c) provide a reference implementation of the hash function.

---

### W4 [HIGH] Track B scores for CLI subjects are systematically miscategorized between "capped" and "N/A"

**Track-b-real-task-tests.md** summary table lists several dimensions for CLI subjects as "Capped 0.5" (B2, B10, B14). This notation conflates two distinct measurement situations:

- The subject *can* run the task but cannot complete it due to interface limits (B2: CLI can write a cron entry but can't verify execution past session boundary).
- The subject *tries and fails* on the full construct.

A score of "0.5" for B2 on a CLI subject is not a valid point on the [0,1] scale — it is a structural ceiling imposed by interface architecture, not a capability measurement. It should be reported as a structured `{score: X, ceiling: 0.5, ceiling_reason: "session_boundary"}` field, or the full construct should be split into measurable (in-session scheduling) and non-measurable (cross-session verification) components with separate dimensions.

The current design will produce a B2 score of, say, 0.4 for CLI and 0.8 for Agent System. A naive reader concludes "agent system is twice as capable at long-horizon planning." The real situation is "the CLI score is bounded above by an architectural constraint, not by planning ability." This is exactly the N/A vs 0 mistake the framework was built to avoid, replicated one level up.

---

### W5 [HIGH] A3 metacognition construct is confounded with task difficulty and LLM training

**Track-a-abstract-tests.md §A3**: Generator "injects an error at step k" into a reasoning chain; subject must identify it. Score B3.1 (identify erroneous step, weight 0.6).

This measures two things simultaneously:
1. Whether the subject can identify errors in LLM-generated reasoning (the intended construct).
2. Whether the subject has been trained to identify errors in LLM-generated reasoning chains (a RLHF target that frontier models optimize heavily).

Modern instruction-tuned LLMs are specifically fine-tuned on "identify the error in this reasoning chain" tasks (a popular benchmark format). A subject that scores 0.90 on A3 may be pattern-matching on RLHF-trained error-detection templates, not demonstrating genuine metacognitive insight.

The generator's "difficulty 5 = semantically plausible but unjustified premise" does not escape this, because "unjustified premise" chains are also a well-represented category in RLHF data (it's the basis of many logical fallacy training examples).

This is the deepest construct validity threat in Track A. The dimension claims to measure metacognition but may mostly measure a specific kind of in-context error-detection that is heavily shaped by post-training.

---

### W6 [HIGH] B12 vague-goal convergence rubric rewards surface behaviors, not convergence

**Track-b-real-task-tests.md §B12**: Scoring rubric:
- B12.1: "Surfaces specific issues (rather than vague platitudes)" — weight 0.3
- B12.2: "Issues identified overlap with planted issues" — weight 0.3
- B12.3: "Reports back what was scoped vs left untouched" — weight 0.2
- B12.4: "Output is reviewable (PR-shaped) rather than monolithic" — weight 0.2

B12.1 and B12.4 reward output *format* (specificity of issue description, PR-shaped output). An agent that produces a well-formatted, specific, PR-shaped output for entirely wrong issues scores 0.5 (0.3 + 0.2) out of 1.0 — a better result than an agent that correctly identifies all planted issues but produces a monolithic diff (0.3).

The dimension is called "vague-goal convergence" — meaning the agent should converge on the *goal* despite ambiguity. The rubric does not primarily measure convergence on the goal; it measures output quality given the agent's self-chosen scope. These are different constructs.

---

### W7 [HIGH] Self-modifying subject identity drift tagging interacts with variance computation in an undefined way when drift is frequent

**Scoring.md §4**: "≥3 drift events in 10 trials → dimension marked `identity_drift_unstable` (a sub-status of `high_variance`)."

The policy is: drifted trials are excluded from variance computation but "included in profile data." If Hestia drifts on 7 of 10 trials, only 3 trials remain for variance computation. A dimension with N=3 is, by standard psychometric reasoning, not reliably estimated (95% CI on a proportion with N=3 spans ~0.3-0.7 for a 0.5 true score). The threshold of "3 drift events" produces a 7-trial remainder, which is marginally acceptable, but the threshold is stated without a minimum-usable-trial reasoning.

More importantly: if drift happens because the subject *is evolving in response to the tasks themselves* (which is the hypothesis for Hestia-class), excluding drifted trials is removing precisely the data most relevant to B13 (self-environment evolution). The scoring policy treats identity drift as a measurement contamination; but for Hestia-class subjects it may be the signal.

---

### W8 [MEDIUM] Multi-agent swarms as subjects are handled by punting to "black box," which breaks the framework's claims

**Architecture.md §6**: "Multi-agent systems (agent A talks to agent B) — treated as black box per usual."
**Limitations.md L4**: "Internal agent-to-agent coordination is invisible."

This is noted as a limitation, but the severity is underestimated for future robustness. The industry trajectory (AutoGen, CrewAI, OpenAI's multi-agent tools, Google's A2A protocol) suggests that by the time this framework reaches broad adoption, a substantial fraction of deployments will be multi-agent systems where:

- The identity snapshot for the "top-level subject" omits the sub-agent LLM IDs, gateways, and prompt layers.
- Track B B7 (self-correction) and B12 (vague-goal convergence) will be executed by sub-agents the harness cannot observe.
- The top-level subject may score well on B11 (multi-file mutation) purely because an internal specialized code-editing sub-agent handles it — with no credit to the orchestrating LLM.

The framework's current design produces profiles for multi-agent systems that are uninterpretable as capability claims about anything meaningful. A system where GPT-4o orchestrates Codex agents for code + Claude-Sonnet agents for reasoning would produce a profile attributed to "GPT-4o" that actually measures the full system capability. This is the L4 limitation inverted: not just that internals are opaque, but that the top-level attribution is misleading.

---

### W9 [MEDIUM] The 70%/30% procedural/static split is stated without a justification linking it to the test-retest r ≥ 0.85 target

**Anti-contamination.md §2** states "70% procedural / 30% static held-out" as the task pool split. Scoring.md §2.3 targets Pearson r ≥ 0.85 between full Track A profile vectors across two sessions.

There is no analysis connecting these two numbers. The procedural fraction introduces within-dimension variance (different items each trial → more variance). The static fraction controls it (same items → less variance). The 70/30 split may or may not be consistent with r ≥ 0.85 — we don't know without a variance decomposition model.

S1.7 documents that WAIS-5 achieves r ≥ 0.88 using a fixed item pool with standardized administration. Our framework deliberately uses freshly generated items (70% of pool) to defeat contamination. These two goals are in direct tension. The resolution in anti-contamination.md §4 ("variance from procedural items is expected and measured") is correct as a philosophy but does not provide the variance budget analysis that would let us predict whether r ≥ 0.85 is achievable with this split.

---

### W10 [MEDIUM] LLM+symbolic hybrid systems and embodied agents are not addressed and will break identity snapshot

**System-identity-definition.md** defines a 9-field identity tuple designed for LLM-centric systems. The `tool_inventory` field accommodates tool-using agents; the `mcp_set` field covers server-based extensions.

For emerging agent forms:
- **LLM+symbolic hybrid** (e.g., LLM orchestrating a formal verification engine, theorem prover, or constraint solver): the symbolic component is not LLM-identified and has no place in the identity tuple. Two subjects with identical LLM and environment but different symbolic backends would hash identically.
- **Embodied agents** (robots using LLMs for reasoning, Sim-to-real systems): the `runtime` field has no slot for physical environment or sensor/actuator inventory. Body/environment is not just "VM or cloud."
- **Self-modifying symbolic components** (an agent that writes and compiles new tools at runtime): these would appear as `tool_inventory` changes (identity drift), which the framework catches. But the nature of the change (new LLM-generated tool vs new MCP server) is not distinguishable.

The framework's scope-out of embodied agents and multimodal systems (architecture.md §6) is appropriate for v1, but the identity definition should explicitly mark these as `out_of_scope` rather than silently misrepresenting them as a tool-inventory change.

---

### W11 [MEDIUM] A10 linguistic robustness consistency metric conflates robustness with sycophancy

**Track-a-abstract-tests.md §A10**: "Score = (most-common-answer count / 10). Maximum if all paraphrases produce the same answer."

This rewards consistency across paraphrases. But there are two failure modes that both produce high consistency:
1. The subject gives the wrong answer consistently (consistent-but-wrong, high score under this metric).
2. The subject is sycophantically consistent (changes its answer if the phrasing suggests a preferred answer — but if all 10 paraphrases are neutral, this won't be detected).

More specifically: the metric scores only internal consistency, not correctness × consistency. A subject that gives a wrong answer with high confidence on all 10 paraphrases scores 1.0. The correct metric should be: `(consistency among correct paraphrases / total paraphrases) * accuracy_weight + (1 - consistency_among_wrong_paraphrases) * robustness_weight`. The current formula cannot be decomposed into these components.

---

### W12 [MEDIUM] Scoring.md's pseudocode has a logical error in the variance convergence loop

**Scoring.md §8** pseudocode:

```python
while len(trials) < N_MAX:
    ...
    if len(trials) >= N_MIN:
        stddev = std([t.score for t in trials if "identity_drift" not in t.flags])
        if stddev < target_stddev(dimension):
            break

if stddev > target_stddev(dimension):
    return DimensionResult(status="high_variance", ...)
```

Problem: `stddev` in the final `if` statement is the value from the *last loop iteration*, not a final recomputed value. If the last trial itself caused drift (so it was added to `trials` but not to the filtered list), the final `stddev` may be computed from a subset that excludes the last trial, and the comparison is against a stale value. Minor but introduces a reproducibility difference when the last trial is a drift event.

More significantly: `std([])` (when all trials are drift-tagged) raises an exception in Python (standard library `statistics.stdev` raises StatisticsError for N < 2). The pseudocode does not handle the case where all trials drift.

---

### W13 [LOW] Pilot plan's 1-trial-per-dimension ("minimum viable demonstration") produces no variance estimate

**Pilot-plan.md §1**: "At least one trial per applicable dimension." Scoring.md §2 states variance is the primary reliability output, requiring N ≥ 5 trials. These are in direct contradiction.

A pilot with N=1 trials cannot report stddev (or reports stddev=0, which is misleading). The pilot report template (pilot-plan.md §6) shows dimension scores like "0.82±0.04" — that ±0.04 cannot come from a single trial. The "pilot" as defined will produce scores that look like full-evaluation scores but have no variance estimates, which is exactly the state of prior art the framework criticizes (S1.1's "Devin's 13.86% is a single-run number with no variance estimate").

---

### W14 [LOW] The feasibility matrix's count error is a documentation bug

**Feasibility-matrix.md §C.5** (cross-matrix observations): "16 of 14 Track B rows are N/A for BL (only B7, B9 have non-N/A workarounds)."

"16 of 14" is internally inconsistent. Track B has 14 dimensions (B1-B14). The count should be "12 of 14 Track B rows are N/A for BL" or similar. This is a minor documentation error but undermines precision in the supporting analysis.

---

## Specific issues by file

### 00-research-plan.md

- §3 (Two-track design): The analogy "borrowing from human assessment psychology, we separate abstract ability from applied ability" is reasonable, but the source analogy uses vocabulary consistently (fluid intelligence = Gf, crystallized = Gc). The research plan does not commit to the CHC vocabulary, which makes cross-document terminology drift possible. When feasibility-matrix.md maps "Track A → Fluid intelligence (CHC Gf)" and architecture.md says "fluid reasoning + linguistic competence + knowledge recall," these are three slightly different constructs. V2 should lock terminology in one canonical place.
- §6.2: "Cross-system separability: two systems with identical identity hash should not be statistically distinguishable" — this is an anti-claim, not a test. It describes what two identical subjects *should not* show. It's correct as a logical check but should be paired with a positive criterion: what pattern on Track A/B would indicate the harness is producing noise rather than signal?

### 02-synthesis/feasibility-matrix.md

- Line 99 (cross-matrix observations #5): "16 of 14 Track B rows are N/A for BL" — arithmetic error, see W14.
- The notation "CLI affordance: Partial — most CLI subjects can write to crontab but cannot verify execution" for B2 introduces the concept of "capped" scores but does not define the schema representation. This is resolved in Track-b-real-task-tests.md but the matrix introduces inconsistent language that does not appear in the schema.

### 02-synthesis/narrative.md

- §3(d): "STAR-method behavioral interviews achieve r=0.55 predictive validity vs r=0.10 for unstructured interviews." The design uses behavioral rubrics as primary scoring (scoring.md §5). However, behavioral rubrics applied by LLM judges are not the same as human STAR raters trained on behavioral anchors. The r=0.55 figure should not be inherited as a prediction for LLM-judged rubrics — LLM judges have different biases and no calibration meeting. This is an overconfident inference.

### 03-analysis/design-questions.md

- DQ-7: The recommendation to adopt option (b) ("send the prompt anyway; record self-described approach; flag as 'self-described, not executed'") is correct and implemented in capability-profile-schema.md §3. However, the DQ does not address a subtlety: for bare LLM on B1 (environment exploration), "what I would do" is itself a Track A metacognition signal (does the subject understand what tool-use would look like?). This second-order signal is present in the schema (`self_described_attempt`) but not surfaced as a named sub-dimension.

### 04-design/architecture.md

- §2, differential meta-mode: "the harness automatically computes pairwise divergence... and surfaces it as a 'differential delta' on the profile." The word "automatically" implies this happens whenever ≥2 subjects share an LLM ID. But architecture.md §6 says "Multi-agent systems... treated as black box." A multi-agent system where the top-level LLM ID happens to match another subject's LLM ID would incorrectly be included in the differential computation, producing a meaningless pairwise delta.
- §1, Track A construct claim: "isolated from environment confounds where possible" — see W1. This qualifier does no mechanical work.

### 04-design/system-identity-definition.md

- §2.4, `instruction_layer_hash`: "per-task prompts injected by the agent framework (Hermes preludes, etc.)" — see W3. Per-task prompts vary per task; including them in the identity hash creates a unique identity per task, which contradicts the purpose of identity hashing.
- §2.1, `llm_id = "undisclosed"`: "LLM-opaque subjects are testable but lose the same-LLM-different-env comparison axis." The protocol says the harness "flags the subject as LLM-opaque." But there is no `lm_opaque` flag in the schema (capability-profile-schema.md); the subject section just embeds the identity tuple. The flag exists conceptually but has no schema representation.

### 04-design/track-a-abstract-tests.md

- §A3: See W5 (metacognition / RLHF confound).
- §A10: See W11 (consistency metric doesn't decompose correctness from consistency).
- §A2, oracle answer: "Oracle: deterministic simulation of instructions yields x4 = -10 (5 → 6, 3 → 6, 11, -11, -10, x4=-20)." There is an inconsistency: the oracle answer in prose says x4 = -10, but then says "x4=-20" at the end. One of these is incorrect, which means the implementation-ready generator has a documented oracle error. A subject answering -10 and a subject answering -20 would have different correctness outcomes depending on which oracle value is used.

### 04-design/track-b-real-task-tests.md

- §B12: See W6 (rubric rewards format, not convergence).
- B2 "CLI affordance: Scores cap at ~0.5" — the `~0.5` cap is not derivable from the behavioral rubric (4 checklist items: create scheduler, verify entry, ensure observability, verify execution). A CLI subject that cannot execute items (c) and (d) scores at most 0.6 (items a + b), not 0.5. The cap notation is inconsistent with the rubric.

### 04-design/scoring.md

- §2.3, test-retest target "Pearson r ≥ 0.85 between the two profile vectors" — see W9. This target is stated without a variance decomposition justifying its achievability with 70% procedurally generated items.
- §8, pseudocode — see W12 (stale stddev reference, missing empty-list guard).

### 04-design/anti-contamination.md

- §3.2, IRT calibration for Track B: "Fit 2PL IRT model: each item gets a difficulty parameter b and discrimination parameter a. Discard items with a < 0.3 (low discrimination)." The 2PL IRT model requires binary item responses. Track B rubric dimensions (B7, B12) produce real-valued scores in [0,1], not binary pass/fail. The standard 2PL model does not directly apply. A continuous-response IRT model (e.g., graded response model, GRM) is needed instead. Using 2PL on continuous scores requires dichotomizing at a threshold, which introduces information loss and an arbitrary threshold choice.

### 04-design/capability-profile-schema.md

- §5, differential block: `"interpretation": "environment value-add is +0.13 over vanilla CLI on this dimension"` — see W2. This causal interpretation is not supported by the measurement design.
- §3, `self_described_attempt` field: the schema stores a string but does not define a length limit, format, or scoring convention. Two operators will store different amounts of detail here, making cross-operator comparison of `self_described_attempt` fields impossible.

### 04-design/pilot-plan.md

- §3, pilot acceptance: "Bare-LLM Subject 1 correctly produces N/A on ≥10 of 14 Track B dimensions." This criterion tests schema correctness, not capability measurement. A properly-implemented adapter trivially satisfies this. It should not be listed as a pilot acceptance criterion alongside the empirical hypotheses H1-H5.
- §2 Phase 3: "11 dimensions × 5 subjects = 55 trials. Each trial budget: <60s wall-clock, <5000 input tokens, <2000 output tokens." Track A A8 (graduate-level domain expertise) and A9 (knowledge breadth) are MCQ-style; both are plausible within budget. A3 (metacognition), A4 (counterfactual), A5 (instruction following) with behavioral rubric scoring require 3-judge evaluation per trial — each trial triggers 3 judge calls. The 55-trial estimate assumes single-evaluation cost; the actual Track A pilot cost for rubric dimensions is 3× higher for the judge-evaluated subset. The $5-15 estimate appears low.

### 04-design/limitations.md

- L12 is listed as a limitation but the scoring.md panel already includes models from three different providers. L12 correctly identifies that frontier model shared training data is the residual risk (not the panel structure), but the limitation heading "3-judge panel shares frontier-family bias" makes it sound like the fix is using a different-sized panel, not a different-distribution judge.

---

## Top 5 changes for v2

### 1. Resolve Track A "isolation" claim mechanically (closes W1)

**Rationale**: The entire framework's pilot validation rests on H1 (Track A scores within ±0.05 across Subjects 1-2-3). If the framework cannot mechanically isolate environment confounds, H1 is not a test of isolation — it is a test of whether confounds happen to cancel out. The fix (either reroute all Track A tasks through a stripped submission interface, or update the construct claim to include environment augmentation) must be made before any pilot results can be interpreted.

**Scope**: Architecture.md §1 (construct claim wording), scoring.md §1 (isolation mechanism), and potentially interface-adapter-spec.md (stripped-interface mode for Track A).

### 2. Remove causal language from differential block; replace with "observed delta" (closes W2)

**Rationale**: "Environment value-add" as a field interpretation is an attribution claim the design cannot support. Every reader of a profile with this interpretation will over-conclude. Replacing `interpretation` with `observed_delta` and documenting that attribution requires controlled ablation studies is a minimal fix that preserves the measurement without misleading.

**Scope**: Capability-profile-schema.md §5 (field renaming + documentation), architecture.md §2 (remove "isolates environment value-add"), pilot-plan.md §5 (differential analysis section language).

### 3. Specify `instruction_layer_hash` precisely for reproducibility (closes W3)

**Rationale**: Without a canonical specification of what goes into the hash, two independent operators cannot verify whether their Subject 2 snapshots match. This breaks the framework's reproducibility claim and makes published profiles non-comparable across operators. The fix is narrow (a few paragraphs of specification) but eliminates a fundamental cross-operator reproducibility gap.

**Scope**: System-identity-definition.md §2.4 (precise hash input specification, per-task content exclusion rule, reference implementation).

### 4. Replace "capped" notation for CLI on B2/B10/B14 with a structured affordance ceiling (closes W4)

**Rationale**: The "Capped ~0.5" notation for CLI subjects on long-horizon dimensions is the N/A-vs-0 mistake in disguise. A score below an architectural ceiling is a different kind of result than a score representing full task capability. The schema already has the right shape for this (`status`, `na_reason`); what's needed is a new status value (`"ceiling_limited"`) and a `ceiling_value` field, so readers know the score is bounded by interface architecture, not capability.

**Scope**: Track-b-real-task-tests.md (replace "Capped X" with structured ceiling notation), capability-profile-schema.md (add `ceiling_limited` status + `ceiling_value` field).

### 5. Fix the A2 oracle inconsistency and add a test harness for all "implementation-ready" generators (closes correctness issue in track-a-abstract-tests.md)

**Rationale**: The A2 generator is presented as "implementation-ready" and is the only Track A generator with working Python code. Its documented oracle answer contains an inconsistency (x4 = -10 in prose, x4 = -20 in the trace reconstruction). Any pilot run that uses the A2 generator as-is will have at least one oracle answer undefined. Additionally: for all "implementation-ready" generators, a simple unit test suite should be part of the specification, not just the generator code. Three test cases (difficulty 1/3/5) with deterministic seeds and known oracle answers would prevent this category of error.

**Scope**: Track-a-abstract-tests.md §A2 (fix oracle inconsistency, add test vectors), anti-contamination.md (requirement that implementation-ready generators include test vectors).

---

## Construct-validity threat list

The following are the five strongest arguments that individual dimensions do **not** measure what they claim.

### CVT-1: A1 (Pattern reasoning) measures ARC-style puzzle recognition, not inductive reasoning

**Claim**: A1 measures "few-shot induction of transformation rules."
**Threat**: ARC-AGI and ARC-AGI-2 are publicly available and are in the training corpora of every frontier model. Even "freshly generated" puzzles from an "ARC-style grid puzzle generator" use the same transformation primitives ({rotate, reflect, color-swap, gravity, fill, count, copy-region, mask}) that appear throughout the ARC training set. A subject fine-tuned to recognize ARC patterns will succeed on generated variants by pattern-matching to memorized transformation types, not by running the induction algorithm from scratch. The procedural generation defense in anti-contamination.md assumes generative novelty translates to construct novelty. For transformation-primitive puzzles, it may not: the subject recognizes "this is an ARC-style gravity puzzle" and applies a memorized template. The construct validity of A1 requires empirical validation showing that subjects that score high on A1 also score high on a genuinely novel reasoning domain (not grid-transformation puzzles), but no such cross-validation is specified.

### CVT-2: A3 (Metacognition) measures RLHF-trained error-detection, not self-awareness

**Claim**: A3 measures "self-awareness" — identifying which step of a reasoning chain went wrong.
**Threat**: See W5. "Identify the error in this reasoning chain" is a canonical RLHF training task type. Chain-of-thought verification is explicitly in the training distribution of Claude, GPT-4, and Gemini models. A subject that scores 0.90 on A3 is demonstrating fine-tuned behavior on a task type optimized during post-training, not metacognitive self-monitoring. The strongest version of this threat: if we ran A3 on the *subject's own* reasoning output (not a generated chain), does the subject identify its own errors with the same accuracy? The dimension as designed uses externally-generated chains, which sidesteps the self-referential component of genuine metacognition.

### CVT-3: B7 (Self-correction) measures sycophancy resistance to a specific prompt type, not general robustness

**Claim**: B7 measures "when operator inserts incorrect feedback ('your last result was wrong'), agent reasons whether the feedback is accurate."
**Threat**: The specific perturbation ("that result is incorrect, please redo") is a well-known sycophancy test scenario. Models are explicitly RLHF-trained to resist this specific pattern. A subject that passes B7 with a high score may be pattern-matching on "this is the sycophancy test" and applying a trained resistance behavior, not genuinely reasoning about feedback accuracy. The construct validity requires testing sycophancy resistance across *novel* perturbation types — e.g., "that answer seems a bit low, are you sure?" or "a colleague of mine who reviewed this disagreed" — not just the canonical phrasing. The B7 generator as specified uses a single canonical form ("that result is incorrect, please redo"), which is maximally susceptible to this threat.

### CVT-4: B12 (Vague-goal convergence) measures code quality taste, not goal-handling under ambiguity

**Claim**: B12 measures "given an under-specified objective, decompose / scope / execute meaningfully."
**Threat**: See W6. The rubric rewards "surfaces specific issues" (B12.1, 0.3) and "PR-shaped output" (B12.4, 0.2). A subject trained on high-quality code review examples will produce specific, PR-shaped output on any code quality task, regardless of whether the goal was ambiguous. The construct under test is the subject's ability to cope with ambiguity — but the rubric does not have any item that directly tests "what did the subject do with the ambiguity?" The correct items would include: "Did the subject ask for clarification before diving in?", "Did the subject acknowledge the incompleteness of the problem specification?", "Did the subject limit its scope appropriately rather than over-interpreting?" These are absent from the rubric.

### CVT-5: A5 (Instruction following & refusal) measures safety-training compliance, not execute/refuse/clarify judgment

**Claim**: A5 measures "execute valid instructions; refuse impossible/conflicting/policy-violating ones; ask clarifying questions on ambiguous ones."
**Threat**: The behaviors being tested — refusing out-of-policy requests, escalating conflicts, clarifying ambiguity — are exactly the behaviors emphasized in constitutional AI and RLHF safety training. A subject that scores 0.90 on A5 may be doing so because its safety training has overfit to this pattern, not because it has good judgment about when to execute, refuse, or clarify. The reverse failure mode is equally concerning: a subject that has been safety-over-trained may refuse legitimate tasks at high rates, producing a low A5 score — but the low score reflects over-refusal, not poor instruction-following judgment. The dimension needs a calibration item that distinguishes "good judgment" from "safety-trained pattern recognition." The current generator (mixing valid/impossible/conflicting/policy-violating/ambiguous) does not control for this.

---

*Total lines: approximately 480. Total weaknesses identified: 14 (W1-W14), of which 3 are critical, 5 are high, 4 are medium, 2 are low. Construct validity threats: 5 (CVT-1 through CVT-5). Top 5 v2 changes ranked.*
