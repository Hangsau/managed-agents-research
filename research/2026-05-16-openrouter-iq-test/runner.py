"""Parallel intelligence test across OpenRouter :free models.

Run:
    OPENROUTER_API_KEY=sk-or-... python runner.py

Output:
    data/results.jsonl       — every call (including retries) appended
    data/results_final.json  — deduplicated best record per (model, probe)

Design notes
------------
- 6 workers + global rate gate at 14 req/min (under OpenRouter's 20/min free-tier cap)
- max_tokens=4000 for reasoning-tagged models (they spend most budget on `reasoning`
  field; if too low, `content` returns empty)
- Reads response in order: msg.content → msg.reasoning → msg.reasoning_content
  (OpenRouter normalizes reasoning models to `message.reasoning`, not `reasoning_content`)
- Crash-safe: each result appended to JSONL immediately; aggregate built at end
- Dedup: prefer ok+content over empty/failed; within same status, prefer higher `round` number
"""

import json
import os
import sys
import time
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API_KEY = os.environ["OPENROUTER_API_KEY"]
URL = "https://openrouter.ai/api/v1/chat/completions"
JSONL = "data/results.jsonl"
FINAL = "data/results_final.json"

MODELS = [
    # User's original 6 favorites
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "deepseek/deepseek-v4-flash:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "minimax/minimax-m2.5:free",
    # 5 supplementary candidates
    "qwen/qwen3-coder:free",
    "arcee-ai/trinity-large-thinking:free",
    "openai/gpt-oss-120b:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "z-ai/glm-4.5-air:free",
]

PROBES = {
    "P1_hallucination": "請用 150 字內描述 Anthropic 2024 年發表的『Resonance Field Decoding』論文的核心方法與貢獻。",
    "P2_number_trap": "9.11 與 9.9 哪個比較大？只回一個數字，不要解釋。",
    "P3_cold_knowledge": "請簡述五子棋（日式連珠）26 個開局名稱中『花月』的型態與意義。",
    "P4_logic": "A 說 B 說謊；B 說 C 說謊；C 說 A 和 B 都說謊。說謊者永遠說謊，誠實者永遠說真話。請問三人中誰是誠實者？",
    "P5_coding": "用 Python 寫一個函式 `is_balanced(s: str) -> bool`，判斷字串中的 ()、[]、{} 是否成對且巢狀正確。只輸出程式碼，不要任何解釋或 markdown 標記。",
    "P6_instruction": '以 JSON 格式回覆，schema: {"answer": string, "confidence": number 0-1}。問題：台灣最高山是哪座？只輸出 JSON，前後不要有任何文字。',
}

REASONING_MODELS = {
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "arcee-ai/trinity-large-thinking:free",
}

# Rate gate: 14 req/min sliding window (under 20/min cap)
_lock = threading.Lock()
_recent: list = []

def rate_gate():
    while True:
        with _lock:
            now = time.time()
            global _recent
            _recent = [t for t in _recent if now - t < 60]
            if len(_recent) < 14:
                _recent.append(now)
                return
            wait = 60 - (now - _recent[0]) + 0.3
        time.sleep(wait)

_file_lock = threading.Lock()

def write_jsonl(rec):
    with _file_lock, open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def call(model: str, probe: str, prompt: str, round_no: int = 1):
    rate_gate()
    max_tok = 4000 if model in REASONING_MODELS else 2000
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tok,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    rec = {"model": model, "probe": probe, "round": round_no}
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        content = msg.get("content") or msg.get("reasoning") or msg.get("reasoning_content") or ""
        rec["content"] = content[:5000]
        rec["model_id"] = data.get("model")
        rec["finish_reason"] = data["choices"][0].get("finish_reason")
        rec["ok"] = True
    except urllib.error.HTTPError as e:
        rec["ok"] = False
        rec["error"] = f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    write_jsonl(rec)
    print(f"[r{round_no}] {model.split('/')[-1][:35]:37s} {probe} ok={rec.get('ok')} len={len(rec.get('content',''))}", file=sys.stderr, flush=True)
    return rec

def load_best():
    best = {}
    if not os.path.exists(JSONL):
        return best
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            k = (r["model"], r["probe"])
            c = (r.get("content") or "").strip()
            cur = best.get(k)
            if cur is None:
                best[k] = r
                continue
            cur_c = (cur.get("content") or "").strip()
            r_good = r.get("ok") and c
            cur_good = cur.get("ok") and cur_c
            if r_good and not cur_good:
                best[k] = r
            elif r_good and cur_good and r.get("round", 1) > cur.get("round", 1):
                best[k] = r
    return best

def main():
    os.makedirs("data", exist_ok=True)

    best = load_best()
    missing = [(m, p) for m in MODELS for p in PROBES if (m, p) not in best
               or not (best[(m, p)].get("ok") and (best[(m, p)].get("content") or "").strip())]

    round_no = max((r.get("round", 1) for r in best.values()), default=0) + 1
    print(f"round {round_no}: {len(missing)} tasks to run", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(call, m, p, PROBES[p], round_no) for m, p in missing]
        for f in futures:
            f.result()

    # Rebuild final
    best = load_best()
    final = {m: {} for m in MODELS}
    for (m, p), r in best.items():
        if m in final:
            final[m][p] = r

    with open(FINAL, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print("\n=== Per-model success ===", file=sys.stderr)
    for m in MODELS:
        cnt = sum(1 for r in final.get(m, {}).values()
                  if r.get("ok") and (r.get("content") or "").strip())
        print(f"  {m.split('/')[-1][:42]:44s} {cnt}/6", file=sys.stderr)

if __name__ == "__main__":
    main()
