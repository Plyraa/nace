# NACE Halk Dili Resolver

Quickstart:

```bash
python -m pip install -r requirements.txt
# Optional for fresh LLM calls; not needed for cached rerun:
# PowerShell: $env:OPENROUTER_API_KEY="..."
# bash/cmd: set/export OPENROUTER_API_KEY=...
run.cmd        # Windows
# or: bash run.sh
python resolver.py "oto galericisiyim"
python demo_ui.py  # optional local UI at http://127.0.0.1:8000
```

Pipeline: `scripts/01_ingest.py` cleans the workbook, `scripts/02_generate_aliases.py` builds aliases, `scripts/03_validate.py` samples LLM validation, and `eval/run_eval.py` reports metrics.

The committed `cache/` files allow the full pipeline and eval to rerun without an API key.
