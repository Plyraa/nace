from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DATA_DIR, OUTPUT_DIR
from llm_client import MissingLLMCache, call_json
from utils import bucket_for_code, load_bucket_maps, normalize_text, split_terms


SYSTEM = """Türkçe KOBİ sektör ifadeleri için alias üreten dikkatli bir veri etiketleyicisin.
Sadece geçerli JSON döndür. Resmi NACE kodu üretme; yalnızca verilen meslek düğümü için halk dili ifadeleri üret."""

MANUAL_SOURCE_ALIASES = {
    "A.01": ["spotçu", "ikinci elci", "ikinci el eşya"],
    "D.03": ["bakkal", "büfe", "bayi", "tekel bayi"],
    "D.12": ["fırın", "fırıncı", "ekmek fırını"],
    "D.15": ["kasap"],
    "D.17": ["lokanta", "restoran", "yemekçi"],
    "D.18": ["manav"],
    "D.20": ["pastacı", "tatlıcı", "pasta satıyorum"],
    "D.25": ["yufkacı", "kadayıfçı"],
    "E.01": ["ayakkabıcı"],
    "E.02": ["kuru temizleme", "ütücü", "çamaşırhane"],
    "E.09": ["halı yıkama"],
    "E.15": ["terzi"],
    "E.16": ["tuhafiye"],
    "F.05": ["çiçekçi", "çiçek dükkanı"],
    "F.07": ["fotoğrafçı", "düğün fotoğrafçısı", "drone çekimi", "video çekimi"],
    "F.12": ["kırtasiye", "kirtasiye"],
    "G.05": ["berber", "erkek berber"],
    "G.09": ["kuaför", "kuafor", "kadın kuaför"],
    "G.06": ["temizlikçi", "ev temizliği", "haşere ilaçlama"],
    "H.18": ["oto servis", "oto tamirci", "tamirci"],
    "H.21": ["oto elektrik", "oto elektrikçi"],
    "H.27": ["oto yıkama"],
    "J.05": ["nakliyeci", "nakliye", "kamyoncu", "yük taşıma"],
    "J.08": ["galerici", "oto galerici", "oto kiralama"],
    "J.09": ["oto kurtarıcı", "çekici"],
    "J.12": ["servisçi", "servis aracı"],
    "K.05": ["emlakçı", "emlak"],
    "K.06": ["nalbur", "hırdavatçı"],
    "K.09": ["inşaatçı", "inşaat", "insaat"],
    "K.14": ["tesisatçı", "sıhhi tesisatçı"],
}


def stem_alias(base: str) -> list[str]:
    stems = []
    for suffix in (
        "cılığı",
        "ciliği",
        "culuğu",
        "cülüğü",
        "çılığı",
        "çiliği",
        "çuluğu",
        "çülüğü",
        "lığı",
        "liği",
        "luğu",
        "lüğü",
        "cılık",
        "cilik",
        "culuk",
        "cülük",
        "çılık",
        "çilik",
        "çuluk",
        "çülük",
        "lık",
        "lik",
        "luk",
        "lük",
    ):
        if base.endswith(suffix) and len(base) > len(suffix) + 2:
            stems.append(base[: -len(suffix)].strip())
    return [s for s in stems if len(normalize_text(s)) >= 3]


def source_aliases(label: str, meslek_kodu: str = "") -> list[str]:
    aliases = {label}
    norm_label = normalize_text(label, deasciify=False)
    aliases.add(norm_label)
    for part in split_terms(label):
        aliases.add(part)
        base = normalize_text(part, deasciify=False)
        aliases.add(base)
        if base.endswith(" ticareti"):
            aliases.add(base[: -len(" ticareti")])
        if base.endswith(" imalatı"):
            aliases.add(base[: -len(" imalatı")])
        if base.endswith(" işletmeciliği"):
            aliases.add(base[: -len(" işletmeciliği")])
        if base.endswith(" hizmetleri"):
            aliases.add(base[: -len(" hizmetleri")])
        if base.endswith(" faaliyetleri"):
            aliases.add(base[: -len(" faaliyetleri")])
        for stem in stem_alias(base):
            aliases.add(stem)
    for alias in MANUAL_SOURCE_ALIASES.get(meslek_kodu, []):
        aliases.add(alias)
    cleaned = []
    for alias in aliases:
        alias = alias.strip(" ,")
        if len(normalize_text(alias)) >= 3:
            cleaned.append(alias)
    return sorted(set(cleaned), key=lambda x: (len(x), x))[:20]


