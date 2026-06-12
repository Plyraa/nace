@echo off
setlocal
python scripts\01_ingest.py || exit /b 1
python scripts\02_generate_aliases.py || exit /b 1
python scripts\03_validate.py --sample-size 150 --batch-size 10 || exit /b 1
python eval\run_eval.py || exit /b 1
