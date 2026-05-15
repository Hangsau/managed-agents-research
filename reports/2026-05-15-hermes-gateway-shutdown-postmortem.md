# Gateway Shutdown 自動診斷

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Gateway 每次重啟時自動檢查上次是否 dirty shutdown，若是則產出根因診斷報告（哪個 session 卡住、drain timeout 多久、建議）。

**Architecture:** Gateway startup hook 掃 gateway.log → 產診斷 report → heartbeat sensor 追蹤頻率趨勢、超過閥值自動升級。

**Tech Stack:** Python 3.14 stdlib (re, json, datetime, pathlib), gateway.log, heartbeat action log.

## Planning Quality Checklist

├── **目標**
│   └── gateway 掛掉不需手動追 log，重啟後自動出診斷報告
│
├── **前置條件檢查**
│   ├── [x] gateway.log 存在且可讀
│   ├── [x] .clean_shutdown marker 邏輯已存在
│   ├── [x] heartbeat action log 已運作
│   ├── [x] systemd journal 可查詢
│   └── [ ] 確認 startup hook 注入點（gateway/run.py 的 __init__）
│
├── **步驟清單**
│   ├── 1. 寫 `_analyze_last_shutdown()` 解析 gateway.log
│   ├── 2. 在 gateway startup 注入診斷調用，輸出 report
│   ├── 3. 加 heartbeat sensor `_scan_shutdown_health()`
│   ├── 4. 接到 `action_evolve`，escalate pattern
│   └── 5. 用真實 log（5/15 事件）驗證
│
├── **每步的驗證方式**
│   ├── Step 1: mock gateway.log 有 drain timeout → 產出正確 dict
│   ├── Step 2: 重啟 gateway → `~/.hermes/health_logs/` 出現 report
│   ├── Step 3: sensor 回傳正確 count
│   ├── Step 4: 連續 3 次 dirty → evolve 報 escalate
│   └── Step 5: 診斷內容吻合 journalctl 手動追查結果
│
├── **潛在卡點**
│   ├── gateway.log rotation / 格式變更 → regex 寬鬆匹配 + 單元測試
│   ├── startup hook 載入時 gateway.log 尚未 flush → 等 2s 再讀
│   ├── systemd journal 權限不足 → fallback 只用 gateway.log
│   └── 舊 gateway 和新的 pid 混淆 → 只抓最後一段 shutdown 序列
│
└── **失敗時的退路**
    └── 若 startup hook 注入太複雜，改為 cron job 每 5 分鐘掃一次

---

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | 🟢 設計完成 (post-review) |
| **目前階段** | 等待實作 |
| **最後行動** | 2026-05-15: Critical issues 修正，plan-review 完成 |
| **下一步** | 確認 startup hook 注入點 → 實作 Task 1 |
| **阻擋** | 無 |

---

## 現況評估

| 原需求 | 狀態 | 位置 |
|--------|------|------|
| Gateway alive check | ✅ | `hermes_health_check.py:check_gateway()` |
| Stuck process detect | ✅ | `snapshot.py:_detect_stuck_sessions()` |
| Drain timeout logic | ✅ | `run.py:3700-3848` |
| .clean_shutdown marker | ✅ | `run.py:3830-3840` |
| Auto diagnosis on crash | ❌ | — |

**Rescope:** 不需要重建 alive detection 或 drain logic。只需要在現有 shutdown flow 上掛一個事後分析器。

---

## 設計

### 觸發時機

Gateway startup (`run.py:__init__` 或 `_start_impl` 完成後) → 檢查 `.clean_shutdown` marker 不存在 → 觸發 `_analyze_last_shutdown()`。

### 解析目標

從 `gateway.log` 找最後一次 shutdown 序列：

```
SIGTERM → "Gateway drain timed out after {N}s with {M} active agent(s)"
       → "response ready: ... time={T}s ... chat={C}"
       → "Skipping .clean_shutdown marker"
```

提取：
- drain timeout 秒數
- 卡住的 agent 數量
- 回應最慢的 session（chat ID + response time）
- 是否有特殊 pattern（例如 "Interrupted during API call"）

**注意：** 若找不到 shutdown 序列 → 回 None（代表不是 crash，只是 marker 被誤刪或手動重啟），避免 false positive。

### 輸出

