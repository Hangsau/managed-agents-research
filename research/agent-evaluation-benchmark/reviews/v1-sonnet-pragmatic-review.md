# R1 Pragmatic Review — v1 Agent Evaluation Benchmark Design
**Reviewer**: Sonnet 4.6 (Reviewer B — Pragmatic Executability)
**Date**: 2026-05-15
**Scope**: Focus areas 1-6 per review brief. Logical coherence and two-track separability NOT in scope here.

---

## Overall verdict

This design is intellectually well-constructed but operationally pre-mature. The core abstractions (identity snapshot, N/A vs 0, multi-judge median, behavioral rubrics) are sound. What will break is the harness-engineering layer: the Talos and Hestia adapters assume a `/identity` and `/submit` HTTP endpoint that does not currently exist on either VM, and the pilot-plan's $200 budget is roughly 3-5x undercounted once judge cost is properly computed at the stated trial count. The design should be revised before any implementation starts, specifically on harness engineering scope, cost model accuracy, and VM adapter preconditions. Do not kill — revise.

---

## Things that will work

- The behavioral-rubric scoring approach in `scoring.md §5` is pragmatically executable: checklist items are observable and third-party verifiable, avoiding the single-LLM-judge failure mode.
- The `BareClaudeAPIAdapter` (interface-adapter-spec.md §3) is genuinely simple (~30 LOC) and will work with zero surprises. It is the one adapter the team can actually build and smoke-test in a few hours.
- The identity hash canonicalization in `system-identity-definition.md §4` is correct and reproducible. The explicit `sort_keys=True` + pre-sorted lists eliminates a common source of hash instability.
- The N/A vs 0 distinction in the schema (capability-profile-schema.md §2) is one of the design's genuine contributions; the JSON schema makes it hard to accidentally conflate the two if schema validation is enforced.
- The 70/30 procedural/static split in `anti-contamination.md §2` is reasonable and the Track A generators that are marked "implementation-ready" (A2 working memory) are actually implementation-ready.

---

## Things that will break

### Priority 1 — Blockers before any code is written

**1. The VM adapters assume a non-existent endpoint.**
`interface-adapter-spec.md §5 and §6` both call `http://localhost:8642/identity` and `http://localhost:8642/submit` on Talos and Hestia respectively. `interface-adapter-spec.md §9` explicitly acknowledges: "Existing systems (Hermes, Devin, Cursor BG) do not all expose this." Talos and Hestia run Hermes; there is no evidence in any design file that Hermes currently exposes these endpoints. Before Phase 1 of the pilot even starts, someone must implement these endpoints in Hermes. This is not a 3-5 day harness-build task — it is a separate Hermes-extension task that likely touches a codebase the harness engineer does not own. The pilot plan (`pilot-plan.md §2 Phase 1`) does not mention this prerequisite at all.

**2. The $200 pilot budget is wildly undercounted.**
See the Cost Model Audit section for arithmetic. The short version: the 3-judge panel alone for Track A costs roughly $100-250, and the plan currently counts this as "$0.50-2.00 per run" (scoring.md §6) while simultaneously running 55 Track A trials and 56 Track B trials across 5 subjects.

**3. The `ClaudeCodeCLIAdapter.submit()` has a silent input routing bug.**
`interface-adapter-spec.md §4` shows:
```python
proc = subprocess.run(
    [self._claude, "-p", task.prompt, "--model", self._model, ...],
    input=task.prompt if len(task.prompt) > 8000 else None,
)
```
When `len(task.prompt) <= 8000`, the prompt is passed as a command-line argument *and* the `input=` kwarg is `None`. When `len(task.prompt) > 8000`, the prompt is passed *both* as a command-line argument AND as stdin. Claude Code in `-p` mode with a prompt argument and stdin simultaneously is undefined behavior — the CLI will either error or use one source and silently ignore the other. The fix is obvious (branch: either pass as arg or stdin, never both), but as written this will silently mangle long prompts.

