# Stage 4.5 — Anti-Contamination

> Answers DQ-16 (procedural vs static balance) and DQ-17 (item-difficulty calibration). Cross-cutting concern affecting Track A and (to lesser extent) Track B.

---

## 1. The contamination problem

Every frontier LLM trained on public web data has seen ARC-AGI, HumanEval, MMLU, GPQA. Reporting a benchmark score on a static public test set increasingly measures memorization, not capability. S1.6 documents this directly — MMLU had 6.5% noisy items including likely contamination; MMLU-Pro was re-curated specifically to combat memorization.

For Track A in particular (the abstract reasoning track), contamination would render the framework useless: a subject that "scores 0.90 on A1 pattern reasoning" might be recognizing previously-seen ARC items, not actually reasoning.

---

## 2. Procedural vs static balance (DQ-16)

The framework uses a **70% procedural / 30% static held-out** task pool split for Track A.

### 2.1 Procedural pool (70%)

Generated fresh per trial via deterministic generators. Each generator takes a seed and produces a task of controlled difficulty.

For each Track A dimension:

| Dimension | Generator approach |
|-----------|--------------------|
| A1 pattern reasoning | ARC-style grid puzzle generator parameterized by (grid size, number of training examples, transformation primitive set) |
| A2 working memory | Random instruction sequence of length L with K interference operations between issue and recall |
| A3 metacognition | Procedurally injected error in a generated reasoning chain; subject asked which step is wrong |
| A4 counterfactual | Generated "if not X, would Y?" templates over generated factual chains |
| A5 instruction following | Compositionally generated conflicting / impossible / ambiguous instruction sets |
| A6 multi-step math | Compositional math word problem generator (already mature; multiple OSS implementations) |
| A7 code synthesis | LeetCode-style problem generator with hidden test suite |
| A8 graduate domain expertise | Hardest to generate procedurally; use static pool until generators mature |
| A9 knowledge breadth | Similarly hard to generate; static pool dominant for now |
| A10 linguistic robustness | Generated paraphrase chains over a seed prompt |
| A11 behavioral disposition | Procedurally generated misalignment-bait scenarios (sycophancy bait, self-pres bait) per Bloom (S1.3) |

**Procedural generation is the design's strongest anti-contamination defense**. No two trials see the same items.

### 2.2 Static held-out pool (30%)

A small (≤200 item) hand-curated set with known item difficulty parameters. Used to:

- Calibrate procedural generators against known-difficulty items.
- Detect systematic regressions when subject scores well procedurally but poorly on static (or vice versa, indicating generator drift).
- Support cross-run comparisons that require fixed-difficulty items.

The static pool is **rotated every 6 months**: new items added, old items publicly retired (and presumed contaminated thereafter). Operators commit not to publish the current static pool until rotation.

### 2.3 Track B anti-contamination

Track B tasks are inherently less contamination-prone because real environments (filesystems, repos, websites) cannot be wholesale memorized. The defense for Track B is **environment freshness**:

- For B1 (environment exploration), the filesystem is freshly generated per trial.
- For B9 (real codebase), use SWE-bench Live or freshly-mined GitHub issues rather than the SWE-bench Verified static set.
- For B11 (multi-file mutation), use freshly-mined commit-based tasks (Cursor Blame approach from S1.3).

---

## 3. Item-difficulty calibration (DQ-17)

### 3.1 Generator-by-construction (preferred for Track A)

Each procedural generator emits items at **explicitly parameterized difficulty levels**. Example for A2 working memory:

```python
def gen_working_memory_task(seed: int, difficulty: int) -> Task:
    """
    difficulty 1: 5-step instruction, 0 interference operations
    difficulty 2: 8-step, 2 interference
    difficulty 3: 12-step, 5 interference
    difficulty 4: 20-step, 10 interference
    difficulty 5: 30-step, 20 interference + recall-from-middle
    """
    ...
```

Each trial draws items uniformly across difficulty levels 1-5. The score is a difficulty-weighted aggregate, equivalent to an IRT trait estimate (S1.7).

