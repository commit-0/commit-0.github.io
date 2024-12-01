#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard 25496719af798e5a276289279651873ea5b6e7d1
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
