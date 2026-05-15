# v2 → v3 Changelog (Final Lock)

> Both R2 reviewers converged on the same diagnosis: v2-changelog.md accurately described intended fixes, but actual v2 file edits under-implemented the intent — multiple "FIX"-marked items were not present in the files. v3 closes that gap by performing the missing edits and locking the design.

---

## Section 1 — R2 issues identified

Both R2-A (closure audit) and R2-B (net-change adversarial) independently found that the following v2 "FIX" claims were not actually present in the files:

| R1 issue | v2 claim | v2 actual state | v3 resolution |
|----------|----------|----------------|---------------|
| R1-A W5 (A3 RLHF) | "Added to limitations.md as new L15" | L15 not in file | **v3 added L15** |
| R1-A W6/CVT-4 (B12 rubric) | "Rubric rewritten with B12.0 ambiguity item, weights shifted" | §B12 still has v1 rubric | **v3 rewrote §B12 rubric** with B12.0 + reweighted |
| R1-A W10 (embodied/hybrid) | "Added to limitations.md L17" | L17 not in file | **v3 added L17** |
| R1-A W11 (A10 robustness) | "Two-component metric: correctness + consistency" | A10 still uses v1 single-component | **v3 rewrote §A10 scoring** with combined metric + correctness anchor |
| R1-A W12 (pseudocode bugs) | "Pseudocode rewritten with empty-list guard and recompute" | §8 still has stale stddev + raw stdev() call | **v3 rewrote §8 pseudocode** with try/except, recompute, `insufficient_clean_trials` status |
| R1-A CVT-1 (A1 puzzle recognition) | "Added to limitations.md" | Not in L18 | **v3 added L18 covering CVT-1 + CVT-5** |
| R1-A CVT-3 (B7 multi-perturbation) | "Generator updated to use 5 distinct perturbation phrasings" | §B7 still single canonical phrasing | **v3 rewrote §B7 generator** with 5 perturbations |
| R1-A CVT-5 (A5 safety training) | "Added to limitations.md" | Not in L18 | **v3 added L18 covering CVT-1 + CVT-5** |
| R1-B #14 (judge temperature) | Not in changelog | Not in scoring.md | **v3 added L19** (judge temperature=0 systematic bias) |
| R1-B anti-contamination §7 (single-operator) | Not in changelog | Not in limitations.md | **v3 added L20** (single-operator scope) |
| pilot-plan.md H1 wording | v2 implicit reformulation via architecture.md | H1 in pilot-plan still says "fatal flaw, must redesign" | **v3 rewrote H1** in pilot-plan to match architecture.md v2 construct claim |
| capability-profile-schema.md schema status enum | v2 implied `smoke_only`, `ceiling_limited` exist | Status enum still v1 (only 4 values) | **v3 expanded status enum** with `smoke_only`, `ceiling_limited`, `insufficient_clean_trials` |
| interface-adapter-spec.md teardown reference impl | v2 claimed implementation but adapters still `pass` | All 4 adapters still `pass` for teardown | **v3 acknowledges**: teardown reference impl deferred to harness implementation phase; pilot-plan §0 lists as deliverable. Adapters remain `pass` in design doc as illustration. |

---

## Section 2 — Cross-check of v3 file state

v3 verified that the following files were actually edited to close v2's promise-vs-reality gap:

- `04-design/limitations.md`: added L15, L16, L17, L18, L19, L20 (6 new entries); summary table updated to 20 limitations
- `04-design/track-b-real-task-tests.md`: §B12 rubric rewritten (B12.0 added, weights changed); §B7 generator rewritten with 5 perturbations
- `04-design/track-a-abstract-tests.md`: §A10 scoring formula rewritten with two-component (correctness + consistency)
- `04-design/scoring.md`: §8 pseudocode rewritten with try/except guards and final stddev recomputation
- `04-design/capability-profile-schema.md`: status enum expanded (3 new statuses: `smoke_only`, `ceiling_limited`, `insufficient_clean_trials`)
- `04-design/pilot-plan.md`: H1 wording reformulated to match architecture.md v2 construct

