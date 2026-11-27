PYTHONPATH := src
export PYTHONPATH

.PHONY: test lint report check-data

test:
	python -m pytest --junitxml=reports/junit.xml --html=reports/pytest-report.html --self-contained-html

lint:
	python -m ruff check src tests scripts
	python -m ruff format --check src tests scripts

report:
	python -m clinic_dq run --dataset clean --report-dir reports/clean
	python -m clinic_dq run --dataset defects --expect-failures --report-dir reports/defects

check-data:
	python scripts/build_sample_data.py --check
