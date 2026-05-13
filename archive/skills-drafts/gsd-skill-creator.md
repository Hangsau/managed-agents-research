---
name: gsd-skill-creator
description: |
  An adaptive learning and coprocessor architecture for [Claude Code](https://docs.anthropic.com/en/docs/build-with-claude/claude-code), built as an extension to [GSD (Get Shit Done)](https://github.com
trigger: |
  User mentions gsd-skill-creator or related functionality.
  Keywords: gsd-skill-creator, Tibsfox
---

# Tibsfox/gsd-skill-creator

Source: https://github.com/Tibsfox/gsd-skill-creator
Stars: 56
Discovery score: 6.5/7

## Quick Start

```bash
npx get-shit-done-cc@latest
```

## Usage

```bash
# A Pipeline List synchronized to GSD lifecycle events
- wait: phase-planned        # Block until planning completes
- move:
    target: skill
    name: test-generator
    mode: sprite              # Lightweight activation (~200 tokens)
- wait: tests-passing        # Block until tests pass
- skip:
    condition: "!exists:.planning/phases/*/SUMMARY.md"
- move:
    target: script
    name: generate-docs
    mode: offload             # Execute outside context window
```

## Notes

- Auto-discovered by daily research agent (deep-dive analysis)
- Needs manual review before activation
- Original repo: https://github.com/Tibsfox/gsd-skill-creator
