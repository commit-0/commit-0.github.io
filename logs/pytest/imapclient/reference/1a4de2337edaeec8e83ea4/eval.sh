#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard b30a04d9def0ccd91564db3915d1203110a5d241
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
