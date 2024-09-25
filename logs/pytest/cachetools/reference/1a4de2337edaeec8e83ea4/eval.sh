#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard fd3810897cb977d2ab8392f3ed9155900f92423a
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
