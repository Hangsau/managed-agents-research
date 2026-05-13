---
name: atmosphere
description: |
  A framework for building streaming AI agents on the JVM. Atmosphere owns the transport layer — tokens flow from the LLM runtime to the client through a broadcaster you can filter, gate, and observe. <
trigger: |
  User mentions atmosphere or related functionality.
  Keywords: atmosphere, Atmosphere
---

# Atmosphere/atmosphere

Source: https://github.com/Atmosphere/atmosphere
Stars: 3765
Discovery score: 7/7

## Quick Start

```bash
brew install Atmosphere/tap/atmosphere
```

## Usage

```bash
// Registers this class as an agent — auto-discovered at startup.
// Endpoints are created based on which modules are on the classpath:
// WebSocket, MCP, A2A, AG-UI, Slack, Telegram, etc.
@Agent(name = "my-agent", description = "What this agent does")
public class MyAgent {

    // Handles user messages. The message is forwarded to whichever AI runtime
    // is on the classpath (Spring AI, LangChain4j, ADK, etc.) and the LLM
    // response is streamed back token-by-token through the session.
    @Prompt
    public void onMessage(String message, StreamingSession session) {
        session.stream(message);
    }

    // Slash command — executed directly, no LLM call.
    // Auto-listed in /help. Works on every channel (web, Slack, Telegram…).
    @Command(value = "/status", description = 
```

## Notes

- Auto-discovered by daily research agent (deep-dive analysis)
- Needs manual review before activation
- Original repo: https://github.com/Atmosphere/atmosphere
