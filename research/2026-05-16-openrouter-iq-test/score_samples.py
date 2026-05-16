"""Auto-score the 200+ samples from consistency.jsonl + nvidia.jsonl using heuristics.

Scoring per probe (matches scoring.md rubric, 0 / 0.5 / 1):
- P1 hallucination: detect refusal/admission phrases → 1; else 0
- P2 number_trap: content stripped equals "9.9" → 1; else 0
- P4 logic: contains "B 是誠實" / "B 誠實" / "B is honest" → 1; else 0
- P6 instruction: parse JSON; answer == "玉山" → 1 (0.5 if wrapped in markdown)

Output: scored.csv + drift.md (cross-provider comparison on shared models)
"""

import json
import os
import re
from collections import defaultdict

P1_REFUSAL_PATTERNS = [
    r"找不到", r"没有公开记录", r"沒有公開記錄", r"不存在", r"無法找到",
    r"记忆偏差", r"記憶偏差", r"无法确认", r"無法確認", r"can.?t find",
    r"not aware", r"no such paper", r"未找到", r"无此论文", r"no record",
    r"建议核实", r"建議核實", r"可能涉及",
]
P4_HONEST_B = [r"B\s*是\s*[誠诚]實?", r"B\s*[誠诚]實", r"B\s*is\s*honest",
                r"唯一[誠诚]實", r"only\s+B", r"诚实的是\s*B", r"誠實者[是为]?\s*B",
                r"B\s*說真話", r"B\s*说真话"]

def load(path):
    out = {}  # (model, probe, sample) -> latest best record
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            try: r = json.loads(line)
            except: continue
            k = (r["model"], r["probe"], r["sample"])
            good = r.get("ok") and (r.get("content") or "").strip()
            cur = out.get(k)
            cur_good = cur and cur.get("ok") and (cur.get("content") or "").strip()
            if not cur or (good and not cur_good):
                out[k] = r
    return out

def score_p1(content):
    """Hallucination resistance: 1 if refuses/admits unknown, 0 if confidently fabricates."""
    c = content
    for pat in P1_REFUSAL_PATTERNS:
        if re.search(pat, c, re.IGNORECASE):
            return 1.0
    # short responses (under 60 chars) likely refusal-ish
    if len(c.strip()) < 60 and ("無" in c or "沒有" in c or "不" in c or "no" in c.lower()):
        return 1.0
    return 0.0

def score_p2(content):
    """9.9 vs 9.11: extract first number-like token."""
    c = content.strip()
    # Common cases: just "9.9" or "9.11" or wrapped
    m = re.search(r"9\.\s*9(?!\d)", c) or re.search(r"^9\.9\b", c)
    if m:
        # also check it's not "9.91" or similar
        if re.search(r"9\.11", c) and content.strip() not in ("9.9", "9.9。", "9.9.", "**9.9**"):
            # both numbers mentioned — find which is concluded
            # last number mentioned wins (often "答案是 X" pattern)
            last = re.findall(r"9\.(?:9|11)", c)
            if last and last[-1] == "9.9": return 1.0
            return 0.0
        return 1.0
    if re.match(r"^\s*9\.11\b", c) or c.strip() in ("9.11", "9.11。"):
        return 0.0
    # ambiguous
    return 0.0

def score_p4(content):
    """B is honest. Strict on B and not other letters."""
    c = content
    # check the conclusion
    for pat in P4_HONEST_B:
        if re.search(pat, c, re.IGNORECASE):
            # also confirm not "A and B both honest" type
            if re.search(r"A.{0,3}(和|與|与|and|&).{0,3}B.{0,8}[誠诚]", c) and not re.search(r"only|唯一|仅|僅", c):
                return 0.0
            return 1.0
    return 0.0

def score_p6(content):
    """JSON {answer:玉山, confidence:...}."""
    c = content.strip()
    # try direct parse
    try:
        d = json.loads(c)
        if d.get("answer") == "玉山":
            return 1.0
    except Exception:
        pass
    # try stripping markdown fence
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", c, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            if d.get("answer") == "玉山":
                return 0.5  # JSON correct but wrapped (penalty)
        except: pass
    # fallback: contains 玉山 + {...}
    if "玉山" in c and "{" in c and "}" in c:
        return 0.5
    return 0.0

SCORERS = {
    "P1_hallucination": score_p1,
    "P2_number_trap": score_p2,
    "P4_logic": score_p4,
    "P6_instruction": score_p6,
}

def main():
    base = "C:/claudehome/projects/managed-agents-research/research/2026-05-16-openrouter-iq-test/data"
    or_data = load(f"{base}/consistency.jsonl")
    nv_data = load(f"{base}/nvidia.jsonl")

    # Score each
    rows = []
    for prov, src in [("openrouter", or_data), ("nvidia", nv_data)]:
        for (m, p, s), r in src.items():
            if not (r.get("ok") and (r.get("content") or "").strip()):
                rows.append({"provider": prov, "model": m, "probe": p, "sample": s, "score": None, "content_len": 0})
                continue
            score = SCORERS[p](r["content"])
            rows.append({"provider": prov, "model": m, "probe": p, "sample": s,
                         "score": score, "content_len": len(r["content"])})

    # Save scored
    with open(f"{base}/scored.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Aggregate per (provider, model, probe)
    agg = defaultdict(list)
    for row in rows:
        if row["score"] is not None:
            agg[(row["provider"], row["model"], row["probe"])].append(row["score"])

    # Build summary
    print("=== Consistency Summary ===")
    print(f"{'provider':10s} {'model':50s} {'probe':18s} | n | mean | distribution")
    for (prov, m, p), scores in sorted(agg.items()):
        n = len(scores)
        mean = sum(scores)/n if n else 0
        dist = {0: scores.count(0), 0.5: scores.count(0.5), 1: scores.count(1)}
        ds = f"0:{dist[0]} 0.5:{dist[0.5]} 1:{dist[1]}"
        print(f"{prov:10s} {m[:48]:50s} {p:18s} | {n} | {mean:.2f} | {ds}")

    # Per-model average across all probes
    print("\n=== Per-Model Average (across probes & samples) ===")
    per_model = defaultdict(list)
    for (prov, m, p), scores in agg.items():
        per_model[(prov, m)].extend(scores)
    for (prov, m), all_scores in sorted(per_model.items(), key=lambda x: -sum(x[1])/len(x[1])):
        n = len(all_scores)
        mean = sum(all_scores)/n
        print(f"  [{prov:10s}] {m[:48]:50s} {mean:.2f}  (n={n})")

    # Cross-provider drift (same model on both)
    print("\n=== Cross-Provider Drift (shared models) ===")
    by_model_prov = defaultdict(lambda: defaultdict(list))
    for (prov, m), all_scores in per_model.items():
        by_model_prov[m][prov] = all_scores
    for m, by_prov in by_model_prov.items():
        if len(by_prov) == 2:
            or_s = by_prov["openrouter"]; nv_s = by_prov["nvidia"]
            or_mean = sum(or_s)/len(or_s); nv_mean = sum(nv_s)/len(nv_s)
            delta = nv_mean - or_mean
            print(f"  {m[:48]:50s} OR={or_mean:.2f} (n={len(or_s)})  NV={nv_mean:.2f} (n={len(nv_s)})  Δ={delta:+.2f}")

if __name__ == "__main__":
    main()
