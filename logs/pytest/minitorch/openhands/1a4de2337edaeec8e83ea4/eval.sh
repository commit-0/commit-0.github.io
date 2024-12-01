#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard 1fc342c98ef62dec22a5b4c82d68f653320edc75
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
