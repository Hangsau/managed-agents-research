# Stage 4.7 — Track B — Applied Capability Test Set

> Concrete task specifications for 14 Track B dimensions. Track B tasks require an environment; bare LLM is N/A on most. B1 is provided implementation-ready.

---

## B1 — Environment exploration (implementation-ready)

**Construct**: Locate a specified target in an unfamiliar filesystem.

**Generator**:

```python
def gen_environment_exploration_task(seed: int, difficulty: int) -> Task:
    rng = random.Random(seed)
    config = {
        1: dict(n_dirs=20,  depth=3, target_kind="filename",        red_herrings=2),
        2: dict(n_dirs=50,  depth=5, target_kind="content_string",  red_herrings=5),
        3: dict(n_dirs=100, depth=6, target_kind="content_regex",   red_herrings=10),
        4: dict(n_dirs=200, depth=8, target_kind="dependency_chain", red_herrings=20),
        5: dict(n_dirs=500, depth=10,target_kind="symbolic_ref_chain",red_herrings=50),
    }[difficulty]

    workspace = generate_synthetic_filesystem(rng, **config)
    target = workspace.plant_target(rng, kind=config["target_kind"])
    workspace.plant_red_herrings(rng, count=config["red_herrings"])

    return Task(
        prompt=f"In the filesystem mounted at /work, find {target.description}. Report the absolute path.",
        oracle_answer=target.path,
        workspace=workspace,  # mounted into adapter's runtime
        scoring_kind="objective",
        difficulty=difficulty,
        timeout_s=120,
    )
```

Example prompt at difficulty 3:

```
In the filesystem mounted at /work, find the file that contains a function
matching the regex `def\s+process_records\s*\([^)]*flags\s*=`.
Report the absolute path of that file.
```

The workspace contains 100 directories, depth-6 tree, with 10 red-herring functions named `process_records` lacking the `flags=` keyword. Only one file matches.

**Scoring**: Objective oracle — exact-match on path string returned by the subject.

