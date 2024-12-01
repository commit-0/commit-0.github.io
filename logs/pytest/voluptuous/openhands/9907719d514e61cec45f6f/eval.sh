#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard d98e0a0b6a909d26dca6ac1a87cf1a3b60fb62d4
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors voluptuous/tests > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
