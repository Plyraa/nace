from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolver import resolve  # noqa: E402


def code_hit(candidates, gold_codes: set[str], top_k: int) -> bool:
    return any(c.nace_code in gold_codes for c in candidates[:top_k])


def main() -> None:
    cases = pd.read_csv(ROOT / "eval" / "test_cases.csv", dtype=str).fillna("")
    rows = []
    fallback_count = 0
    match_counter = Counter()
    for _, case in cases.iterrows():
        candidates = resolve(case["utterance"], k=3)
        if candidates and candidates[0].match_type == "llm":
            fallback_count += 1
        for cand in candidates[:1]:
            match_counter[cand.match_type] += 1
        gold_codes = {c.strip() for c in case["acceptable_nace_codes"].split("|") if c.strip()}
        top1 = code_hit(candidates, gold_codes, 1)
        top3 = code_hit(candidates, gold_codes, 3)
        bucket = bool(candidates and candidates[0].bucket == case["gold_bucket"])
        rows.append(
            {
                "utterance": case["utterance"],
                "category": case["category"],
                "gold_bucket": case["gold_bucket"],
                "top1_nace": top1,
                "top3_nace": top3,
                "bucket_hit": bucket,
                "pred_code": candidates[0].nace_code if candidates else "",
                "pred_bucket": candidates[0].bucket if candidates else "",
                "score": candidates[0].score if candidates else 0,
                "match_type": candidates[0].match_type if candidates else "none",
                "acceptable_nace_codes": case["acceptable_nace_codes"],
            }
        )

    result = pd.DataFrame(rows)
    summary = {
        "cases": int(len(result)),
        "top1_nace_accuracy": round(float(result["top1_nace"].mean()), 4),
        "top3_nace_accuracy": round(float(result["top3_nace"].mean()), 4),
        "bucket_accuracy": round(float(result["bucket_hit"].mean()), 4),
        "llm_fallback_top1_count": int(fallback_count),
        "top1_match_type_counts": dict(match_counter),
        "by_category": {},
        "by_match_type": {},
    }
    for category, group in result.groupby("category"):
        summary["by_category"][category] = {
            "n": int(len(group)),
            "top1": round(float(group["top1_nace"].mean()), 4),
            "top3": round(float(group["top3_nace"].mean()), 4),
            "bucket": round(float(group["bucket_hit"].mean()), 4),
        }
    for match_type, group in result.groupby("match_type"):
        summary["by_match_type"][match_type] = {
            "n": int(len(group)),
            "top1": round(float(group["top1_nace"].mean()), 4),
            "top3": round(float(group["top3_nace"].mean()), 4),
            "bucket": round(float(group["bucket_hit"].mean()), 4),
        }

    worst = result[~result["top1_nace"]].sort_values(["bucket_hit", "score"]).head(15)
    (ROOT / "output").mkdir(exist_ok=True)
    result.to_csv(ROOT / "output" / "eval_predictions.csv", index=False, encoding="utf-8")
    (ROOT / "output" / "eval_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not worst.empty:
        print("\nWorst failures:")
        print(worst[["utterance", "category", "acceptable_nace_codes", "pred_code", "pred_bucket", "score", "match_type"]].to_string(index=False))


if __name__ == "__main__":
    main()
