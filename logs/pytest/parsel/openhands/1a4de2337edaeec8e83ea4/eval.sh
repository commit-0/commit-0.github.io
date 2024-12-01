#!/bin/bash
set -uxo pipefail
cd /testbed
source .venv/bin/activate
git reset --hard 7e73d60665ef2e3ddfe3c1bb01eed981cd317c6f
git apply --allow-empty -v /patch.diff
git status
pytest --assert=plain --ignore=setup.py --json-report --json-report-file=report.json --continue-on-collection-errors tests/ > test_output.txt 2>&1
echo $? > pytest_exit_code.txt