`~/.hermes/health_logs/shutdown_YYYYMMDD_HHMMSS.md`:
```markdown
# Gateway Shutdown 診斷 — 2026-05-15 07:53

**類型:** dirty — drain timed out
**卡住 agent:** 1 (session: telegram:8636326243, response: 516.6s)
**可能原因:** 長回應（34 API calls），超過 60s drain 上限
**建議:** 考慮拉高 drain_timeout 到 120s，或加 mid-turn interrupt checkpoint
```

### Heartbeat sensor

```python
def _scan_shutdown_health(lookback_hours=24):
    """Count dirty shutdowns in last N hours. Escalate if >2."""
    health_dir = _HERMES_HOME / "health_logs"
    cutoff = time.time() - lookback_hours * 3600
    reports = [p for p in health_dir.glob("shutdown_*.md") if p.stat().st_mtime > cutoff]
    return {"count": len(reports), "reports": [p.name for p in reports]}
```

接到 `action_evolve` 第 3 步之後：count > 2 → escalate 到 Telegram 通知。

---

## Task 1: 實作 `_analyze_last_shutdown()` 解析器

**Objective:** 從 gateway.log 提取最後一次 shutdown 的關鍵資訊

**Files:**
- Create: `~/.hermes/scripts/gateway_shutdown_analyzer.py`
- Test: `~/.hermes/scripts/test_gateway_shutdown_analyzer.py`

**Step 1: 寫測試**

```python
def test_parse_drain_timeout():
    from gateway_shutdown_analyzer import parse_shutdown_sequence
    log = """
2026-05-15 07:52:50,089 INFO gateway.run: Received SIGTERM
2026-05-15 07:53:50,594 WARNING gateway.run: Gateway drain timed out after 60.0s with 1 active agent(s)
2026-05-15 07:53:51,193 INFO gateway.run: response ready: platform=telegram chat=8636326243 time=516.6s api_calls=34 response=0 chars
2026-05-15 07:53:52,110 INFO gateway.run: Skipping .clean_shutdown marker
"""
    result = parse_shutdown_sequence(log)
    assert result["type"] == "drain_timeout"
    assert result["drain_timeout_s"] == 60.0
    assert result["active_agents"] == 1
    assert result["slowest_session"]["chat"] == "8636326243"
    assert result["slowest_session"]["response_time_s"] == 516.6

def test_clean_shutdown_returns_none():
    log = "2026-05-15 08:00:00 INFO gateway.run: Clean shutdown complete"
    assert parse_shutdown_sequence(log) is None

def test_no_log_returns_none():
    assert parse_shutdown_sequence("") is None
```

**Step 2:** 跑測試 → FAIL

**Step 3:** 實作 `parse_shutdown_sequence(text: str) -> dict | None` — regex 掃描，找不到 shutdown pattern 回 None。同時實作包裝函數 `analyze_and_report(hermes_home: Path) -> Path | None`：

```python
def analyze_and_report(hermes_home: Path) -> Path | None:
    log_path = hermes_home / "logs" / "gateway.log"
    if not log_path.exists():
        return None  # no log, nothing to analyze
    text = log_path.read_text(errors="ignore")
    result = parse_shutdown_sequence(text)
    if result is None:
        return None  # no shutdown sequence found (legitimate restart or log rotated)
    report = format_report(result)
    out_dir = hermes_home / "health_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"shutdown_{ts}.md"
    path.write_text(report)
    return path
```

**Step 4:** 測試 → PASS（含 absent log、clean restart、drain timeout 三種 case）

**Step 5:** Commit

---

## Task 2: Gateway startup hook 注入

**Objective:** Gateway 啟動時自動觸發診斷

**Files:**
- Modify: `/usr/local/lib/hermes-agent/gateway/run.py` — 在 `_start_impl()` 完成後調用

**注意：** 這是上游 Hermes Agent 原始碼，改動需最小化。只加 ~15 行 import + 調用。

**Step 1:** 在 `_start_impl` 最後加：
```python
# Gateway shutdown post-mortem
if not (_hermes_home / ".clean_shutdown").exists():
    try:
        from gateway_shutdown_analyzer import analyze_and_report
        analyze_and_report(_hermes_home)
    except Exception as e:
        logger.debug("shutdown post-mortem skipped: %s", e)
```

**Step 2:** 重啟 gateway（`sudo systemctl restart hermes-gateway`），檢查 `~/.hermes/health_logs/shutdown_*.md` 是否生成

