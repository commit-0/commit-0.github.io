#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard bd290d2b49f5030a2369aedc5538cffa4815982d
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
