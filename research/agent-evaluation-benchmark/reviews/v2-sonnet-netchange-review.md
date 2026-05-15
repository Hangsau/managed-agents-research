# R2 Net-Change Review — v2 Agent Evaluation Benchmark Design
**Reviewer**: Sonnet 4.6 (R2 Reviewer B — Net Change Assessment)
**Date**: 2026-05-15
**Scope**: Adversarial net-change audit. Focus: did v2 introduce new failure modes, are claimed fixes complete, are there second-order consequences, and can a third party build this?

---

## Overall verdict on v2

**REVISE — do not ship as-is.**

v2 is materially better than v1 on the issues that were raised. The critical construct-claim rewrites (W1, W2, W3) are genuine improvements, not cosmetic. The smoke/full pilot split, Hermes Phase 0, and cost rewrite are necessary operational fixes that close real blockers. The net change is positive.

However, v2 introduces or leaves unresolved enough second-order problems that shipping it would mislead an implementer in at least three concrete ways: (a) the H1 hypothesis in pilot-plan.md was rewritten per the changelog but the actual file text still contains the old falsification language, creating a spec/file inconsistency; (b) the B12 rubric rewrite claimed in the changelog does not appear in the actual track-b-real-task-tests.md file — the file retains the v1 rubric; (c) the scoring.md pseudocode fix (W12) was partially applied — stddev recomputation and empty-list guard were not actually made to the file. Three of the most explicitly claimed fixes are absent from the files they were claimed to touch. A third party handed these files would implement against the wrong spec.

