cd /mnt/d/Research/SurveyTool/nona
source SE/bin/activate

python scripts/collect_titles.py --source cvpr --year 2026 --keyword-filter --min-keyword-score 4
python scripts/collect_titles.py --source iclr --year 2025 --keyword-filter --min-keyword-score 4
python scripts/collect_titles.py --source iclr --year 2026 --keyword-filter --min-keyword-score 4
python scripts/collect_titles.py --source iccv --year 2025 --keyword-filter --min-keyword-score 4
python scripts/collect_titles.py --source siggraph --year 2025 --keyword-filter --min-keyword-score 4
python scripts/collect_titles.py --source cvpr --year 2025 --keyword-filter --min-keyword-score 4

python scripts/quick_verify.py