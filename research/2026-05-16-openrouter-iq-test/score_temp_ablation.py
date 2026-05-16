"""Score temp_ablation.jsonl and print pivot table by temperature.

Usage: python score_temp_ablation.py
"""

import json
import re
import sys
from collections import defaultdict

JSONL = "data/temp_ablation.jsonl"

P1_REFUSAL = [
    r"找不到", r"没有公开记录", r"沒有公開記錄", r"不存在", r"無法找到",
    r"记忆偏差", r"記憶偏差", r"无法确认", r"無法確認", r"can.?t find",
    r"not aware", r"no such paper", r"未找到", r"无此论文", r"no record",
    r"建议核实", r"建議核實", r"可能涉及",
]
P4_HONEST_B = [
    r"B\s*是\s*[誠诚]實?", r"B\s*[誠诚]實", r"B\s*is\s*honest",
    r"唯一[誠诚]實", r"only\s+B", r"诚实的是\s*B", r"誠實者[是为]?\s*B",
    r"B\s*說真話", r"B\s*说真话",
]


def score_p1(c):
    for pat in P1_REFUSAL:
        if re.search(pat, c, re.IGNORECASE):
            return 1.0
    if len(c.strip()) < 60 and any(w in c for w in ["無", "沒有", "不", "no"]):
        return 1.0
    return 0.0


def score_p4(c):
    for pat in P4_HONEST_B:
        if re.search(pat, c, re.IGNORECASE):
            if re.search(r"A.{0,3}(和|與|与|and|&).{0,3}B.{0,8}[誠诚]", c) and \
               not re.search(r"only|唯一|仅|僅", c):
                return 0.0
            return 1.0
    return 0.0


SCORERS = {"P1_hallucination": score_p1, "P4_logic": score_p4}


def main():
    records = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if not (r.get("ok") and (r.get("content") or "").strip()):
                continue
            probe = r["probe"]
            if probe not in SCORERS:
                continue
            score = SCORERS[probe](r["content"])
            records.append({
                "model": r["model"].split("/")[-1][:28],
                "probe": probe,
                "temp": r["temperature"],
                "sample": r.get("sample"),
                "score": score,
                "content_len": len(r.get("content", "")),
            })

    # Aggregate: mean score per (model, probe, temp)
    agg = defaultdict(list)
    for rec in records:
        agg[(rec["model"], rec["probe"], rec["temp"])].append(rec["score"])

    temperatures = [0.0, 0.3, 0.5, 0.7]
    probes = ["P1_hallucination", "P4_logic"]
    models = sorted(set(r["model"] for r in records))

    for probe in probes:
        print(f"\n=== {probe} — mean score by temperature ===")
        header = f"{'Model':30s}" + "".join(f"  T={t}" for t in temperatures)
        print(header)
        for m in models:
            row = f"{m:30s}"
            for t in temperatures:
                scores = agg.get((m, probe, t), [])
                if scores:
                    row += f"  {sum(scores)/len(scores):.2f}"
                else:
                    row += "    —"
            n_70 = len(agg.get((m, probe, 0.7), []))
            print(row + f"   (T=0.7 from consistency.jsonl, n varies)")
        print()

    # Also print raw n per cell
    print("=== Sample counts per cell ===")
    for m in models:
        for probe in probes:
            row = f"  {m:30s} {probe}"
            for t in temperatures:
                scores = agg.get((m, probe, t), [])
                row += f"  T={t}:n={len(scores)}"
            print(row)


if __name__ == "__main__":
    main()
