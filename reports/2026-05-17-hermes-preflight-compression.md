# 研究報告：Hermes Agent Preflight Compression 問題分析

> 日期：2026-05-17  
> 研究主題：壓縮頻繁、耗時長、效果不持久  
> 優先順序：H

---

## 1. 問題概述

用戶回報三個症狀：
1. **壓縮頻繁**：在 65,536 tokens 就觸發壓縮
2. **壓縮時間長**：每次壓縮耗費大量時間
3. **效果不持久**：壓完後短時間又需再壓

---

## 2. 根本原因分析

### 2.1 為何 65,536 tokens 就觸發？

研究發現 65,536 = 0.50 × 131,072。

`131,072` 這個數字來自 `agent/model_metadata.py` 中多個模型家族的默認 context length：
- `gemma-3`: 131,072
- `llama`: 131,072  
- `qwen` (非特定家族): 131,072
- `grok-3/2`: 131,072

預設 threshold_percent = 0.50（50%），所以：
```
threshold_tokens = 131,072 × 0.50 = 65,536
```

這是**正確的預設行為**，不是 bug。用戶的模型 context length 應為 131K。

### 2.2 為何保護的 tail 很少導致快速 re-trigger？

根據 `context_compressor.py` 的演算法：

```python
# tail_token_budget = threshold_tokens × target_ratio
tail_token_budget = 65,536 × 0.20 = 13,107 tokens
```

每個 turn 平均消費：
- user message：500-2000 tokens
- assistant reply：500-2000 tokens  
- tool result：200-5000 tokens

所以大約 **5-10 個 turn** 就會再次到達 65,536 threshold。

此外，system prompt 通常佔 3,000-8,000 tokens（取決於 toolsets 和 memory blocks），protected head 另有 3 個消息，實際可用於 tail 的預算更少。

### 2.3 為何壓縮時間長？

`ContextCompressor.compress()` 需要一次 LLM 呼叫來生成摘要。默認使用：
- 模型：`google/gemini-3-flash-preview`（通过 OpenRouter）
- 溫度：0.3
- 重試次數：3
- 每次壓缩的 summary ceiling：12,000 tokens

加上網路延遲和 API 處理時間，整個壓缩週期可達 5-15 秒。

### 2.4 Anti-thrashing 機制存在但可能未生效

代碼中已有 anti-thrashing：
```python
# context_compressor.py 第 503-512 行
if self._ineffective_compression_count >= 2:
    logger.warning("Compression skipped — last %d compressions saved <10%% each.")
    return False
```

但問題是：「saved < 10%」指的是相對於被壓缩的內容，而非整體 context length。當 tail budget 很小時，每次壓缩的 savings 可能永遠達不到 <10% 的閾值。

---

## 3. Hermes 現有緩解機制

### 3.1 三大保護策略

根據 `agent/context_compressor.py`：
1. **Head 保護**：`protect_first_n=3`（額外保護前3個非-system消息）
2. **Tail 保護**：token budget 方式（基於 `target_ratio`）
3. **Anti-thrashing**：連續2次低效壓缩後跳過

### 3.2 可配置參數（`~/.hermes/config.yaml`）

```yaml
compression:
  enabled: true
  threshold: 0.50      # 調高到 0.70-0.80 可減少頻率
  target_ratio: 0.20    # 調高到 0.30-0.40 增加 tail 持久度
  protect_last_n: 20    # 消息數（回溯兼容）
  protect_first_n: 3    # 頭部保護消息數
```

### 3.3 Session Hygiene 系統

`gateway/run.py` 的 session hygiene 系統：
- 在每個消息處理前檢查是否需要觸發壓缩
- 使用 `last_prompt_tokens`（API 報告的真實值）而非 char-based 估算
- 硬上限：400 消息（可配置 `hygiene_hard_msg_limit`）

---

## 4. 横向比較：其他 Agent 框架的處理方式

| 框架 | 策略 | 優點 | 缺點 |
|------|------|------|------|
| **LangChain** | `ConversationSummaryMemory` + 浮動觸發 | 可控摘要頻率 | 額外 LLM 呼叫成本 |
| **AutoGen** | 固定 max rounds 後截斷 | 簡單 | 丢失早期對話 |
| **CrewAI** | 任務導向摘要 | 保持任務焦點 | 需要明確任務邊界 |
| **Letta** | rolling memory consolidation | 主動歸檔 | 需閒置時間觸發 |
| **smolagents** | 無內建（需自整合） | 彈性 | 需手動處理 |

**關鍵差異**：Hermes 是唯一同時提供（1）token budget tail 保護、（2）head 保護、（3）LLM 驅動摘要這三層的框架。其他框架通常只做其中1-2層。

---

## 5. 具體候選解法

### 解法 A：提高 threshold（最簡單）

```yaml
# ~/.hermes/config.yaml
compression:
  threshold: 0.70   # 從 0.50 改為 0.70
  # 65,536 → 91,750 tokens（對 131K context）
```

**優點**：無需改 code，config 調整  
**缺點**：接近 context limit 時才觸發，風險較高  
**適用**：長 session、已啟用 memory 的用戶

### 解法 B：提高 target_ratio（推薦）

