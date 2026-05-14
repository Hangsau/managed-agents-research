# Consolidation Injection Layer (INJ-001) 實作計畫

> **For Hermes:** 實作時參照本計畫，逐任務進行。

**Goal:** 讓 consolidation 的產出（synthesis insight）自動回饋到 agent 的 session context，閉合「筆記→消化→注入→決策→新筆記」的飛輪。

**Architecture:** standalone `briefing.py` 讀取最新 consolidation synthesis，萃取關鍵 insight 濃縮為 <1000 chars 的 briefing 檔。Memory 加一行指標指向 briefing，agent 在 session 啟動時可讀取。

**Tech Stack:** Python 3 stdlib（os, glob, json, re, datetime），純檔案操作，無依賴。

---

## 現況評估

| 現有資產 | 狀態 | 位置 |
|----------|------|------|
| consolidate_memory.py | ✅ 上線 | `~/.hermes/scripts/` |
| memory-consolidator cron | ✅ 每 12h | job `a89f6965daa0` |
| 唯一 synthesis 產出 | ✅ 1 篇 | `obsidian-vault/research/2026-05-14-hermes-consolidation-synthesis.md` |
| synthesis → agent context | ❌ **缺** | — |
| briefing 檔 | ❌ 不存在 | — |

**範圍：不做**
- 不修改 consolidate_memory.py 核心邏輯
- 不改 memory-consolidator cron job prompt
- 不處理 compaction decay（那是另一個專案）
- 不做 BV 瓶頸分析

**規模預估**：新增 ~100 行 Python + 更新 1 行 memory。不新增依賴。

---

## 風險

| 風險 | 對策 |
|------|------|
| 沒有新的 synthesis 檔時 briefing.py 輸出空 | 輸出「尚無新 insight」而非 crash |
| briefing 過長塞滿 memory | hard cap 1000 chars，超過截斷 |
| synthesis 格式變更導致 parse 失敗 | 寬鬆解析 frontmatter + heading，fallback 到全文摘要 |

---

## 實作任務

### Task 1: 寫 `briefing.py`

**Objective:** 從最新 consolidation synthesis 萃取 briefing

**Files:**
- Create: `~/.hermes/scripts/briefing.py`

**Step 1: 實作**