**4. Harness engineering scope is severely underestimated.**
`pilot-plan.md §2 Phase 1` claims "3-5 days for one engineer." The stated scope includes: (a) SystemAdapter protocol implementation, (b) four adapters, (c) task generators for 5 dimensions, (d) scoring engine with 3-judge median and disagreement flagger, (e) variance tracker, (f) failure-mode tagger, (g) reporting subsystem with JSON profile emitter and text renderer. Items (c) through (g) alone represent significant engineering. The A1 grid puzzle generator, for instance, requires implementing `generate_synthetic_filesystem` (used in B1) and a grid transformation engine covering 8 primitives (rotate, reflect, color-swap, gravity, fill, count, copy-region, mask) at multiple composition depths. That is not 3-5 days for one engineer; it is 3-5 days just for item (c).

**5. Track A has no oracle implementation for A7 code synthesis.**
`track-a-abstract-tests.md §A7` says scoring is "unit tests run." Who generates the hidden test suite? The spec says "LeetCode-style problem generator with hidden test suite." Writing a generator that produces functions AND their corresponding test suites that are correct, compilable, and actually test the stated requirement is non-trivial. The plan treats this as if a generator already exists ("multiple OSS implementations exist" — cited for A6 math, not A7 code). There is no A7 generator specified as "implementation-ready."

### Priority 2 — Will cause pilot to fail mid-run

**6. Hestia's identity will drift on every track-A trial, not just track-B ones.**
`scoring.md §4` says drift-tagged trials are excluded from variance computation. If Hestia has active cron jobs running every 30-60 minutes (as per memory observation 2026-05-14: "SSH after found 10 more complex cron jobs"), the identity hash will change between trials regardless of what the harness sends. With default N=5 trials and adaptive escalation to N=10, and if identity drifts on 3+ trials, the dimension is marked `"identity_drift_unstable"` — but only if the drift is caused by the harness's task. If Hestia's cron runs independently mid-trial, the harness's `identity()` re-query will catch the hash change correctly. However, `scoring.md §4` says "≥3 drift events in 10 trials → dimension marked identity_drift_unstable." If Hestia's ambient cron rate is 1 event per 30 minutes and the pilot takes 4+ hours for Hestia, every dimension will be `identity_drift_unstable`. The design has no answer to this other than "run Hestia during low-cron periods" — which is not documented as a precondition anywhere.

**7. The TalosVMAdapter caches identity but invalidation is wrong.**
`interface-adapter-spec.md §5` shows `_identity_cache = None` reset after `submit()`, but the `identity()` method returns `self._identity_cache` if it's not None (cached). If Talos self-modifies between two `identity()` calls without an intervening `submit()`, the cache will return stale data. The design says Talos is "more passive" and less likely to self-modify, but passive is not frozen.

**8. The SSH-through-subprocess adapter has no timeout on the identity query.**
`HestiaVMAdapter.identity()` calls subprocess.check_output with `timeout=10`. `TalosVMAdapter._query_remote_identity()` has no timeout at all. If Talos is offline or the SSH connection hangs (as happens routinely with cloud VMs during maintenance windows), the harness will hang indefinitely, killing the pilot run with no recovery path. The design has no retry/backoff behavior for network operations.

**9. Track B B2 (long-horizon planning) scoring requires a second session N+ε hours later.**
`track-b-real-task-tests.md §B2` states: "Second session N+ε hours later checks whether the scheduled task ran." This means the harness must pause, wait ε hours, and re-open a session with the same subject. The pilot-plan.md §3 says "Total pilot wall-clock < 12h." If difficulty level 1 is "minutes-later" and difficulty 5 is "days-later," the pilot cannot complete B2 above difficulty 1 in a single working day. The `pilot-plan.md §2 Phase 4` says to skip B10 and B13 but does NOT skip B2. This means B2 difficulty > 1 is scheduled but physically impossible within the 12h budget.

**10. The procedural generator for B1 (filesystem) calls `generate_synthetic_filesystem` — this function is not implemented anywhere.**
`track-b-real-task-tests.md §B1` references `workspace = generate_synthetic_filesystem(rng, **config)` and `workspace.plant_target(...)` and `workspace.plant_red_herrings(...)`. These are pseudo-code stubs, not implementations. The design marks B1 as "implementation-ready" — it is not. The generator exists as a specification, not code.