```yaml
compression:
  threshold: 0.50
  target_ratio: 0.35   # 從 0.20 改為 0.35
  # tail: 65,536 × 0.35 = 22,938 tokens（幾乎翻倍）
```

**優點**：更多 tail 保護，減少 re-trigger 頻率  
**缺點**：壓缩時需處理的歷史更多（但有 head 保護）  
**效果**：約 10-20 個 turn 的 tail → 20-40 個 turn

### 解法 C：減少 protect_first_n（針對長 session）

```yaml
compression:
  protect_first_n: 1   # 只保留 system prompt
  # 更多消息進入可壓缩區域，壓缩效率提升
```

**優點**：壓缩時可處理更多歷史  
**缺點**：早期對話 context 丢失  
**適用**：多日 session、early context 已過時

### 解法 D：更換 compression summarization 模型

```yaml
auxiliary:
  compression:
    provider: "openrouter"
    model: "deepseek-chat"   # 比 Gemini Flash 便宜且更快
```

或使用本地模型：
```yaml
auxiliary:
  compression:
    provider: "main"          # 使用已配置的本地端點
    model: ""                 # 留空使用默認
```

**優點**：降低壓缩延遲  
**缺點**：本地模型質量影響摘要品質

### 解法 E：使用 context engine 插件

Hermes 支援 pluggable context engine（v0.9.0+）：
- 默認：`compressor`（ContextCompressor）
- 替代：`plugins/context_engine/<name>/`

研究 `plugins/context_engine/` 若存在 LCM engine，可提供：
- DAG-based 壓缩（非線性）
- 主題感知保留
- 更高效的 token 利用

### 解法 F：手動 Session Summary（減少被動觸發）

使用 `/compress <focus>` 主動壓缩，而非被動等待 threshold：
```
/compress 我的研究項目目前的進度和待解決問題
```

主動壓缩可以：
1. 在 session 開始時做一次，形成結構化摘要
2. 在長 task 完成後做一次
3. 控制 focus topic，保留相關歷史

---

## 6. 實作建議矩陣

| 問題 | 最優先解法 | 備選解法 |
|------|-----------|---------|
| 壓缩太頻繁 | 方案 B（target_ratio → 0.35） | 方案 A（threshold → 0.70）|
| 壓缩時間長 | 方案 D（更換模型） | 方案 E（LCM engine）|
| 效果不持久 | 方案 B（擴大 tail）+ 方案 C（減少 head） | 方案 F（主動 /compress）|

**推薦組合**：
```yaml
compression:
  threshold: 0.55      # 稍微提高（131K × 0.55 = 72K）
  target_ratio: 0.35   # 大幅提高 tail
  protect_first_n: 1   # 減少 head 保護增加壓缩效率
```

---

## 7. 驗證方法

1. **觀察 compression_count**：每次觸發時 `context_compressor.compression_count` 增加
2. **日誌監控**：`hermes logs` 中的 `Session hygiene:` 行
3. **Token 報告**：使用 `/usage` 觀察 `prompt_tokens` 變化
4. **配置測試**：
   ```bash
   # 查看當前配置
   hermes config get compression
   # 測試不同的 target_ratio
   ```

---

## 8. 已知限制

1. **MiniMax 模型**：context length = 204,800，threshold = 102,400，此類用戶不受 65,536 影響
2. **1M context 模型**（如 Qwen3-Coder-Plus）：threshold = 512,000，幾乎不會觸發
3. **保護消息數（protect_last_n）** 與 **tail budget** 的 interaction：當 tail budget 足夠大時，protect_last_n 的消息數 cap 不再是限制因素
4. **Summary 模型失敗回退**：若 auxiliary model 失敗，會回退到主模型，此時 Summary 品質可能下降但 session 不中斷

---

## 9. 延伸研究方向

1. **LCM Context Engine**：研究 `plugins/context_engine/lcm/` 是否存在及效果
2. **記憶系統整合**：`MemoryService.get_session_summary()` 和 `save_session_summary()` 如何與 ContextCompressor 互動
3. **Tail budget vs message count 的取捨**：在 `_prune_old_tool_results()` 中，token budget 和 count floor 同時存在時的 boundary 計算邏輯
4. **跨壓缩迭代的 summary 更新**：`_previous_summary` 如何在多次壓缩中保持信息

---

## 10. 結論

65,536 threshold 是 `131,072 × 0.50` 的正確預設行為，不是 bug。三個症狀的根本原因是：

1. **頻繁**：threshold 50% 太早，且 tail budget 只有 threshold 的 20%（約 13K tokens）
2. **時間長**：每次需呼叫 auxiliary LLM（Gemini Flash）生成摘要
3. **不持久**：tail 太小，只能容納 ~5-10 個 turn

**最直接有效的緩解**是提高 `target_ratio` 至 0.35 並降低 `protect_first_n` 至 1，可在不修改 code 的情況下將两次壓缩間的 turn 數從 ~5-10 提升到 ~15-30。

---

*研究完成時間：2026-05-17*
*主要來源：hermes-agent/agent/context_compressor.py、gateway/run.py、model_metadata.py、cli-config.yaml.example*