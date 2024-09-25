#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard 9c3adc041e44cc5e0470c8be6f91c7a26a955981
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors voluptuous/tests > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
