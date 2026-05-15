# Stage 4.3 — Capability Profile Schema

> Answers DQ-2 (N/A vs 0), DQ-7 (bare-LLM Track B reporting), DQ-11 (cost/latency unit), DQ-12 (Pareto vs point).

---

## 1. Top-level structure

A capability profile is a JSON document with four sections:

```json
{
  "schema_version": "1.0",
  "subject": { ... identity tuple from system-identity-definition.md ... },
  "tracks": {
    "A": { ... track-A dimensions ... },
    "B": { ... track-B dimensions ... },
    "C": { ... track-C operational ... }
  },
  "differential": { ... pairwise divergence vs other subjects in run ... },
  "metadata": { ... run timestamp, harness version, task pool versions, etc. ... }
}
```

---

## 2. Per-dimension score block

Every dimension score uses this exact shape:

```json
{
  "score": <float in [0,1]> | null,
  "stddev": <float> | null,
  "n_trials": <int>,
  "trials_used": <int>,           // ≤ n_trials, excludes drifted/invalid
  "status": "scored" | "na" | "high_variance" | "trial_failed",
  "na_reason": null | "interface_lacks_affordance" | "B13_not_opted_in" | "<other>",
  "self_described_attempt": null | <string>,
  "failure_modes": [<string>, ...],
  "trial_ids": [<uuid>, ...]
}
```

**Status semantics** (answers DQ-2 and DQ-6; v3 adds `smoke_only`, `ceiling_limited`, `insufficient_clean_trials`):

| Status | Meaning | `score` field |
|--------|---------|---------------|
| `"scored"` | Successfully measured at full trial count with variance under target | float ∈ [0,1] |
| `"smoke_only"` (v3) | Single-trial pilot — score exists but no variance estimate. Use for smoke pilot only. | float ∈ [0,1], stddev null |
| `"na"` | Not applicable — interface lacks affordance or test mode not run | `null` |
| `"high_variance"` | Trials completed but stddev > threshold; signal insufficient | `null` |
| `"insufficient_clean_trials"` (v3) | After drift-filtering, fewer than 3 clean trials available | `null` |
| `"ceiling_limited"` (v3 — per R1-A W4) | Score bounded above by architectural ceiling, not capability ceiling. `score` reports the empirical observation; `ceiling_value` reports the structural maximum the subject can achieve. | float ∈ [0,1], plus `ceiling_value` field |
| `"trial_failed"` | All trials errored at harness level (not subject failure) | `null` |

**Critical rule**: When `status != "scored"`, the `score` field is **strictly `null`**, never `0`. Visualization libraries must distinguish `null` (gray bar, "N/A" label) from `0.0` (filled bar at zero, "tried and failed" label). A profile renderer that maps null to 0 is non-conformant.

---

## 3. Bare-LLM Track B reporting (answers DQ-7)

For bare-LLM subjects on Track B dimensions where interface lacks affordance, we adopt the user-recommended Option (b) from DQ-7: collect self-described attempt as metadata, do NOT score it.

```json
{
  "B1_environment_exploration": {
    "score": null,
    "stddev": null,
    "n_trials": 3,
    "trials_used": 0,
    "status": "na",
    "na_reason": "interface_lacks_affordance",
    "self_described_attempt": "I would use the `ls` command recursively from the root, then grep for filename pattern 'X' across all subdirectories...",
    "failure_modes": [],
    "trial_ids": []
  }
}
```

The `self_described_attempt` is informative — it shows whether the bare LLM at least understands what the task would require — but is not part of the score. Downstream analysis can use this for "planning-only competence" comparisons.

---

## 4. Track C — operational block (answers DQ-11, DQ-12)

```json
{
  "C1_cost_per_task": {
    "median_input_tokens": 1247,
    "median_output_tokens": 893,
    "median_reasoning_tokens": 142,
    "median_usd_at_report_time": 0.087,
    "price_table_version": "2026-05-15",
    "p95_total_tokens": 4520
  },
  "C2_latency_seconds": {
    "median_wall_clock_s": 14.2,
    "median_llm_call_s": 9.7,
    "p95_wall_clock_s": 38.4
  },
  "C3_reliability_pass_at_k": {
    "k": 5,
    "pass_rate_per_task": [
      {"task_id": "...", "pass_at_5": 0.8, "pass_at_1": 0.4},
      ...
    ],
    "aggregate_pass_at_5_mean": 0.72
  },
  "C4_adapter_complexity": {
    "loc_total": 38,
    "loc_excluding_imports": 31,
    "external_deps_count": 2
  },
  "C5_failure_modes": {
    "<category>": <count_across_trials>,
    "scope_creep_mid_task": 3,
    "infinite_loop": 0,
    "refusal_when_shouldnt": 1
  },
  "C6_test_retest": {
    "intra_session_stddev_mean": 0.067,
    "between_session_stddev_mean": 0.083,
    "dimensions_meeting_threshold": 22,
    "dimensions_below_threshold": 3
  },
  "C7_identity_stability": {
    "hash_at_start": "sha256:7c3f...",
    "hash_at_end": "sha256:7c3f...",
    "drift_count": 0,
    "drifted_trials": []
  }
}
```

