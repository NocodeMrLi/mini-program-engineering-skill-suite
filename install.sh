#!/usr/bin/env bash
set -euo pipefail

SUITE_NAME="mini-program-engineering-suite"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_DIR="$SCRIPT_DIR"
TARGET="auto"
PROJECT_DIR=""
USER_HOME="${HOME:-}"
FORCE=0
DRY_RUN=0

usage() {
  cat <<'USAGE'
Mini Program Engineering Skill Suite installer

Usage:
  bash install.sh [options]

Options:
  --target auto|agents|codex|claude|cursor|copilot|all
      auto   Install to existing user-level Agent skill directories.
      agents Install to ~/.agents/skills for generic Agent Skills runners.
      codex  Install to ~/.codex/skills for Codex App / Codex local skills.
      claude Install to ~/.claude/skills.
      cursor Install to <project>/.cursor/rules.
      copilot Install to <project>/.github/skills.
      all    Install user-level targets and, when --project is provided, project targets.

  --project PATH
      Required for cursor and copilot targets.

  --source PATH
      Skill suite source directory. Defaults to this script's directory.

  --home PATH
      Home directory override, mainly for tests and controlled automation.

  --force
      Replace an existing installation after moving it to a timestamped backup.

  --dry-run
      Print planned destinations without copying files.

  -h, --help
      Show this help.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --project)
      PROJECT_DIR="${2:-}"
      shift 2
      ;;
    --source)
      SOURCE_DIR="${2:-}"
      shift 2
      ;;
    --home)
      USER_HOME="${2:-}"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$TARGET" in
  auto|agents|codex|claude|cursor|copilot|all) ;;
  *)
    echo "Unsupported --target: $TARGET" >&2
    exit 2
    ;;
esac

if [ -z "$USER_HOME" ]; then
  echo "Unable to resolve home directory. Pass --home PATH." >&2
  exit 2
fi

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd -P)"
if [ ! -f "$SOURCE_DIR/SKILL.md" ]; then
  echo "Source directory does not look like a skill suite: $SOURCE_DIR" >&2
  exit 2
fi

require_project() {
  if [ -z "$PROJECT_DIR" ]; then
    echo "--target $TARGET requires --project PATH" >&2
    exit 2
  fi
  PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd -P)"
}

DESTINATIONS=()

add_destination() {
  DESTINATIONS+=("$1")
}

add_user_target_if_present() {
  parent="$1"
  if [ -d "$parent" ]; then
    add_destination "$parent/$SUITE_NAME"
  fi
}

case "$TARGET" in
  auto)
    add_user_target_if_present "$USER_HOME/.agents/skills"
    add_user_target_if_present "$USER_HOME/.codex/skills"
    add_user_target_if_present "$USER_HOME/.claude/skills"
    if [ "${#DESTINATIONS[@]}" -eq 0 ]; then
      add_destination "$USER_HOME/.agents/skills/$SUITE_NAME"
    fi
    ;;
  agents)
    add_destination "$USER_HOME/.agents/skills/$SUITE_NAME"
    ;;
  codex)
    add_destination "$USER_HOME/.codex/skills/$SUITE_NAME"
    ;;
  claude)
    add_destination "$USER_HOME/.claude/skills/$SUITE_NAME"
    ;;
  cursor)
    require_project
    add_destination "$PROJECT_DIR/.cursor/rules/$SUITE_NAME"
    ;;
  copilot)
    require_project
    add_destination "$PROJECT_DIR/.github/skills/$SUITE_NAME"
    ;;
  all)
    add_destination "$USER_HOME/.agents/skills/$SUITE_NAME"
    add_destination "$USER_HOME/.codex/skills/$SUITE_NAME"
    add_destination "$USER_HOME/.claude/skills/$SUITE_NAME"
    if [ -n "$PROJECT_DIR" ]; then
      PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd -P)"
      add_destination "$PROJECT_DIR/.cursor/rules/$SUITE_NAME"
      add_destination "$PROJECT_DIR/.github/skills/$SUITE_NAME"
    fi
    ;;
esac

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Install source: $SOURCE_DIR"
  echo "Planned destinations:"
  for destination in "${DESTINATIONS[@]}"; do
    echo "- $destination"
  done
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to verify/export the public package before install." >&2
  exit 2
