# Agent Evaluation Benchmark Research

> **Owner**: Opus 4.7 led research, do not auto-overwrite from other agents' cron jobs.
> **Status**: **v3 LOCKED** (2026-05-15). Framework design phase complete; harness implementation + pilot are post-v3 work.
> **Goal**: Capability assessment framework for any deployed AI system (bare LLM, CLI, agent system), treating "LLM + environment + skills + MCP + training" as one black box.

## Reading order

1. `00-research-plan.md` — research proposal (v1.2)
2. `01-information-gathering/` — Stage 1 outputs (S1.1 – S1.9)
3. `02-synthesis/` — Stage 2 outputs
4. `03-analysis/` — Stage 3 outputs
5. `04-design/` — Stage 4 design artifacts
6. `reviews/` — peer-review reports (R1, R2)

## Version history

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-05-15 | Initial framing as framework comparison (later corrected) |
| v1.1 | 2026-05-15 | Reframed to deployed-system capability assessment |
| v1.2 | 2026-05-15 | Added system-identity definition; added test-retest reliability requirement; added pilot variants for same-LLM different-environment |
| v2 | 2026-05-15 | Integrated R1 reviews (2 Sonnet reviewers, coherence + pragmatic focus). 34 R1 issues addressed: 14 inline edits + extensive ACK in changelog. |
| v3 | 2026-05-15 | **LOCKED**. Closed R2-identified gaps where v2 changelog claimed FIX but file state was unchanged. 6 new limitations (L15-L20), B12 + A10 + B7 + scoring pseudocode + capability-profile-schema status enum all updated to match v2 changelog promises. |

## What this research is NOT

- Not a framework recommendation
- Not a LLM ranking
- Not a benchmark that ships with task data (data design is in scope; task data generation is out of scope for v1)

## What's next (post-v3)

Per `reviews/v3-final-changelog.md` §5:
1. External human expert review (psychometrician + senior ML engineer)
2. Hermes endpoint implementation on Talos and Hestia VMs (Phase 0 prerequisite)
3. Harness implementation (Phase 1, 2-4 weeks)
4. Smoke pilot — validate end-to-end
5. Full pilot (N=5 trials) — proper v1 evaluation with variance reporting
6. Framework v2 based on pilot findings

## Final file inventory (v3 lock)

- 1 plan file (`00-research-plan.md`)
- 9 Stage 1 information-gathering files (`01-information-gathering/`)
- 2 Stage 2 synthesis files (`02-synthesis/`)
- 2 Stage 3 analysis files (`03-analysis/`)
- 11 Stage 4 design files (`04-design/`)
- 6 review files (`reviews/`: 4 reviews + 2 changelogs)

**Total**: 31 markdown files; ~5000 lines; 49 review issues addressed (34 R1 + 15 R2); 20 limitations enumerated.
