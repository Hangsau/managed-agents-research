"""NVIDIA NIM intelligence test — cross-provider comparison with OpenRouter.

Same 4 high-discrimination probes (P1/P2/P4/P6), 3 samples each at temperature=0.7,
matching runner_consistency.py exactly so results are directly comparable.

Models tested (8):
  Shared with OpenRouter (drift comparison):
    - openai/gpt-oss-120b
    - deepseek-ai/deepseek-v4-flash
    - google/gemma-4-31b-it
  NVIDIA-exclusive:
    - nvidia/llama-3.3-nemotron-super-49b-v1.5
    - meta/llama-3.3-70b-instruct
    - deepseek-ai/deepseek-v4-pro
    - qwen/qwen3-coder-480b-a35b-instruct  (OpenRouter blocked us with guardrail)
    - qwen/qwen3-next-80b-a3b-thinking     (Qwen reasoning)

Output: data/nvidia.jsonl
NVIDIA rate limit: 40 req/min per model (verified 2026-05). 3 samples → trivial.
"""

import json
import os
import sys
import time
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API_KEY = os.environ["NVIDIA_API_KEY"]
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
JSONL = "data/nvidia.jsonl"

MODELS = [
    # shared with OpenRouter (drift)
    "openai/gpt-oss-120b",
    "deepseek-ai/deepseek-v4-flash",
    "google/gemma-4-31b-it",
    # NVIDIA exclusive
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "meta/llama-3.3-70b-instruct",
    "deepseek-ai/deepseek-v4-pro",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "qwen/qwen3-next-80b-a3b-thinking",
]

PROBES = {
    "P1_hallucination": "請用 150 字內描述 Anthropic 2024 年發表的『Resonance Field Decoding』論文的核心方法與貢獻。",
    "P2_number_trap": "9.11 與 9.9 哪個比較大？只回一個數字，不要解釋。",
    "P4_logic": "A 說 B 說謊；B 說 C 說謊；C 說 A 和 B 都說謊。說謊者永遠說謊，誠實者永遠說真話。請問三人中誰是誠實者？",
    "P6_instruction": '以 JSON 格式回覆，schema: {"answer": string, "confidence": number 0-1}。問題：台灣最高山是哪座？只輸出 JSON，前後不要有任何文字。',
}

REASONING_MODELS = {"qwen/qwen3-next-80b-a3b-thinking"}

SAMPLES = 3
TEMPERATURE = 0.7

# Rate gate: 30 req/min global (NVIDIA is 40/min/model, so global 30 is safe across 8 models)
_lock = threading.Lock()
_recent: list = []

def gate():
    while True:
        with _lock:
            now = time.time()
            global _recent
            _recent = [t for t in _recent if now - t < 60]
            if len(_recent) < 30:
                _recent.append(now)
                return
            wait = 60 - (now - _recent[0]) + 0.3
        time.sleep(wait)

_fl = threading.Lock()

def write_jsonl(rec):
    with _fl, open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def call(model, probe, prompt, sample_idx):
    gate()
    max_tok = 4000 if model in REASONING_MODELS else 2000
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tok,
        "temperature": TEMPERATURE,
        "seed": 1000 + sample_idx,
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }, method="POST")
    rec = {"provider": "nvidia", "model": model, "probe": probe, "sample": sample_idx, "temperature": TEMPERATURE}
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        content = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
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
    print(f"  {model[:45]:47s} {probe} s{sample_idx} ok={rec.get('ok')} len={len(rec.get('content',''))}",
          file=sys.stderr, flush=True)
    return rec

def main():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(JSONL):
        os.remove(JSONL)

    tasks = [(m, p, i) for m in MODELS for p in PROBES for i in range(SAMPLES)]
    print(f"NVIDIA tasks: {len(tasks)}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(call, m, p, PROBES[p], i) for m, p, i in tasks]
        for f in futures:
            f.result()

    print("NVIDIA DONE", file=sys.stderr)

if __name__ == "__main__":
    main()