**DQ-11 — Cost unit**: Primary unit is **tokens** (input + output + reasoning, separately). Secondary unit is **USD computed at report time** using a static price table whose version is recorded. This way USD numbers don't silently drift as vendors change prices.

**DQ-12 — Pareto vs point**: Default is **single point** at the subject's nominal operating configuration. For subjects with explicit cost-capability dials (Claude Code `--effort`, o-series reasoning level), an optional `pareto_points` field can be populated by running the full track at multiple operating points:

```json
{
  "pareto_points": [
    {"effort": "low",    "track_b_b9_score": 0.42, "cost_usd": 0.02},
    {"effort": "medium", "track_b_b9_score": 0.61, "cost_usd": 0.08},
    {"effort": "high",   "track_b_b9_score": 0.78, "cost_usd": 0.31}
  ]
}
```

Pareto sweeps cost ≥5× single-point evaluation; opt-in only.

---

## 5. Differential block

```json
{
  "differential": {
    "reference_subjects": ["bare_claude_api", "claude_code_vanilla", "claude_code_full"],
    "shared_llm_id": "claude-opus-4-7",
    "delta_per_dimension": {
      "A1_pattern_reasoning": {
        "this_subject": 0.82,
        "ref_bare_claude_api": 0.85,
        "ref_claude_code_vanilla": 0.83,
        "ref_claude_code_full": 0.82,
        "max_pairwise_delta": 0.03,
        "observed_delta_note": "Observed delta vs reference subjects is within ±0.05 — consistent with environment-invariant abstract scoring, but not a causal claim."
      },
      "B11_multi_file_mutation": {
        "this_subject": 0.91,
        "ref_bare_claude_api": null,
        "ref_claude_code_vanilla": 0.78,
        "ref_claude_code_full": 0.85,
        "max_pairwise_delta": 0.13,
        "observed_delta_note": "Observed delta vs vanilla CLI: +0.13. This is a divergence measurement, not an attribution claim. Identifying which identity-tuple field contributed requires controlled ablation studies (out of scope for v1)."
      }
    }
  }
}
```

**v2 note (response to R1-A W2)**: v1 used a field named `interpretation` with text like "environment value-add is +0.13," which over-claimed causal attribution. v2 renames the field to `observed_delta_note` and removes causal language. The differential block reports divergence; attribution requires controlled ablation (varying one identity field at a time, e.g., adding one skill to Subject 2 to produce Subject 2.1), which is documented as future work in limitations.md.

The differential block exists only when ≥2 subjects in the run share `llm_id` AND both subjects have `single_agent_top_level: true` in their identity metadata. Multi-agent systems with matching top-level LLM IDs are excluded from automatic differential computation since their LLM ID is misleading as a comparison anchor.

---

## 6. Metadata block

```json
{
  "metadata": {
    "harness_version": "v1.0",
    "run_id": "uuid",
    "run_started_at": "2026-05-15T14:22:00Z",
    "run_ended_at": "2026-05-15T16:48:30Z",
    "task_pool_version_a": "2026-05-A.3",
    "task_pool_version_b": "2026-05-B.1",
    "task_generator_seeds": {"a1": 423, "a2": 891, ...},
    "scoring_judge_models": ["claude-opus-4-7", "gpt-5", "gemini-3.1-pro"],
    "operator": "Hang",
    "notes": "Pilot run #1; opcode-go gateway test"
  }
}
```

`task_generator_seeds` is critical for reproducibility — re-running the same seed regenerates the same procedural tasks, allowing variance to be decomposed into "task-source variance" vs "subject-source variance."

---

## 7. Visualization spec

The default profile visualization is a **horizontally stacked radar / bar chart** with:

- Track A dimensions in the top group (blue/cool palette)
- Track B dimensions in the middle group (green/warm palette)
- Track C operational on the right (text + small inline charts)
- N/A bars rendered in **gray with diagonal hatching**; never zero-height
- Variance bands rendered as ±stddev whiskers on the score bar
- Differential subjects overlaid as transparent ghost-bars when available

A minimum-viable text profile (for CI / log embedding) is also defined:

```
Subject: <identity_hash[:8]> (Talos / Claude Opus 4.7 / Hetzner CX23)
Track A (abstract):
  A1  pattern_reasoning      0.82 ± 0.04
  A2  working_memory         0.70 ± 0.06
  ...
Track B (applied):
  B1  environment_explore    0.91 ± 0.05
  B2  long_horizon_plan      N/A (interface_lacks_affordance)
  ...
Track C (operational):
  cost: 1247 in / 893 out / 142 reasoning tokens median, $0.087 median
  latency: 14.2s median wall-clock
  adapter: 38 LOC, 2 external deps
  failure modes: scope_creep×3, refusal_when_shouldnt×1
```

This text profile is the canonical output for CLI consumers; the JSON is the canonical machine format; the chart is a derived rendering.