**Step 3:** Commit

---

## Task 3: Heartbeat sensor + escalate

**Objective:** 追蹤 dirty shutdown 頻率，高頻時自動升級

**Files:**
- Modify: `~/.hermes/scripts/heartbeat/utils.py` — 加 `_scan_shutdown_health()`
- Modify: `~/.hermes/scripts/heartbeat/actions.py` — `action_evolve` 加 shutdown health 步驟

**Step 1:** 加 sensor 函數（見上方設計，使用 `_HERMES_HOME` 私有變數保持一致）

**Step 2:** 加到 `action_evolve`（在 workspace drift 之後）：
```python
shutdown_health = _scan_shutdown_health()
if shutdown_health["count"] >= 2:
    errors.append(f"gateway dirty shutdowns: {shutdown_health['count']} in 24h")
    steps.append({"op": "shutdown_health", "count": shutdown_health["count"],
                  "result": f"ESCALATE: {shutdown_health['count']} dirty shutdowns"})
else:
    steps.append({"op": "shutdown_health", "result": "clean"})
```

**Step 3:** 跑 heartbeat test → PASS

**Step 4:** Commit

---

## Task 4: 用真實數據驗證

**Objective:** 用 5/15 的實際 gateway.log 跑一次完整流程

**Step 1:** 手動呼叫 `analyze_and_report()`，確認輸出
**Step 2:** 對比 journalctl 手動追查結果 → 吻合
**Step 3:** 確認 heartbeat action log 有記錄

---

## 不做事項

- ❌ 不自動重啟 gateway（已在 Phase 3 明確排除）
- ❌ 不修改 drain timeout 參數（留給使用者決定）
- ❌ 不改 systemd unit（風險太高）
- ❌ 不監控 gateway crash loop（那是 systemd `Restart=on-failure` 的責任）

---

## 預估規模

- 新增：~100 行（analyzer + sensor）
- 修改：~20 行（gateway startup hook + action_evolve injection）
- 測試：~50 行
- 零外部依賴，純 stdlib

---

## Self-Critique

**漏洞 1：** gateway.log 可能還在 buffer 中未 flush，startup 讀到舊的 shutdown 序列

→ **對策：** 在讀取前 sleep 1 秒 + 用 `errors.log` 當備援來源（WARNING level 已即時寫入）

**漏洞 2：** 如果 gateway 是被 `kill -9` 殺掉，log 中沒有 drain timeout 行

→ **對策：** `parse_shutdown_sequence` 也偵測 "沒有 shutdown 序列但 marker 不存在" → 回傳 `type: "hard_kill"` + 從 journalctl 補原因

**漏洞 3：** 上游 `run.py` 的修改可能在 Hermes Agent 升級時被覆蓋

→ **對策：** startup hook 最小化（只有 import + try/except 調用），並在 plan 中標註這是 patch point。若被覆蓋，heartbeat `plan_drift` sensor 會 flag（因為 STATUS block 未更新）

---

## Plan Review

> Reviewed by: plan-review skill v1.2.1

**Overall:** 🟢 Pass (post-fix) | **Raw Score:** 85/100

### Dimension Scores

| Dimension | Score | Criticals Fixed |
|-----------|-------|-----------------|
| Completeness | 🟢 | Critical 1 → `analyze_and_report()` 已補定義 |
| Correctness | 🟢 | Critical 2 → false positive fixed (parser 回 None) |
| Coherence | 🟢 | — |
| Robustness | 🟡 | absent log 防禦已補；hard kill 場景有對策 |
| Efficiency | 🟢 | Task 2+3 可並行 |
| Spec Alignment | 🟢 | 對齊使用者的追溯+自我檢討需求 |

### Issues Resolved

- [x] **Critical 1** — `analyze_and_report()` 未定義 (Task 1 Step 3 已補)
- [x] **Critical 2** — false positive on marker missing (parser 找不到 shutdown pattern → None)
- [x] **Rec 1** — 並行 Task 2+3 (實作時 delegate_task)
- [x] **Rec 2** — missing log 防禦 (analyze_and_report 開頭 check)
- [x] **Rec 3** — marker 路徑確認 (實作前確認)
- [x] **Rec 4** — heartbeat sensor 用 `_HERMES_HOME` 私有變數 (保持一致性)
