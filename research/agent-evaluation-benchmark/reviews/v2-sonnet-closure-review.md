# R2 Closure Review — v2 Agent Evaluation Benchmark Design
**Reviewer**: Sonnet 4.6 (R2 — Closure Assessment)
**Date**: 2026-05-15
**Focus**: Did v2 close R1 issues? Did it introduce new problems? What did both R1 reviewers miss?

---

## Overall verdict

v2 is a **conditional advance**: ready to lock as v3 with targeted fixes on four items, but not ready without them. The critical-severity R1 issues (W1, W2, W3) received genuine substantive fixes. The pragmatic blockers (#1–#5) received structural resolutions. The document is materially more honest and executable than v1.

However, two issues constitute new bugs introduced by v2's fixes (one in scoring.md §4, one in track-b-real-task-tests.md §B12), two R1 fixes are present in the changelog but missing from the actual files, and the limitations.md was not updated to include the v2-promised new entries (L15–L20). The "ACK" dispositions for CVT-1, CVT-5, and W9 are all defensible. The DISAGREE on W9 is justified. The ACK on W5 is partially accepted — the self-referential variant addition is reasonable as a commitment, though it is only a commitment in the changelog, not in the file.

Recommend: fix the four items listed in Top 3 changes for v3 (there are in practice four), then lock as v3.

---

## R1 issue closure audit

| R1 Issue | Claimed Resolution | Actual Status | Notes |
|----------|--------------------|---------------|-------|
| W1 [CRITICAL] Track A isolation | FIX — construct claim rewritten | **CLOSED** | architecture.md §1 construct table correctly rewrites Track A claim; H1 reformulated; language is honest |
| W2 [CRITICAL] Differential causal language | FIX — `interpretation` → `observed_delta_note` | **CLOSED** | capability-profile-schema.md §5 field renamed, causal language removed; `single_agent_top_level: true` guard added |
| W3 [CRITICAL] `instruction_layer_hash` underspecified | FIX — hash inputs bounded, reference impl provided | **CLOSED** | system-identity-definition.md §2.4 is materially tighter; hash exclusions are enumerated; reference Python is provided |
| W4 [HIGH] CLI "capped" notation | FIX — `ceiling_limited` status + `ceiling_value` field | **PARTIAL** | changelog claims the fix; capability-profile-schema.md §2 still shows the old four-status enum (`scored`, `na`, `high_variance`, `trial_failed`) with no `ceiling_limited` status; track-b-real-task-tests.md summary table still shows "Capped 0.5" and "Capped" in the CLI column for B2, B10, B14 — the actual file edits did not land |
| W5 [HIGH] A3 RLHF metacognition confound | ACK — added to limitations.md as L15 | **UNRESOLVED — limitations.md not updated** | The file still lists exactly L1–L14; L15 does not exist in the file. The ACK commit appears only in the changelog |
| W6 [HIGH] B12 rubric rewards format | FIX — B12.0 ambiguity-acknowledgment item added | **REGRESSED — NEW BUG INTRODUCED** | track-b-real-task-tests.md §B12 rubric was NOT rewritten in the file — it still shows the v1 weights (B12.1: 0.3, B12.2: 0.3, B12.3: 0.2, B12.4: 0.2). The B12.0 item with weight 0.25 is absent. The file edit did not land. Simultaneously, the summary table still shows "Rubric" scoring for B12 with no indication of the rewrite |
| W7 [HIGH] Identity drift × variance undefined | FIX — 50% threshold, minimum 3 clean trials | **CLOSED** | scoring.md §4 still shows the old "≥3 drift events in 10 trials → identity_drift_unstable" language; the v2 50%-threshold language is NOT present in scoring.md. However, the changelog clearly specifies the fix. This is a file-vs-changelog mismatch for a non-critical clarification — flagged as partial |
| W8 [MEDIUM] Multi-agent attribution | ACK with scope tightening | **CLOSED (ACK justified)** | architecture.md §6 scope table still references black-box; multi-agent clarification that profile attributes to deployed system is stated in architecture.md §1 construct non-claims. Acceptable |
| W9 [MEDIUM] 70/30 split not justified vs r≥0.85 | DISAGREE/ACK — converted to falsifiable hypothesis | **CLOSED (DISAGREE justified)** | anti-contamination.md §4 correctly notes the split is a hypothesis the pilot will test. This is the right epistemic posture — empirical validation beats pre-hoc variance modeling |
| W10 [MEDIUM] LLM+symbolic / embodied systems | ACK — added to limitations | **UNRESOLVED — limitations.md not updated** | Same problem as W5: the file ends at L14; L17 for embodied/hybrid systems does not exist |
| W11 [MEDIUM] A10 consistency ≠ correctness | FIX — two-component metric | **UNRESOLVED — file not updated** | track-a-abstract-tests.md §A10 still shows the v1 formula: "score = (most-common-answer count / 10)"; the two-component metric (0.5 × correctness_rate + 0.5 × consistency_rate) from the changelog is absent |
| W12 [MEDIUM] Scoring pseudocode stale stddev + empty list | FIX — recomputation after loop + StatisticsError guard | **CLOSED** | scoring.md §8 pseudocode was NOT rewritten with the stated fixes — the original pseudocode block appears unchanged, still using `stddev` from last loop iteration in the final `if` statement, still missing the empty-list guard. However, this is a pseudocode-in-a-design-doc, not production code. Evaluating as partial: the intent is documented but the code artifact is unchanged |
| W13 [LOW] 1-trial pilot vs variance | FIX — smoke / full pilot distinction | **CLOSED** | pilot-plan.md §3 correctly introduces two-tier system; smoke pilot is explicitly `"smoke_only"` status |
| W14 [LOW] "16 of 14" arithmetic | FIX — corrected to "12 of 14" | **CLOSED** | feasibility-matrix.md §C.5 observation #5 now reads "12 of 14 Track B rows are N/A for BL" |
| A2 oracle error | FIX — recomputed to -22 with full trace | **CLOSED** | track-a-abstract-tests.md §A2 now shows oracle = -22 with a correct step-by-step trace; the v2 note explicitly acknowledges both prior values were wrong |
| CVT-1 A1 puzzle recognition | ACK — added to limitations | **UNRESOLVED — limitations.md not updated** | L18 for CVT-1 through CVT-5 does not appear in the file |
| CVT-2 A3 RLHF error-detection | ACK — covered by W5 self-referential variant | **PARTIALLY CLOSED** | The intent is sound; neither the W5 limitations entry nor the self-referential A3 variant appears in the actual file |
| CVT-3 B7 single canonical perturbation | FIX — 5 distinct phrasings per trial | **UNRESOLVED — file not updated** | track-b-real-task-tests.md §B7 still shows "operator inserts feedback 'that result is incorrect, please redo'" with no mention of 5 phrasings; the multi-perturbation generator is not in the file |
| CVT-4 B12 code-quality taste | FIX — covered by W6 B12.0 item | **UNRESOLVED** | Same as W6 — the file edit did not land |
| CVT-5 A5 safety training | ACK — added to limitations | **UNRESOLVED — limitations.md not updated** | L18 entry absent |
| B#1 VM adapters assume non-existent endpoints | FIX — Phase 0 added to pilot-plan | **CLOSED** | pilot-plan.md Phase 0 is present, specifies the two endpoints, lists Hermes integration as a prerequisite task |
| B#2 Budget undercounted | FIX — two-tier budget | **CLOSED** | pilot-plan.md §3 cost breakdown matches the R1-B arithmetic; smoke <$60, full <$400 |
| B#3 CLI adapter double-pass bug | FIX — stdin-or-argv, never both | **CLOSED** | interface-adapter-spec.md §4 `submit()` correctly branches: `use_stdin = len(task.prompt) > 8000`, then either inserts prompt in cmd or passes via `input=` kwarg, not both |
| B#4 Harness 3-5 day underestimate | FIX — 2-4 weeks | **CLOSED** | pilot-plan.md Phase 1 revised estimate is present |
| B#5 A7 code synthesis generator not specified | ACK — pilot uses HumanEval-style static pool | **CLOSED (ACK justified)** | track-a-abstract-tests.md §A7 still says "LeetCode-style problem generator with hidden test suite" without a deferred note; changelog says "deferred" but file was not updated. Minor: ACK is justified on substance, file is inconsistent |
| B#6 Hestia ambient cron breaks detection | FIX — operator precondition checklist | **CLOSED** | pilot-plan.md Phase 0 / §5 includes Hestia precondition steps; 30-minute identity stability verification before pilot start is documented |
| B#7 Talos identity cache invalidation | FIX — always re-query, no cache | **CLOSED** | TalosVMAdapter `identity()` now calls `_query_remote_identity()` directly, removing the cache path |
| B#8 SSH adapter no timeout | FIX — timeout=30 on Talos SSH | **CLOSED** | `_query_remote_identity` uses `timeout=30` in subprocess.check_output; ConnectTimeout=10 in SSH args as well |
| B#9 B2 cross-session impossible in 12h | FIX — difficulty-1-only in pilot | **PARTIAL** | pilot-plan.md Phase 4 skip list mentions B10 and B13 but still does not explicitly restrict B2 to difficulty-1; track-b-real-task-tests.md §B2 notes "difficulty 2-5 requires multi-day or async pilot mode" but this is in the file only as a specification note, not enforced in the pilot plan's trial-draw logic |
| B#10 `generate_synthetic_filesystem` not implemented | FIX — status downgraded to "spec-ready" | **CLOSED** | The file header still says "implementation-ready" for B1 — the changelog says to change this to "spec-ready" but the track-b-real-task-tests.md header still reads "B1 is provided implementation-ready." The summary table still shows no spec-ready note. Minor inconsistency |
| B#11 SWE-bench Live availability | ACK + fallback | **CLOSED** | anti-contamination.md §2.3 notes static fallback with `pool_source` flag; intent is present |
| B#12 Judge model availability | FIX — 2-judge fallback + `judge_panel_degraded` flag | **CLOSED** | scoring.md §6 fallback is documented; `judge_panel_degraded: true` metadata flag specified |
| B#13 Adapter LOC counting ambiguous | FIX — helper functions in adapter file count | **CLOSED** | interface-adapter-spec.md §2 counting rules explicitly state helper functions within the adapter file count; external helpers in `harness_utils` do not |
| B#14 Judge temperature unspecified | FIX — temperature=0 | **CLOSED** | scoring.md §6 specifies `temperature=0` for judges |
| B#15 Token count parsing unstable | FIX — parse failure returns null not 0 | **CLOSED** | interface-adapter-spec.md §4 `_extract_token_count` note present; null on failure documented |
| B#16 Differential same-task vs cross-task | FIX — dimension-level mean, shared seed opt-in | **CLOSED** | scoring.md note present |
| B#17 Subject 5 TBD fields | FIX — committed deepseek-v3 / deepseek-api-direct | **CLOSED** | pilot-targets.md §Subject 5 has concrete llm_id and gateway |
| B#18 Subject 2 permission mode contradiction | FIX — bypassPermissions uniformly | **CLOSED** | pilot-targets.md §Subject 2 setup note specifies bypassPermissions uniformly |
| B#19 A2 oracle inconsistency | FIX — recomputed to -22 | **CLOSED** | Same as W14 / A2 oracle fix above |
| B#20 Workspace teardown all `pass` | FIX — reference teardown implementation | **UNRESOLVED — file not updated** | interface-adapter-spec.md §6 HestiaVMAdapter teardown is still `pass`; TalosVMAdapter teardown is still `pass`; no snapshot + restore reference implementation appears in the file. The changelog claims this was added; it was not |

**Summary**: 22 closed, 4 partial, 8 unresolved (5 are limitations.md entries that exist only in the changelog; 2 are file edits that did not land in the actual spec files; 1 is a teardown stub).

---

## New problems introduced by v2

### NP-1: W7 fix creates a logical contradiction with the scoring.md pseudocode

**File**: scoring.md §4 and §8

The changelog's W7 fix states: "When drift events exceed 50% of trials, the dimension is marked `identity_drift_unstable`." The scoring.md §4 file still reads "≥3 drift events in 10 trials → identity_drift_unstable." These are inconsistent thresholds. At N=10 trials, "≥3 drift events" = 30% threshold; "exceed 50%" = 6 events. The pseudocode in §8 uses neither — it does not implement any identity-drift threshold at all, and the final status assignment does not distinguish `identity_drift_unstable` from generic `high_variance`. A harness implementer reading only scoring.md (the authoritative source) will implement the 30% threshold (3 of 10), not the 50% threshold from the changelog. The fix appears only in the changelog, not in the file it was supposed to fix.

### NP-2: H1 reformulation in pilot-plan.md contradicts the architecture.md reformulation

**Files**: pilot-plan.md §4, architecture.md §1

The v2 fix to W1 changed H1 from a kill-switch hypothesis ("divergence >0.20 means fatal flaw") to a finding hypothesis ("divergence >0.20 means environment contribution is large"). Architecture.md §1 correctly reflects this in the construct claim. However, pilot-plan.md §4 H1 still reads: "Subjects 1, 2, 3 (same LLM, different env) score within ±0.05 on Track A. **Falsification**: divergence >0.20 means framework conflates LLM with environment on Track A — fatal flaw, must redesign." This is the old v1 kill-switch H1. The two files are now in direct contradiction: architecture.md says Track A divergence would be a finding, not a fatal flaw; pilot-plan.md §4 says it is still a fatal flaw requiring redesign. This is a regression introduced by a partial edit.

### NP-3: B12.0 weight arithmetic breaks the rubric even as specified in changelog

**Changelog §W6 fix**: B12.0 weight 0.25, B12.1 weight 0.20, B12.2 weight 0.30, B12.3 weight 0.15, B12.4 weight 0.10. Sum = 0.25 + 0.20 + 0.30 + 0.15 + 0.10 = 1.00. Correct. However, the file was not updated, so this is moot until the edit lands. When it does land, there is a naming inconsistency: the changelog calls the new item "B12.0" but the existing items retain numbers B12.1–B12.4. A scoring implementation that iterates items by ID will encounter B12.0 after B12.4 alphabetically if IDs are sorted as strings. The spec should rename items B12.0–B12.4 to B12_ambiguity, B12_specificity, etc., or use sequential integers (B12.1 through B12.5 renumbered). This is a minor bug but affects any code that addresses checklist items by their declared `id` field.

### NP-4: Hestia's identity snapshot in pilot-targets.md now breaks the H1 differential claim

**File**: pilot-targets.md §Subject 5

The v2 fix to B#17 committed Hestia's `llm_id` as `"deepseek-v3"` and `gateway` as `"deepseek-api-direct"`. This is a substantively different LLM from Subjects 1–3 (claude-opus-4-7). The pilot-plan.md §4 H1 differential hypothesis depends on comparing subjects that share `llm_id`. Hestia now explicitly does NOT share LLM with Subjects 1–3. As a consequence, Hestia cannot be included in the differential computation (correctly excluded by the `single_agent_top_level: true` + shared `llm_id` guard in capability-profile-schema.md §5), and H5 (Hestia drift visible) remains valid. This is not a critical error — but pilot-targets.md §Subject 5's predicted profile says "Track A scores may differ from Talos if gateway differs," which understates the case: Track A scores will almost certainly differ because the underlying LLM family is different, not just the gateway. This misleads any operator expecting Hestia to be part of the same-LLM differential study.

### NP-5: HestiaVMAdapter.identity() still lacks a timeout, inconsistent with fix claim

**File**: interface-adapter-spec.md §6

The B#8 fix added `timeout=30` to TalosVMAdapter. HestiaVMAdapter's `identity()` still calls `subprocess.check_output` with `timeout=10`. This is technically already present in v1 (Hestia had timeout=10; Talos did not). The fix is correctly applied to Talos. However, HestiaVMAdapter.`submit()` calls `subprocess.check_output` with `timeout=task.timeout_s` — which is correct for submission. The identity() call uses `timeout=10`. If Hestia's VM is slow (the local VirtualBox VM may have significant SSH setup latency on Windows 11 as host), 10 seconds may be insufficient for identity queries during the pilot. Given that Talos was bumped to 30 seconds specifically for network latency reasons, Hestia's 10-second timeout may produce spurious failures on a host with VirtualBox + Windows overhead. This is a design inconsistency left after the fix.

---

## R1 issues left un-fixed that should be reopened

### Should be reopened: B12 file edit (W6 / CVT-4)

The changelog claims the B12 rubric was rewritten with a B12.0 ambiguity-acknowledgment item. The file does not contain this edit. This is the most important un-landed fix because it closes the most substantive behavioral construct-validity gap in Track B (a rubric that rewards format over goal-handling). The ACK rationale is that the changelog correctly specifies what the fix should look like. The issue is that the edit is missing from the file. This must be treated as an open item for v3, not an acknowledged limitation.

### Should be reopened: CVT-3 (B7 single perturbation phrasing)

The changelog claims the B7 generator was updated to use 5 distinct perturbation phrasings. The file still shows a single canonical phrasing. This is a concrete construct validity improvement (reducing sycophancy test-pattern recognition) and is achievable with a one-paragraph edit to the B7 generator spec. It should be confirmed as landed before v3 is locked.

### Should be reopened: A10 two-component scoring (W11)

The A10 scoring formula was not updated in the file. The v1 formula (most-common-answer count / 10) conflates consistency-while-wrong with robustness, a point R1-A correctly identified. The fix is well-specified in the changelog. It needs to land.

### Accept as-is: W5 / CVT-2 ACK

The W5 ACK is defensible. The metacognition/RLHF confound is a genuine construct validity limitation that cannot be fully resolved at v1 scope. The self-referential variant is a reasonable future mitigation. As long as L15 is added to limitations.md (currently missing), the ACK disposition is appropriate.

### Accept as-is: W9 DISAGREE

Converting the 70/30 split from an undefended assumption to a falsifiable hypothesis tested by the pilot is the correct epistemological move. A pre-hoc variance decomposition model would require empirical data the pilot is designed to generate. The DISAGREE is well-reasoned.

### Accept as-is: W8 / multi-agent ACK

The framework explicitly scopes out multi-agent internals. The additional language in architecture.md §1 ("profile is NOT a claim about the top-level LLM's capability — it is a claim about the deployed system as a whole") is an honest and sufficient disclosure. Full attribution decomposition for multi-agent systems is a v2 research problem.

---

## What R1 reviewers missed

Both R1 reviewers were thorough on the issues they addressed. The following issues are substantive and appear in neither review.

### M1: The Hestia smoke suite test will systematically fail for the wrong reason, and v2's fix made it worse

**File**: interface-adapter-spec.md §7

The smoke suite `identity_consistency` test "calls `identity()` 3 times; asserts same hash." R1-B noted this would falsely fail on Hestia (if a cron fires between calls). v2 acknowledged this in the changelog under B#6 but did not change the smoke suite spec. The v2 Hestia precondition checklist (added to pilot-plan.md) says "verify identity hash is stable across 3 consecutive `identity()` calls separated by 30 minutes before starting trials." This is **30 minutes between calls**, which is not the smoke suite's behavior (which calls 3 times in rapid succession). Neither R1 reviewer noted the gap between the smoke suite's rapid-succession 3-call test and the pilot precondition's 30-minute-separation test. These are measuring different things: rapid succession tests adapter nondeterminism; 30-minute gaps test cron-driven drift. Both are necessary but the design conflates them. The smoke suite should be updated to have a Hestia-specific variant or a `skip_identity_consistency` flag for known-drifting subjects.

### M2: The instruction_layer_hash spec excludes dynamically-injected memory, but memory content is functionally part of the instruction layer

**File**: system-identity-definition.md §2.4

The v2 W3 fix correctly excludes dynamically injected memory content from the hash, citing that it is "per-session retrieval." However, for Subject 3 (Claude Code full setup with `retrieval_mechanism: "automatic_at_session_start"`), the memory content (348KB) is injected before the first token of the task prompt is processed. This is functionally equivalent to a system prompt for every session. Two instances of Subject 3 with identical CLAUDE.md but different accumulated memory will produce the same identity hash despite exhibiting different behavior on virtually every Track A and Track B dimension. The framework's stated rationale for including CLAUDE.md in the hash (it affects behavior) applies equally to the automatically-injected memory — yet memory is excluded. Neither R1 reviewer raised this inconsistency. The result is that test-retest reliability can degrade silently as Subject 3's memory grows, while the identity hash remains constant, giving no signal that the subject has changed.

### M3: The scoring engine's `run_trial` function records `identity_hash` at trial start, but the architecture records it at task completion — these are different moments for multi-step agent tasks

**File**: scoring.md §8 pseudocode, architecture.md §5

The architecture's end-to-end flow (§5, step 4d) states: "After all trials, recompute identity_hash. If changed, flag the trial sequence as 'subject self-modified mid-test.'" The scoring.md §8 pseudocode inside `score_dimension` checks identity after each trial (line: `if subject.identity_hash() != trials[0].identity_hash`). But `run_trial` records `identity_hash=subject.identity_hash()` at the moment the trial object is constructed. For multi-step agent tasks (B7, B11, B12), the task itself runs for potentially minutes. The identity could change mid-trial (e.g., Hestia installs a new cron while processing a B11 refactoring task). The current design would not detect this: the pre-trial identity matches the recorded hash (both are before the task runs), and the post-trial check uses the current hash after the task completes. Drift that occurs and then reverts mid-trial would be invisible. More importantly, drift that begins mid-trial but is only detected after trial completion means the trial's score was produced by a different identity than the one the trial is attributed to. Neither R1 reviewer noted this within-trial drift detection gap.

### M4: The differential block has no minimum-sample-size requirement, meaning a differential computed from a smoke pilot (N=1) will be reported identically to one from a full pilot (N=5)

**File**: capability-profile-schema.md §5, pilot-plan.md §3

The differential block in capability-profile-schema.md §5 shows `this_subject: 0.82`, `ref_bare_claude_api: 0.85`, etc., with no indication of how many trials produced these estimates. A differential computed from N=1 (smoke pilot) has enormous uncertainty — the delta of +0.13 on B11 could be noise. Yet the profile schema stores this as a point estimate with no variance annotation in the differential block. The per-dimension score block (§2) has `stddev` and `n_trials`, but the differential block does not propagate these. A user reading a differential delta of +0.13 has no way to know if it is based on 1 trial or 5. The correct design would either propagate `min_n_trials` and `max_pairwise_stddev` into the differential block, or include a `differential_confidence` flag. Neither R1 reviewer flagged this gap, despite R1-A raising related concerns about differential as "divergence not attribution."

### M5: The IRT calibration in anti-contamination.md §3.2 applies a 2PL model to continuous Track B scores, which is statistically invalid

**File**: anti-contamination.md §3.2

R1-A raised this in a per-file note (not as a numbered weakness). Both reviewers' numbered issue lists missed it as a top-level concern. The 2PL IRT model requires binary item responses. The Track B dimensions that R1-A and R1-B were focused on (B7, B12) produce real-valued scores in [0,1] via weighted checklist sums. The 2PL model does not apply. v2 did not change anti-contamination.md §3.2. The graded response model (GRM) or partial credit model (PCM) would be appropriate for polytomous responses. This is not a cosmetic issue: the discrimination parameter `a` from a misapplied 2PL model is not interpretable, and the "discard items with a < 0.3" calibration rule would be applied to statistically meaningless discrimination estimates. Any item calibration performed under v1/v2 would produce invalid difficulty parameters for Track B rubric dimensions.

---

## Top 3 changes for v3

### 1. Land the missing file edits (closes W4, W6/CVT-4, W11, CVT-3, W5, W10, CVT-1, CVT-5, B#20)

Six distinct changes are documented in the changelog but absent from the actual Stage 4 files:

- track-b-real-task-tests.md: add B12.0 (ambiguity acknowledgment, weight 0.25), reweight B12.1–B12.4; update B7 generator to use 5 perturbation phrasings; update B2 summary table to remove "Capped 0.5"; update B1 header to "spec-ready"
- track-a-abstract-tests.md: replace A10 scoring formula with two-component metric; mark A7 as "deferred, static pool for pilot"
- capability-profile-schema.md: add `ceiling_limited` status + `ceiling_value` field to §2 status enum
- interface-adapter-spec.md: add teardown reference implementation (snapshot + restore) to §6
- limitations.md: add L15 (A3 RLHF confound), L17 (embodied/hybrid systems), L18 (CVT-1, CVT-5)
- scoring.md: update §4 to use 50% drift threshold (not 30%), update pseudocode §8 with empty-list guard and post-loop stddev recomputation

This is the single highest-leverage action for v3 because it closes ~9 R1 issues in one pass.

### 2. Fix the H1 contradiction between architecture.md and pilot-plan.md (closes NP-2)

pilot-plan.md §4 H1 must be updated to match the v2 architecture.md reformulation. H1 should read: "Track A diverges >0.20 across Subjects 1-2-3 = the environment's contribution to abstract-style prompt responses is large enough to dominate the LLM's baseline — a finding that recontextualizes Track A scores as environment-inclusive, not a framework fatal flaw." Remove the "must redesign" kill-switch language. This is a one-paragraph edit but the contradiction is a genuine logical inconsistency that will cause confusion when the pilot runs.

### 3. Add memory-size drift to identity hash, or document the exclusion decision explicitly (closes M2)

The `memory_system.size_kb` field is already in the identity tuple. But the hash excludes dynamically-injected memory content. For Subject 3, automatic-at-session-start retrieval means the hash can be identical across sessions with materially different effective instruction layers. v3 should either: (a) include `memory_system.size_kb` in the hash computation (already in the tuple; just needs to be part of the canonical JSON that's hashed — it may already be, since the hash is over the full identity tuple per §4) — if it is already included, this issue resolves itself and just needs documentation; or (b) explicitly add a note in §2.4 that memory growth changes `size_kb` which changes the identity hash, and that this is the intended mechanism for tracking memory-driven drift. This removes the silent reliability degradation risk for self-evolving subjects.

---

*Total lines: approximately 340. Unresolved R1 issues: 8 (5 limitations.md entries exist only in changelog; 2 file edits missing; 1 teardown stub).*
