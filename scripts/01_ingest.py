from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DATA_DIR
from utils import bucket_for_code, clean_nace_code, load_bucket_maps, nace_division, normalize_text


def find_workbook() -> Path:
    matches = sorted(ROOT.glob("SektörMeslekNace*.xlsx"))
    if not matches:
        matches = sorted(ROOT.glob("*.xlsx"))
    if not matches:
        raise FileNotFoundError("No xlsx workbook found in project root")
    return matches[0]


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    workbook = find_workbook()
    raw = pd.read_excel(workbook, dtype=str)
    original_columns = list(raw.columns)
    raw.columns = [c.strip() for c in raw.columns]

    rename = {
        "SEKTOR KODU": "sektor_kodu",
        "SEKTOR TANIM": "sektor_tanim",
        "MESLEK KODU": "meslek_kodu",
        "MESLEK TANIM": "meslek_tanim",
        "NACE REV. 2.1 KODU": "nace_code",
        "NACE REV.2.1 TANIM": "nace_label",
        "NACE TANIM": "nace_label",
    }
    df = raw.rename(columns=rename)
    required = ["sektor_kodu", "sektor_tanim", "meslek_kodu", "meslek_tanim", "nace_code", "nace_label"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns after cleanup: {missing}")

    df = df[required].copy()
    for col in required:
        df[col] = df[col].astype(str).str.strip()
    df["nace_code"] = df["nace_code"].map(clean_nace_code)
    df["division"] = df["nace_code"].map(nace_division)
    division_map, exceptions = load_bucket_maps()
    df["bucket"] = df["nace_code"].map(lambda c: bucket_for_code(c, division_map, exceptions))
    df["normalized_meslek"] = df["meslek_tanim"].map(normalize_text)
    df["normalized_nace_label"] = df["nace_label"].map(normalize_text)
    df = df.drop_duplicates().sort_values(["meslek_kodu", "nace_code"]).reset_index(drop=True)

    nodes = (
        df.groupby(["meslek_kodu", "meslek_tanim", "normalized_meslek"], as_index=False)
        .agg(
            sektor_kodu=("sektor_kodu", lambda s: "|".join(sorted(set(s)))),
            sektor_tanim=("sektor_tanim", lambda s: "|".join(sorted(set(s)))),
            nace_codes=("nace_code", lambda s: "|".join(s)),
            nace_count=("nace_code", "nunique"),
        )
        .sort_values("meslek_kodu")
    )

    profile = {
        "source_file": workbook.name,
        "row_count": int(len(df)),
        "original_columns": original_columns,
        "clean_columns": list(raw.columns),
        "unique_meslek_kodu": int(df["meslek_kodu"].nunique()),
        "unique_meslek_tanim": int(df["meslek_tanim"].nunique()),
        "unique_nace_code": int(df["nace_code"].nunique()),
        "codes_per_meslek_distribution": {
            str(k): int(v)
            for k, v in df.groupby(["meslek_kodu", "meslek_tanim"])["nace_code"]
            .nunique()
            .value_counts()
            .sort_index()
            .items()
        },
        "null_counts": {k: int(v) for k, v in df.isna().sum().items()},
        "notes": [
            "Header cleanup strips whitespace; source has trailing space in 'NACE REV. 2.1 KODU '.",
            "All NACE rows in the supplied workbook are unique NACE codes.",
        ],
    }

    df.to_csv(DATA_DIR / "nace_clean.csv", index=False, encoding="utf-8")
    df.to_parquet(DATA_DIR / "nace_clean.parquet", index=False)
    nodes.to_csv(DATA_DIR / "meslek_nodes.csv", index=False, encoding="utf-8")
    (DATA_DIR / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {DATA_DIR / 'nace_clean.csv'} ({len(df)} rows)")
    print(f"Wrote {DATA_DIR / 'meslek_nodes.csv'} ({len(nodes)} meslek nodes)")
    print(json.dumps(profile, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
