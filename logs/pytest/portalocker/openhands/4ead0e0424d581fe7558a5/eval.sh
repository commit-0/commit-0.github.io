#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard 300136afca11ea23c79ecfd110ed0d2819322f11
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors portalocker_tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
