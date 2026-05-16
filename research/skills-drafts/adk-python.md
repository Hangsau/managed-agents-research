---
name: adk-python
description: |
  An open-source, code-first Python framework for building, evaluating, and deploying sophisticated AI agents with flexibility and control.
trigger: |
  User mentions adk-python or related functionality.
  Keywords: adk-python, google
---

# google/adk-python

Source: https://github.com/google/adk-python
Stars: 19606
Discovery score: 7/7

## Quick Start

```bash
pip install google-adk
```

## Usage

```bash
from google.adk.agents import Agent
from google.adk.tools import google_search

root_agent = Agent(
    name="search_assistant",
    model="gemini-2.5-flash", # Or your preferred Gemini model
    instruction="You are a helpful assistant. Answer user questions using Google Search when needed.",
    description="An assistant that can search the web.",
    tools=[google_search]
)
```

## Notes

- Auto-discovered by daily research agent (deep-dive analysis)
- Needs manual review before activation
- Original repo: https://github.com/google/adk-python
