# Stage 4.10 — Pilot Plan

> End-to-end pilot execution: from harness initialization to comparative report. The pilot is the v1 deliverable; full evaluation (N=5 trials all dimensions) is v1.1.

---

## 1. Pilot scope (minimum viable demonstration)

A pilot run produces, for each of the 5 mandatory subjects:

- Identity snapshot recorded.
- At least one trial per applicable dimension (Track A, B, C).
- A capability profile JSON.
- A text-format profile for log inclusion.

And, at the run level:

- A differential block linking subjects 1-2-3 (shared LLM).
- A comparative report `pilot-report.md` summarizing the five profiles.
- A run log (`pilot.log`) capturing all trial-level events.

---

## 2. Phases

### Phase 1 — Harness setup (one-time, before any pilot run)

1. Build the harness: implement the SystemAdapter protocol from interface-adapter-spec.md, the four example adapters, the task generators for Track A dimensions A1, A2, A6, A7 and Track B B1 (the implementation-ready ones).
2. Build the scoring engine: rubric evaluator, 3-judge median + disagreement flagger, variance tracker, failure-mode tagger.
3. Build the reporting subsystem: JSON profile emitter, text profile renderer.
4. Run the 3-task adapter smoke suite (interface-adapter-spec.md §7) for each of the 5 adapters.
5. Pre-warm the 30% static held-out pool: confirm items available + uncontaminated.

**Estimated effort**: 3-5 days for one engineer. Out of scope for this research document; this phase is harness implementation.

### Phase 2 — Dry-run (validation-only, no scoring)

For each subject, run a single Track A2 task (working memory, difficulty 2) end-to-end:

- Verify adapter `identity()` returns valid tuple
- Verify `submit()` returns Trace with all fields populated
- Verify `cost()` produces non-zero numbers
- Verify scoring engine processes the trace
- Verify profile JSON is well-formed

This is the **dry-run acceptance gate**. Pilot does not proceed past Phase 2 until all 5 subjects pass.

### Phase 3 — Track A pilot

For each subject, for each Track A dimension (A1-A11):

- Draw 1 task at difficulty 3 (mid-range).
- Run via adapter.
- Score.
- Record cost + latency.
- Update profile.

11 dimensions × 5 subjects = 55 trials. Each trial budget: <60s wall-clock, <5000 input tokens, <2000 output tokens.

**Expected cost**: ~$5-15 USD total across all subjects.

### Phase 4 — Track B pilot

For each subject (excluding bare LLM where N/A applies), for each Track B dimension applicable:

- Draw 1 task at difficulty 2.
- Run via adapter.
- For dimensions where the subject's interface lacks affordance, mark N/A and (optionally) collect self-described attempt.
- Score.
- Update profile.