fi

WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

PACKAGE_DIR="$WORK_DIR/package"
INSTALL_TREE="$WORK_DIR/install-tree"

if [ -f "$SOURCE_DIR/package-manifest.json" ]; then
  python3 "$SOURCE_DIR/scripts/verify_public_package.py" "$SOURCE_DIR" >/dev/null
  SOURCE_FOR_COPY="$SOURCE_DIR"
else
  python3 "$SOURCE_DIR/scripts/export_public_package.py" "$SOURCE_DIR" --output "$PACKAGE_DIR" >/dev/null
  python3 "$PACKAGE_DIR/scripts/verify_public_package.py" "$PACKAGE_DIR" >/dev/null
  SOURCE_FOR_COPY="$PACKAGE_DIR"
fi

python3 - "$SOURCE_FOR_COPY" "$INSTALL_TREE" <<'PY'
import json
import shutil
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
manifest = json.loads((source / "package-manifest.json").read_text(encoding="utf-8"))
for entry in manifest["files"]:
    relative = Path(entry["path"])
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / relative, destination)
PY

# Transaction log for THIS run only: "destination<TAB>backup-or-empty" per
# completed target. Rollback uses exactly these recorded paths — never a
# filesystem search for the "newest backup", which could pick a stale backup
# from a previous run (audit finding).
TRANSACTION_LOG="$(mktemp)"
trap 'rm -f "$TRANSACTION_LOG"' EXIT

# Full transactional rollback: restore every target this run already touched,
# in reverse order. For each target: remove whatever we wrote, and restore the
# backup WE created this run (recorded in the log); a target installed fresh
# (no backup) is simply removed.
rollback_all() {
  local failed_dest="$1"
  echo "Install failed at: $failed_dest" >&2
  echo "Rolling back all targets touched this run (reverse order):" >&2
  # tac may be absent on macOS; reverse with tail -r fallback
  if command -v tac >/dev/null 2>&1; then
    reversed="$(tac "$TRANSACTION_LOG")"
  else
    reversed="$(tail -r "$TRANSACTION_LOG")"
  fi
  while IFS=$'\t' read -r dest backup; do
    [ -z "$dest" ] && continue
    rm -rf "$dest"
    if [ -n "$backup" ] && [ -d "$backup" ]; then
      mv "$backup" "$dest"
      echo "  restored $dest <- $backup" >&2
    else
      echo "  removed partial install at $dest (was fresh, no prior version)" >&2
    fi
  done <<< "$reversed"
}

for destination in "${DESTINATIONS[@]}"; do
  parent="$(dirname "$destination")"
  # Pre-flight every destination BEFORE touching any of them: a mid-loop
  # failure used to leave earlier targets updated and later ones stale
  # (mixed-version installs, audit finding: no transactionality).
  if [ -e "$destination" ] && [ "$FORCE" -ne 1 ]; then
    echo "Destination already exists: $destination" >&2
    echo "Use --force to replace it after creating a backup." >&2
    echo "No destination has been modified (pre-flight check)." >&2
    exit 1
  fi
  if ! mkdir -p "$parent" 2>/dev/null; then
    echo "Cannot create destination parent directory: $parent" >&2
    echo "No destination has been modified (pre-flight check)." >&2
    exit 1
  fi
  if [ ! -w "$parent" ]; then
    echo "Destination parent not writable: $parent" >&2
    echo "No destination has been modified (pre-flight check)." >&2
    exit 1
  fi
done

for destination in "${DESTINATIONS[@]}"; do
  this_backup=""
  if [ -e "$destination" ]; then
    this_backup="$destination.backup.$(date +%Y%m%d%H%M%S).$RANDOM"
    if ! mv "$destination" "$this_backup"; then
      rollback_all "$destination"
      exit 1
    fi
    echo "Backed up existing installation: $this_backup"
  fi
  printf '%s\t%s\n' "$destination" "$this_backup" >> "$TRANSACTION_LOG"
  if ! cp -R "$INSTALL_TREE" "$destination"; then
    rollback_all "$destination"
    exit 1
  fi
  echo "Installed $SUITE_NAME -> $destination"
done

echo "Open a new Agent session and call: /mini-program-engineering-suite"
