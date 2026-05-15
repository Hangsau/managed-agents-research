# Stage 2.1 — Capability × System-Class Feasibility Matrix

**Purpose**: For each candidate capability dimension extracted from Stage 1, score whether and how cleanly it can be measured on three classes of deployed system. Cells answer: "given this system class, can we get a reliable signal on this dimension?"

**System classes** (column headers):

- **BL** — Bare LLM: HTTP API endpoint, no system prompt, no tools, no memory, no environment
- **CLI** — CLI wrapper: claude-code / codex / aider / cursor-cli (stdout + stdin + filesystem + sometimes web/shell tools, single-session)
- **AS** — Agent System: Talos (Hetzner VM + Hermes + Claude), Hestia (local VM + Hermes), Devin, Cursor BG Agent — full environment, persistent memory, scheduled execution, multi-agent

**Cell legend**:

- **5** = Native fit. Can be measured cleanly with low-overhead adapter.
- **4** = Cleanly measurable. Mild adapter / scaffolding required.
- **3** = Measurable but signal partial. Confounded by interface limits or environment differences.
- **2** = Possible only with workarounds; weak signal.
- **1** = Effectively infeasible / structurally N/A for this class. Score should be reported as N/A (interface lacks affordance), not 0 (tried, failed).

---

## A. Track A — Abstract / Construct Capabilities (bare LLM can compete)

These dimensions test the underlying LLM's reasoning, knowledge, and language behavior — the "fluid intelligence" axis in CHC terms. Environment adds little; framework can confound by injecting prompt scaffolds.

| # | Capability dimension | BL | CLI | AS | Source benchmark / theory references |
|---|---------------------|----|-----|----|--------------------------------------|
| A1 | Abstract pattern reasoning (ARC-style induction, novel symbolic puzzles) | **5** | 4 (CLI wrapper may inject CoT scaffolding) | 3 (agent framework may auto-decompose; conflates reasoning with planning) | ARC-AGI / ARC-AGI-2 [S1.1, S1.6]; Raven's Progressive Matrices [S1.7] |
| A2 | Working memory (10+ step instruction retention, recall under interference) | **5** | 4 | 3 (memory system may externalize and inflate) | Digit Span / WAIS-5 working-memory index [S1.7]; multi-turn dialogue [S1.4] |
| A3 | Metacognition (self-confidence calibration, "where did you go wrong?") | **5** | 5 | 4 (framework may auto-add reflection steps) | ADEPTS Evaluation pillar [S1.2]; reflection in S1.6 |
| A4 | Counterfactual reasoning ("if X were not true…") | **5** | 5 | 4 (env may surface ground truth and shortcut) | HellaSwag (counterfactual) [S1.6]; surveys [S1.2] |
| A5 | Instruction following + refusal (impossible/conflicting tasks, ambiguity) | **5** | 4 | 3 (agent loop may persist past refusal point) | AgentBench instruction-following [S1.1]; Bloom behavioral evals [S1.3] |
| A6 | Multi-step mathematical / logical reasoning (chains of 2-8 steps) | **5** | 5 | 4 (tool calls may bypass reasoning) | GSM8K, MATH [S1.6] |
| A7 | Code synthesis from spec (single-function, no repo context) | **5** | 5 | 4 | HumanEval, MBPP [S1.1, S1.6] |
| A8 | Graduate-level domain expertise (Google-proof) | **5** | 5 | 4 (web access may shortcut) | GPQA [S1.6] |
| A9 | Knowledge breadth across domains (MMLU-Pro style) | **5** | 5 | 4 (web access shortcut) | MMLU-Pro [S1.6] |
| A10 | Linguistic / commonsense robustness under phrasing variation | **5** | 5 | 4 | HellaSwag, MMLU-Pro robustness [S1.6] |
| A11 | Behavioral disposition (sycophancy, self-preservation, instructed sabotage) | **5** | 4 (CLI safety harness may suppress signal) | 3 (framework + memory bias amplifies / dampens) | Anthropic Bloom [S1.3]; ADEPTS Safety [S1.2] |

**Pattern**: Track A is the column where BL **wins on signal cleanliness**. Adding environment is noise here, not capability. Score *drops* moving BL → CLI → AS for many dimensions, because scaffolding and tools introduce confounds (CoT auto-injection, web shortcut, framework reflection layers).

