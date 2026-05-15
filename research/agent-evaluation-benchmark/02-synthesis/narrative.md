# Stage 2.2 — Synthesis Narrative

> Companion to `feasibility-matrix.md`. Read the matrix first for the structured view; this file is the prose that ties Stage 1's nine threads into a single picture and points at what Stage 3 must analyze.

## 1. The fragmented landscape we are walking into

Stage 1 documents ~80 distinct artifacts across nine sub-topics — about 15 agent benchmarks, 10 academic surveys, 6 industry methodologies, 12 framework-built-in evaluators, 10 deployment case studies, 9 AI-focused intelligence benchmarks, 9 human assessments, 10 software-engineering testing techniques, and 10 vendor self-eval reports. The dominant impression is **fragmentation**: every actor measures what suits their position. Labs publish open benchmarks they win on (Anthropic on OSWorld-Verified, OpenAI on ARC-AGI, Google on WebVoyager). Tooling vendors avoid open benchmarks and report production telemetry (Replit's 92% deployment success, Cognition's 67% PR merge). Frameworks ship eval modules tightly coupled to their own primitives (LangSmith for LangChain, AutoGen evals for AutoGen). Survey papers propose unified taxonomies (ADEPTS' six capabilities, MontyCloud's four pillars, Mohammadi's two-dimensional framework) but none have crossed into deployment.

**Nothing in Stage 1 evaluates "an arbitrary deployed system" the way our project needs to.** The closest existing artifact is Inspect-AI (AISI), which supports plugging in heterogeneous solvers including claude-code, Codex CLI, Gemini CLI, and custom agents. Inspect-AI scores 5/5 on framework-agnosticism in S1.4 and is the only piece of prior art that meaningfully approximates our scope. Stage 4 should treat Inspect-AI as an existence proof, not a competitor — its primitives (Dataset / Solver / Scorer) are reusable scaffolding for our adapter spec.

## 2. The single biggest empirical signal: benchmark vs reality

The most consequential finding across S1.3, S1.5, and S1.9 is that **benchmark scores and real-world capability diverge sharply, in both directions**:

- Cognition Devin: **13.86%** on SWE-bench Verified, but Cognition's annual deployment review reports **67%** PR merge rate. Selection bias (merged PRs are easier than full issue resolution) explains a 4-5× inflation.
- METR's 2025 RCT on 16 experienced developers using Cursor + Claude 3.7 Sonnet: developers *expected* 24% speedup, *perceived* 20% speedup, but were *measured* at **19% slowdown**. The perception-reality gap is itself a measurable property of deployed systems — not a property of the LLM.
- OpenAI Operator claims to "beat Anthropic Computer Use and Google Mariner in all benchmarks" while reporting **38.1% OSWorld**, materially below Anthropic Opus 4.7's **78%** on the same benchmark.
- 8 of 10 vendors surveyed in S1.9 publish **no open-benchmark numbers at all**, substituting feature enumeration ("multi-file editing", "200-minute sessions", "1 billion lines of code daily") for capability measurement.

**Implication for our design**: any score we produce will be compared by users to vendor marketing. If we conflate "scores well on Track A" with "is a good deployed system," we replicate exactly the inflation pattern Stage 1 documented. The multi-track design in §3 of the plan is not stylistic — it is a structural defense against this failure mode.

## 3. Conceptual building blocks that survived Stage 1 review

Five conceptual structures appear repeatedly across independent sources and look load-bearing for Stage 4:

**(a) Hierarchical capability taxonomy.** CHC theory (S1.7) organizes human cognition as three strata: general factor (g) → broad abilities (Gf, Gc, Gv, Gsm…) → narrow skills. WAIS-5 (S1.7), MontyCloud's four pillars (S1.2), ADEPTS' six capabilities (S1.2), and Inspect-AI's modular Solver/Scorer (S1.6) all converge on hierarchy. A flat single-score system loses diagnostic power; a deeply nested system loses comparability. Our Track A / Track B / Track C split is the broad-abilities layer; individual dimensions (A1-A11, B1-B14, C1-C7 in the matrix) are the narrow-skills layer. The general factor (g) we explicitly reject — it leads to single-score inflation.

**(b) Multi-axis cost-aware scoring.** HELM (S1.6) measures 7 metrics across 42 scenarios precisely because single-accuracy benchmarks hide trade-offs. Cursor's CursorBench (S1.3) plots correctness against median completion tokens. Anthropic publishes turn duration, auto-approval, interrupt rate alongside OSWorld scores. The deployment-case data (S1.5) consistently shows that **cost and latency are inseparable from capability** — Bolt.new's 20M tokens to debug one auth issue is a capability statement, not just a cost statement. Track C handles this; we report cost / latency / reliability as primary outputs, not footnotes.

**(c) Test-retest reliability as a precondition for validity.** All major human assessments (WAIS-5 r ≥ 0.88, Stanford-Binet r ≥ 0.84, Raven's APM r ≥ 0.85) gate publication on test-retest. The user's explicit requirement ("same system, same test → small variance acceptable") is the same property. No agent benchmark surveyed in Stage 1 reports test-retest reliability. Devin's 13.86% SWE-bench is a single-run number with no variance estimate. Anthropic averages over 5 OSWorld runs and reports the mean, but not the stddev. Our framework treats variance as a first-class output (§6 of the plan), which is unusual in AI benchmarking but standard in psychometrics.

**(d) Construct validity via behavioral observation, not output similarity.** Assessment Centers (S1.7) score *observable behaviors* against rubrics, not subjective impression. STAR-method behavioral interviews achieve r=0.55 predictive validity vs r=0.10 for unstructured interviews. The analog for agent evaluation is in S1.8: property-based testing (Hypothesis, QuickCheck) verifies invariants over generated input distributions, not output-match against reference. Anthropic's Bloom framework (S1.3) follows this — it specifies behavioral seeds and measures consistency of observed behavior across generated scenarios, achieving Spearman ρ = 0.86 with human judgment. Stage 4's scoring rubric should anchor to behavioral assertions ("agent escalates ambiguity to user before proceeding"), not output similarity.

**(e) Differential testing for cross-system comparison.** S1.8 documents differential testing as the SE answer to "no perfect oracle, multiple implementations." It maps directly to our problem: bare API vs Claude Code vs Talos vs Hestia produce divergent outputs on the same prompt, and divergence patterns are themselves a measurement. This is more powerful than reference-based scoring because it sidesteps the "what is the correct answer" question that LLM-as-judge benchmarks struggle with.

## 4. Tensions Stage 3 must resolve

The feasibility matrix surfaced four tensions that look like first-order design questions:

**Tension 1 — Reasoning measurement is contaminated by environment.** Track A dimensions score *lower* on agent systems than bare LLM (A1-A2 at 3 vs 5; A11 at 3 vs 5). More environment = more scaffolding = more confound. Is this a measurement bug to fix, or a feature to surface (i.e., agent-system frameworks really do constrain underlying LLM reasoning, and users should see this)?

**Tension 2 — N/A vs 0 reporting.** 16 cells in Track B are N/A for bare LLM, 3 for CLI. How do these surface in the final profile? Visually distinct? Excluded from aggregate? Reported as "interface lacks affordance" in metadata? The wrong choice here turns the profile into an environment-richness ranking.

**Tension 3 — Same model ID, different gateway, different behavior.** Memory observation (2026-05-12) and S1.5 / S1.9 both document this: Kimi via opencode-go ≠ Kimi via NVIDIA NIM. If two pilot subjects have nominally the same LLM but different gateways, do we treat them as the same identity (and so a contradiction in our framework) or different identities (and so identity-snapshot must include gateway as a variable)? The plan's §2.2 already lists "runtime environment" as an identity field; Stage 4 must commit to gateway inclusion.

**Tension 4 — Self-modifying systems break test-retest.** Hestia-class agents modify themselves between runs (cron added, skills installed, memory accumulated). C7 (self-environment-modification detection) measures this, but if the system self-modifies *during* a test session, test-retest reliability is violated by definition. Stage 4 must specify whether self-modification is (a) blocked during testing, (b) allowed and noted, or (c) itself a measured capability dimension.

## 5. What we will NOT do (precommitting in synthesis to avoid drift)

Stage 4 will not produce:

- A leaderboard or single-score ranking
- Vendor-comparable absolute scores (we report relative to per-LLM baseline + variance band)
- A new agent framework (we evaluate, we don't build)
- Replacement benchmarks for SWE-bench / OSWorld / ARC-AGI (we re-use them as Track B/A inputs where the adapter can plug into them)
- Custom infra for running agents (we lean on Inspect-AI's existing sandbox primitives where possible)

These exclusions are load-bearing: Stage 1 showed every prior attempt that tried to be all of these things produced fragmentation or contamination.

## 6. What Stage 3 must deliver

Per the plan's §7 Stage 3 acceptance: gap analysis + ≥10 design questions Stage 4 must answer. Based on the matrix and tensions above, the gap inventory should at minimum cover:

- The N/A-vs-0 reporting convention (Tension 2)
- The Track A signal-degradation phenomenon (Tension 1)
- Same-LLM-different-gateway identity question (Tension 3)
- Self-modification policy during testing (Tension 4)
- Where Inspect-AI's primitives can be reused vs where new adapter scaffolding is needed
- How procedurally-generated tasks (anti-contamination) interact with test-retest reliability
- Multi-rater consensus mechanism (no existing AI benchmark uses it; S1.7's claim it could improve construct validity is testable)
- Track C C4 (adapter complexity) — how do we measure it without disincentivizing the harness from supporting hard-to-adapt systems?
- The bare-LLM-Track-B reporting convention beyond N/A (e.g., is "interface lacks affordance" enough, or should we report the system's *self-reported* response to a Track B task as a separate axis?)
- Whether Track A construct validity can be guaranteed when CLI/AS subjects can refuse to answer "non-applicable" prompts

Stage 3 will produce these as concrete questions; Stage 4 will answer each with a design decision and rationale.

---

*Word count: ~1480.*