### 3.2 IRT calibration (Track B fallback)

For Track B dimensions where generator-by-construction is infeasible (B12 vague-goal convergence, B7 self-correction on adversarial feedback), we use **IRT-style calibration via reference panel**:

1. Curate a candidate item pool of ~50 tasks.
2. Run a reference panel of ~10 subjects (mix of bare LLM, CLI, agent systems) on each item.
3. Fit 2PL IRT model: each item gets a difficulty parameter `b` and discrimination parameter `a`.
4. Discard items with `a < 0.3` (low discrimination — don't distinguish capable from incapable subjects).
5. Future runs use the calibrated pool; subject ability estimates use IRT scoring rather than raw accuracy.

The reference panel is re-run quarterly to detect drift.

### 3.3 Why both — generator-by-construction (Track A) + IRT (Track B)

Generator-by-construction is cheaper at run-time (no calibration overhead) but only works where you can parameterize difficulty. IRT works on any item pool but requires calibration runs. The combination gives Track A clean construct measurement and Track B usable signal where construct cleanliness is harder.

---

## 4. Variance vs anti-contamination — resolving the tension

Stage 2's narrative noted procedural generation defeats memorization but introduces variance, which fights test-retest reliability. Resolution:

- **Within-task variance** from procedural generation is **acceptable and expected**. Two trials of A1 see two different puzzles; scores can differ by ±0.1 on a single puzzle pair, which is meaningless.
- **Across-trials aggregation** within a dimension absorbs this variance — N = 5 trials, all on different procedural variants, produces a stable mean (as long as the generator's difficulty distribution is fixed).
- **Test-retest** across sessions is the proper reliability axis. If a subject's mean over 5 fresh procedural items at run 1 vs run 2 differs by ≤0.10, the subject is stable; the framework is reliable.

The key insight: variance from procedural items is **measured by the framework as part of the variance estimate**, not as a flaw. If a subject can only succeed on memorized items, its variance on fresh procedural items will be high, and `status` will be `high_variance` — which is the correct diagnosis.

---

## 5. Detection of contamination during a run

The framework actively monitors for contamination signals:

- **Static vs procedural delta**: if subject scores significantly higher (>0.15) on the static held-out pool than on procedural items in the same dimension, flag `contamination_suspected` in profile.
- **Pre-test answer disclosure**: if subject's trace contains the exact answer string before the reasoning portion, flag.
- **Memorization-suggestive recall**: if subject solves a hard procedural item in <100ms (much faster than reasoning would require), flag for review.

These are heuristics, not proof. The profile surfaces them as metadata for the operator's judgment.

---

## 6. The rotating-pool commitment

The 30% static pool is committed to a rotation schedule:

- **Current pool publicly retired**: at the end of each 6-month period (2026-11-15, 2027-05-15, ...), the current static pool is published with full answers. The framework refuses to use it on new runs after that date.
- **New pool added**: 2 weeks before retirement, a new pool of equal size is curated and made available to operators (not publicly published until next rotation).
- **Calibration carryover**: items that perform similarly (in IRT discrimination) to retired items inherit their difficulty class, easing calibration burden.

This rotation explicitly trades short-term comparability against long-term contamination resistance. Six months is the rotation cadence; this can be tuned based on observed contamination signals.

---

## 7. Out-of-scope for v1

- **Cross-run contamination via shared task pools across operators**: if multiple operators run the framework, their procedural seeds may collide. v1 assumes single-operator. v2 should add seed-namespace per operator.
- **Adversarial subjects that probe the harness**: a subject that probes the task pool to extract items is out of scope. Mitigated softly by procedural generation; no defensive mechanism in v1.
- **Cryptographic commitments to task pool versions**: a stronger anti-tampering posture would commit task pool versions to a public hash before runs. Out of scope for v1.

---

## 8. DQ closure

| DQ | Resolved in this file |
|----|----------------------|
| DQ-16 | §2 — 70% procedural / 30% static held-out + 6-month rotation |
| DQ-17 | §3 — generator-by-construction for Track A, IRT calibration for Track B |
