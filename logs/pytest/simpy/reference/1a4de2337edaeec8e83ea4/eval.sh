#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard ac12781cef2610ac3e272f15245a54ef5529ade5
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
