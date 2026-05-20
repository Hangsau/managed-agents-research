# 探索：MCP Server as Agent Interface + Declarative Pipelines

**日期**: 2026-05-20 | **來源**: HN Algolia | **類型**: 探索

## Per-Source Insight

### 1. lastmile-ai/mcp-agent — Agents as MCP Servers (58 pts)

**核心發現**：一行代码把整個 agent app 變成 MCP server。

```python
from mcp_agent.server import create_mcp_server_for_app

@app.tool
def grade_story(story: str) -> str:
    return "Report..."

if __name__ == "__main__":
    server = create_mcp_server_for_app(app)
    server.run_stdio()
```

**Hermes 啟發（WS-019 直接相關）**：
- 現有 Hermes 的 native-mcp 整合只需：`create_mcp_server_for_app(hermes_app)` + stdio transport
- 不需要從頭寫 MCP server protocol implementation
- agent 的 `@tool` decorators 自動變成 MCP tools
- Pattern: decorator-based tools → MCP server export → stdio transport → 任何 MCP client 都能 call

**對 Hermes 的具體價值**：
- Hestia 的 skills/tools 可以暴露成 MCP server，供 Claude Code、Talos、或外部工具呼叫
- 繞過目前的 function-calling interface，改用 MCP stdio transport
- 這是 Anthropic 官方推薦的 agent building pattern（Building Effective Agents）

### 2. Pipelex — Declarative Pipeline Methods (122 pts)

**核心發現**：typed .mthds 格式 + 60+ model routing + batch processing。

```toml
[pipe.summarize_article]
type    = "PipeLLM"
inputs  = { article = "Text", audience = "Text" }
output  = "Text"
prompt  = "Summarize $article in three bullet points for $audience."
```

**Hermes 啟發（WS-020 直接相關）**：
- Pipelex 的 typed pipe system 其實就是 **structured write queue with type guarantees**
- Batch processing over lists is first-class — `batch_over: cvs` maps each CV to a sub-pipe
- Concept types (CandidateProfile, JobRequirements, CandidateMatch) = structured data contracts
- WS-020 的 multi-agent write queue 可以借鑒：typed inputs/outputs instead of raw JSON files

**架構差異**：
- Pipelex: declarative config → runtime resolves types + model routing
- Hermes current: imperative Python → no type checking, no routing

## 跨文章 Synthesis

MCP-agent 和 Pipelex 代表兩個互補的方向：
1. **MCP-agent = interface layer**：把工具暴露出去，讓其他 client 呼叫
2. **Pipelex = orchestration layer**：把流程声明化，讓多個步驟自動串聯

Hermes 的現狀：沒有 interface layer（MCP），也沒有 orchestration layer（declarative pipelines）。WS-019 是 interface layer 的起點；WS-020 是 orchestration layer 的起點。兩者應該分開做，不要在 WS-020 裡摻 MCP 概念。

## Hermes 啟發

1. **WS-019 下一步**：用 mcp-agent 的 `create_mcp_server_for_app()` pattern 測試 Hermes native-mcp，不自己實作 protocol，用現成 library。參考：`examples/mcp_agent_server/`。
2. **WS-020 重新定位**：用 typed pipe 概念替代「write queue」——不只協調順序，還要保證輸入輸出類型。這比 naive file-based queue 強很多。
3. **批量處理**：mcp-agent 的 `batch_over` pattern（map-reduce）在 WS-018 的替代方案（session-level counter）也有價值——如果可以批量計算 tool call 而非逐個追蹤，doom-loop detection 可行。

## 未追蹤 Leads

- https://docs.mcp-agent.com/mcp-agent-sdk/mcp/agent-as-mcp-server — mcp-agent agent-as-server 完整文件
- https://docs.mcp-agent.com/llms-full.txt — mcp-agent 完整文檔（LLM-readable）
- https://docs.pipelex.com/latest/setup/configure-ai-providers/ — Pipelex model routing 配置
- https://github.com/Pipelex/pipelex/blob/main/gallery.md — 完整 workflow gallery

## ✅ 本次探索完成

**時間**: 2026-05-20 02:05 CST
**Token cost**: ~1200 input tokens（低，因為 README 只讀到 400 行）
**品質**: 高 — 兩個都有實際程式碼和具體 Hermes 應用場景