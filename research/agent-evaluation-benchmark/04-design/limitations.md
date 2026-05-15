# Stage 4.11 — Known Limitations

> Honest enumeration of what this framework cannot do or does not handle well. Acceptance requires ≥5 limitations; here we list 11 grouped by category.

---

## L1 (Construct-validity) Track A construct validity is not separable from instruction-tuning

Plan §1 says we measure "the system as deployed, which includes its instruction layer." This means the framework cannot answer "what is the underlying LLM's raw reasoning capability stripped of vendor RLHF?" The framework intentionally rejects that question — but users hoping to compare base models will be disappointed. They should look elsewhere (e.g., bare-base-model academic benchmarks).

---

## L2 (Construct-validity) Track B mixes "what the LLM contributed" with "what the env contributed"

Same-LLM-different-env pilots (Subjects 1-2-3) **partially** address this via differential, but cannot fully decompose. A score of 0.85 on B11 (multi-file mutation) on Subject 3 could reflect skilled LLM, well-designed scaffolding, helpful CLAUDE.md, or all three. The framework reports the deployed score and the differential; further decomposition is out of scope.

---

## L3 (Coverage) Multimodal capabilities (vision, audio, video) are deferred

Track A and Track B as currently specified assume text-and-tool-call interfaces. Vision-based reasoning (VisualWebArena-style), audio understanding, video are out of scope for v1. Subjects with vision capabilities (Anthropic Computer Use, OpenAI Operator) cannot fully express their capability through this framework's v1 dimensions.

---

## L4 (Coverage) Multi-agent / agent-of-agents systems are evaluated as their top-level interface

If an agent system internally orchestrates 3 sub-agents to solve a task, the framework only observes the top-level subject. Internal agent-to-agent coordination is invisible. Capabilities like "agent A correctly delegates to agent B" cannot be measured by this framework.

---

## L5 (Coverage) Human-in-loop interactions are not modeled

METR's RCT showed AI tools' real-world effect requires modeling the human's interaction patterns (perception-reality gap, validation overhead). The framework measures agent-alone capability. A "deployed system that is great when paired with a skilled developer but useless solo" looks identical to a "deployed system that is useless period" in our profiles.

---

## L6 (Operationalization) The 100-LOC adapter cap will exclude or penalize some systems

If a system requires 300 LOC of adapter to be testable, its `C4` adapter_complexity is reported as 300, which may discourage adoption. The framework explicitly states this is *information*, not a flag. But behaviorally, the cap creates an incentive against supporting hard-to-adapt systems.

---

## L7 (Operationalization) The 12h pilot budget is tight for full Track B + Track A across 5 subjects

We acknowledged in pilot-plan.md that the pilot is a minimum-viable demonstration (1 trial per dimension), not a full N=5 evaluation. The full evaluation is roughly 5× the cost and time. Operators who need rigorous statistics must commit to v1.1 scope, not pilot scope.

---

## L8 (Operationalization) Cost reporting in USD depends on a price table that goes stale

The `price_table_version` field documents the table used. But as soon as a vendor changes prices, historical USD numbers are no longer comparable to current ones. Tokens are more stable; USD is convenience that should not be over-trusted.

---

## L9 (Anti-contamination) The 30% static held-out pool will eventually leak

Even with 6-month rotation, sophisticated subjects may probe the framework over time and accumulate item knowledge. The procedural 70% provides defense-in-depth, but the static portion is structurally vulnerable to long-run contamination. Operators should monitor `contamination_suspected` flags and rotate aggressively if signals appear.

---

## L10 (Anti-contamination) Procedural generators themselves can leak

If an attacker examines the generator code and pre-computes solutions to all parameterized variants, the procedural pool is no longer procedural. We assume the generator code stays operator-private. This is weaker than cryptographic anti-contamination, which is out of scope for v1.

---

## L11 (Reliability) Self-modifying subjects cannot have stable test-retest scores

