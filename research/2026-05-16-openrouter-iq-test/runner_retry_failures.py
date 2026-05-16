"""Retry failed samples from both consistency.jsonl and nvidia.jsonl.

Root cause of OpenRouter failures: the `seed` parameter triggered HTTP 502
on OpenInference upstream (gpt-oss-120b, minimax-m2.5). This retry omits seed.

NVIDIA failures: qwen3-coder-480b sporadic 503 ResourceExhausted. Wait and retry.
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

# Rate gates per provider
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
    body_data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tok,
        "temperature": 0.7,
    }  # NOTE: no seed (caused OpenInference 502)
    url = OR_URL if provider == "openrouter" else NV_URL
    key = OR_KEY if provider == "openrouter" else NV_KEY
    req = urllib.request.Request(url, data=json.dumps(body_data).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    rec = {"provider": provider, "model": model, "probe": probe, "sample": sample,
           "temperature": 0.7, "retry": True}
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

def collect_failures(path, provider):
    failures = set()
    if not os.path.exists(path):
        return failures
    # bucket by (model, probe, sample)
    by_key = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try: r = json.loads(line)
            except: continue
            key = (r["model"], r["probe"], r["sample"])
            good = r.get("ok") and (r.get("content") or "").strip()
            if key not in by_key or good:
                by_key[key] = good
    for k, good in by_key.items():
        if not good:
            failures.add(k)
    return failures

def main():
    or_fail = collect_failures("data/consistency.jsonl", "openrouter")
    nv_fail = collect_failures("data/nvidia.jsonl", "nvidia")
    print(f"openrouter failures: {len(or_fail)}", file=sys.stderr)
    print(f"nvidia failures: {len(nv_fail)}", file=sys.stderr)

    tasks = []
    for (m, p, s) in or_fail:
        tasks.append(("openrouter", m, p, s, PROBES[p], "data/consistency.jsonl"))
    for (m, p, s) in nv_fail:
        tasks.append(("nvidia", m, p, s, PROBES[p], "data/nvidia.jsonl"))

    print(f"total retry tasks: {len(tasks)}", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(call, *t) for t in tasks]
        for f in futures: f.result()

    print("RETRY DONE", file=sys.stderr)

if __name__ == "__main__":
    main()
