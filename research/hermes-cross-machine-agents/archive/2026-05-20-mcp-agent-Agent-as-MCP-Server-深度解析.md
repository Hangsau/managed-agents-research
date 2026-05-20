# 2026-05-20 — mcp-agent Agent-as-MCP-Server 深度解析

**延續自**: [[2026-05-20-mcp-agent-hermes-pipelex-write-queue]]

## 核心發現

`create_mcp_server_for_app(app)` 是將 Hermes app 本身暴露為標準 MCP server 的正確方式。

### 三種 tool 類型

| 裝飾器 | 語意 | 適用場景 |
|--------|------|----------|
| `@app.tool` | 同步，client 立即收到結果 | 快速查詢、程式碼執行、檔案操作 |
| `@app.async_tool` | 異步，回 workflow_id + run_id，client polling | 長時運行工作、需 pause/resume |
| `@app.workflow` | 宣告式 workflow entry point | 複雜多步驟流程 |

### 內建管理工具

`create_mcp_server_for_app()` 自動註冊：
- `workflows-list` — 探索可用 workflow
- `workflows-run` — 同步啟動 workflow
- `workflows-get_status` — polling 直到完成
- `workflows-cancel` — 終止
- `workflows-resume` — 恢復 paused workflow

### 部署模式

1. **asyncio**（記憶體執行，無額外依賴）— 本地開發、輕量部署
2. **Temporal**（持久化 workflow，支援 pause/resume）— 生產環境

### Claude Desktop 整合

```json
{
  "mcpServers": {
    "my-agent-server": {
      "command": "uv",
      "args": ["run", "examples/mcp_agent_server/asyncio/main.py"]
    }
  }
}
```

## Hermes 啟發：WS-019 實作路徑

### 方案 A（推薦）：asyncio 模式

```
Hermes (as MCP server) ←→ Claude Desktop / Cursor
                      ←→ 自家 MCP client tool（另一個 agent）
```

```python
from mcp_agent.app import MCPApp
from mcp_agent.server import create_mcp_server_for_app

app = MCPApp(name="hermes-agent")

@app.tool
async def hermes_execute(command: str) -> str:
    """Execute Hermes terminal command."""
    # 封裝現有的 terminal tool
    result = await run_terminal(command)
    return result

if __name__ == "__main__":
    mcp_server = create_mcp_server_for_app(app)
    mcp_server.run_stdio()
```

**優勢**：
- 不需要自己實作 MCP protocol，用 mcp-agent library
- asyncio 模式零外部依賴（Temporal 需要額外服務）
- Claude Desktop / Cursor 天然支援，client 生態豐富
- 自家 MCP client（另一個 agent）也可以 call

**劣勢**：
- 需要 mcp-agent SDK 安裝（`uvx --from "mcp-agent"` — CLI 可用，但 Python SDK import 待驗證）

### 方案 B：MCP Inspector 測試先行

在實作 Hermes agent server 前，先用 MCP Inspector 驗證 asyncio example 可跑：
```bash
npx @modelcontextprotocol/inspector uv --directory examples/mcp_agent_server/asyncio run main.py
```

### WS-020 orchestration layer 同步更新

agent-as-MCP-server pattern 讓 WS-020 的方向更清晰：
- **WS-019（interface layer）**：用 mcp-agent 把 Hermes 變成 MCP server
- **WS-020（orchestration layer）**：用 `workflows-list` / `workflows-run` 呼叫其他 WS，或用 `@app.workflow` 宣告複雜 pipeline

不再需要自己搞 MCP gateway — 借用 mcp-agent 的實作。

## 驗證待辦

- [ ] 確認 `from mcp_agent.server import create_mcp_server_for_app` 在 Python 可 import
- [ ] 用 MCP Inspector 跑通 asyncio example
- [ ] 評估 Hermes @app.tool 需要多少包裝層（terminal tool → MCP tool）

## 未追蹤 Leads

- https://docs.mcp-agent.com/mcp-agent-sdk/mcp/agent-as-mcp-server — ✅ 本次已讀
- https://docs.mcp-agent.com/examples/mcp_agent_server/asyncio — asyncio example source code
- https://docs.mcp-agent.com/examples/mcp_agent_server/temporal — Temporal example
- https://docs.mcp-agent.com/mcp-agent-sdk/core-components/workflows — Workflow class 文件

## ✅ 本次探索完成

**時間**: 2026-05-20T09:15 CST
**Token cost**: 低（直接 fetch 文件，無 LLM 閱讀）
**品質**: 高 — 有完整程式碼範例、部署架構、client 整合方式