Approximate trial count: 14 dimensions × 4 non-bare subjects = 56 trials (with N/A handling for B-track items the subject can't run).

**Expected cost**: ~$30-100 USD (Track B tasks are heavier — repo cloning, long sessions for B2/B14).

**Skip in pilot**: B10 (MLE-Bench-Lite — too expensive) and B13 (self-evolution — opt-in only, requires ≥6h). These run only in dedicated full-evaluation runs.

### Phase 5 — Differential computation + report

1. For each pair of subjects sharing `llm_id` (subjects 1-2, 1-3, 2-3): compute pairwise delta per dimension.
2. Generate `pilot-report.md` with:
   - Side-by-side profile cards for all 5 subjects.
   - Differential analysis section: "Same Claude Opus 4.7 + different environment yielded these dimension deltas..."
   - Track C cross-subject comparison (cost / latency / failure modes).
   - Any anomalies flagged (e.g., identity drift events, high-variance dimensions).
3. Commit profile JSONs, text profiles, and report.

---

## 3. Pilot acceptance criteria

A pilot is **PASSED** when:

| Criterion | Required value |
|-----------|---------------|
| All 5 subjects adapters pass smoke suite | yes |
| Track A: ≥1 valid scored trial per dimension per subject (where applicable) | yes |
| Track B: ≥1 valid trial per applicable dimension per subject | yes |
| Bare-LLM Subject 1 correctly produces N/A on ≥10 of 14 Track B dimensions | yes |
| Differential block populated for at least one Claude Opus 4.7 pair | yes |
| Comparative report generated and human-readable | yes |
| Total pilot wall-clock | < 12h |
| Total pilot cost | < $200 USD |

A pilot is **FAILED** when any of:
- An adapter cannot pass smoke suite (interface issue; not a framework bug).
- Track A scores diverge significantly (>0.20) on Subjects 1, 2, 3 — would invalidate the environment-isolation hypothesis; halt pilot and revisit framework assumptions.
- Identity-drift exceeds 50% of trials on a non-Hestia subject (signals harness instability).

---

## 4. Hypotheses being tested by the pilot

1. **H1 — Environment isolation**: Subjects 1, 2, 3 (same LLM, different env) score within ±0.05 on Track A. **Falsification**: divergence >0.20 means framework conflates LLM with environment on Track A — fatal flaw, must redesign.

2. **H2 — Environment value-add quantifiable**: Subject 3 - Subject 2 differential on Track B B11 (multi-file mutation) is >0.10. **Falsification**: indifference would suggest skills/MCP/CLAUDE.md add no measurable Track B capability — surprising and worth investigating.

3. **H3 — Bare LLM Track B handling**: Subject 1 reports N/A (not 0) on ≥10 of 14 Track B dimensions, and `self_described_attempt` is non-empty on ≥3. **Falsification**: 0-scoring would mean profile schema is implemented incorrectly.

4. **H4 — Test-retest stable for static subjects**: Subjects 1, 2, 4 (non-self-modifying) show identity_drift_count = 0 across pilot. **Falsification**: any drift in supposedly-static subjects reveals a measurement bug in identity-hashing.

5. **H5 — Hestia drift visible**: Subject 5 (Hestia) shows identity_drift_count > 0 across the pilot. **Falsification**: zero drift means Hestia is more static than HANDOFF.md suggests, or our detection is undersensitive.

---

## 5. Operational logistics

**Operator**: Hang (initial pilot) or any future operator who follows the runbook.

**Environment**: Operator's local machine for Subjects 1-3 + Subject 5 (Hestia VM is local); SSH-reachable Hetzner CX23 for Subject 4 (Talos).

**Cost authority**: Operator approves before Phase 3 starts (estimated total $200; budget cap enforced by harness — abort if running cost exceeds $250).

**Time window**: Pilot designed to complete in 1 working day. Phase 1 (harness build) is a separate 3-5 day effort that precedes any pilot run.

**Notification**: On completion, harness emits a summary to operator-specified channel (`notify_channel` config — recall plan §6.1 of v1 acknowledged we don't hardcode this).

---

## 6. Pilot report template

`pilot-report.md` (generated automatically; structure here for reference):

```markdown
# Pilot Run <date> — Capability Profile Comparison

## Subjects
- subject 1: bare-claude-api (identity hash X)
- subject 2: claude-code-vanilla (Y)
- ... (5 total)

## Profile summary table (Track A)
| Dimension | Subj 1 | Subj 2 | Subj 3 | Subj 4 | Subj 5 |
| A1 ... | 0.82±0.04 | 0.83±0.04 | 0.82±0.05 | 0.81±0.06 | 0.78±0.07 |
| ... |

## Profile summary table (Track B)
... (N/As distinct from 0s) ...

## Track C summary
... (cost, latency, adapter complexity, failure modes per subject) ...

## Differential analysis
- Subjects 1, 2, 3 share LLM. Track A delta < 0.05 across all
  dimensions (hypothesis H1 supported / not supported).
- Subject 3 - Subject 2 on Track B:
   * B1 environment_exploration: +0.15 (skills + memory enable richer exploration)
   * B11 multi-file mutation: +0.13 (CLAUDE.md instructs cross-file alignment)
   * ...

## Anomalies
- Subject 5 identity_drift events: N (...detail per drift...)
- Dimensions marked high_variance: ...
- Adapters that exceeded LOC cap: ...

## Hypotheses outcomes
H1: <supported / not supported>
H2: ...
H3: ...
H4: ...
H5: ...

## Open questions for v2
- ...
```

---

## 7. Post-pilot deliverables

After pilot completion, the framework should produce, in addition to the report:

- All trial-level JSONs (for re-analysis and debugging).
- All adapter source files (under `adapters/` directory).
- The exact task pool versions and generator seeds used (for reproducibility).
- A short engineering retrospective from the operator on adapter ergonomics — feeds into v2 adapter spec.
