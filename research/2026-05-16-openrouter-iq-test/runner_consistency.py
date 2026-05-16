"""Round 4: consistency check.

Same 4 high-discrimination probes (P1/P2/P4/P6), 3 samples each at temperature=0.7.
Output: data/consistency.jsonl (each line = one of the 3 samples).

Skip:
- P3 cold_knowledge: all models failed (0/0.5) → no signal
- P5 coding: all models passed (1.0) → no signal
- qwen3-coder, hermes-3-405b: guardrail blocked

Why temp=0.7: temperature=0 gives same answer every time. To measure consistency
across stochastic sampling, we need a temperature > 0.
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
JSONL = "data/consistency.jsonl"

MODELS = [
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

REASONING_MODELS = {
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "arcee-ai/trinity-large-thinking:free",
}

SAMPLES_PER_PROBE = 3
TEMPERATURE = 0.7

# Rate gate 14 req/min
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

_fl = threading.Lock()

def write_jsonl(rec):
    with _fl, open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def call(model, probe, prompt, sample_idx):
    rate_gate()
    max_tok = 4000 if model in REASONING_MODELS else 2000
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tok,
        "temperature": TEMPERATURE,
        "seed": 1000 + sample_idx,  # reproducible-ish samples
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }, method="POST")
    rec = {"model": model, "probe": probe, "sample": sample_idx, "temperature": TEMPERATURE}
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
    print(f"  {model.split('/')[-1][:35]:37s} {probe} s{sample_idx} ok={rec.get('ok')} len={len(rec.get('content',''))}",
          file=sys.stderr, flush=True)
    return rec

def main():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(JSONL):
        os.remove(JSONL)

    tasks = [(m, p, i) for m in MODELS for p in PROBES for i in range(SAMPLES_PER_PROBE)]
    print(f"total tasks: {len(tasks)}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(call, m, p, PROBES[p], i) for m, p, i in tasks]
        for f in futures:
            f.result()

    # Aggregate per (model, probe): collect 3 contents
    agg = {}
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            key = (r["model"], r["probe"])
            agg.setdefault(key, []).append(r)

    with open("data/consistency_aggregate.json", "w", encoding="utf-8") as f:
        json.dump({f"{m}|{p}": v for (m,p), v in agg.items()}, f, ensure_ascii=False, indent=2)

    print("DONE", file=sys.stderr)

if __name__ == "__main__":
    main()
