#!/usr/bin/env python3
"""Inspect an anonymous mini-program project without executing or modifying it."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence


MAX_CONFIG_BYTES = 1024 * 1024
KNOWN_CAPABILITIES = {
    "jest",
    "miniprogram-simulate",
    "mpflow",
    "playwright",
    "vitest",
}


def read_json_object(path: Path, warnings: list[str]) -> dict[str, Any]:
    """Read one known JSON file within a fixed size budget."""
    if not path.is_file():
        return {}
    try:
        if path.stat().st_size > MAX_CONFIG_BYTES:
            warnings.append(f"oversized-config:{path.name}")
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        warnings.append(f"unreadable-config:{path.name}")
        return {}
    if not isinstance(value, dict):
        warnings.append(f"non-object-config:{path.name}")
        return {}
    return value


def dependency_names(package: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        section = package.get(key, {})
        if isinstance(section, dict):
            names.update(item for item in section if isinstance(item, str))
    return names


def detect_framework(root: Path, package: dict[str, Any], warnings: list[str]) -> tuple[str, list[str]]:
    deps = dependency_names(package)
    scripts = package.get("scripts", {}) if isinstance(package.get("scripts", {}), dict) else {}
    script_names = {item for item in scripts if isinstance(item, str)}
    try:
        root_entries = {item.name for item in root.iterdir() if item.is_file()}
    except OSError:
        warnings.append("unreadable-root-directory")
        root_entries = set()
    taro = any(item.startswith("@tarojs/") for item in deps) or (root / "config/index.js").is_file() or (
        root / "config/index.ts"
    ).is_file()
    uni_app = (
        any(item.startswith("@dcloudio/") for item in deps)
        or ("manifest.json" in root_entries and (root / "pages.json").is_file())
        or any("mp-weixin" in item for item in script_names)
    )
    native = (root / "app.json").is_file() or (root / "project.config.json").is_file()

    signals = [name for name, present in (("taro", taro), ("uni-app", uni_app), ("native-wechat", native)) if present]
    if taro and uni_app:
        warnings.append("multiple-framework-signals")
        return "ambiguous", signals
    if taro:
        return "taro", signals
    if uni_app:
        return "uni-app", signals
    if native:
        return "native-wechat", signals
    return "unknown", []


def inspect_project(root: Path, devtools_cli: Path | None = None) -> dict[str, object]:
    """Return only redacted facts; never execute repository commands."""
    warnings: list[str] = []
    package = read_json_object(root / "package.json", warnings)
    app = read_json_object(root / "app.json", warnings)
    project = read_json_object(root / "project.config.json", warnings)
    manifest = read_json_object(root / "manifest.json", warnings)
    pages = read_json_object(root / "pages.json", warnings)
    framework, signals = detect_framework(root, package, warnings)

    scripts = package.get("scripts", {}) if isinstance(package.get("scripts", {}), dict) else {}
    script_names = sorted(item for item in scripts if isinstance(item, str))
    deps = dependency_names(package)
    capabilities = sorted(KNOWN_CAPABILITIES.intersection(deps))
    has_subpackages = any(
        isinstance(config.get(key), list) and bool(config.get(key))
        for config in (app, pages)
        for key in ("subpackages", "subPackages")
    )
    output_hints = []
    for name in ("dist", "unpackage", "miniprogram", "src"):
        if (root / name).is_dir():
            output_hints.append(name)

    constraints = [
        "read-only-static-inspection",
        "no-project-command-executed",
        "no-dependency-installed",
        "simulator-not-device-evidence",
    ]
    if framework in {"unknown", "ambiguous"}:
        constraints.append("manual-confirmation-required")

    return {
        "schema_version": 1,
        "framework": framework,
        "framework_signals": signals,
        "facts": {
            "has_package_json": bool(package),
            "has_app_json": bool(app),
            "has_project_config": bool(project),
            "has_manifest_mp_weixin": isinstance(manifest.get("mp-weixin"), dict),
            "has_pages_json": bool(pages),
            "has_subpackages": has_subpackages,
            "devtools_cli_supplied": devtools_cli is not None,
            "devtools_cli_available": bool(devtools_cli and devtools_cli.is_file() and os.access(devtools_cli, os.X_OK)),
        },
        "script_names": script_names,
        "capabilities": capabilities,
        "output_directory_hints": output_hints,
        "constraints": constraints,
        "warnings": sorted(set(warnings)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Project root to inspect read-only")
    parser.add_argument("--devtools-cli", type=Path, help="Optional known DevTools CLI path; only existence is checked")
    args = parser.parse_args(argv)
    root = args.project.resolve()
    if not root.is_dir():
        print(json.dumps({"valid": False, "error": "project-root-not-directory"}))
        return 2
    print(json.dumps(inspect_project(root, args.devtools_cli), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