Beyond the missing edits, v2 makes one new unverified claim (Hestia's `deepseek-v3` + `deepseek-api-direct`) and leaves the limitations.md file without the promised L15-L20 entries. The net verdict: v2 is a credible design revision, but the changelog overstates what was actually committed to disk.

---

## v2 edits audit

### W1 fix — Track A construct rewrite

The fix is correctly applied in architecture.md §1. The construct table row for Track A now explicitly reads "NOT a measure of the underlying LLM's raw reasoning capability stripped of environment scaffolding." This is a substantive change that correctly removes the unfounded isolation claim.

**Propagation check**: The changelog states this fix must propagate to pilot-plan.md H1 hypothesis text. Pilot-plan.md §4 H1 reads: "Subjects 1, 2, 3 (same LLM, different env) score within ±0.05 on Track A. Falsification: divergence >0.20 means framework conflates LLM with environment on Track A — fatal flaw, must redesign." This is the old v1 H1 text. The changelog promised a reformulated H1: "Track A diverges >0.20 = a finding, not a falsification." The pilot-plan.md file was not updated. The H1 kill-switch language ("fatal flaw, must redesign") remains intact, which is now directly inconsistent with the v2 architecture.md construct claim. **Partial fix: architecture.md updated, pilot-plan.md H1 not updated.** Implementers reading the pilot plan will apply a kill-switch the architecture no longer supports.

The changelog also lists narrative.md as needing updated language on the isolation claim. narrative.md §4 Tension 1 still reads "Track A dimensions score lower on agent systems than bare LLM... More environment = more scaffolding = more confound. Is this a measurement bug to fix, or a feature to surface?" — this framing is consistent with the v1 construct claim but not with v2's. narrative.md was not in the changelog's file-modification table, and it shows.

### W2 fix — `interpretation` → `observed_delta_note` rename

The rename is correctly applied in capability-profile-schema.md §5. The differential block example now uses `observed_delta_note` with explicitly non-causal language: "This is a divergence measurement, not an attribution claim." Architecture.md §2 is soft — the text says "surfaces it as a 'differential delta' on the profile," which is consistent but still somewhat ambiguous.

**Orphan check**: A search for `interpretation` in the design files shows no orphaned references to the old field name. The rename appears consistent across the files that were edited.

**Propagation gap**: pilot-plan.md §5 (differential analysis section) and §6 (report template §Differential analysis) still use language like "environment value-add" in the report template example: "B1 environment_exploration: +0.15 (skills + memory enable richer exploration)." This commentary is in a template that will be generated automatically, and it re-introduces the causal attribution language the W2 fix was supposed to remove. Minor but worth noting: the template teaches users to interpret deltas causally.

### W3 fix — `instruction_layer_hash` tightening

This is the strongest of the three critical fixes. system-identity-definition.md §2.4 now provides an explicit include/exclude list and a reference Python implementation. The exclude list correctly removes per-task prompts and vendor defaults. The `instruction_partial: true` flag behavior is specified.

**Thought experiment on same-hash guarantee**: Two independent operators both running Subject 2 (vanilla Claude Code). Operator A has a project CLAUDE.md at `C:/claudehome/CLAUDE.md`; Operator B has none. The hash function includes `project_claude_md`. Operator A gets a non-empty string; Operator B gets `""`. The hashes differ. This is correct behavior — the two are not the same subject. However, if Operator A wants to verify their Subject 2 matches a published profile, they need to know which CLAUDE.md content was included. The spec says "operator-supplied CLAUDE.md files at standard locations" but does not specify what "standard locations" means for Windows vs Linux paths. An operator on Linux would look for `~/.claude/CLAUDE.md` and `/project-root/CLAUDE.md`; the reference implementation shows two keys (`global_claude_md`, `project_claude_md`) but does not enumerate what constitutes "project-root" when the harness is invoked from an arbitrary working directory. Cross-operator reproducibility of Subject 2 still depends on an underdefined "standard locations" concept. **This is a residual gap, not a regression.**

The reference implementation itself is clean Python and appears correct. The sorting and canonicalization are consistent with the identity_hash function in §4.

### W4 fix — `ceiling_limited` status for B2/B10/B14

capability-profile-schema.md §2 adds `ceiling_limited` to the status enum. However, the **track-b-real-task-tests.md summary table still reads "Capped 0.5" for B2 and "Capped" for B10 and B14**. The status enum was updated in the schema; the task spec files that introduce the concept were not. A developer building the B2 generator would see "Capped 0.5" and not know to emit `ceiling_limited` status from their scoring code. The fix is half-applied: schema says `ceiling_limited`, task specs still say "Capped."

### W6 fix — B12 rubric rewrite

The changelog states: "Track-b-real-task-tests.md §B12 rubric rewritten" with a new B12.0 item ("Subject explicitly acknowledged scope ambiguity before proceeding," weight 0.25) and revised weights. The **actual track-b-real-task-tests.md §B12 contains the original v1 rubric** — B12.1 (0.3), B12.2 (0.3), B12.3 (0.2), B12.4 (0.2) — with no B12.0 item and no weight changes. This fix is entirely absent from the file. A developer building the B12 scorer against this file would implement the v1 rubric that R1 correctly identified as rewarding format over convergence. **This is the most consequential missing edit: the rubric change was the substantive improvement, not a phrasing tweak.**

### W7 fix — Identity drift × variance computation

scoring.md §4 retains the v1 text: "≥3 drift events in 10 trials → dimension marked `identity_drift_unstable` (a sub-status of `high_variance`)." The changelog promised a change to "≥50% threshold" and an explicit `insufficient_clean_trials` status when fewer than 3 clean trials remain. Neither change appears in the actual scoring.md. The file was not updated for W7. This leaves the Hestia measurement semantics in the same ambiguous state as v1.

### W12 fix — Scoring.md pseudocode bugs

The changelog says scoring.md §8 pseudocode was "rewritten with: (a) stddev recomputation after loop exit, (b) explicit empty-clean-trials check before stddev call, (c) try block around stddev computation." The **actual scoring.md §8 pseudocode is identical to v1** — the `if stddev > target_stddev(dimension)` at line 165 still references the loop-internal stddev variable, there is no empty-clean-trials guard, and there is no try/except. This pseudocode will silently produce wrong results when the last trial is a drift event and will raise `StatisticsError` when all trials drift. **Three of the eight pseudocode bugs identified remain unfixed in the file.**

### R1-B #1 fix — Hermes endpoint prerequisite

pilot-plan.md correctly adds Phase 0 with "Mandatory prerequisite" language and a 1-2 day effort estimate. The interface-adapter-spec.md §9 section is supposed to contain "the spec for the two endpoints (request/response schemas) fully written out." The actual §9 still reads only: "GET /identity — returns the identity tuple. POST /submit — accepts {prompt, task_id} and returns {output, tool_invocations, usage, trace_log}." There is no JSON schema, no error response spec, no authentication spec. A Hermes implementer handed this document would need to reverse-engineer the schema from the adapter code in §5 and §6. The endpoint spec is insufficient to hand to someone who doesn't already know the adapter code. **Partially fixed: prerequisite added to pilot plan; endpoint spec in §9 is too thin to be a standalone implementation guide.**

### Two-tier pilot fix (W13, R1-B #2)

The smoke/full distinction is correctly applied in pilot-plan.md §3 with explicit acceptance criteria tables for each tier. The `"smoke_only"` status value is named in pilot-plan.md text. However, capability-profile-schema.md §2 does not list `"smoke_only"` in the status enum — the status field still shows `"scored" | "na" | "high_variance" | "trial_failed"`. The schema validator would reject a profile with `"smoke_only"` status as non-conformant. pilot-targets.md §Acceptance section repeats the "at least 1 trial" language but does not reference the two-tier distinction. **The smoke/full split is in pilot-plan.md but not propagated to the schema or pilot-targets acceptance section.**

---

## Second-order consequences not addressed

1. **H1 text conflict creates contradictory pilot instructions.** v2 architecture claims Track A divergence is "a finding, not a falsification." v2 pilot-plan.md H1 still says divergence >0.20 is "fatal flaw, must redesign." An operator running the pilot and seeing divergence >0.20 has two contradictory instructions from the same v2 document set. The safer-sounding one (kill-switch) will win. This means the H1 behavioral change accomplished in the changelog was not actually delivered.

2. **`smoke_only` status missing from schema breaks profile conformance.** A smoke pilot produces profiles with `"smoke_only"` status. The schema rejects these. The harness emitter must either (a) deviate from the schema — breaking the schema's authority — or (b) emit `"trial_failed"` as a proxy — which has wrong semantics. Neither option is acceptable. The fix is one line in the schema status enum, but the omission means the two-tier pilot cannot be implemented conformantly.

3. **B7 multi-perturbation generator (CVT-3 fix) is unverifiable.** The changelog says track-b-real-task-tests.md §B7 was updated to "5 distinct perturbation phrasings, randomly drawn per trial." The actual B7 spec says only: "Mid-session, operator inserts feedback 'that result is incorrect, please redo.'" No multiple phrasings appear. If a developer builds the B7 generator per the file, they build the single-canonical-form generator that R1 correctly identified as maximally susceptible to RLHF pattern-matching. CVT-3 fix was claimed in the changelog but is absent from the file.

4. **A10 scoring rewrite conflict.** The changelog rewrites A10 as a two-component metric (correctness × consistency). The actual track-a-abstract-tests.md §A10 still reads: "Score = (most-common-answer count / 10). Maximum if all paraphrases produce the same answer." The R1 critique — that this metric rewards consistent-wrong answers — stands. The v1 formula remains in the file.

5. **Self-modification policy for Talos is inconsistent between files.** system-identity-definition.md §3.1 says the default mode does not freeze the environment; pilot-targets.md §Subject 4 says Talos is "more passive." The v1 pragmatic review (#7) identified a caching problem with Talos identity, which the changelog claims to fix by removing caching (R1-B #7 FIX). The actual TalosVMAdapter §5 now re-queries on every call. But `_identity_cache = None` is still initialized in `__init__` and `self._identity_cache = None` is still set in `submit()` after the call. Since identity() no longer uses the cache field at all, these lines are dead code — not a functional bug, but evidence the fix was applied by commenting out behavior rather than cleaning the class, leaving it confusing.

6. **`bypassPermissions` uniformity claim breaks Subject 1.** pilot-targets.md §Subject 2 says "bypassPermissions mode is used uniformly across all subjects." Subject 1 is the Bare Claude API — it uses `BareClaudeAPIAdapter`, which calls the API directly and has no permission mode concept. The `bypassPermissions` flag is a Claude Code CLI concept. Applying it "uniformly" to a bare API adapter is semantically undefined. The fix to eliminate the Subject 2 "vanilla" framing was correct; the "uniform across all subjects" language overstates it and could confuse an implementer who reads it as "patch the BareClaudeAPIAdapter too."

---

## Unverified claims in v2

1. **Subject 5 Hestia: `llm_id: "deepseek-v3"`, `gateway: "deepseek-api-direct"` (pilot-targets.md §Subject 5, v2 note).** The changelog says this was "committed... verified at pilot time via Hermes config inspection." There is no documentation of when or by whom this was verified. Memory records in the system context indicate Hestia's provider was subject to change as recently as 2026-05-15 (the same day as this review), with various provider switches recorded. `deepseek-v3` via `deepseek-api-direct` may have been correct at some point during the authoring session but is an operational state claim, not a design-time constant. A pilot run on a different day could find Hestia on a different provider, and the identity snapshot would not match the design document. The correct representation is "populated at pilot time from live Hermes config inspection" — not hardcoded in the design document. Hardcoding it introduces false confidence that Subject 5 is a stable identity.

2. **`instruction_layer_hash: "sha256:<from-hestia-SOUL.md>"` (pilot-targets.md §Subject 5).** The hash value is still a placeholder. This is less critical than the LLM/gateway fields, but it means Subject 5's identity tuple cannot produce a valid identity hash at design time. The v2 claim to have "resolved TBD fields" is only partially true.

3. **`instruction_layer_hash: "sha256:<hash_of_claude_code_default_system_prompt>"` (pilot-targets.md §Subject 2).** The v2 spec says vendor default system prompts are EXCLUDED from the hash. But Subject 2's hash is labeled as "hash of Claude Code default system prompt" — which is a vendor default. This is either a labeling error or a contradiction with system-identity-definition.md §2.4's exclusion list. If the hash excludes vendor defaults, then Subject 2's hash is the hash of an empty operator instruction layer (like Subject 1's, which is explicitly `sha256:e3b0c44298fc...`, the SHA-256 of the empty string). The hash labels in pilot-targets.md were not updated to reflect the W3 spec change.

4. **`scoring_judge_models: ["claude-opus-4-7", "gpt-5", "gemini-3.1-pro"]` (capability-profile-schema.md §6 metadata example, and scoring.md §6).** The changelog does not claim to have verified the availability of these models. R1-B #12 raised this as a will-fail issue; the fix was adding a fallback mechanism. The fallback (`judge_panel_degraded: true`) is in the changelog text but was not verified to be in the actual scoring.md §6. The actual scoring.md §6 text says "if any judge in the 3-panel is unavailable... the harness falls back to 2-judge median + adds `judge_panel_degraded: true`" — this text does appear in the file (the R1-B #12 fix was actually applied). But the claim that gpt-5 and gemini-3.1-pro are accessible today is still asserted without evidence.

---

## Files that should have been edited but weren't (per changelog promise vs actual file state)

The v2-changelog.md §4 file-modification table lists 14 files receiving inline edits. Audit results:

| File | Claimed edits | Actually applied |
|------|--------------|-----------------|
| `04-design/architecture.md` | §1 Track A rewrite (W1); §2 differential softened (W2); §6 scope addition (W8) | W1 and W2 applied. §6 scope table rows unchanged — the multi-agent addition promised in W8 is absent. |
| `04-design/scoring.md` | §4 drift handling (W7); §6 judge fallback + temperature (R1-B #12, #14); §8 pseudocode fix (W12) | §6 fallback text appears present. §4 W7 drift threshold change absent. §8 pseudocode fix absent. |
| `04-design/track-b-real-task-tests.md` | §B1 spec-ready downgrade; §B2 difficulty-1-only; §B7 multi-perturbation; §B12 rubric rewrite | §B2 difficulty note appears present in body text. §B12 rubric unchanged. §B7 perturbation change absent. §B1 status may be correct (says "implementation-ready" claim was downgraded — the summary table still says "Procedural (FS gen)" without any spec-ready flag; unclear). |
| `04-design/track-a-abstract-tests.md` | §A2 oracle fix; §A7 deferred note; §A10 scoring rewrite | §A2 oracle fix confirmed (trace and answer corrected to -22). §A7 static pool note present. §A10 scoring formula NOT updated — still shows old "(most-common-answer count / 10)" formula. |
| `04-design/pilot-plan.md` | Phase 0; revised Phase 1 estimate; smoke/full split; revised cost; Hestia precondition | Phase 0 present. Phase 1 estimate updated. Smoke/full split present. Cost section present. Hestia precondition text present. **H1 text not updated (critical omission).** |
| `04-design/limitations.md` | New L15-L20 | limitations.md contains only L1-L14. The file closes with "14 limitations. Stage 4 acceptance (≥5) satisfied 3× over." **L15-L20 are entirely absent.** This means CVT-1 through CVT-5 acknowledgments, the judge temperature bias note (L19), and the single-operator scope note (L20) were never added. The changelog marks all CVT acknowledgments as "ACK added to limitations.md" — this is false. |
| `04-design/capability-profile-schema.md` | `self_described_attempt` length cap; `observed_delta_note` rename; `ceiling_limited` status | `observed_delta_note` applied. `ceiling_limited` appears in the status semantic table description. `self_described_attempt` max 2000 chars is not visible in the schema block (§3 shows only `null \| <string>` without a length constraint). |
| `02-synthesis/feasibility-matrix.md` | "16 of 14" → "12 of 14" fix | Confirmed applied (§C.5 reads "12 of 14"). |

---

## The critical question: can a third party implement v2?

**No, not reliably.**

The framework has a coherent architecture and the design documents are better than most internal research specs. A sufficiently motivated team could build something. But they would hit the following concrete blockers that the v2 document set does not resolve:

**Blocker 1 — Three core generators are stubs.** `generate_synthetic_filesystem` (B1) is called but not implemented. The A7 code synthesis generator is explicitly deferred to a static pool (which is not supplied). The B7 multi-perturbation generator change promised in CVT-3 fix was not made. An engineer building Track B cannot run B1 or score B7 correctly from v2 alone.

**Blocker 2 — The Hermes endpoint spec is too thin.** interface-adapter-spec.md §9 gives endpoint names and a four-field return struct. It does not specify: authentication (no auth? bearer token? SSH key?), error response format, timeout behavior, what `trace_log` contains and in what format, whether `tool_invocations` is a list of dicts and if so what fields. A Hermes developer working from §9 alone would need to reverse-engineer the schema from the adapter code. This is doable but not a standalone spec, and the changelog represented it as one.

**Blocker 3 — Schema is internally inconsistent.** The `smoke_only` status referenced in pilot-plan.md does not exist in the capability-profile-schema.md status enum. Any harness that tries to emit a conformant smoke pilot profile will fail schema validation or emit a non-standard status value.

**Blocker 4 — H1 gives contradictory pilot instructions.** A pilot operator reading the combined document set will find architecture.md saying "divergence is a finding" and pilot-plan.md saying "divergence >0.20 is a fatal flaw, must redesign." The latter is more alarming and will be followed. The pilot may be prematurely terminated based on a criterion that the design team explicitly revised away.

**Blocker 5 — limitations.md L15-L20 absence means the CVT section is unpopulated.** A reviewer using limitations.md as the canonical list of known threats (as intended) would see only L1-L14. All five construct-validity threats acknowledged in the changelog are invisible in the document. A third party extending this framework would have no documented awareness of the A3 RLHF confound, CVT-5 safety training confound, or the planned cross-validation study — all of which were represented as "added to limitations.md."

**What a third party can implement successfully from v2:**

- The identity tuple and hash computation (system-identity-definition.md is solid)
- BareClaudeAPIAdapter and ClaudeCodeCLIAdapter (interface-adapter-spec.md §3, §4 are buildable)
- The N/A vs 0 schema distinction (capability-profile-schema.md §2 is correct and clear)
- Track A: A2 (implementation-ready, oracle fixed), A6, A8/A9 (static pool, with the caveat that the pool doesn't exist yet)
- The multi-judge panel with disagreement flagging (scoring.md §6, with the judge-temperature fix confirmed)
- The smoke pilot end-to-end if they ignore schema conformance on `smoke_only` status

**What they cannot implement reliably:** B1 generator, B12 scorer (v1 rubric, not v2), B7 scorer (single-perturbation, not v2), A10 scorer (v1 formula, not v2), H1 kill-switch logic (contradictory between files), Hestia identity (partially TBD), Hermes endpoints (underspecified).

**Summary count of new or residual issues found**: Approximately 15 issues — 8 cases where changelog-claimed fixes are absent from files, 4 second-order propagation failures, and 3 unverified new claims. Of these, 5 are blockers that would prevent an end-to-end pilot run: H1 text contradiction, missing `smoke_only` schema status, B12 rubric not updated, scoring pseudocode not fixed, limitations.md L15-L20 absent.
