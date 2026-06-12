from pathlib import Path

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "deepseek/deepseek-v4-flash"
OPENROUTER_TEMPERATURE = 0.2

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CACHE_DIR = ROOT / "cache"
EVAL_DIR = ROOT / "eval"

ALIAS_TABLE = OUTPUT_DIR / "alias_table.csv"
NACE_CLEAN = DATA_DIR / "nace_clean.csv"
MESLEK_NODES = DATA_DIR / "meslek_nodes.csv"

EXACT_SCORE = 0.98
FUZZY_THRESHOLD = 85
AUTO_ASSIGN_THRESHOLD = 0.86
AUTO_ASSIGN_MARGIN = 0.08
LLM_FALLBACK_THRESHOLD = 0.78