```python
#!/usr/bin/env python3
"""
Briefing generator — extracts key insights from consolidation synthesis
and writes a concise briefing for agent context injection.

Usage:
    python3 briefing.py              # generate briefing from latest synthesis
    python3 briefing.py --print      # print to stdout instead of writing file
"""

import os, sys, glob, re, argparse
from datetime import datetime

SYNTHESIS_DIR = os.path.expanduser("~/obsidian-vault/research")
BRIEFING_FILE = os.path.expanduser("~/.hermes/consolidation_briefing.md")
MAX_BRIEFING_CHARS = 1000


def find_latest_synthesis() -> str | None:
    """Find the most recent consolidation synthesis file."""
    patterns = [
        os.path.join(SYNTHESIS_DIR, "*consolidation-synthesis*"),
        os.path.join(SYNTHESIS_DIR, "*consolidation-step*"),
    ]
    candidates = []
    for pat in patterns:
        candidates.extend(glob.glob(pat))
    if not candidates:
        return None
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def extract_yaml_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter between --- markers."""
    match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).strip().split('\n'):
        if ':' in line:
            key, _, val = line.partition(':')
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def extract_heading_section(text: str, heading: str) -> str:
    """Extract content under a ## heading until the next ## heading."""
    # Match: ## Heading Name\n(content until next ## or EOF)
    pattern = rf'^##\s+{re.escape(heading)}.*?\n(.*?)(?=\n##\s|\Z)'
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def extract_key_themes(text: str) -> str:
    """Extract Cross-Cutting Theme headings as bullet list."""
    themes = re.findall(r'^##\s+Cross-Cutting Theme \d+: (.+)$', text, re.MULTILINE)
    if themes:
        return "\n".join(f"- {t}" for t in themes)
    return ""


def extract_next_steps(text: str) -> str:
    """Extract actionable next steps."""
    section = extract_heading_section(text, "可行動的 Next Steps")
    if not section:
        return ""
    # Grab only the immediate/short-term items, skip checkmarks
    lines = section.split('\n')
    items = []
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith('- ')):
            # Strip checkmark emoji
            clean = re.sub(r'^[\d.\s✅🔄]*\s*', '', line)
            if clean and len(clean) > 10:
                items.append(f"- {clean}")
    return "\n".join(items[:3])  # cap at 3


def extract_quality_confidence(text: str) -> str:
    """Extract confidence assessment."""
    fm = extract_yaml_frontmatter(text)
    conf = fm.get('confidence', 'unknown')
    # Also check quality self-assessment table
    section = extract_heading_section(text, "品質自我評估")
    if section and 'high' in section.lower():
        conf = 'high'
    return conf


def generate_briefing(path: str) -> str:
    """Generate a concise briefing from a synthesis file."""
    with open(path) as f:
        text = f.read()

    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    basename = os.path.basename(path).replace('.md', '')
    conf = extract_quality_confidence(text)
    themes = extract_key_themes(text)
    summary = extract_heading_section(text, "摘要")

    # Build briefing
    lines = []
    lines.append(f"# Consolidation Briefing")
    lines.append(f"**更新時間**: {mtime.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**來源**: `{basename}`")
    lines.append(f"**信心**: {conf}")
    lines.append("")

    if summary:
        # Truncate summary to ~200 chars
        if len(summary) > 250:
            summary = summary[:247] + "..."
        lines.append(f"## 摘要\n{summary}")
        lines.append("")

    if themes:
        lines.append(f"## 核心主題\n{themes}")
        lines.append("")

    next_steps = extract_next_steps(text)
    if next_steps:
        lines.append(f"## 下一步\n{next_steps}")
        lines.append("")

    result = "\n".join(lines)

    # Hard cap
    if len(result) > MAX_BRIEFING_CHARS:
        result = result[:MAX_BRIEFING_CHARS-20] + "\n\n[...truncated]"

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate consolidation briefing")
    parser.add_argument("--print", action="store_true",
                        help="Print to stdout instead of writing file")
    args = parser.parse_args()

    path = find_latest_synthesis()
    if not path:
        msg = "⚠️ 尚無 consolidation synthesis 檔案\n"
        if args.print:
            print(msg, end="")
        else:
            os.makedirs(os.path.dirname(BRIEFING_FILE), exist_ok=True)
            with open(BRIEFING_FILE, "w") as f:
                f.write(msg)
        return 0

    briefing = generate_briefing(path)

    if args.print:
        print(briefing)
        return 0

    os.makedirs(os.path.dirname(BRIEFING_FILE), exist_ok=True)
    with open(BRIEFING_FILE, "w") as f:
        f.write(briefing)
    print(f"Briefing written to {BRIEFING_FILE} ({len(briefing)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Test**

```bash
chmod +x ~/.hermes/scripts/briefing.py
python3 ~/.hermes/scripts/briefing.py --print
```

Expected: 簡潔 briefing 輸出，<1000 chars。

---

### Task 2: Memory 加入 briefing 指標

**Objective:** Memory 加上一行，讓 agent 知道 briefing 存在

用 `memory` tool 在「你的筆記」區塊加入一行：
```
Consolidation briefing: ~/.hermes/consolidation_briefing.md（由 briefing.py 每 12h 更新）
```

---

### Task 3: 排 cron 自動更新 briefing

**Objective:** consolidation synthesis 完成後，自動生成 briefing

**方式 A**（簡單）：新增獨立 cron job `briefing-updater`，每 13h 跑一次（跑在 memory-consolidator 之後）
**方式 B**（緊耦合）：修改 memory-consolidator cron job 的 prompt，在 synthesis 完成後呼叫 briefing.py

選 **方式 A**，理由：
- 獨立，不影響現有 consolidation 流程
- 失敗不影響 consolidation
- 簡單

Cron spec:
```
schedule: "30 */12 * * *"     # 12:30, 00:30 — 跑在 consolidation (12:00, 00:00) 之後
deliver: "local"
toolsets: ["terminal"]
prompt: "執行 python3 ~/.hermes/scripts/briefing.py"
```

---

### Task 4: 確認 briefing 在 session 中可用

**Objective:** 驗證新的 session 能讀到 briefing

1. 確保 briefing 檔存在
2. 手動跑 `briefing.py --print` 確認內容
3. 確認 memory 包含 briefing 指標
4. 在下一個 session（或本 session）中讀取 briefing 內容

---

## 預估

- Task 1: ~5 分鐘（寫 code + 測試）
- Task 2: ~1 分鐘（memory update）
- Task 3: ~1 分鐘（cronjob create）
- Task 4: ~1 分鐘（驗證）

**總計**: ~8 分鐘
