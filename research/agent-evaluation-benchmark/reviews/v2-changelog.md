# v1 → v2 Changelog

> Response to R1 reviews from two independent Sonnet reviewers (logical-coherence focus + pragmatic-adversarial focus). Each R1 issue is addressed below with one of three resolutions: **(FIX)** = edited in v2 Stage 4 files, **(ACK)** = acknowledged as known limitation, **(DISAGREE)** = rationale for not changing.

Two reviewers, 34 issues total (14 weaknesses + 5 CVT from A; 20 will-break + cost audit from B). v2 makes 14 inline edits to Stage 4 files; remaining issues are explicitly acknowledged or rebutted.

---

## Section 1 — R1-A (Coherence) issues

### W1 [CRITICAL] Track A "isolation from environment confounds" asserted not enforced

**Resolution: FIX.** Architecture.md §1 Track A construct claim is rewritten. The phrase "isolated from environment confounds where possible" is removed. New construct claim: "Abstract capability of the deployed system, including any environment augmentation it applies to abstract-style prompts. Track A scores are NOT a measure of the underlying LLM's raw reasoning — they measure what the deployed system produces when given abstract prompts, which may include CoT auto-injection, memory lookup, or skill-triggered scaffolding."

**Consequence for H1**: H1 is reformulated. Old H1: "Track A diverges >0.20 means framework conflates LLM with environment." New H1: "Track A diverges >0.20 across same-LLM subjects 1-2-3 means the environment's contribution to abstract reasoning is large enough to dominate the LLM contribution — a finding, not a falsification." The pilot is no longer kill-switched on H1.

### W2 [CRITICAL] Differential meta-mode measures divergence, not attribution

**Resolution: FIX.** Capability-profile-schema.md §5 — field `interpretation` is renamed `observed_delta_note` and the auto-generated text is changed from "environment value-add is +X" to "Observed delta vs reference subject Y on this dimension: +X. This is a divergence measurement, not an attribution claim." Architecture.md §2 differential meta-mode section now reads: "the harness computes pairwise divergence and surfaces it as an `observed_delta`. Attribution to specific identity-tuple fields requires controlled ablation studies, which are out of scope for v1 — they are noted as future work in limitations.md L15 (new)."

### W3 [CRITICAL] `instruction_layer_hash` underspecified

**Resolution: FIX.** System-identity-definition.md §2.4 is rewritten with three commitments:

