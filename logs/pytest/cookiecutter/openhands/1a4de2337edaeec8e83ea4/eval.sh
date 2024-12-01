#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard c7a8c70a666270053d848f5664413af1af7a987f
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
