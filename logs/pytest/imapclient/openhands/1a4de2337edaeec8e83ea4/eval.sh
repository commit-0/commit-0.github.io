#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard 7ca5a23640bcb0b102673eaaf5eaa6e7fcebd76b
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