def llm_aliases(row: pd.Series, codes: pd.DataFrame) -> list[str]:
    examples = codes[["nace_code", "nace_label"]].head(12).to_dict(orient="records")
    user = {
        "meslek_kodu": row["meslek_kodu"],
        "meslek_tanim": row["meslek_tanim"],
        "sektor_tanim": row.get("sektor_tanim", ""),
        "nace_examples": examples,
        "instruction": (
            "Bu meslek düğümü için küçük işletme sahibinin yazabileceği 5-15 Türkçe alias üret. "
            "Dükkan adı gibi kısa adlar, meslek sözcükleri, birinci tekil şahıs ifadeleri ve yaygın yazım hataları olsun. "
            "Başka mesleklere kayan alias yazma."
        ),
        "schema": {"aliases": ["string"]},
    }
    parsed = call_json(
        task="alias_generation",
        system=SYSTEM,
        user=json.dumps(user, ensure_ascii=False),
        max_tokens=1200,
    )
    aliases = parsed if isinstance(parsed, list) else parsed.get("aliases", [])
    if not isinstance(aliases, list):
        raise ValueError(f"Invalid alias schema for {row['meslek_kodu']}: {parsed}")
    return [str(a).strip() for a in aliases if len(normalize_text(str(a))) >= 3][:15]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="debug limit for meslek nodes")
    parser.add_argument("--no-llm", action="store_true", help="only emit deterministic source aliases")
    parser.add_argument("--workers", type=int, default=4, help="parallel LLM calls; keep small for provider friendliness")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(DATA_DIR / "nace_clean.csv", dtype=str)
    nodes = pd.read_csv(DATA_DIR / "meslek_nodes.csv", dtype=str)
    if args.limit:
        nodes = nodes.head(args.limit)

    division_map, exceptions = load_bucket_maps()
    failures: list[dict] = []
    codes_by_meslek = {k: g.copy() for k, g in df.groupby("meslek_kodu")}

    alias_by_meslek: dict[str, dict[str, str]] = {}
    for i, node in nodes.iterrows():
        alias_sources: dict[str, str] = {}
        for alias in source_aliases(node["meslek_tanim"], node["meslek_kodu"]):
            alias_sources[alias] = "source-vocab"
        alias_by_meslek[node["meslek_kodu"]] = alias_sources

    if not args.no_llm:
        def generate_for_node(row: pd.Series) -> tuple[str, list[str], str | None]:
            try:
                return row["meslek_kodu"], llm_aliases(row, codes_by_meslek[row["meslek_kodu"]]), None
            except MissingLLMCache as exc:
                return row["meslek_kodu"], [], str(exc)
            except Exception as exc:
                return row["meslek_kodu"], [], repr(exc)

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = [pool.submit(generate_for_node, row) for _, row in nodes.iterrows()]
            for done, future in enumerate(as_completed(futures), start=1):
                meslek_kodu, aliases, error = future.result()
                if error:
                    failures.append({"meslek_kodu": meslek_kodu, "error": error})
                else:
                    for alias in aliases:
                        alias_by_meslek[meslek_kodu].setdefault(alias, "llm-generated")
                if done % 10 == 0 or done == len(futures):
                    print(f"llm alias calls completed {done}/{len(futures)}", flush=True)

    rows: list[dict] = []
    for _, node in nodes.iterrows():
        meslek_codes = codes_by_meslek[node["meslek_kodu"]]
        for alias, provenance in alias_by_meslek[node["meslek_kodu"]].items():
            normalized_alias = normalize_text(alias)
            for _, code_row in meslek_codes.iterrows():
                rows.append(
                    {
                        "alias": alias,
                        "normalized_alias": normalized_alias,
                        "meslek_kodu": node["meslek_kodu"],
                        "meslek_tanim": node["meslek_tanim"],
                        "nace_code": code_row["nace_code"],
                        "nace_label": code_row["nace_label"],
                        "bucket": bucket_for_code(code_row["nace_code"], division_map, exceptions),
                        "confidence": 0.86 if provenance == "source-vocab" else 0.74,
                        "provenance": provenance,
                    }
                )

    out = pd.DataFrame(rows).drop_duplicates(
        subset=["normalized_alias", "meslek_kodu", "nace_code", "provenance"]
    )
    meslek_counts = out.groupby("normalized_alias")["meslek_kodu"].nunique()
    out["ambiguous"] = out["normalized_alias"].map(meslek_counts).fillna(0).astype(int) > 1
    out = out.sort_values(["normalized_alias", "confidence", "nace_code"], ascending=[True, False, True])
    out.to_csv(OUTPUT_DIR / "alias_candidates.csv", index=False, encoding="utf-8")

    if failures:
        (OUTPUT_DIR / "alias_generation_failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(f"Wrote {OUTPUT_DIR / 'alias_candidates.csv'} ({len(out)} rows)")
    print(f"LLM/cache failures: {len(failures)}")


if __name__ == "__main__":
    main()
