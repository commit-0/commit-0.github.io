#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard e2d08907536469bd2f00c30ccffc0b2685f2d6e8
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
