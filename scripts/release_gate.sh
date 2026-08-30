#!/usr/bin/env bash
# Release gate runner: unittest + validate + sensitive scan -> gate-summary.json.
# Extracted from .github/workflows/release.yml so the gating logic is testable
# (tests/test_release_gate.py drives it with fake unittest output). The workflow
# calls this script; behavior must stay identical.
#
# Usage: release_gate.sh <repo-root> <log-file-path> <summary-output-path>
# Exit codes: 0 = all gates pass; 1 = gate failure; 2 = usage error.
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

# validate/scan must emit JSON; a crash (import error, bad checkout) leaves
# empty output which would kill the summary step with an opaque traceback.
# Capture rc and fail with a clear reason instead.
validate_json="$(python3 scripts/validate_suite.py .)" || {
  echo "validate_suite crashed; release blocked" >&2
  exit 1
}
scan_json="$(python3 scripts/scan_sensitive_content.py . --format json)" || {
  echo "scan_sensitive_content crashed; release blocked" >&2
  exit 1
}
python3 - "$validate_json" <<'PYCHECK'
import json, sys
try:
    json.loads(sys.argv[1])
except Exception:
    print("validate_suite produced non-JSON output; release blocked", file=sys.stderr)
    raise SystemExit(1)
PYCHECK
python3 - "$scan_json" <<'PYCHECK'
import json, sys
try:
    json.loads(sys.argv[1])
except Exception:
    print("scan produced non-JSON output; release blocked", file=sys.stderr)
    raise SystemExit(1)
PYCHECK

python3 - "$test_count" "$validate_json" "$scan_json" "$summary_path" <<'PYEOF'
import json
import sys
from datetime import datetime, timezone

test_count = int(sys.argv[1])
validate = json.loads(sys.argv[2])
scan = json.loads(sys.argv[3])
summary_path = sys.argv[4]
summary = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "tests_passed": test_count,
    "validate_valid": validate["valid"],
    "validate_checked_files": validate["checked_files"],
    "skill_count": validate["skill_count"],
    "scan_candidate_count": scan["candidate_count"],
    "scan_finding_count": scan["finding_count"],
}
with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
print(json.dumps(summary, ensure_ascii=False))
# Always persist the summary first: a failed run's summary is the evidence of
# which gate blocked the release (the workflow uploads it either way).
if not validate["valid"] or scan["finding_count"]:
    sys.exit(1)
PYEOF