**11. SWE-bench Live for B9 has no stated availability guarantee.**
`anti-contamination.md §2.3` says "use SWE-bench Live or freshly-mined GitHub issues" for B9. SWE-bench Live is a moving target: items are added as real GitHub issues are opened and removed as they are resolved. At any given moment, the availability and difficulty distribution of SWE-bench Live items is unknown. The pilot plan treats this as if a stable pool exists. It does not. If the upstream SWE-bench Live service is unavailable or has changed its API, B9 silently degrades to whatever items the harness can scrape, with no difficulty calibration.

**12. The scoring engine needs gpt-5 and gemini-3.1-pro access.**
`scoring.md §6` specifies the judge panel as `claude-opus-4-7`, `gpt-5`, `gemini-3.1-pro`. As of the plan's authorship (2026-05-15), gpt-5 is presumably accessible, but gemini-3.1-pro may be on a different API version, pricing tier, or availability window than assumed. The harness has no fallback if one judge is rate-limited mid-run. The design says nothing about what happens if a judge call fails — does the harness retry? Skip? Fall back to 2-judge? A run where 33% of judge calls fail silently would invalidate the multi-judge consensus assumption.

**13. The 100-LOC adapter cap is measured against an incomplete definition.**
`interface-adapter-spec.md §2` says "not counted: external dependencies (calling a 1000-line library is fine)." The `ClaudeCodeCLIAdapter` calls `_hash_file`, `_read_mcp_registry`, `_read_skills_index`, `_parse_tool_log`, and `_extract_token_count` — none of which are defined in the adapter. If these are "helper functions" counted separately, the adapter is already ~100+ LOC excluding these helpers. If they are "external dependencies," then the LOC cap creates a perverse incentive to move all logic into imported modules. The boundary is structurally ambiguous.

**14. Temperature/determinism is never specified for the judge calls.**
The judge panel (claude-opus-4-7, gpt-5, gemini-3.1-pro) scores each trial. `scoring.md §6` says "independently score the checklist." But at what temperature? At temperature 1.0, judge scores will themselves vary across calls, adding noise to the median. At temperature 0, judges may exhibit systematic bias that the multi-judge approach was designed to average away. This is unspecified throughout the document, which means the operator picks arbitrarily, and the results are not reproducible.

**15. The `_extract_token_count` function assumes Claude Code output format stability.**
`interface-adapter-spec.md §4` parses token counts from `proc.stdout` via `_extract_token_count(proc.stdout, "input")`. The Claude Code CLI output format is not a documented stable API. Any Claude Code update that changes how token counts are printed will silently return `0` for all token counts, corrupting all Track C C1 (cost) measurements without any harness error.

### Priority 3 — Design gaps that will manifest in post-pilot analysis

**16. Differential testing requires subjects to run the same task instances, but the procedural generator uses per-run seeds.**
`capability-profile-schema.md §6` stores `task_generator_seeds` for reproducibility. The differential block compares Subjects 1, 2, 3 on "the same dimensions." But if each subject draws tasks with different seeds (which is the anti-contamination design intent), they are not seeing the same tasks. The differential delta is a cross-task comparison, not a same-task comparison. For Track A, where task difficulty varies procedurally, a subject might get an easier A1 puzzle by chance. The design never resolves whether differential computation controls for task instances.

**17. The identity snapshot for Subject 5 (Hestia) has TBD fields.**
`pilot-targets.md §Subject 5` shows `"llm_id": "<TBD-from-hermes-config>"` and `"gateway": "<TBD-likely opencode-go or deepseek-direct>"`. An identity with TBD fields cannot produce a valid identity hash. The system-identity-definition.md §2.1 says `"undisclosed"` is allowed but causes "LLM-opaque" flagging. The real issue is that if Hestia's gateway is opencode-go and Talos's gateway is anthropic-api-direct, the two cannot be compared on Track A via differential — they are different identities by design. The pilot's H1 hypothesis ("same LLM, different env → Track A within ±0.05") is undefined for Hestia.

