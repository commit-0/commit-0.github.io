#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard 3da8f12d012e68cf4aa9848cd97656c0c68ccdb3
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