Hestia and similar self-evolving agents will produce different scores at run 1 vs run 2 by design. The framework reports this via `identity_drift_count`, but the variance is real and inherent. For Hestia-class subjects, "capability" is a moving target; the score is a snapshot, not a stable property.

---

## L12 (Reliability) 3-judge median introduces its own judge-family bias

We use claude-opus-4-7, gpt-5, and gemini-3.1-pro for the multi-judge panel. These are the three frontier model families, but they share many training data sources. A cultural/topical bias common to all three would not be caught by the disagreement-flagger. Adding an OSS judge (e.g., qwen, llama) is recommended for v2.

---

## L13 (Scope) No public leaderboard, no cross-operator comparison

The framework is designed as an internal tool. Two operators running it independently will produce profiles that are not directly comparable (different procedural seeds, different price tables, possibly different static pool versions). Cross-operator leaderboards would require additional cryptographic + governance infrastructure not in scope for v1.

---

## L14 (Self-knowledge gap) The framework cannot evaluate itself

There is no meta-evaluation step where we verify the framework reports what it claims to report. The DQ closures across Stage 4 are author-asserted, not externally validated. R1 + R2 reviews (Sonnet + MiniMax) partially address this but are themselves LLM-based; a true external audit by independent human researchers is the appropriate next step and is out of scope.

---

## L15 (Construct-validity) A3 metacognition confounded with RLHF error-detection (v3 — added per R1-A W5, CVT-2)