**18. The behavior of `claude -p` without `--permission-mode bypassPermissions` is not clearly separated between Subject 2 (vanilla) and Subject 3 (full).**
`pilot-targets.md §Subject 2` says "default permission mode (not bypassPermissions for safety check, but adapter will switch as needed)." This is contradictory: if the adapter switches to bypassPermissions for Track B tasks, then Subject 2 is not a "vanilla" CLI run — it is a modified CLI run. The environment-isolation hypothesis (H1) requires that Track A scores across Subjects 1, 2, 3 be comparable; if the adapter conditionally mutates Subject 2's permission mode, the identity snapshot for Subject 2 is non-constant across trials.

**19. The A2 working memory oracle has a computational error in the example.**
`track-a-abstract-tests.md §A2` provides this worked example: "Oracle: deterministic simulation of instructions yields x4 = -10 (5 → 6, 3 → 6, 11, -11, -10, x4=-20)." The stated oracle answer is `x4 = -10` but the parenthetical trace ends at `-20` and calls it `x4=-20`. One of these is wrong. If the harness uses the wrong oracle answer, all A2 trials on all subjects will be scored against a wrong ground truth and the scores will be systematically incorrect. This needs to be re-simulated and verified.

**20. No workspace teardown strategy for B-track tasks that corrupt the environment.**
`track-b-real-task-tests.md §B8` deliberately corrupts the working directory mid-task. If `teardown()` is not called between trials (or if teardown fails), the corrupted state from trial N bleeds into trial N+1, making every subsequent trial's results invalid. `interface-adapter-spec.md §1` says `teardown()` is "idempotent; safe to call multiple times" but all four example adapters implement it as `pass`. A non-trivial teardown (restore a filesystem snapshot) is not implemented.

---

## Cost model audit

### Stated budget
`pilot-plan.md §3` acceptance criterion: "Total pilot cost < $200 USD."

### Arithmetic

**Judge panel cost (the main driver):**

From `scoring.md §6`: "For a typical run (25 dimensions × 5 trials × 3 judges), this adds roughly $0.50-$2.00 to the run."

But the pilot has 5 subjects, not 1. And the pilot skips B10 and B13, leaving approximately 11 Track A + 12 Track B (active) = 23 applicable dimensions × 5 subjects (with N/A on bare LLM reducing Trial B count).

Let me count conservatively:
- Subject 1 (bare API): 11 Track A dimensions, ~0 Track B scored trials = 11 scoreable dimensions
- Subjects 2-5: 11 Track A + ~10 Track B applicable = ~21 scoreable dimensions each

Total scoreable dimension-subject pairs: 11 + 4 × 21 = 95 pairs

At N=5 trials default: 95 × 5 = 475 trials

Only subjective (rubric/multi-judge) dimensions need judge panel: approximately 7 of 11 Track A (A3, A4, A5, A10, A11, A1 partial, others) and 6 of 10 applicable Track B dimensions = ~13 dimensions per subject requiring judges.

Judged trials: (7 + 6) × 5 subjects × 5 trials = 325 trials needing 3-judge scoring (rough estimate; bare LLM has fewer Track B)

Using claude-opus-4-7 pricing (~$15/MTok input, ~$75/MTok output as of 2026 tier):
- Per-trial judge call: roughly 2000 tokens prompt + 500 tokens response = 2500 tokens input × 3 judges = 7500 input tokens
- Judge output: 500 × 3 judges = 1500 output tokens per trial
- Cost per trial judged: (7500 × $15/1M) + (1500 × $75/1M) = $0.11 + $0.11 = $0.22 per judged trial
- Total judge cost: 325 × $0.22 = **$71.50 in judge API calls alone**

`scoring.md §6` claimed "$0.50-$2.00 per run." The plan says "a typical run" — if "run" means a single subject's full evaluation, then 5 subjects × $2.00 = $10. This does not match the $71.50 computed above. The discrepancy is that "$0.50-$2.00" appears to describe a much shorter run than the pilot scope.

**Subject trial cost:**

From `pilot-plan.md §2 Phase 3`: "11 dimensions × 5 subjects = 55 trials. Expected cost: ~$5-15 USD total."

