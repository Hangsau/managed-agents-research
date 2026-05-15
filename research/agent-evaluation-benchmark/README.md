# Agent Evaluation Benchmark Research

> **Owner**: Opus 4.7 led research, do not auto-overwrite from other agents' cron jobs.
> **Status**: v1.2 plan locked, executing 4-stage pipeline.
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
| v2 | TBD | After R1 review integration |
| v3 | TBD | After R2 review, final lock |

## What this research is NOT

- Not a framework recommendation
- Not a LLM ranking
- Not a benchmark that ships with task data (data design is in scope; task data generation is out of scope for v1)
