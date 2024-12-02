#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard ed761a72c8c1e1cb24ca4dbcc089f35c5264d357
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