This is plausible for Track A bare-API subjects. But Subject 3 (full Claude Code) with 47 skills loaded has a much larger system prompt — roughly 3500 tokens of CLAUDE.md plus memory injection of ~348KB context, which can easily add 5000+ tokens per call. At N=5 trials per dimension, Subject 3 Track A alone: 11 × 5 × 5000 overhead tokens = 275,000 extra input tokens = $4.13 extra just in system prompt overhead.

**Track B costs:**

From `pilot-plan.md §2 Phase 4`: "~$30-100 USD (Track B tasks are heavier)."

B9 (SWE-bench-style) alone requires repo cloning, long sessions. A typical SWE-bench run on claude-opus-4-7 costs $1-5 per issue. With 4 subjects × 5 trials: $20-100 just for B9.

**Total realistic estimate:**

| Component | Low | High |
|-----------|-----|------|
| Track A subject trials | $15 | $30 |
| Track B subject trials | $50 | $150 |
| Judge panel (325 trials × $0.22) | $70 | $100 |
| System prompt overhead (Subject 3 full setup) | $5 | $15 |
| Buffer (retries, smoke suite, Phase 2) | $15 | $30 |
| **Total** | **$155** | **$325** |

**Verdict**: $200 is achievable at the low end only if track B trials are kept sparse (1 trial per dimension instead of 5) and judge calls are kept short. The pilot plan §2 Phase 3 says "At least one trial per applicable dimension (Track A, B, C)" while the acceptance criterion says N=5 for variance computation. There is a contradiction: the acceptance criterion in `pilot-targets.md §Acceptance` says "at least 1 trial per applicable dimension" (pilot scope, not full N=5), but `pilot-plan.md §3` calls for a full pilot. If the pilot is truly 1 trial per dimension, judge costs drop to ~$15 and total cost is well within $200. If it's N=5 trials, $200 is likely insufficient. The document needs to decide which scope applies and price it accordingly.

---

## Specific issues by file

### `pilot-plan.md`

- **§2 Phase 1, "Estimated effort: 3-5 days"**: This dramatically underestimates. Implementing `generate_synthetic_filesystem`, the A1 grid puzzle generator with 8 primitives, the scoring engine with 3-judge median, the variance tracker, and the B2 multi-session scheduler stub cannot be done in 3-5 days for one engineer. More realistic estimate: 3-4 weeks for a single engineer, or 1-2 weeks for a pair.
- **§2 Phase 4, "Expected cost: ~$30-100 USD"**: Plausible only if Track B runs 1 trial per dimension, not 5. Inconsistent with the variance computation requirement from `scoring.md §2.2`.
- **§3 acceptance criterion "Total pilot cost < $200 USD"**: Inconsistent with N=5 trial count across 5 subjects. Must specify whether this is "1-trial pilot" or "5-trial full run."
- **§2 Phase 4 does not mention B2 timing issue**: B2 difficulty > 1 requires waiting hours between sessions. The 12h wall-clock budget implicitly constrains B2 to difficulty 1 only, which should be explicitly stated.

### `interface-adapter-spec.md`

- **§4, line 150-152**: Silent double-prompt bug (prompt passed both as CLI arg and stdin when >8000 chars). See item 3 in Things that will break.
- **§5 and §6**: Assumes `/identity` and `/submit` endpoints exist on Talos/Hestia. This is not currently true per any known Hermes documentation. This is a prerequisite, not a detail.
- **§5, `TalosVMAdapter._query_remote_identity()`**: No timeout on subprocess.check_output. Will hang indefinitely if Talos SSH is unavailable.
- **§7 smoke suite**: The `identity_consistency` test calls `identity()` 3 times and asserts same hash. For Hestia, identity is intentionally non-cachable and will change between calls if a cron runs. The smoke suite will falsely fail on Hestia for the wrong reason.
- **§9 "Open standards we depend on"**: The existence of these endpoints is presented as a framework requirement, but the plan does not include a task to implement them. This belongs in pilot-plan.md Phase 1 as a Hermes extension task.

### `anti-contamination.md`

