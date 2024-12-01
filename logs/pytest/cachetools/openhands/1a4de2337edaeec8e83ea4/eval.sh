#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard a0a7e2b73f9e146b8a8f2912948b17a918e5fe83
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
