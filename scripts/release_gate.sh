#!/usr/bin/env bash
# Release gate runner: unittest + validate + sensitive scan -> gate-summary.json.
# Extracted from .github/workflows/release.yml so the gating logic is testable
# (tests/test_release_gate.py drives it with fixtures). The workflow calls this
# script; behavior must stay identical.
#
# Failure-path contract (three distinct shapes, never conflated):
#   1. GATE FAILURE  - validate/scan emit valid JSON and report failure
#                      (valid=false or finding_count>0). The summary IS written
#                      (it is the evidence of which gate blocked the release).
#   2. TOOL CRASH    - validate/scan exit non-zero with NON-JSON output (import
#                      error, broken checkout). Blocked with a "crashed" reason.
#   3. unittest      - failure or zero-test discovery blocks before tools run.
#
# Usage: release_gate.sh <repo-root> <log-file-path> <summary-output-path>
# Exit codes: 0 = all gates pass; 1 = gate failure/blocked; 2 = usage error.
set -uo pipefail

root="${1:-.}"
log_path="${2:-/tmp/unittest.log}"
summary_path="${3:-/tmp/gate-summary.json}"

cd "$root" || exit 2

# The unittest pipeline must gate the release: pipefail alone is not enough
# under `cmd | tee`, and a failed run can also emit "Ran 1 test" (singular)
# that a plural-only regex would miss, or omit the count line entirely.
set +e
python3 -m unittest discover -s tests -q 2>&1 | tee "$log_path"
unittest_rc="${PIPESTATUS[0]}"
set -e
test_count="$(grep -Eo 'Ran [0-9]+ tests?' "$log_path" | grep -Eo '[0-9]+' | head -1 || true)"

if [ "$unittest_rc" -ne 0 ]; then
  echo "unittest failed with rc=$unittest_rc; release blocked" >&2
  exit 1
fi
if [ -z "$test_count" ] || [ "$test_count" -eq 0 ]; then
  echo "unittest reported no tests (discovery failure?); release blocked" >&2
  exit 1
fi

# validate/scan EXIT NON-ZERO ON NORMAL GATE FAILURE while still printing JSON
# (that is their contract). So: capture stdout+rc together, parse JSON first,
# write the summary, then block on the verdict. Only NON-JSON output is a crash.
set +e
validate_json="$(python3 scripts/validate_suite.py .)"
validate_rc=$?
scan_json="$(python3 scripts/scan_sensitive_content.py . --format json)"
scan_rc=$?
set -e

run_summary_python() {
  # Args: test_count validate_json scan_json summary_path
  python3 - "$@" <<'PYEOF'
import json
import sys
from datetime import datetime, timezone

test_count, validate_json, scan_json, summary_path = sys.argv[1:5]

def parse_or_none(text):
    try:
        return json.loads(text)
    except Exception:
        return None

validate = parse_or_none(validate_json)
scan = parse_or_none(scan_json)

# Tool crash: non-JSON output (empty stdout, traceback text, import error).
if validate is None:
    print("validate_suite crashed (non-JSON output); release blocked", file=sys.stderr)
    sys.exit(1)
if scan is None:
    print("scan crashed (non-JSON output); release blocked", file=sys.stderr)
    sys.exit(1)

summary = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "tests_passed": int(test_count),
    "validate_valid": validate["valid"],
    "validate_checked_files": validate.get("checked_files"),
    "skill_count": validate.get("skill_count"),
    "scan_candidate_count": scan.get("candidate_count"),
    "scan_finding_count": scan.get("finding_count"),
}
# Persist the summary BEFORE deciding the verdict: a failed run's summary is
# the evidence of which gate blocked the release (uploaded by the workflow).
with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
print(json.dumps(summary, ensure_ascii=False))
if not validate["valid"] or scan.get("finding_count"):
    print("gate failure (validate_valid/scan_finding_count); release blocked", file=sys.stderr)
    sys.exit(1)
PYEOF
}

run_summary_python "$test_count" "$validate_json" "$scan_json" "$summary_path"