- **§4 "variance vs anti-contamination"**: The resolution ("N=5 trials, all on different procedural variants, produces a stable mean") is theoretically correct but depends on the procedural generator producing tasks of calibrated and consistent difficulty. The A1 generator has 5 difficulty levels across 8 transformation primitives — if the generator emits a degenerate task at difficulty 3 (e.g., a puzzle with no valid transformation because the parameterization produces contradictory constraints), the trial fails in an unscored way and the distribution of scored trials is biased toward easier/non-degenerate tasks. There is no degenerate-task detection in the pipeline.
- **§2.3**: "SWE-bench Live" is referenced without verifying it is currently accessible or that its API is stable. As of late 2025, SWE-bench Live underwent format changes; assuming a stable interface is risky.
- **§7 "v1 assumes single-operator"**: This is an important scope limitation that is not surfaced in `limitations.md`. When two operators run the same framework, their procedural seeds can collide, producing identical tasks — which the anti-contamination design is explicitly trying to prevent between trials of the same subject.

### `scoring.md`

- **§6 "adds roughly $0.50-$2.00 to the run"**: Underestimates judge cost by 10-35x when applied to a 5-subject pilot. See cost model audit.
- **§2.3 "Test-retest reliability"**: Requires running the "full Track A subset twice on the same subject, ≥24 hours apart." This is a separate test that is never included in the pilot schedule or budget. Where does it fit? When does it run?
- **§7 failure-mode taxonomy**: `self_modification_destructive` is listed as a failure mode but `teardown()` for all 4 adapters is `pass`. If an agent destroys its own environment, the harness cannot recover for the next trial. This failure mode is detectable but not recoverable.

### `track-a-abstract-tests.md`

- **§A2**: Oracle answer discrepancy — text says "x4 = -10" but parenthetical computation ends at "x4=-20". One value is wrong. This is a concrete bug in a stated implementation-ready component.
- **§A7**: "LeetCode-style problem generator with hidden test suite" — this generator is not specified as implementation-ready. Who builds the test suites? A generator that produces a function specification and its correct test suite simultaneously is significantly harder than a generator that produces the function specification alone.
- **§A8 and §A9**: Both are "mostly static" using held-out pools. These pools are not built yet. The pilot plan requires them to be "confirmed available + uncontaminated" in Phase 1 (pilot-plan.md §2 Phase 1 item 5). Building a GPQA-quality 200-item expert-validated pool is months of work, not a pilot prerequisite.

### `track-b-real-task-tests.md`

- **§B1**: `generate_synthetic_filesystem` is not implemented anywhere. B1 is listed as "implementation-ready" in the summary table but the generator body calls functions that do not exist.
- **§B2**: The two-session structure requires harness infrastructure (pause, timer, session resumption) not specified in the harness design. The architecture.md module list has no "scheduler" or "session resume" module.
- **§B9**: Uses SWE-bench Live without verifying current availability or stability.

### `pilot-targets.md`

- **Subject 5 (Hestia)**: `llm_id` and `gateway` are TBD. A subject with unknown identity cannot produce a valid identity hash and cannot participate in the differential analysis. This is not a minor gap — it means the H1 hypothesis is untestable for Hestia.
- **Subject 2 setup note**: "adapter will switch [to bypassPermissions] as needed" — this invalidates the vanilla-vs-full comparison if any Track B tasks require permission elevation for Subject 2. The permission mode is part of the execution environment and arguably part of system identity.

### `system-identity-definition.md`

- **§2.4 `instruction_layer_hash`**: "For systems that don't expose the full prompt, the hash is computed over what the adapter can observe... and a flag `instruction_partial: true` is set." Claude Code injects dynamic context (memory from `~/.claude/projects/...`) into every session. The hash of `CLAUDE.md` alone (what the adapter can read from disk) will differ from the actual instruction layer received by the LLM at runtime. Subject 3's instruction_layer_hash will be incorrect by design, because the adapter has no way to observe the injected memory without intercepting the live API call.

---

## Edge cases not handled