A3 (metacognition) as currently specified injects errors into externally generated reasoning chains and asks the subject to identify them. This is a heavily RLHF-trained task pattern; high A3 scores may reflect fine-tuned error-detection capability rather than genuine metacognitive insight. A stronger test (using the subject's own past reasoning trace as the target chain) is added to the v2 task pool but not retrofitted to v1 scoring. Operators reading A3 scores should treat them as upper bounds on metacognition — high scores may be inflated by training-data overlap.

## L16 (Coverage) Multi-agent attribution scope tightened (v3 — added per R1-A W8)

Multi-agent systems whose top-level LLM differs from sub-agent LLMs produce profiles attributed to the top-level subject. The profile is **NOT** a claim about the top-level LLM's capability — it is a claim about the deployed system as a whole. Operators evaluating multi-agent systems must report the system's full agent topology (sub-agent LLM IDs, gateways, prompt layers) in profile metadata; without that disclosure, the profile is interpretable but not comparable to single-agent profiles.

## L17 (Coverage) Embodied, hybrid, self-compiling-tool agents are out of scope (v3 — added per R1-A W10)

The identity tuple in v1 does not accommodate:
- **Embodied agents**: physical sensor/actuator inventory, sim-to-real configuration
- **LLM+symbolic hybrid systems**: theorem provers, formal verifiers, constraint solvers as non-LLM components
- **Self-compiling-tool agents**: systems that write and execute new tools at runtime, where tool inventory drift is a capability, not noise

v2 extension proposal: add `symbolic_components` and `physical_environment` optional fields to the identity tuple. Out of scope for v1.

## L18 (Construct-validity threats requiring future cross-validation, v3 — added per R1-A CVT-1, CVT-5)

The following are correctly identified construct-validity threats that v1 cannot fully resolve:

- **CVT-1 (A1 measures puzzle recognition, not induction)**: ARC-style transformation primitives are in training data of every frontier model. Procedural generation produces variants within the same primitive set; high A1 scores may reflect template-matching on known primitives, not novel induction. Cross-validation with a genuinely novel reasoning domain is the appropriate next step.
- **CVT-5 (A5 measures safety-training compliance, not execute/refuse/clarify judgment)**: Constitutional AI and RLHF safety training heavily emphasize the exact behaviors A5 tests. High A5 scores may reflect pattern-matched safety responses rather than judgment quality. A calibration item distinguishing "good judgment" from "safety-trained pattern" is needed; v1 generator does not control for this.

Both threats require empirical cross-validation studies that are out of scope for v1.

## L19 (Reliability) Judge temperature=0 introduces systematic bias (v3 — added per R1-B #14)

To make scoring more deterministic, v2 specified `temperature=0` for the 3-judge panel (scoring.md §6). This trades within-run variance for between-judge systematic bias: at temperature=0, each judge always selects its highest-probability scoring decision, which may exhibit consistent overscoring or underscoring of specific output styles. The multi-judge median partially averages these biases but cannot eliminate them. A higher-temperature judge panel would have more variance but less systematic skew. Operators should be aware that scores are reproducible but may not be calibrated across all output styles.

## L20 (Scope) Single-operator anti-contamination scope (v3 — added per R1-B anti-contamination §7)

The 70/30 procedural/static anti-contamination design (anti-contamination.md §2) assumes a single operator. When two operators run the framework independently, their procedural-generator seeds can collide — producing identical tasks across operators that the anti-contamination design tries to prevent within an operator's own runs. v2 should add seed-namespace per operator. Until then, cross-operator profile comparisons should be treated as suggestive, not definitive.

---

## Summary table (v3)

| # | Category | Limitation |
|---|----------|-----------|
| L1 | Construct | Track A inseparable from instruction-tuning |
| L2 | Construct | Track B mixes LLM and environment contributions |
| L3 | Coverage | Multimodal deferred |
| L4 | Coverage | Multi-agent internals opaque |
| L5 | Coverage | Human-in-loop unmodeled |
| L6 | Operational | 100-LOC adapter cap creates exclusion incentive |
| L7 | Operational | 12h pilot budget = 1-trial-per-dim, not full eval |
| L8 | Operational | USD price table goes stale |
| L9 | Anti-contamination | Static held-out leaks over time |
| L10 | Anti-contamination | Procedural generator code is leak vector |
| L11 | Reliability | Self-modifying subjects have inherent variance |
| L12 | Reliability | 3-judge panel shares frontier-family bias |
| L13 | Scope | No cross-operator leaderboard |
| L14 | Self-knowledge | Framework cannot evaluate itself |
| L15 | Construct (v3) | A3 metacognition × RLHF confound |
| L16 | Coverage (v3) | Multi-agent attribution requires topology disclosure |
| L17 | Coverage (v3) | Embodied / hybrid / self-compiling-tool agents OOS |
| L18 | Construct (v3) | CVT-1 (A1) and CVT-5 (A5) need cross-validation |
| L19 | Reliability (v3) | Judge temperature=0 systematic bias |
| L20 | Scope (v3) | Single-operator anti-contamination namespace |

20 limitations total in v3.

---

## Summary table

| # | Category | Limitation |
|---|----------|-----------|
| L1 | Construct | Track A inseparable from instruction-tuning |
| L2 | Construct | Track B mixes LLM and environment contributions |
| L3 | Coverage | Multimodal deferred |
| L4 | Coverage | Multi-agent internals opaque |
| L5 | Coverage | Human-in-loop unmodeled |
| L6 | Operational | 100-LOC adapter cap creates exclusion incentive |
| L7 | Operational | 12h pilot budget = 1-trial-per-dim, not full eval |
| L8 | Operational | USD price table goes stale |
| L9 | Anti-contamination | Static held-out leaks over time |
| L10 | Anti-contamination | Procedural generator code is leak vector |
| L11 | Reliability | Self-modifying subjects have inherent variance |
| L12 | Reliability | 3-judge panel shares frontier-family bias |
| L13 | Scope | No cross-operator leaderboard |
| L14 | Self-knowledge | Framework cannot evaluate itself |

14 limitations. Stage 4 acceptance (≥5) satisfied 3× over.

---

## What we explicitly do NOT consider a limitation

- "It doesn't produce a single score" — by design, not a flaw.
- "Bare LLMs score N/A on most Track B dimensions" — correct reporting, not a flaw.
- "Same LLM through different gateways are treated as different subjects" — by design, gateway is part of identity.
- "Test-retest variance > 0 on rubric-scored dimensions" — expected; psychometric tests with r=0.85 have inherent variance.
- "Adapter complexity reduces user friendliness" — feature, not bug; surfaces interface-immaturity signals.
