"""Round 5: append 3 more samples (idx 3-5) to both providers.

Appends to existing data/consistency.jsonl and data/nvidia.jsonl.
After this run, each (model, probe) has 6 samples (indices 0-5).

No seed parameter (avoids OpenInference 502).
"""

import json
import os
import sys
import time
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OR_KEY = os.environ["OPENROUTER_API_KEY"]
NV_KEY = os.environ["NVIDIA_API_KEY"]
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
NV_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

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

NV_MODELS = [
    "openai/gpt-oss-120b",
    "deepseek-ai/deepseek-v4-flash",
    "google/gemma-4-31b-it",
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

REASONING = {
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "arcee-ai/trinity-large-thinking:free",
    "qwen/qwen3-next-80b-a3b-thinking",
}

SAMPLE_INDICES = [3, 4, 5]  # add 3 more on top of existing 0-2
TEMPERATURE = 0.7

_locks = {"or": threading.Lock(), "nv": threading.Lock()}
_recent = {"or": [], "nv": []}
_limits = {"or": 14, "nv": 28}

def gate(p):
    while True:
        with _locks[p]:
            now = time.time()
            _recent[p][:] = [t for t in _recent[p] if now - t < 60]
            if len(_recent[p]) < _limits[p]:
                _recent[p].append(now)
                return
            wait = 60 - (now - _recent[p][0]) + 0.3
        time.sleep(wait)

_fl = threading.Lock()

def write(path, rec):
    with _fl, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def call(provider, model, probe, sample, prompt, out_path):
    p = "or" if provider == "openrouter" else "nv"
    gate(p)
    max_tok = 4000 if model in REASONING else 2000
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tok,
        "temperature": TEMPERATURE,
    }).encode("utf-8")
    url = OR_URL if provider == "openrouter" else NV_URL
    key = OR_KEY if provider == "openrouter" else NV_KEY
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }, method="POST")
    rec = {"provider": provider, "model": model, "probe": probe, "sample": sample,
           "temperature": TEMPERATURE, "round": 5}
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
    write(out_path, rec)
    print(f"  [{provider[:2]}] {model.split('/')[-1][:35]:37s} {probe} s{sample} ok={rec.get('ok')}", file=sys.stderr, flush=True)

def main():
    tasks = []
    for m in OR_MODELS:
        for p in PROBES:
            for s in SAMPLE_INDICES:
                tasks.append(("openrouter", m, p, s, PROBES[p], "data/consistency.jsonl"))
    for m in NV_MODELS:
        for p in PROBES:
            for s in SAMPLE_INDICES:
                tasks.append(("nvidia", m, p, s, PROBES[p], "data/nvidia.jsonl"))

    print(f"round 5 tasks: {len(tasks)} ({len(OR_MODELS)*4*3} OR + {len(NV_MODELS)*4*3} NV)", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(call, *t) for t in tasks]
        for f in futs:
            f.result()
    print("ROUND5 DONE", file=sys.stderr)

if __name__ == "__main__":
    main()