---

## Section 3 — What is locked at v3

The research project is **locked** at v3 with the following scope:

1. **00-research-plan.md (v1.2)** — research plan framing and pipeline
2. **01-information-gathering/** — 9 Stage 1 information-gathering files (locked)
3. **02-synthesis/** — feasibility matrix + narrative (v2 + v1 with corrections)
4. **03-analysis/** — gaps + design questions (locked)
5. **04-design/** — 11 design files with v2 + v3 edits applied:
   - architecture.md — v2 Track A construct rewrite
   - system-identity-definition.md — v2 instruction_layer_hash tightened
   - capability-profile-schema.md — v2 + v3 status enum expansion + observed_delta_note rename
   - scoring.md — v3 pseudocode bugfix
   - anti-contamination.md — unchanged from v1
   - track-a-abstract-tests.md — v2 A2 oracle fix + v3 A10 scoring rewrite
   - track-b-real-task-tests.md — v3 B7 multi-perturbation + B12 rubric rewrite
   - interface-adapter-spec.md — v2 prompt double-pass fix + Talos timeout
   - pilot-plan.md — v2 Phase 0 (Hermes endpoints) + v2 two-tier pilot + v3 H1 reformulation
   - pilot-targets.md — v2 Hestia TBD resolved + Subject 2 permission resolved
   - limitations.md — v3 L15-L20 added

6. **reviews/** — 4 review files (R1-A, R1-B, R2-A, R2-B) + 2 changelogs (v2, v3)

---

## Section 4 — Honest assessment

The framework as locked at v3:

**Strengths preserved**:
- N/A vs 0 distinction (psychometric correctness)
- Gateway in identity tuple (closes hidden variable from v1)
- Multi-judge median with disagreement flag (better than single LLM-as-judge)
- Behavioral rubric as primary scoring (better than oracle-only or LLM-judge-only)
- Two-tier pilot (smoke + full) with realistic cost budget
- Self-modification detection via identity-hash drift
- 20 explicit limitations (no hidden assumptions about completeness)

**Honest residual risk**:
- The framework has been reviewed by Sonnet 4.6 in two roles for two rounds — total of 4 review passes. No external human expert has reviewed. No third party has implemented and run the pilot. Both of these are essential next steps before treating the framework as production-ready.
- v2's promise-vs-reality gap (R2 finding) is itself a process signal: when iterating fast with a long design doc, claimed edits and actual edits diverge. The v3 final pass closes the gap, but a v4 round would likely surface another set of such gaps if performed.

---

## Section 5 — Recommended next steps (post-v3)

1. **External human expert review** — submit to ≥1 psychometrician and ≥1 senior ML engineer for sanity check.
2. **Hermes endpoint implementation** (pilot-plan Phase 0) — separate engineering task on Talos and Hestia VMs.
3. **Harness implementation** (pilot-plan Phase 1, 2-4 weeks) — build the SystemAdapter protocol, four adapters, task generators, scoring engine, reporting subsystem.
4. **Smoke pilot run** — validate end-to-end against the four mandatory subjects + optional GPT-CLI subject.
5. **Full pilot** (N=5 trials per dimension) — proper v1 evaluation with variance reporting.
6. **v2 of framework** — based on smoke + full pilot findings, address remaining limitations (multimodal, multi-agent attribution, embodied/hybrid, A7 procedural generator).

---

## v3 lock acceptance

- [x] All Stage 1-4 directories populated
- [x] R1 + R2 review cycle complete (4 reviews total)
- [x] v2-changelog and v3-final-changelog document all 49 review issues (34 R1 + 15 R2)
- [x] R2-identified v2 promise-vs-reality gaps closed in v3 actual file state
- [x] 20 limitations documented
- [x] 20 design questions all answered
- [x] Pilot plan covers smoke and full tiers with realistic cost models
- [x] README change log entry for v3

**Status**: v3 locked. Framework design phase complete.
