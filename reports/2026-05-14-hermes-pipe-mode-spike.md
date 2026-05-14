# SPIKE Report: Hermes Pipe Mode

**日期**: 2026-05-14 | **SPIKE ID**: WS-007-1 | **花費**: ~15 分鐘（含測試）
**結論**: ✅ Pipe mode 已存在，`hermes -z` 就是

---

## 發現

### 1. `hermes -z` = One-Shot Pipe Mode

`hermes -z "prompt"` 是內建的 one-shot 模式：
- stdin 進、stdout 出、exit code 反映成功/失敗
- 零雜訊：無 banner、無 session ID、無 tool preview
- 不開 session、不進 gateway、不跑 long-running

### 2. 實測結果

```bash
# 基本 pipe
$ echo "reply with only the word: hello" | hermes -z "$(cat)"
hello

# Git diff 分析
$ DIFF=$(git diff HEAD~1 --stat); hermes -z "How many files changed? $DIFF"
2

# Commit 摘要
$ git log --oneline -5 | hermes chat -q --quiet "$(cat)"
Workspace Manager 從 Phase 1 ... 收束為 v2.0 模組化架構附 95 個測試。
```

### 3. 兩種模式對比

| 模式 | 指令 | 用途 |
|------|------|------|
| `-z` (zero-noise) | `hermes -z "prompt"` | 最短輸出，適合 pipe chain |
| `chat -q` (quiet) | `hermes chat -q --quiet "prompt"` | 稍多 context（session ID），適合需要追蹤的 |

### 4. 效能

| 指標 | 數值 |
|------|------|
| Latency（簡單任務） | ~4.5s |
| Latency（含 git diff context） | ~5-8s |
| Exit code | 0 = success |
| Token 成本 | ~300-500 tokens/次（deepseek-v4-pro） |

---

## 與原始提案的差異

原始提案設想 `echo "task" | hermes run`。實際情況：

- ❌ `hermes run` 子命令不存在
- ✅ `hermes -z` 功能等價，只是界面不同
- 可以包一層 `hermes-run` wrapper script 達到提案中的語法

### Wrapper 建議

```bash
#!/bin/bash
# ~/.hermes/scripts/hermes-run
# Usage: echo "prompt" | hermes-run
exec hermes -z "$(cat)"
```

---

## 什麼還不能做

1. **Model 切換** — `hermes -z` 用 default model，pipe 中無法動態換 model（但 `hermes -z -m openrouter/kimi-k2.6 "prompt"` 可以手動指定）
2. **Skill injection** — `hermes -z` 不支援 `--skills` flag，但 `hermes chat -q --skills reviewer "prompt"` 可以
3. **Context from file** — 需要 `$(cat file)` 或 heredoc，不像 Axe 有 `--config` 自動載入

---

## 建議下一步

1. **P1**: 寫 `hermes-run` wrapper script（5 分鐘）
2. **P2**: 測試更多 pipe chain 場景（curl + hermes、find + hermes、cron + hermes）
3. **P3**: 探索 `hermes chat -q --skills` 的 pipe 用法（reviewer 場景）
4. **P4**: 如果「model 切換」成痛點，可 PR 到 hermes-agent 加 `-z --model` flag

---

## 結論

**Pipe mode 不用實作——已經在了。** 原始提案高估了開發成本（估算 2-3h SPIKE），實際只需要發現 `-z` flag 並寫文件。WS-007 的剩餘價值在於：

1. 包 wrapper → 讓語法更自然
2. 測試更多邊界 case → 建立 confidence
3. 寫使用文件 → 讓未來 agent 知道怎麼用

這份 SPIKE 報告本身已經滿足「驗證 pipe mode 可行性」的目標。WS-007 可以從「SPIKE」轉為「輕量包裝 + 文件化」。
