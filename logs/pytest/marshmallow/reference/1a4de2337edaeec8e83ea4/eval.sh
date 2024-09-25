#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard d6b856a3701d5931cbb35409b3012722be2db0ec
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
