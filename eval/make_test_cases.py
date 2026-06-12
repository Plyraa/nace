from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


CASES = [
    ("bakkal", "D.03", "food", "easy"),
    ("berber", "G.05", "services", "easy"),
    ("kasap", "D.15", "food", "easy"),
    ("lokanta", "D.17", "food", "easy"),
    ("manav", "D.18", "food", "easy"),
    ("fırın", "D.12", "food", "easy"),
    ("dondurmacı", "D.10", "food", "easy"),
    ("kırtasiye", "F.12", "trade", "easy"),
    ("nalbur", "K.06", "trade", "easy"),
    ("emlakçı", "K.05", "services", "easy"),
    ("taksi", "J.14", "logistics", "easy"),
    ("nakliyeci", "J.05", "logistics", "easy"),
    ("çiçekçi", "F.05", "trade", "easy"),
    ("kuaför", "G.09", "services", "easy"),
    ("terzi", "E.15", "textile", "easy"),
    ("marangoz", "A.03", "manufacturing", "easy"),
    ("mobilyacı", "A.06", "manufacturing", "easy"),
    ("kuyumcu", "H.13", "trade", "easy"),
    ("oto yıkama", "H.27", "services", "easy"),
    ("oto elektrik", "H.21", "services", "easy"),
    ("bakkalım", "D.03", "food", "suffix"),
    ("lokantacıyım", "D.17", "food", "suffix"),
    ("kasabım", "D.15", "food", "suffix"),
    ("berberim", "G.05", "services", "suffix"),
    ("manavım", "D.18", "food", "suffix"),
    ("oto galericisiyim", "J.08", "trade", "suffix"),
    ("nakliyeciyim", "J.05", "logistics", "suffix"),
    ("emlakçıyım", "K.05", "services", "suffix"),
    ("çiçekçiyim", "F.05", "trade", "suffix"),
    ("terziyim", "E.15", "textile", "suffix"),
    ("galerici", "J.08", "trade", "ambiguous"),
    ("tatlıcı", "D.20", "food", "ambiguous"),
    ("servisçi", "J.12", "logistics", "ambiguous"),
    ("tamirci", "H.18", "services", "ambiguous"),
    ("pazarcı", "I.03", "trade", "ambiguous"),
    ("bayi işletiyorum", "D.03", "food", "ambiguous"),
    ("plastikçi", "F.11", "manufacturing", "ambiguous"),
    ("boyacı", "K.01", "manufacturing", "ambiguous"),
    ("tesisatçı", "K.14", "construction", "ambiguous"),
    ("servis aracı işletiyorum", "J.12", "logistics", "ambiguous"),
    ("kuafor", "G.09", "services", "typo"),
    ("börber", "G.05", "services", "typo"),
    ("kirtasiye", "F.12", "trade", "typo"),
    ("insaatciyim", "K.09", "construction", "typo"),
    ("pasta satiyorum", "D.20", "food", "typo"),
    ("oto galericiyim", "J.08", "trade", "typo"),
    ("elektrikci", "C.08", "construction", "typo"),
    ("cicek dukkanim var", "F.05", "trade", "typo"),
    ("tuhafiye", "E.16", "textile", "typo"),
    ("ayakkabici", "E.01", "textile", "typo"),
    ("drone ile düğün çekiyorum", "F.07", "services", "long_tail"),
    ("evden pasta yapıp satıyorum", "D.20", "food", "long_tail"),
    ("instagramdan el yapımı takı satıyorum", "H.13", "trade", "long_tail"),
    ("evlere temizliğe gidiyorum", "G.06", "services", "long_tail"),
    ("klima bakım montaj yapıyorum", "H.10", "manufacturing", "long_tail"),
    ("telefon ekranı değiştiriyorum", "C.16", "technology", "long_tail"),
    ("bilgisayar format atıyorum", "C.04", "technology", "long_tail"),
    ("çocuklara özel ders kursu veriyorum", "F.15", "services", "long_tail"),
    ("web sitesi ve yazılım yapıyorum", "C.04", "technology", "long_tail"),
    ("evde yufka açıp satıyorum", "D.25", "food", "long_tail"),
    ("balık tutup satıyorum", "D.04", "agriculture", "long_tail"),
    ("arı kovanım var bal satıyorum", "D.02", "agriculture", "long_tail"),
    ("köy tavuğu yumurta satıyorum", "D.23", "agriculture", "long_tail"),
    ("ikinci el eşya alıp satıyorum", "A.01", "trade", "long_tail"),
    ("halı yıkama dükkanım var", "E.09", "services", "long_tail"),
    ("kuru temizleme yapıyorum", "E.02", "services", "long_tail"),
    ("düğün salonu işletiyorum", "B.02", "services", "long_tail"),
    ("internet kafe işletiyorum", "B.08", "services", "long_tail"),
    ("oto kurtarıcı çekici", "J.09", "logistics", "long_tail"),
    ("akaryakıt istasyonum var", "J.01", "trade", "long_tail"),
]


def main() -> None:
    nace = pd.read_csv(ROOT / "data" / "nace_clean.csv", dtype=str)
    rows = []
    for utterance, meslek_kodu, bucket, category in CASES:
        codes = nace.loc[nace["meslek_kodu"].eq(meslek_kodu), "nace_code"].tolist()
        if not codes:
            raise ValueError(f"No NACE codes found for {meslek_kodu}: {utterance}")
        rows.append(
            {
                "utterance": utterance,
                "acceptable_nace_codes": "|".join(codes),
                "gold_bucket": bucket,
                "category": category,
                "gold_meslek_kodu": meslek_kodu,
            }
        )
    pd.DataFrame(rows).to_csv(ROOT / "eval" / "test_cases.csv", index=False, encoding="utf-8")
    print(f"Wrote {ROOT / 'eval' / 'test_cases.csv'} ({len(rows)} cases)")


if __name__ == "__main__":
    main()
