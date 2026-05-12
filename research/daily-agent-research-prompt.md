# Daily AI Agent Research — Agentic Quality Protocol

## Mission
Produce ONE deep-dive research artifact per day on AI agent evolution/construction.
Quality threshold: would Hang actually read this and change something in `firn` or `managed-agents`?
If the answer is no, discard and report "nothing worth reporting today."

## Scope (IN)
- LLM agent architecture (planning, reasoning, tool use, memory)
- Multi-agent orchestration (swarm, debate, hierarchy, communication protocols)
- Agent frameworks and runtime design (Hermes, AutoGen, CrewAI, LangGraph, etc.)
- Agent reliability, testing, evaluation (agent benchmarks, failure modes)
- Autonomous agents and long-horizon task execution
- New models/methods that directly improve agent capabilities

## Scope (OUT)
- Pure CV/NLP research with no agent angle
- RL papers unless applied to agent decision-making
- Hardware/efficiency papers unless enabling new agent paradigms
- Marketing announcements without technical depth

## Research Protocol

### Step 1: Scout (15 min)
Query these sources for the last 24-48h:
- arXiv cs.AI, cs.CL, cs.MA — filter for agent-related keywords
- GitHub trending repos with agent/framework tags
- Key blogs: Anthropic Engineering, OpenAI Blog, DeepMind, AI2, LangChain, LlamaIndex
- Twitter/X: @karpathy, @swyx, @hardmaru, @bindureddy + agent community

### Step 2: Filter (5 min)
For each candidate, ask:
1. Is this a NEW idea or just a repackaging of known techniques?
2. Does it have a concrete implementation or reproducible result?
3. Can it inform `firn` (personal agent framework) or `managed-agents` (batch runner)?
4. Would a competent engineer learn something they didn't know?

Kill anything that scores <3 yes.

### Step 3: Deep Dive (30-40 min)
Pick ONE item that passes. Dive deep:
- Read the paper/code/blog thoroughly
- Extract the core mechanism, not just claims
- Identify the key insight that makes it work
- Note limitations and failure modes (be honest, not hype-driven)
- Map to user's projects: "If we adopt X in firn, Y would change"

### Step 4: Write Report (20 min)
Format: Markdown at `/root/managed-agents/research/YYYY-MM-DD-<topic-slug>.md`

Required sections:
```
# <Title>
**Source**: <URL>  
**Type**: paper | repo | blog | thread  
**Date**: YYYY-MM-DD  
**Confidence**: high | medium | low (how sure are we this is solid)

## 1. The Problem
What specific agent problem does this address? One paragraph.

## 2. Core Mechanism
How does it work? Explain like to a senior engineer who hasn't read it.
Include code snippets or diagrams if helpful.

## 3. Why It Matters
What is the non-obvious insight? What changes if this becomes standard?

## 4. Limitations / Honest Assessment
Where does it break? What assumptions does it make?

## 5. Actionable for Our Projects
### firn
Specific changes or experiments to try.
### managed-agents
Specific changes or experiments to try.
If none, say "None directly applicable today."

## 6. Follow-up Questions
What should we watch next? Related work to track?
```

## Quality Gates
- [ ] NOT a list of links with one-sentence summaries
- [ ] NOT a rewrite of the abstract/intro
- [ ] Contains at least one "huh, that's clever" insight
- [ ] Contains at least one honest limitation
- [ ] Ends with concrete next steps, not vague "this is interesting"

## Fallback
If nothing passes the filter after Step 2, output a one-line file:
`/root/managed-agents/research/YYYY-MM-DD-NOTHING-WORTH-REPORTING.md`
with the reason. Better no report than garbage report.
