from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache

import pandas as pd
from rapidfuzz import fuzz, process

from config import (
    ALIAS_TABLE,
    AUTO_ASSIGN_MARGIN,
    AUTO_ASSIGN_THRESHOLD,
    DATA_DIR,
    EXACT_SCORE,
    FUZZY_THRESHOLD,
    LLM_FALLBACK_THRESHOLD,
)
from llm_client import MissingLLMCache, call_json
from utils import BUCKETS, bucket_for_code, load_bucket_maps, normalize_text


@dataclass
class Candidate:
    nace_code: str
    nace_label: str
    bucket: str
    score: float
    match_type: str


@lru_cache(maxsize=1)
def _tables():
    aliases = pd.read_csv(ALIAS_TABLE, dtype={"nace_code": str})
    aliases["confidence"] = aliases["confidence"].astype(float)
    nace = pd.read_csv(DATA_DIR / "nace_clean.csv", dtype={"nace_code": str})
    alias_choices = sorted(aliases["normalized_alias"].dropna().unique().tolist())
    search = nace.copy()
    search["search_text"] = (
        search["nace_code"].fillna("")
        + " "
        + search["nace_label"].fillna("")
        + " "
        + search["meslek_tanim"].fillna("")
    ).map(normalize_text)
    return aliases, nace, alias_choices, search


def _aggregate(rows: list[Candidate], k: int) -> list[Candidate]:
    best: dict[str, Candidate] = {}
    for cand in rows:
        old = best.get(cand.nace_code)
        if old is None or cand.score > old.score:
            best[cand.nace_code] = cand
    return sorted(best.values(), key=lambda c: c.score, reverse=True)[:k]


def _rows_to_candidates(rows: pd.DataFrame, score: float | None, match_type: str, k: int) -> list[Candidate]:
    candidates = []
    for _, row in rows.iterrows():
        if score is not None:
            row_score = float(score) * (0.85 + 0.15 * float(row["confidence"]))
        else:
            row_score = float(row["confidence"])
        candidates.append(
            Candidate(
                nace_code=row["nace_code"],
                nace_label=row["nace_label"],
                bucket=row["bucket"],
                score=round(min(row_score, 1.0), 4),
                match_type=match_type,
            )
        )
    return _aggregate(candidates, k)


def _shortlist(text: str, limit: int = 30) -> pd.DataFrame:
    _, _, _, search = _tables()
    norm = normalize_text(text)
    choices = search["search_text"].tolist()
    matches = process.extract(norm, choices, scorer=fuzz.token_set_ratio, limit=limit * 3)
    idxs = []
    seen = set()
    ratios = {}
    for _, ratio, idx in matches:
        code = search.iloc[idx]["nace_code"]
        if code not in seen:
            seen.add(code)
            idxs.append(idx)
            ratios[idx] = ratio
        if len(idxs) >= limit:
            break
    out = search.iloc[idxs][["nace_code", "nace_label", "bucket", "meslek_tanim"]].copy()
    out["shortlist_score"] = [ratios[i] for i in idxs]
    return out


def _llm_fallback(text: str, fuzzy_candidates: list[Candidate], k: int) -> list[Candidate]:
    aliases, nace, _, _ = _tables()
    valid_codes = set(nace["nace_code"])
    shortlist = _shortlist(text, limit=30)
    system = (
        "Türkçe serbest meslek/sektör ifadesini verilen NACE kısa listesinden seçen bir resolver'sın. "
        "Sadece geçerli JSON döndür; listede olmayan kod üretme."
    )
    user = {
        "user_text": text,
        "normalized_text": normalize_text(text),
        "buckets": BUCKETS,
        "candidate_nace_codes": shortlist.to_dict(orient="records"),
        "instruction": "En olası ilk 3 NACE kodunu sırala. Kodlar sadece candidate_nace_codes içinden olmalı.",
        "schema": {"candidates": [{"nace_code": "string", "bucket": "string", "confidence": 0.0}]},
    }
    try:
        parsed = call_json(
            task="resolver_fallback",
            system=system,
            user=json.dumps(user, ensure_ascii=False),
            max_tokens=700,
        )
    except MissingLLMCache:
        return fuzzy_candidates[:k]
    except Exception:
        return fuzzy_candidates[:k]

    rows = []
    division_map, exceptions = load_bucket_maps()
    labels = nace.drop_duplicates("nace_code").set_index("nace_code")["nace_label"].to_dict()
    for item in parsed.get("candidates", []):
        code = str(item.get("nace_code", "")).strip()
        if code not in valid_codes:
            continue
        try:
            conf = float(item.get("confidence", 0.45))
        except (TypeError, ValueError):
            conf = 0.45
        rows.append(
            Candidate(
                nace_code=code,
                nace_label=labels.get(code, ""),
                bucket=bucket_for_code(code, division_map, exceptions),
                score=round(max(0.0, min(conf, 1.0)), 4),
                match_type="llm",
            )
        )
    if rows:
        return _aggregate(rows, k)
    fallback_rows = []
    for _, row in shortlist.head(k).iterrows():
        fallback_rows.append(
            Candidate(
                nace_code=row["nace_code"],
                nace_label=row["nace_label"],
                bucket=row["bucket"],
                score=round(min(float(row["shortlist_score"]) / 100.0 * 0.55, 0.55), 4),
                match_type="fuzzy",
            )
        )
    return fallback_rows or fuzzy_candidates[:k]


def resolve(text: str, k: int = 3) -> list[Candidate]:
    aliases, _, alias_choices, _ = _tables()
    norm = normalize_text(text)
    if not norm:
        return []

    exact_rows = aliases[aliases["normalized_alias"].eq(norm)]
    if not exact_rows.empty:
        exact_rows = exact_rows.sort_values("confidence", ascending=False)
        return _rows_to_candidates(exact_rows, EXACT_SCORE, "exact", k)

    fuzzy_rows: list[Candidate] = []
    matches = process.extract(norm, alias_choices, scorer=fuzz.token_set_ratio, limit=20)
    for alias, ratio, _ in matches:
        if ratio < FUZZY_THRESHOLD:
            continue
        rows = aliases[aliases["normalized_alias"].eq(alias)].copy()
        rows["score"] = rows["confidence"].astype(float) * (ratio / 100.0) * 0.96
        for _, row in rows.iterrows():
            fuzzy_rows.append(
                Candidate(
                    nace_code=row["nace_code"],
                    nace_label=row["nace_label"],
                    bucket=row["bucket"],
                    score=round(min(float(row["score"]), 0.94), 4),
                    match_type="fuzzy",
                )
            )
    fuzzy_candidates = _aggregate(fuzzy_rows, k)
    best = fuzzy_candidates[0].score if fuzzy_candidates else 0.0
    second = fuzzy_candidates[1].score if len(fuzzy_candidates) > 1 else 0.0
    clear = best >= AUTO_ASSIGN_THRESHOLD and (best - second) >= AUTO_ASSIGN_MARGIN
    if fuzzy_candidates and (best >= LLM_FALLBACK_THRESHOLD or clear):
        return fuzzy_candidates
    return _llm_fallback(text, fuzzy_candidates, k)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python resolver.py "oto galericisiyim"')
        raise SystemExit(2)
    result = [asdict(c) for c in resolve(" ".join(sys.argv[1:]))]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
