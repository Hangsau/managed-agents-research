#!/usr/bin/env python3
"""Daily research topic rotation for AI Agent self-improvement."""
import datetime

TOPICS = {
    0: {  # Monday
        "name": "Agent Frameworks",
        "queries": [
            "AI agent framework 2026",
            "Hermes agent features updates",
            "autonomous agent orchestration",
        ],
        "github_topics": ["ai-agent", "agent-framework", "llm-agent"],
        "arxiv_query": "cat:cs.AI AND (agent framework OR autonomous agent)",
    },
    1: {  # Tuesday
        "name": "MCP & Tool Use",
        "queries": [
            "Model Context Protocol 2026",
            "MCP server ecosystem",
            "LLM tool use patterns",
        ],
        "github_topics": ["mcp", "model-context-protocol", "llm-tools"],
        "arxiv_query": "cat:cs.AI AND (tool use OR MCP OR function calling)",
    },
    2: {  # Wednesday
        "name": "Multi-Agent Systems",
        "queries": [
            "multi-agent orchestration 2026",
            "agent delegation patterns",
            "swarm intelligence LLM",
        ],
        "github_topics": ["multi-agent", "agent-swarm", "agent-orchestration"],
        "arxiv_query": "cat:cs.AI AND (multi-agent OR swarm OR delegation)",
    },
    3: {  # Thursday
        "name": "Agent Safety & Sandboxing",
        "queries": [
            "LLM sandbox security 2026",
            "agent safety guardrails",
            "prompt injection defense",
        ],
        "github_topics": ["llm-security", "agent-safety", "sandbox"],
        "arxiv_query": "cat:cs.CR AND (LLM safety OR prompt injection OR sandbox)",
    },
    4: {  # Friday
        "name": "Open Source Projects",
        "queries": [
            "open source AI agent projects",
            "new agent repositories github",
            "Claude Code alternatives",
        ],
        "github_topics": ["ai-agent", "autonomous-agent", "coding-agent"],
        "arxiv_query": "cat:cs.SE AND (open source agent OR coding assistant)",
    },
    5: {  # Saturday
        "name": "Research Papers",
        "queries": [
            "AI agent survey 2026",
            "autonomous agent research",
            "LLM reasoning agent",
        ],
        "github_topics": ["paper-implementation", "research"],
        "arxiv_query": "cat:cs.AI AND (agent OR autonomous) AND (survey OR review)",
    },
    6: {  # Sunday
        "name": "Skill & Tool Review",
        "queries": [
            "Hermes skills ecosystem",
            "AI agent tools roundup",
            "productivity automation tools",
        ],
        "github_topics": ["automation", "productivity", "cli-tools"],
        "arxiv_query": "cat:cs.HC AND (automation OR productivity OR tools)",
    },
}


def get_today_topic():
    weekday = datetime.datetime.now().weekday()
    return TOPICS[weekday]


if __name__ == "__main__":
    import json
    topic = get_today_topic()
    print(json.dumps(topic, ensure_ascii=False))
