"""Round 6: fill missing OR samples (any gap in 0-5) + add samples 6,7,8.

Reads consistency.jsonl to find which (model, probe, sample) are missing or failed,
then runs them at T=0.7. Appends to data/consistency.jsonl with provider="openrouter".

Target: all 9 OR models × 4 probes × samples 0-8 = 324 valid records.
"""

import json
import os
import sys
import time
import threading
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

OR_KEY = os.environ["OPENROUTER_API_KEY"]
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
JSONL = "data/consistency.jsonl"

OR_MODELS = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "deepseek/deepseek-v4-flash:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "minimax/minimax-m2.5:free",
    "arcee-ai/trinity-large-thinking:free",
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
]

PROBES = {
    "P1_hallucination": "請用 150 字內描述 Anthropic 2024 年發表的『Resonance Field Decoding』論文的核心方法與貢獻。",
    "P2_number_trap": "9.11 與 9.9 哪個比較大？只回一個數字，不要解釋。",
    "P4_logic": "A 說 B 說謊；B 說 C 說謊；C 說 A 和 B 都說謊。說謊者永遠說謊，誠實者永遠說真話。請問三人中誰是誠實者？",
    "P6_instruction": '以 JSON 格式回覆，schema: {"answer": string, "confidence": number 0-1}。問題：台灣最高山是哪座？只輸出 JSON，前後不要有任何文字。',
}

REASONING = {
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "arcee-ai/trinity-large-thinking:free",
}

TARGET_SAMPLES = list(range(9))  # 0-8; fill gaps in 0-5 + add 6,7,8
TEMPERATURE = 0.7

_lock = threading.Lock()
_recent: list = []
_fl = threading.Lock()


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


def write(rec):
    with _fl, open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_existing():
    """Return set of (model, probe, sample) that already have a valid record."""
    existing = set()
    if not os.path.exists(JSONL):
        return existing
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ok") and (r.get("content") or "").strip():
                existing.add((r["model"], r["probe"], r.get("sample")))
    return existing


def call(model, probe, sample):
    rate_gate()
    max_tok = 4000 if model in REASONING else 2000
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROBES[probe]}],
        "max_tokens": max_tok,
        "temperature": TEMPERATURE,
    }).encode("utf-8")
    req = urllib.request.Request(OR_URL, data=body, headers={
        "Authorization": f"Bearer {OR_KEY}",
        "Content-Type": "application/json",
    }, method="POST")
    rec = {"provider": "openrouter", "model": model, "probe": probe,
           "sample": sample, "temperature": TEMPERATURE, "round": 6}
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        content = msg.get("content") or msg.get("reasoning") or msg.get("reasoning_content") or ""
        rec["content"] = content[:5000]
        rec["model_id"] = data.get("model")
        rec["ok"] = True
    except urllib.error.HTTPError as e:
        rec["ok"] = False
        rec["error"] = f"HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    write(rec)
    print(f"  [or] {model.split('/')[-1][:35]:37s} {probe} s{sample} ok={rec.get('ok')}", file=sys.stderr, flush=True)
    return rec


def main():
    existing = load_existing()
    tasks = []
    for m in OR_MODELS:
        for p in PROBES:
            for s in TARGET_SAMPLES:
                if (m, p, s) not in existing:
                    tasks.append((m, p, s))

    print(f"round 6: {len(tasks)} tasks to run (target 0-8 for {len(OR_MODELS)} models x {len(PROBES)} probes)", file=sys.stderr)
    if not tasks:
        print("Nothing to do — all cells already complete.", file=sys.stderr)
        return

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(call, m, p, s) for m, p, s in tasks]
        for f in futs:
            f.result()

    # Coverage report
    existing2 = load_existing()
    print("\n=== Post-run coverage ===", file=sys.stderr)
    for m in OR_MODELS:
        counts = [sum(1 for s in TARGET_SAMPLES if (m, p, s) in existing2) for p in PROBES]
        print(f"  {m.split('/')[-1][:37]:39s} {counts}", file=sys.stderr)
    print("ROUND6 DONE", file=sys.stderr)


if __name__ == "__main__":
    main()
