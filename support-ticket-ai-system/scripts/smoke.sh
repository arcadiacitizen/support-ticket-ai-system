#!/usr/bin/env bash
set -euo pipefail

python3 -m unittest discover -s tests -v
python3 scripts/check_links.py
rm -f artifacts/smoke-decisions.jsonl
python3 -m support_ticket_ai.demo --scenario all --audit-log artifacts/smoke-decisions.jsonl >/dev/null
test "$(wc -l < artifacts/smoke-decisions.jsonl | tr -d ' ')" = "3"
echo "Smoke test passed: tests green and 3 decisions audited."
