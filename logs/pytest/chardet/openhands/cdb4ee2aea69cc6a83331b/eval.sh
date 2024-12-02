#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard 5539fa54d17ec61bacb4d3bb29ec6fba9dfcb882
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors . > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
