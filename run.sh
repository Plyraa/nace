#!/usr/bin/env bash
set -euo pipefail

python scripts/01_ingest.py
python scripts/02_generate_aliases.py
python scripts/03_validate.py --sample-size 150 --batch-size 10
python eval/run_eval.py
