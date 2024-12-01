#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard b7e2114c046abb489e4e23ab9f829778b076650d
git apply --allow-empty -v /patch.diff
git status
pytest --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