---

## B. Track B — Applied / Environmental Capabilities (agent system advantage)

These dimensions require the system to write to / read from / persist in an environment. Bare LLM is structurally N/A on most.

| # | Capability dimension | BL | CLI | AS | Source references |
|---|---------------------|----|-----|----|-------------------|
| B1 | Environment exploration ("find X in unknown filesystem") | **N/A** | 5 | 5 | OSWorld, SWE-bench navigation [S1.1, S1.3] |
| B2 | Long-horizon planning (set up X to execute 24h later, multi-day workflow) | **N/A** | 2 (session-bound; can write scheduler but cannot verify execution within session) | 5 | METR HCAST [S1.3]; Anthropic autonomy metrics [S1.9] |
| B3 | Tool use under domain policies (TAU-style customer-service simulation) | **N/A** | 3 (only if CLI has tool affordance) | 5 | TAU-bench [S1.1] |
| B4 | Web navigation (multi-hop browsing, form filling) | **N/A** | 3 (if browser tool wired in) | 5 | WebArena, WebVoyager, BrowseComp [S1.1, S1.9] |
| B5 | GUI / computer use (real desktop OS, app workflows) | **N/A** | 2 (only with Computer Use API) | 4 (only if VM has display) | OSWorld, VisualWebArena [S1.1] |
| B6 | Cross-session continuity (Session A builds state, Session B continues) | **N/A** | 2 (file-system based persistence possible but session protocol awkward) | 5 | MontyCloud four-pillar Memory [S1.2] |
| B7 | Self-correction under misleading feedback (handle adversarial reviewer) | 3 (single-turn only) | 4 | 5 | AgentBench [S1.1]; cross-case "perception vs reality" [S1.5] |
| B8 | Error recovery (corrupted state mid-task, tool failure) | **N/A** | 4 | 5 | Aider second-attempt design [S1.5]; InterCode [S1.1] |
| B9 | Real codebase / repo-level reasoning (SWE-bench Verified) | 2 (only if entire repo fits in context, no real exec) | 5 | 5 | SWE-bench Verified [S1.1, S1.3] |
| B10 | ML engineering end-to-end (train model, submit to leaderboard) | **N/A** | 2 (one-shot ML script possible; no iteration loop) | 4 | MLE-Bench [S1.1] |
| B11 | Multi-file mutation (cross-file refactor) | **N/A** | 5 | 5 | Anysphere, Cursor BG, GitHub Coding Agent [S1.9] |
| B12 | Vague-goal convergence ("make this system better") | 2 (returns text plan, cannot execute) | 4 | 5 | Cognition Devin "ambiguous projects" failure mode [S1.5, S1.9] |
| B13 | Self-environment evolution ("over a week, make yourself better at X") | **N/A** | **N/A** | 4 (only for systems that allow self-modification, e.g. Hestia-class) | Hestia autonomous expansion (memory); ADEPTS Personalization [S1.2] |
| B14 | Async / batch-mode long-runner (overnight PR generation) | **N/A** | 3 | 5 | GitHub Coding Agent, Replit 200-min sessions [S1.9] |

