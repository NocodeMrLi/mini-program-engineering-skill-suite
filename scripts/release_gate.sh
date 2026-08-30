#!/usr/bin/env bash
# Release gate runner: unittest + validate + sensitive scan + manual-verification
# gate -> gate-summary.json. Extracted from .github/workflows/release.yml so the
# gating logic is testable (tests/test_release_gate.py drives it with fixtures).
# The workflow calls this script; behavior must stay identical.
#
# Failure-path contract (four distinct shapes, never conflated):
#   1. GATE FAILURE  - validate/scan emit valid JSON and report failure
#                      (valid=false or finding_count>0). The summary IS written
#                      (it is the evidence of which gate blocked the release).
#   2. TOOL CRASH    - validate/scan exit non-zero with NON-JSON output (import
#                      error, broken checkout). Blocked with a "crashed" reason.
#   3. unittest      - failure or zero-test discovery blocks before tools run.
#   4. MANUAL VERIFICATION - release_recommendation returns
#                      MANUAL_VERIFICATION_REQUIRED (or crashes / reports an
#                      error): blocked. The recommender is a GATE, not advice.
#
# Usage: release_gate.sh <repo-root> <log-file-path> <summary-output-path> [candidate-tag]
# Exit codes: 0 = all gates pass; 1 = gate failure/blocked; 2 = usage error.
set -uo pipefail

root="${1:-.}"
log_path="${2:-/tmp/unittest.log}"
summary_path="${3:-/tmp/gate-summary.json}"
candidate_tag="${4:-}"

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

# Manual-verification gate (fourth): MANUAL_VERIFICATION_REQUIRED, tool crash,
# or an error payload all block the release. The recommender is a hard gate.
set +e
if [ -n "$candidate_tag" ]; then
  recommend_json="$(python3 scripts/release_recommendation.py . --candidate-tag "$candidate_tag" --format json)"
else
  recommend_json="$(python3 scripts/release_recommendation.py . --format json)"
fi
recommend_rc=$?
set -e
recommend_verdict="$(printf '%s' "$recommend_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("recommendation", "error"))' 2>/dev/null || echo crashed)"

if [ "$recommend_rc" -ne 0 ] || [ "$recommend_verdict" = "error" ] || [ "$recommend_verdict" = "crashed" ]; then
  echo "release_recommendation crashed or errored; release blocked" >&2
  exit 1
fi

# A valid recommender result is evidence even when its verdict blocks. Persist
# it before any verdict exit so the always-upload workflow step preserves the
# complete fourth-gate trail for failed releases too.
python3 - "$summary_path" "$candidate_tag" "$recommend_json" <<'GATEPY'
import json
import sys
from datetime import datetime, timezone

summary_path, candidate_tag, recommend_json = sys.argv[1:4]
recommend = json.loads(recommend_json)
with open(summary_path, encoding="utf-8") as handle:
    summary = json.load(handle)
summary["candidate_tag"] = candidate_tag or None
summary["baseline_tag"] = recommend.get("baseline_tag")
summary["release_recommendation"] = recommend.get("recommendation")
summary["release_level"] = recommend.get("level")
summary["release_commit_count"] = recommend.get("commit_count")
summary["release_classes"] = recommend.get("classes") or {}
summary["release_reasons"] = recommend.get("reasons") or []
summary["history_complete"] = recommend.get("history_complete")
mv = recommend.get("manual_verification") or {}
summary["manual_verification_required"] = mv.get("required")
summary["manual_verification_platforms"] = {
    name: {
        "needs_verification": detail.get("needs_verification"),
        "unknown_count": detail.get("unknown_count"),
        "oldest_verified": detail.get("oldest_verified"),
        "why": detail.get("why") or [],
    }
    for name, detail in (mv.get("platforms") or {}).items()
}
summary["gate4_generated_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
GATEPY

if [ "$recommend_verdict" = "MANUAL_VERIFICATION_REQUIRED" ]; then
  echo "MANUAL_VERIFICATION_REQUIRED: record per-platform verification evidence in this release's CHANGELOG entry; release blocked" >&2
  printf '%s\n' "$recommend_json" >&2
  exit 1
fi
# With a candidate tag, HOLD is anomalous (double tag / empty range / tooling
# drift) — it must block, not pass through as success (the P0 bypass shape).
if [ "$recommend_verdict" = "HOLD" ] && [ -n "$candidate_tag" ]; then
  echo "HOLD with candidate tag $candidate_tag is anomalous (empty range or mis-sequenced tags); release blocked" >&2
  printf '%s\n' "$recommend_json" >&2
  exit 1
fi
# Unknown verdict values fail closed after their valid payload is preserved.
case "$recommend_verdict" in
  RECOMMEND_RELEASE|HOLD) ;;
  *) echo "unknown recommendation verdict '$recommend_verdict'; release blocked" >&2; exit 1 ;;
esac
