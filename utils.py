import re
import unicodedata
from pathlib import Path

import pandas as pd

from config import DATA_DIR


BUCKETS = {
    "manufacturing": "Gıda/tekstil hariç imalat, üretim ve onarım ağırlıklı sanayi.",
    "trade": "Perakende, toptan satış, bayilik, e-ticaret ve aracılık.",
    "food": "Gıda üretimi, gıda perakendesi, lokanta, kafe ve içecek faaliyetleri.",
    "textile": "Tekstil, konfeksiyon, ayakkabı, deri ve ilgili bakım/ticaret.",
    "construction": "İnşaat, tesisat, yapı malzemesi ve yapı destek işleri.",
    "logistics": "Yolcu/yük taşımacılığı, depolama, otopark, kurye ve taşıma destekleri.",
    "technology": "Yazılım, bilişim, telekom, elektronik cihaz ve dijital altyapı.",
    "services": "Kişisel, mesleki, eğitim, sağlık, sanat, turizm ve bakım hizmetleri.",
    "agriculture": "Tarım, hayvancılık, ormancılık, balıkçılık ve zirai destek.",
    "other": "Yukarıdaki kovalara net oturmayan veya kamusal/karma faaliyetler.",
}

_TR_LOWER = str.maketrans({"I": "ı", "İ": "i"})
_PUNCT_RE = re.compile(r"[^0-9a-zçğıöşü\s]+", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


def tr_lower(text: str) -> str:
    return str(text).translate(_TR_LOWER).lower()


def deasciify_light(text: str) -> str:
    replacements = {
        "cicek": "çiçek",
        "cikolata": "çikolata",
        "dugun": "düğün",
        "dukkani": "dükkanı",
        "dukkan": "dükkan",
        "elektrikci": "elektrikçi",
        "emlakci": "emlakçı",
        "galerici": "galerici",
        "insaat": "inşaat",
        "kasap": "kasap",
        "kirtasiye": "kırtasiye",
        "kuafor": "kuaför",
        "lokanta": "lokanta",
        "nakliyeci": "nakliyeci",
        "pastaci": "pastacı",
        "satici": "satıcı",
        "tamirci": "tamirci",
        "tuhafiye": "tuhafiye",
    }
    words = text.split()
    return " ".join(replacements.get(w, w) for w in words)


def normalize_text(text: str, deasciify: bool = True) -> str:
    if text is None:
        return ""
    value = unicodedata.normalize("NFKC", str(text))
    value = tr_lower(value)
    value = value.replace("&", " ve ")
    value = _PUNCT_RE.sub(" ", value)
    value = _SPACE_RE.sub(" ", value).strip()
    if deasciify:
        value = deasciify_light(value)
    value = strip_business_fillers(value)
    value = strip_first_person_suffixes(value)
    if deasciify:
        value = deasciify_light(value)
    value = _SPACE_RE.sub(" ", value).strip()
    return value


def strip_business_fillers(text: str) -> str:
    fillers = [
        "işi yapıyorum",
        "iş yapıyorum",
        "yapıyorum",
        "işletiyorum",
        "dükkanım var",
        "dükkanım",
        "dukkanım var",
        "dukkanım",
        "dükkanı var",
        "dukkanı var",
        "satıyorum",
        "alım satım",
    ]
    value = f" {text} "
    for filler in fillers:
        value = value.replace(f" {filler} ", " ")
    return value.strip()


def strip_first_person_suffixes(text: str) -> str:
    tokens = []
    for token in text.split():
        original = token
        for suffix in (
            "cısıyım",
            "cisiyim",
            "cusuyum",
            "cüsüyüm",
            "çısıyım",
            "çisiyim",
            "çusuyum",
            "çüsüyüm",
            "cıyım",
            "ciyim",
            "cuyum",
            "cüyüm",
            "çıyım",
            "çiyim",
            "çuyum",
            "çüyüm",
            "ıyım",
            "iyim",
            "uyum",
            "üyüm",
            "yım",
            "yim",
            "yum",
            "yüm",
            "ım",
            "im",
            "um",
            "üm",
        ):
            if token.endswith(suffix) and len(token) > len(suffix) + 2:
                token = token[: -len(suffix)]
                break
        if len(token) < 3:
            token = original
        tokens.append(token)
    return " ".join(tokens)


def clean_nace_code(code: str) -> str:
    return str(code).strip()


def nace_division(code: str) -> str:
    return clean_nace_code(code).split(".")[0].zfill(2)


def load_bucket_maps(data_dir: Path = DATA_DIR):
    divisions = pd.read_csv(data_dir / "division_to_bucket.csv", dtype=str)
    exceptions = pd.read_csv(data_dir / "bucket_exceptions.csv", dtype=str)
    division_map = dict(zip(divisions["division"].str.zfill(2), divisions["bucket"]))
    exceptions = exceptions.sort_values("nace_prefix", key=lambda s: s.str.len(), ascending=False)
    return division_map, exceptions


def bucket_for_code(code: str, division_map=None, exceptions=None) -> str:
    if division_map is None or exceptions is None:
        division_map, exceptions = load_bucket_maps()
    code = clean_nace_code(code)
    for _, row in exceptions.iterrows():
        if code.startswith(str(row["nace_prefix"])):
            return str(row["bucket"])
    return division_map.get(nace_division(code), "other")


def split_terms(label: str) -> list[str]:
    label = re.sub(r"\([^)]*\)", " ", str(label))
    parts = re.split(r",|/| ve | ile ", label)
    return [p.strip() for p in parts if p.strip()]
