from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import OUTPUT_DIR
from llm_client import MissingLLMCache, call_json


SYSTEM = """Türkçe iş tanımı ile NACE faaliyet kodu uyumunu kontrol eden dikkatli bir değerlendiricisin.
Sadece geçerli JSON döndür. Verdict alanı yes/no/unsure değerlerinden biri olmalı."""


def validate_batch(batch: pd.DataFrame) -> dict[str, str]:
    items = []
    for idx, row in batch.iterrows():
        items.append(
            {
                "id": str(idx),
                "alias": row["alias"],
                "meslek_tanim": row["meslek_tanim"],
                "nace_code": row["nace_code"],
                "nace_label": row["nace_label"],
            }
        )
    parsed = call_json(
        task="alias_validation",
        system=SYSTEM,
        user=json.dumps(
            {
                "instruction": (
                    "Her satır için şu soruyu cevapla: Türkçe konuşan biri kendine alias ifadesini diyorsa, "
                    "bu işletme verilen NACE kodu altında makul biçimde çalışır mı? "
                    "Cevap yes/no/unsure olsun. Dar ve dürüst davran."
                ),
                "items": items,
                "schema": {"results": [{"id": "string", "verdict": "yes|no|unsure"}]},
            },
            ensure_ascii=False,
        ),
        max_tokens=1200,
    )
    results = parsed.get("results", [])
    verdicts = {}
    for item in results:
        verdict = str(item.get("verdict", "")).lower()
        if verdict in {"yes", "no", "unsure"}:
            verdicts[str(item.get("id"))] = verdict
    return verdicts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()

    path = OUTPUT_DIR / "alias_candidates.csv"
    out = pd.read_csv(path, dtype={"nace_code": str})
    out["validation"] = "not-sampled"

    pool = out[out["provenance"].eq("llm-generated")].copy()
    if len(pool) > args.sample_size:
        random.seed(42)
        sample_idx = random.sample(list(pool.index), args.sample_size)
        sample = out.loc[sample_idx].copy()
    else:
        sample = pool

    verdicts: dict[str, str] = {}
    failures = []
    for start in range(0, len(sample), args.batch_size):
        batch = sample.iloc[start : start + args.batch_size]
        try:
            verdicts.update(validate_batch(batch))
        except MissingLLMCache as exc:
            failures.append(str(exc))
            break
        except Exception as exc:
            failures.append(repr(exc))

    for idx_str, verdict in verdicts.items():
        idx = int(idx_str)
        out.loc[idx, "validation"] = verdict
        if verdict == "no":
            out.loc[idx, "confidence"] = float(out.loc[idx, "confidence"]) * 0.45
        elif verdict == "unsure":
            out.loc[idx, "confidence"] = float(out.loc[idx, "confidence"]) * 0.70

    meslek_counts = out.groupby("normalized_alias")["meslek_kodu"].nunique()
    out["ambiguous"] = out["normalized_alias"].map(meslek_counts).fillna(0).astype(int) > 1
    final_cols = [
        "alias",
        "normalized_alias",
        "nace_code",
        "nace_label",
        "bucket",
        "confidence",
        "provenance",
        "ambiguous",
        "meslek_kodu",
        "meslek_tanim",
        "validation",
    ]
    out[final_cols].to_csv(OUTPUT_DIR / "alias_table.csv", index=False, encoding="utf-8")
    if failures:
        (OUTPUT_DIR / "validation_failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"Wrote {OUTPUT_DIR / 'alias_table.csv'} ({len(out)} rows)")
    print(f"Validated sampled rows: {len(verdicts)} / {len(sample)}")
    print(f"Validation failures: {len(failures)}")


if __name__ == "__main__":
    main()