**Pattern**: Track B is where BL is **structurally N/A**, not failed. Conflating N/A with 0 was the most consistent design error in industry self-eval (S1.9 — bare-LLM Track B scores not reported as 0, they're not even computed). Our framework must keep N/A distinct.

---

## C. Track C — Operational / Cross-Cutting (always measurable, but interpretation differs)

These are not "capabilities" in the construct sense — they are operating-point measurements that accompany every Track A/B result. Cost and latency are non-optional axes per HELM and Cursor's CursorBench.

| # | Operational dimension | BL | CLI | AS | Source references |
|---|----------------------|----|-----|----|-------------------|
| C1 | Cost per task (USD or token count) | 5 | 5 | 4 (multi-provider chain may obscure) | HELM efficiency [S1.6]; CursorBench correctness×cost [S1.3] |
| C2 | Latency (wall-clock to final output) | 5 | 5 | 5 | Same as C1 |
| C3 | Reliability under repeated trials (TAU's pass^k) | 5 | 5 | 4 (env state drift between trials) | TAU-bench pass^k [S1.1] |
| C4 | Adapter complexity (LOC needed to plug into harness) | 5 (HTTP) | 4 (CLI wrapping) | 3 (SSH / TG / web UI) | New dimension introduced by this research |
| C5 | Failure-mode profile (what kinds of errors when failing) | 4 | 5 | 5 (richer signal: infinite loop, scope creep, env corruption) | Devin annual review failure modes [S1.5, S1.9] |
| C6 | Test-retest reliability (same identity, repeated → stddev) | 5 | 5 | 4 (env state may change between runs) | Stanford-Binet / WAIS-5 test-retest [S1.7] |
| C7 | Self-environment-modification detection (did system change itself mid-test) | 5 (trivially: no env) | 4 | 3 (Hestia-class actively modifies; harder to freeze) | Hestia self-built cron [memory observation 2026-05-14] |

---

## Cross-matrix observations

1. **Track A scores generally degrade as we move BL → CLI → AS**, not improve. This is **counter-intuitive but correct**: more environment = more scaffolding noise on pure reasoning measurement. Designers who instinctively assume "bigger system = better score everywhere" misread the matrix.

2. **Track B has cliff transitions at BL→CLI and CLI→AS**, not smooth scaling. B2 (long-horizon planning) jumps from N/A → 2 → 5 because long-horizon needs both persistent state and execution past session boundary; either both are present or measurement collapses.

3. **A few dimensions are AS-exclusive**:
   - B13 (self-environment evolution) requires runtime that permits self-modification — most CLI sandboxes block this; bare LLM has nothing to modify
   - B6 (cross-session continuity) requires persistent memory bound to a stable identity
   - B14 (overnight async) requires execution past user session

4. **Operational axes (Track C) are the only fully comparable axes across all three system classes** — they are the "tying ribbon" that lets us produce a single profile graphic with BL / CLI / AS overlaid.

5. **N/A vs 0 is design-critical**:
   - 12 of 14 Track B rows are N/A for BL (only B7 and B9 have non-N/A workarounds)
   - 3 of 14 Track B rows are N/A even for CLI (B6, B10, B13)
   - Any scoring that averages these as "0" will systematically rank bare LLM and CLI below agent system on a meaningless axis — environment richness, not capability.

6. **Same LLM × different environment** isolates environment value-add (the pilot's central claim):
   - Subject 1 (bare API), Subject 2 (Claude Code vanilla), Subject 3 (user's full Claude Code) share LLM
   - Predicted: Track A scores within ±0.05 across the three; Track B scores diverge dramatically (Subject 1 ~all N/A; Subject 3 ~all 4-5)
   - This pattern, if observed, validates the framework's core claim. If Track A scores diverge significantly across same-LLM trio, our environment-isolation hypothesis is wrong.

7. **Dimensions where agent system can score *worse* than CLI**:
   - A1, A2, A11 — when framework auto-injects CoT, externalizes memory, or applies safety-suppression in ways that distort the reasoning signal
   - This is a genuine finding (in psychometric terms: agent system has lower **construct validity** on Track A because environment is confounding the signal). Frameworks should not assume "more sophisticated agent" means "higher score on every axis."

---

## Mapping back to industry / academic vocabulary

| Our dimension | Closest established term |
|---------------|--------------------------|
| Track A | Fluid intelligence (CHC Gf), construct measurement of LLM-itself |
| Track B | Crystallized "applied" capability, ADEPTS Actuation + Personalization, MontyCloud four-pillar Environment |
| Track C C1-C3 | HELM efficiency + accuracy multi-metric |
| C4 (adapter complexity) | New — proposed metric, no exact analog in prior work |
| C6 (test-retest) | Direct borrow from psychometrics (WAIS-5 reliability target ≥0.88) |
| C7 (self-modification) | New — relevant for self-evolving agents (Hestia / Devin annual review) |
| N/A vs 0 distinction | New — implicit in psychometrics (ceiling/floor effects) but never explicit in agent benchmarks |

---

## What this matrix does NOT do (out of scope for Stage 2)

- It does not propose actual task content (task specs are Stage 4 deliverables)
- It does not weight dimensions into a single score (we reject single-score by design, per Track A vs B split)
- It does not specify pass thresholds (acceptance criteria are downstream)
- It does not address the contamination question (handled in Stage 4 anti-contamination doc)

These are deliberate boundaries; Stage 2 is a **map of the measurable territory**, not the test itself.