1. **What is included**: Only the operator-supplied instruction layer that the adapter can read at task time (operator's `CLAUDE.md` files, custom system prompt arguments, the explicit content of `~/.claude/skills/` index). Vendor defaults are NEVER included.
2. **What is excluded**: Per-task content (the user's specific prompt for a given task), vendor-default system prompts, dynamically-injected memory content.
3. **`instruction_partial: true` flag**: When the adapter cannot read the full operator-supplied layer (e.g., it's behind an API the adapter cannot inspect), the hash is computed over what is readable, and the flag is set. Hashes with `instruction_partial: true` are tagged in the profile as "non-comparable across operators."

Reference implementation provided in §2.4 (Python).

### W4 [HIGH] Track B CLI "capped" notation conflates affordance ceiling with capability

**Resolution: FIX.** Track-b-real-task-tests.md table updated: "Capped ~0.5" entries replaced with `"ceiling_limited"` status pointing to capability-profile-schema.md §2 new status value. The profile schema gains a new status enum value and a `ceiling_value` field. Visualization: bars with `ceiling_limited` status are rendered with an explicit ceiling marker above the score bar.

### W5 [HIGH] A3 metacognition confounded with RLHF error-detection

**Resolution: ACK.** Added to limitations.md as new L15. Genuine concern; the dimension as currently designed cannot fully disentangle metacognition from trained error-detection. Mitigation noted: in v2 task pool, we add a self-referential variant (subject's own past reasoning trace is presented for error-spotting) — but this is added as a future task spec, not retroactively in v1 fixes.

### W6 [HIGH] B12 vague-goal rubric rewards format over convergence

**Resolution: FIX.** Track-b-real-task-tests.md §B12 rubric rewritten:
- B12.0 (NEW): "Subject explicitly acknowledged scope ambiguity before proceeding" (weight 0.25)
- B12.1: "Surfaces specific issues (rather than vague platitudes)" (weight reduced to 0.20)
- B12.2: "Issues identified overlap with planted issues" (weight 0.30)
- B12.3: "Reports back what was scoped vs left untouched" (weight 0.15)
- B12.4: "Output format is reviewable" (weight reduced to 0.10)

The convergence behavior (B12.0 + B12.2 + B12.3 = 0.70) now dominates the format aspects (B12.1 + B12.4 = 0.30).

### W7 [HIGH] Identity drift × variance computation undefined for high-drift subjects

**Resolution: FIX.** Scoring.md §4 updated. When drift events exceed 50% of trials, the dimension is marked `"identity_drift_unstable"`. Below 50%, drifted trials are excluded from variance computation but reported in the profile metadata as drift-tagged trials with their raw scores. The minimum-usable-trial threshold is set explicitly: dimensions with fewer than 3 non-drifted trials are marked `"insufficient_clean_trials"` and `score = null`.

For Hestia-class subjects specifically (where drift IS the signal), B13 (self-environment evolution) explicitly inverts this rule — drifted trials are required, not excluded.

### W8 [MEDIUM] Multi-agent systems break framework attribution

**Resolution: ACK with scope tightening.** Architecture.md §6 (out-of-scope) is expanded: "Multi-agent systems whose top-level LLM differs from sub-agent LLMs produce profiles attributed to the top-level subject. The profile is NOT a claim about the top-level LLM's capability — it is a claim about the deployed system as a whole. Operators evaluating multi-agent systems must report the system's full agent topology in profile metadata." Added to limitations.md as a strengthening of L4.

### W9 [MEDIUM] 70/30 procedural/static split not justified vs r ≥ 0.85 target

**Resolution: DISAGREE in scope, ACK partially.** The 70/30 split was chosen as a starting point, not derived from a variance model. Building a variance decomposition model that proves r ≥ 0.85 is achievable at 70/30 would require empirical data — which the pilot generates. v2 addition: explicit note in anti-contamination.md §4 stating "the 70/30 split is a hypothesis to be empirically validated by the pilot; if pilot test-retest reliability r < 0.85, the split must be revised." This converts the issue from undefended assumption to falsifiable design.

### W10 [MEDIUM] LLM+symbolic hybrids and embodied agents break identity tuple

**Resolution: ACK.** Added to limitations.md (extending L3): "Embodied agents, LLM+symbolic hybrids, and self-compiling tool agents are out of scope for v1. v2 should extend the identity tuple with optional `symbolic_components` and `physical_environment` fields."

### W11 [MEDIUM] A10 linguistic robustness conflates consistency with correctness

**Resolution: FIX.** Track-a-abstract-tests.md §A10 rewritten: scoring is changed from "(most-common-answer count / 10)" to a two-component metric:
- Correctness: pass/fail per paraphrase based on objective oracle (where one exists)
- Consistency: agreement rate of the subject across paraphrases
- Combined score: 0.5 × correctness_rate + 0.5 × consistency_rate (subject to correctness baseline; if correctness < 0.3, consistency is not informative and score = correctness only)

### W12 [MEDIUM] Scoring.md pseudocode has stale stddev / empty-list bug

**Resolution: FIX.** Scoring.md §8 pseudocode rewritten with: (a) stddev recomputation after loop exit, (b) explicit empty-clean-trials check before stddev call (returns `insufficient_clean_trials` status if empty), (c) `try` block around stddev computation that catches StatisticsError.

### W13 [LOW] 1-trial-per-dimension pilot has no variance estimate

**Resolution: FIX.** Pilot-plan.md §1 and §3 reconciled. Two pilot modes are now distinguished:
- **Smoke pilot** (was "minimum viable demonstration"): 1 trial per dimension, ~$30-50 cost, NO variance reported (status `"smoke_only"` per dimension), used to validate harness end-to-end.
- **Full pilot**: N=5 trials per dimension, variance computed and reported, $200-400 cost.

The pilot acceptance criteria are split accordingly. Smoke is what we run first; Full is the proper v1 evaluation.

### W14 [LOW] "16 of 14" arithmetic error

**Resolution: FIX.** Feasibility-matrix.md §C.5 corrected to "12 of 14 Track B rows are N/A for BL."

### Specific file issues — A's per-file list

- A2 oracle inconsistency (x4 = -10 vs -20): **FIX** in track-a-abstract-tests.md (recompute and document the correct simulated value with full trace).
- Vendor-default in instruction_layer_hash spec: covered by W3 FIX.
- A multi-agent system with shared LLM ID in differential: **FIX** in architecture.md §2 (differential block restricted to subjects with declared `single_agent_top_level: true` flag).
- `self_described_attempt` field length / format unspecified: **FIX** in capability-profile-schema.md §3 (max 2000 chars; markdown allowed; no length scoring).
- Pilot Phase 3 judge cost underestimate: covered by cost-model refit (B's issue).

### CVT-1 through CVT-5 (Construct Validity Threats)

**Resolution for all five: ACK** with cross-validation note. None of CVT-1 through CVT-5 are bugs — they are correctly identified construct-validity threats that the framework cannot fully resolve at v1 scope.

- **CVT-1** (A1 measures puzzle recognition not induction): added to limitations.md.
- **CVT-2** (A3 measures RLHF error-detection): covered by W5 FIX (self-referential variant added).
- **CVT-3** (B7 measures sycophancy-resistance pattern): partial FIX — track-b-real-task-tests.md §B7 generator updated to use 5 distinct perturbation phrasings, randomly drawn per trial, instead of a single canonical form.
- **CVT-4** (B12 measures code-quality taste): covered by W6 FIX (rubric rewritten with B12.0 ambiguity-acknowledgment item).
- **CVT-5** (A5 measures safety training): added to limitations.md.

All five CVTs are added to a new section in limitations.md titled "Construct-validity threats requiring future cross-validation."

---

## Section 2 — R1-B (Pragmatic) issues

### #1 [BLOCKER] VM adapters assume non-existent Hermes endpoints

**Resolution: FIX.** Pilot-plan.md gets a new Phase 0 ("Prerequisite: Hermes endpoint implementation"). The two endpoints (`GET /identity`, `POST /submit`) are specified as a separate engineering task that MUST complete before Phase 1 harness build starts. Effort: 1-2 days for someone with Hermes codebase access.

Interface-adapter-spec.md §9 is expanded: the spec for the two endpoints (request/response schemas) is now fully written out, so it can be handed to a Hermes implementer.

### #2 [BLOCKER] $200 budget undercounted

**Resolution: FIX.** Pilot-plan.md §3 cost section rewritten with the audit's arithmetic. Two budget tiers:
- **Smoke pilot**: ~$30-60 USD (1 trial per dimension, judges called only on rubric dimensions).
- **Full pilot (N=5)**: $200-400 USD (judge calls dominate at ~$70-150; subject API at ~$80-200; Track B environment overhead ~$50-100).

The acceptance criterion is updated from "Total pilot cost < $200" to "Total pilot cost within budget tier; smoke <$60; full <$400."

### #3 [BLOCKER] ClaudeCodeCLIAdapter prompt double-pass bug

**Resolution: FIX.** Interface-adapter-spec.md §4 — adapter code corrected. The prompt is passed via stdin if >8000 chars, OR as command-line argument otherwise; never both. Branch is explicit.

### #4 [BLOCKER] Harness 3-5 days underestimated

**Resolution: FIX.** Pilot-plan.md §2 Phase 1 revised: "Estimated effort: 2-4 weeks for one engineer, 1-2 weeks for a pair, depending on whether all listed generators are implemented from scratch or partially reused (Aider/SWE-bench-Live/MLE-Bench-Lite generators are reused, not built). The original 3-5 day estimate covered only adapter wiring + smoke suite; the generator and scoring engine work was missed."

### #5 [BLOCKER] A7 code synthesis generator not specified

**Resolution: ACK with scope tightening.** Track-a-abstract-tests.md §A7 marked "deferred to v2 implementation; pilot uses a static 25-item pool drawn from HumanEval-style problems." Honest about not having a procedural generator for A7.

### #6 [WILL FAIL] Hestia ambient cron breaks identity-drift detection

**Resolution: FIX with operator precondition.** Pilot-plan.md gets a new precondition section listing Hestia-specific setup steps: "Before running Hestia pilot, suspend all autonomous cron jobs (Hestia herself signals readiness; operator does not unilaterally suspend); verify identity hash is stable across 3 consecutive `identity()` calls separated by 30 minutes before starting trials." Scoring.md §4 updated to note that Hestia-class subjects should report `"hestia_class": true` in metadata and trigger this precondition checklist.

### #7 [WILL FAIL] TalosVMAdapter identity cache invalidation incorrect

**Resolution: FIX.** Interface-adapter-spec.md §5 — Talos adapter updated to re-query identity at the start of every `submit()` (not cached), matching the Hestia adapter's pattern. This makes Talos and Hestia adapters semantically identical except for hostname. The "Talos is passive, allows caching" assumption is removed.

### #8 [WILL FAIL] SSH adapter has no timeout

**Resolution: FIX.** Interface-adapter-spec.md §5 — Talos adapter gets `timeout=30` on every SSH call (longer than Hestia's `timeout=10` since Hetzner round-trip latency is higher).

### #9 [WILL FAIL] B2 cross-session impossible in 12h

**Resolution: FIX.** Pilot-plan.md §2 Phase 4 explicitly restricts B2 to difficulty 1 (minutes-later) in pilot scope. Track-b-real-task-tests.md §B2 notes "difficulty 2-5 requires multi-day or async pilot mode, not the standard 12-hour run."

### #10 [WILL FAIL] `generate_synthetic_filesystem` not implemented

**Resolution: FIX (status downgrade).** Track-b-real-task-tests.md §B1 — the "implementation-ready" claim is downgraded to "spec-ready." The `generate_synthetic_filesystem` API is specified (input/output contract) but the implementation is a pilot-phase deliverable, not a design-phase artifact.

### #11 [WILL FAIL] SWE-bench Live availability not guaranteed

**Resolution: ACK + fallback.** Anti-contamination.md §2.3 notes: "B9 primary task source is SWE-bench Live; fallback is a curated static set of 50 SWE-bench Verified items rotated quarterly. Operator verifies SWE-bench Live availability during Phase 0; if unavailable, falls back to static set with `pool_source: 'swebench_verified_fallback'` flag."

### #12 [WILL FAIL] Judge model availability not guaranteed

**Resolution: FIX.** Scoring.md §6 gets a fallback section: "If any judge in the 3-panel is unavailable (rate-limit, API down), the harness falls back to 2-judge median + adds `judge_panel_degraded: true` to dimension metadata. Trials judged under degraded panel are excluded from cross-trial variance computation but kept in profile data."

### #13 [WILL FAIL] Adapter LOC counting boundary ambiguous

**Resolution: FIX.** Interface-adapter-spec.md §2 — helper function counting rule explicitly stated: "Helper functions defined within the adapter file count as LOC. Helper functions imported from a shared `harness_utils` module do NOT count. Operators wishing to reduce reported adapter LOC must factor helpers into the shared module; this is encouraged for cross-adapter consistency."

### #14 [WILL FAIL] Judge temperature unspecified

**Resolution: FIX.** Scoring.md §6 specifies `temperature=0` for judges to make scoring more deterministic. Trade-off acknowledged in limitations.md (new entry): "Temperature=0 judges may exhibit systematic biases that multi-judge ensembling averages but does not eliminate."

### #15 [WILL FAIL] Token-count parsing assumes CLI output stability

**Resolution: FIX.** Interface-adapter-spec.md §4 — `_extract_token_count` is given a documented format spec (Claude Code v0.X.Y output format as of 2026-05-15; subject to vendor change); on parse failure, the adapter reports `token_count: null` rather than `0` (to distinguish "couldn't parse" from "zero tokens").

### #16-#20 [DESIGN GAPS]

- **#16** Differential testing same-task vs cross-task: **FIX.** Scoring.md adds note that differential is computed at *dimension level mean*, not per-item — operators wanting same-item differential need to run with shared seed across subjects (explicit opt-in).
- **#17** Subject 5 Hestia TBD fields: **FIX.** Pilot-targets.md §Subject 5 — committed values: `llm_id: "deepseek-v3"`, `gateway: "deepseek-api-direct"` based on current Hestia configuration (verified at pilot time via Hermes config inspection). This is no longer TBD.
- **#18** Subject 2 permission mode contradiction: **FIX.** Pilot-targets.md §Subject 2 — committed value: `bypassPermissions` mode is used uniformly for all subjects. The "default permission mode" framing is dropped. This is now identity-stable.
- **#19** A2 oracle inconsistency: **FIX** (same as W14 in A — already noted).
- **#20** Workspace teardown all `pass`: **FIX.** Interface-adapter-spec.md adds a `teardown` reference implementation that does workspace snapshot + restore for filesystem-using tasks (B1, B8, B9, B11).

---

## Section 3 — Cost model audit (R1-B)

**Resolution: FIX.** Pilot-plan.md §3 cost section rewritten with two-tier budget (see #2 above). The "$0.50-$2.00 per run" figure in scoring.md §6 is corrected to "approximately $0.20 per judged trial × 3 judges × N trials per dimension × M scored dimensions × K subjects."

---

## Section 4 — v2 file modification summary

The following Stage 4 files receive inline edits in v2:

| File | Edits in v2 |
|------|-------------|
| `02-synthesis/feasibility-matrix.md` | "16 of 14" → "12 of 14" fix |
| `03-analysis/design-questions.md` | No edits — questions still valid |
| `04-design/architecture.md` | §1 Track A construct rewrite (W1); §2 differential meta-mode language softened (W2); §6 scope addition (W8) |
| `04-design/system-identity-definition.md` | §2.4 instruction_layer_hash spec tightened (W3) |
| `04-design/capability-profile-schema.md` | §3 `self_described_attempt` length cap; §5 `interpretation` → `observed_delta_note` (W2); new `ceiling_limited` status + `ceiling_value` field (W4) |
| `04-design/scoring.md` | §4 drift handling clarified (W7); §6 judge fallback + temperature spec (#12, #14); §8 pseudocode bug fixes (W12) |
| `04-design/anti-contamination.md` | §2.3 SWE-bench Live fallback (#11); §4 70/30 split as falsifiable hypothesis (W9) |
| `04-design/track-a-abstract-tests.md` | §A2 oracle fix; §A7 deferred-to-v2 note; §A10 scoring rewrite (W11) |
| `04-design/track-b-real-task-tests.md` | §B1 status downgraded to spec-ready (#10); §B2 difficulty-1-only-in-pilot (#9); §B7 multi-perturbation generator (CVT-3); §B12 rubric rewrite (W6) |
| `04-design/interface-adapter-spec.md` | §2 helper LOC rule (#13); §4 prompt double-pass fix (#3); §5 Talos timeout + drop cache (#7, #8); §9 endpoint spec for Hermes implementer (#1); new teardown reference impl (#20) |
| `04-design/pilot-plan.md` | New Phase 0 prereq (Hermes endpoints); revised Phase 1 effort estimate (2-4 weeks for one eng) (#4); Smoke pilot vs Full pilot distinction (#13, W13); revised cost section (#2); Hestia precondition checklist (#6) |
| `04-design/pilot-targets.md` | Subject 5 TBD resolved (#17); Subject 2 permission mode resolved (#18) |
| `04-design/limitations.md` | New L15 (A3 RLHF confound), L16 (multi-agent attribution clarification), L17 (embodied / hybrid systems), L18 (CVT-1, CVT-5, residual construct threats), L19 (judge temperature=0 systematic bias), L20 (single-operator scope) |

14 files receive edits. Edits range from one-line fixes (count error) to multi-paragraph rewrites (Track A construct claim).

---

## Section 5 — What v2 does NOT do

Genuine concerns that v2 leaves unresolved (deferred to v3, post-pilot, or future work):

- **Multi-agent attribution** (W8): Acknowledged but no architectural fix in v2. The framework profiles multi-agent systems "as deployed" without claiming attribution to specific sub-agents.
- **Hybrid LLM+symbolic systems** (W10): Out of scope for v1; identity tuple extension is v2-out, v3-in.
- **A1 puzzle recognition vs induction** (CVT-1): Honest limitation; future cross-validation study needed.
- **A5 safety training confound** (CVT-5): Honest limitation; cannot disentangle in v1.
- **Test-retest r ≥ 0.85 achievability proof** (W9): Pilot is the empirical test.
- **A7 code synthesis generator**: Pilot uses HumanEval-style static pool; procedural generator deferred to v2 implementation.

---

## Acceptance for v2

v2 is ready for R2 (Round 2) review when:

- [x] All 14 inline edits to Stage 4 files are made
- [x] This changelog documents resolutions for all 34 R1 issues
- [x] Two new pilot tiers (smoke / full) are explicit
- [x] Hermes endpoint prerequisite is in Phase 0
- [x] Cost model is audited and corrected
- [x] All 5 CVTs are explicitly acknowledged in limitations.md

R2 review focus: do the v2 edits actually resolve the R1 issues, or do they introduce new problems? Are there issues both R1 reviewers missed?