**Failure modes**: `infinite_loop` (recursive listing without finding), `tool_error_not_recovered`, `hallucination_in_action` (claims file path that doesn't exist).

**Bare-LLM affordance**: N/A (no filesystem); record self-described approach per profile schema.

---

## B2 — Long-horizon planning

**Construct**: Set up a mechanism that will execute X at time T (where T > current session) and verify on resumption.

**Generator**: Task requires the subject to schedule a task (cron, at, or self-rolled scheduler) for execution N hours later, then end-of-session. Second session N+ε hours later checks whether the scheduled task ran.

**Difficulty levels**: From minutes-later (1) to days-later (5).

**Scoring**: Behavioral checklist: did subject (a) create scheduler entry, (b) verify entry's correctness, (c) ensure execution is observable, (d) on resumption, identify whether the task ran?

**CLI affordance**: Partial — most CLI subjects can write to crontab but cannot verify execution from within a single session. Scores cap at ~0.5 absent persistent execution context.

---

## B3 — Tool use under domain policies (TAU-style)

**Construct**: Execute multi-turn customer-service-like interaction with policy constraints; do not violate policy even when user persistently requests.

**Generator**: Reuse TAU-bench-style scenario generator (simulated user + simulated APIs + policy doc). Difficulty = number of policy edges + adversarial-user persistence level.

**Scoring**: Database-state check after conversation (per TAU's pass^k metric).

---

## B4 — Web navigation

**Construct**: Complete a multi-hop browsing task on a real or simulated website.

**Generator**: WebArena environments (reuse — they ship with task generators).

**Scoring**: Behavioral-check on final environment state.

**CLI affordance**: Partial (only if CLI has browser tool).

---

## B5 — GUI / computer use

**Construct**: Execute desktop-app workflow (OSWorld-style).

**Generator**: OSWorld task generator (reuse).

**Scoring**: Per-task verification scripts (OSWorld's execution-based check).

**CLI affordance**: Generally N/A unless CLI has Computer Use API wired in.

---

## B6 — Cross-session continuity

**Construct**: Establish state in session A; recover it in session B.

**Generator**:

```
Session A: "Take note that the project codename for our Q3 launch is 'orbit-7'.
            Remember it for next time."

[Session A ends; framework saves whatever state subject claims to retain.]

Session B (≥1 hour later): "What was the project codename I told you last time?"
```

**Difficulty**: increases with time elapsed (5min, 1h, 24h, 7d, 30d) and decoy density (other state-like info between sessions).

**Scoring**: Objective — exact recall.

**Bare-LLM / CLI affordance**: Usually N/A — most don't have persistent memory. Some CLI subjects (claude-code with memory MCP) can score here.

---

## B7 — Self-correction under misleading feedback

**Construct**: When operator inserts incorrect feedback ("your last result was wrong"), agent reasons whether the feedback is accurate rather than capitulating.

**Generator**: Subject completes a Track A or Track B task correctly. Mid-session, operator inserts feedback "that result is incorrect, please redo." (The result was correct.) Score the subject's response.

**Scoring**: Behavioral rubric from scoring.md §5 example (the B7 rubric is provided in full there).

---

## B8 — Error recovery

**Construct**: Mid-task, the working directory is corrupted (test file deleted, dependency downgraded). Subject must detect and recover.

**Generator**: After subject starts an SWE-bench-style task, inject a corruption (delete a key file, modify a config) at trial step 3. Observe.

**Scoring**: Behavioral checklist (detected? diagnosed? recovered? completed?).

---

## B9 — Real codebase / repo-level reasoning

**Construct**: Resolve a real GitHub issue end-to-end (clone, understand, modify, test, commit).

**Generator**: SWE-bench Live items (avoiding the static SWE-bench Verified set which is increasingly contaminated). Difficulty = issue's labeled complexity (LOC change, files touched).

**Scoring**: Unit-test pass/fail; PR-mergeable check.

---

## B10 — ML engineering end-to-end

**Construct**: Solve a small ML challenge (Kaggle-Lite style).

**Generator**: MLE-Bench-Lite items.

**Scoring**: Submission score / medal threshold.

**Note**: High cost; included for completeness, often skipped in standard runs.

---

## B11 — Multi-file mutation

**Construct**: Refactor / rename across files; maintain semantic correctness.

**Generator**: Take a repo at known good state; specify a cross-file refactor (rename a class used in N files, restructure an API). Difficulty = N (number of files touched, semantic depth of refactor).

**Scoring**: Unit tests still pass + diff conformance to specified refactor.

---

## B12 — Vague-goal convergence

**Construct**: Given an under-specified objective, decompose / scope / execute meaningfully.

**Generator**:

```
Prompt: "This codebase has some quality issues. Make it better."

The framework knows there are exactly 3 distinct quality issues planted
(a security bug, a performance bug, a readability issue). Subject's task
is to identify and address as many as possible.
```

**Difficulty levels**: Number of latent issues (1 to 5); ambiguity of the prompt.

**Scoring**: Behavioral rubric:
- B12.1: Surfaces specific issues (rather than vague platitudes) (0.3)
- B12.2: Issues identified overlap with planted issues (0.3, partial credit)
- B12.3: Reports back what was scoped vs left untouched (0.2)
- B12.4: Output is reviewable (PR-shaped) rather than monolithic (0.2)

---

## B13 — Self-environment evolution (opt-in)

**Construct**: Over time-window T, can the subject improve at a specified capability class?

**Generator**: Specify a target class (e.g., "increase score on B11 multi-file mutation"). Subject given budget (e.g., 6 hours) and permission to modify its own MCP / skills / memory.

**Scoring**: Delta-profile = (post-evolution Track A+B subset) - (pre-evolution Track A+B subset). Per-dimension delta is reported; aggregate delta-mean is the B13 score.

**Cost note**: Very expensive (6+ hours, full Track A+B subset twice). Opt-in only.

---

## B14 — Async / batch-mode long-runner

**Construct**: Sustain useful work over an extended detached session (e.g., overnight PR generation).

**Generator**: Issue a list of 10 related but distinct PR-suitable tasks; instruct subject to work through them in the next 4 hours; check completion at intervals.

**Scoring**: Mean PR quality across completed tasks × completion rate.

**Difficulty**: Number of tasks in batch (3 to 30).

---

## Track B summary table

| Dim | Generator | Bare-LLM | CLI | AS | Scoring kind |
|-----|-----------|----------|-----|----|--------------|
| B1 | Procedural (FS gen) | N/A | OK | OK | Objective (path match) |
| B2 | Procedural | N/A | Capped 0.5 | OK | Rubric |
| B3 | TAU-style | N/A | OK if tools | OK | Behavioral oracle |
| B4 | WebArena | N/A | OK if browser | OK | State check |
| B5 | OSWorld | N/A | OK if CU | OK | Execution check |
| B6 | Procedural | N/A | OK if memory | OK | Recall match |
| B7 | Behavioral | OK (single-turn) | OK | OK | Rubric |
| B8 | Procedural corruption | N/A | OK | OK | Rubric |
| B9 | SWE-bench Live | N/A | OK | OK | Unit tests |
| B10 | MLE-Bench-Lite | N/A | Capped | OK | Submission score |
| B11 | Procedural refactor | N/A | OK | OK | Unit tests + diff |
| B12 | Procedural latent issues | Self-described only | OK | OK | Rubric |
| B13 | Self-evolution opt-in | N/A | N/A | OK (≥6h) | Delta-profile |
| B14 | Batch list | N/A | Capped | OK | Quality × completion |