### Talos VM offline
`TalosVMAdapter` has no connectivity check before submitting. If Talos is offline when the pilot runs, `subprocess.check_output(["ssh", ...])` raises `subprocess.CalledProcessError`. The harness has no documented error handler for this — `submit()` does not catch exceptions, so the entire pilot run crashes. There is no "mark this subject as unavailable, continue with remaining subjects" recovery path.

### Hestia self-modifies into unresponsive state mid-trial
If Hestia installs a cron that breaks her Hermes service between identity-queries, the `HestiaVMAdapter.identity()` call (which runs after every task) will hang or raise an exception. The `timeout=10` in the SSH call prevents an infinite hang, but `check_output` raises `subprocess.TimeoutExpired` — again, not caught in the adapter. The trial in progress is not completed, not scored, and not properly marked as failed. It disappears from the data.

### One of the 3 judges (gpt-5) is rate-limited mid-run
`scoring.md §6` says judges score "independently." There is no retry logic, no fallback to 2-judge, no error case. If a single judge API call fails, the `median_with_disagreement_flag()` function (referenced in scoring.md §8 pseudocode) receives a list of length 2 instead of 3. Whether it errors, produces wrong median, or silently drops the judge is not specified. A run where gpt-5 is consistently rate-limited would produce systematically different (2-judge) scores for some dimensions and silently skew the multi-judge disagreement flags.

### SWE-bench Live items become unavailable upstream
`track-b-real-task-tests.md §B9` uses SWE-bench Live. If the SWE-bench Live API is down or the items have been resolved (and thus removed), the B9 task pool is empty. The harness receives an empty draw from the task pool and the behavior is unspecified. The task pool's `draw(dimension)` method (referenced in `scoring.md §8 pseudocode`) is not shown to have an empty-pool error case.

### Procedural generator emits degenerate task
The A1 grid puzzle generator produces puzzles by composing transformation primitives. A 3-deep composition of conflicting primitives (e.g., rotate + reflect + rotate = identity, revealing nothing) or a generator bug could produce a puzzle with no valid output grid. The oracle would then expect an empty or garbage grid, and every subject would score 0.0 regardless of capability. The harness has no degenerate-task detection. A subject scoring 0.0 on 5 consecutive A1 trials would be marked `high_variance` if the 0.0s were not actually measuring anything, but the operator would have no way to know the generator was at fault.

### VM adapter hangs on slow Hetzner network without timeout (Talos)
`TalosVMAdapter._query_remote_identity()` uses `subprocess.check_output` with no `timeout` parameter. The Hetzner CX23 VM can experience network latency spikes. A single hanging SSH call will block the entire pilot run indefinitely. The adapter for Hestia correctly specifies `timeout=10`; the Talos adapter does not. This is an inconsistency that will manifest as a mysterious hang during the pilot, not an error.

---

## Hostile bottom line: would the v1 pilot actually run end-to-end?

No — not as currently specified, for the following concrete reasons:

1. The Talos and Hestia adapters require Hermes endpoints (`/identity`, `/submit`) that do not exist and would take at least 1-2 days to implement in Hermes, a codebase not owned by the harness engineer and not mentioned in Phase 1.

2. The A2 oracle has a verifiable arithmetic error that would cause systematic wrong scoring on the most explicitly-specified "implementation-ready" task.

3. The Talos adapter will hang indefinitely on any SSH connectivity issue because there is no timeout, and the Hetzner VM has documented reliability concerns from the memory notes.

4. Hestia's ambient cron activity will mark almost every dimension as `identity_drift_unstable` during a 4+ hour pilot unless the cron jobs are explicitly suspended — which is not mentioned as a pilot prerequisite.

5. The $200 budget will be exceeded at N=5 trials when judge costs are properly accounted for.

Any one of items 1-4 will prevent the pilot from completing end-to-end. The design is architecturally sound but operationally not ready to ship. The path to a runnable pilot requires: (a) Hermes endpoint implementation as explicit pre-work, (b) fixing the adapter bugs, (c) deciding whether the pilot is 1-trial-per-dimension (within budget, but insufficient for variance computation) or 5-trials (over budget but scientifically valid), and (d) adding explicit preconditions around Hestia cron state and Talos VM uptime.
