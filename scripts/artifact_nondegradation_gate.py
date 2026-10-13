#!/usr/bin/env python3
"""Validate private Tier 4 paired-project evidence without exposing artifacts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


MAX_INPUT_BYTES = 20_000_000
MAX_ARTIFACT_BYTES = 512_000_000
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_OID_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
ARMS = {"baseline", "with-skill"}
CONTROL_FIELDS = (
    "prompt_sha256",
    "snapshot_sha256",
    "environment_sha256",
    "model",
    "model_version",
    "permissions_sha256",
    "tools_sha256",
    "time_budget_seconds",
    "call_budget",
    "retry_budget",
    "retry_count",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def safe_relative_name(value: Any) -> str | None:
    if not isinstance(value, str) or value in {"", ".", ".."} or "\x00" in value:
        return None
    try:
        if Path(value).name != value:
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return value


def bound_path(base: Path, name: str) -> Path | None:
    try:
        path = base / name
        if path.is_symlink() or path.resolve(strict=False).parent != base.resolve():
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError(f"symlink:{path.name}")
    if not path.is_file():
        raise ValueError(f"missing:{path.name}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"oversized:{path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"not-object:{path.name}")
    return value


def load_bound_json(base: Path, name: Any, expected_sha256: Any, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    problems: list[str] = []
    safe_name = safe_relative_name(name)
    if safe_name is None:
        return None, [f"{label}:path-invalid"]
    if not valid_sha256(expected_sha256):
        return None, [f"{label}:sha256-invalid"]
    path = bound_path(base, safe_name)
    if path is None:
        return None, [f"{label}:path-outside-evidence-root"]
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError(f"oversized:{safe_name}")
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"not-object:{safe_name}")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, [f"{label}:unreadable:{type(exc).__name__}"]
    if sha256_bytes(raw) != expected_sha256:
        problems.append(f"{label}:sha256-mismatch")
    return value, problems


def verify_artifact(base: Path, record: dict[str, Any], label: str) -> list[str]:
    name = safe_relative_name(record.get("artifact_path"))
    expected = record.get("artifact_sha256")
    if name is None:
        return [f"{label}:artifact-path-invalid"]
    if not valid_sha256(expected):
        return [f"{label}:artifact-sha256-invalid"]
    path = bound_path(base, name)
    if path is None:
        return [f"{label}:artifact-outside-evidence-root"]
    try:
        if not path.is_file():
            return [f"{label}:artifact-missing"]
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            return [f"{label}:artifact-oversized"]
        actual = sha256_file(path)
    except OSError:
        return [f"{label}:artifact-unreadable"]
    return [] if actual == expected else [f"{label}:artifact-sha256-mismatch"]


def validate_controls(controls: Any, label: str) -> list[str]:
    if not isinstance(controls, dict):
        return [f"{label}:controls-not-object"]
    problems: list[str] = []
    if set(controls) != set(CONTROL_FIELDS):
        problems.append(f"{label}:controls-fields-mismatch")
    for field in (
        "prompt_sha256",
        "snapshot_sha256",
        "environment_sha256",
        "permissions_sha256",
        "tools_sha256",
    ):
        if not valid_sha256(controls.get(field)):
            problems.append(f"{label}:{field}-invalid")
    for field in ("model", "model_version"):
        if not nonempty(controls.get(field)):
            problems.append(f"{label}:{field}-missing")
    for field in ("time_budget_seconds", "call_budget"):
        value = controls.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            problems.append(f"{label}:{field}-invalid")
    retry_budget = controls.get("retry_budget")
    if not isinstance(retry_budget, int) or isinstance(retry_budget, bool) or retry_budget < 0:
        problems.append(f"{label}:retry_budget-invalid")
    retry_count = controls.get("retry_count")
    if not isinstance(retry_count, int) or isinstance(retry_count, bool) or retry_count < 0:
        problems.append(f"{label}:retry_count-invalid")
    elif isinstance(retry_budget, int) and not isinstance(retry_budget, bool) and retry_count > retry_budget:
        problems.append(f"{label}:retry-count-exceeds-budget")
    return problems


# Opt-in transport accounting. Default trials retain exact controls equality.
# This permits one proved no-output quota refusal, never a semantic reroll.
TRANSPORT_RECOVERY_POLICY = {
    "id": "one-no-output-rate-refusal-exact-input-v1",
    "maximum_recoveries_per_run": 1,
    "automatic_retries": 0,
    "actor_call_cap": 5,
    "closed_stage_call_cap": 1,
}


# An explicitly declared longer waiting experiment; scoring and default trials stay unchanged.
WAITING_TRANSPORT_POLICY = {
    **TRANSPORT_RECOVERY_POLICY,
    "id": "bounded-long-wait-exact-input-v2",
    "actor_deadline_seconds": 900,
    "closed_deadline_seconds": 1200,
    "total_deadline_seconds": 4500,
}


def waiting_bound_path(base: Path, name: Any) -> Path | None:
    """Permit only contained nonsymlink components for opt-in immutable lineage."""
    if not isinstance(name, str) or "\\" in name:
        return None
    parts = name.split("/")
    if not parts or any(safe_relative_name(part) is None for part in parts):
        return None
    try:
        path = base
        for part in parts:
            path = path / part
            if path.is_symlink():
                return None
        if not path.resolve(strict=False).is_relative_to(base.resolve()) or path.resolve(strict=False) == base.resolve():
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return path


def bound_bytes(base: Path, reference: Any, *, allow_subdirectories: bool = False) -> bytes:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError("reference-invalid")
    name = safe_relative_name(reference["path"])
    path = waiting_bound_path(base, reference["path"]) if allow_subdirectories else bound_path(base, name) if name else None
    if path is None or not valid_sha256(reference["sha256"]):
        raise ValueError("reference-invalid")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES or sha256_bytes(raw) != reference["sha256"]:
        raise ValueError("reference-sha-or-size-invalid")
    return raw


def waiting_bound_bytes(base: Path, reference: Any) -> bytes:
    return bound_bytes(base, reference, allow_subdirectories=True)


def waiting_adapter_lineage(base: Path, record: dict[str, Any], reference: Any) -> tuple[str, str]:
    """Accept only an exact timeout/audit-field change and immutable stricter-stage ancestry."""
    if not isinstance(reference, dict) or set(reference) != {"prior_adapter", "current_adapter"}:
        raise ValueError("waiting-adapter-lineage-invalid")
    prior_raw = waiting_bound_bytes(base, reference["prior_adapter"])
    current_raw = waiting_bound_bytes(base, reference["current_adapter"])
    old = b"deadline=900 if fixture else 600"
    new = b"deadline=900 if fixture else 1200"
    field = b"'maximum_provider_calls':maximum,"
    if prior_raw.count(old) != 1 or prior_raw.count(field) != 1:
        raise ValueError("waiting-adapter-deadline-unbound")
    tree = ast.parse(prior_raw.decode("utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "call"]
    if len(functions) != 1:
        raise ValueError("waiting-adapter-call-unbound")
    nodes = list(ast.walk(functions[0]))
    assignments = [node for node in nodes if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "deadline" for target in node.targets)]
    gateways = [node for node in nodes if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "BudgetGateway"]
    waits = [node for node in nodes if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
             and node.func.value.id == "p" and node.func.attr == "wait" and node.keywords]
    def named(value: Any, name: str) -> bool:
        return isinstance(value, ast.Name) and value.id == name
    if (len(assignments) != 1 or len(gateways) != 1 or len(gateways[0].args) != 3
            or gateways[0].keywords or not named(gateways[0].args[1], "maximum")
            or not named(gateways[0].args[2], "deadline")
            or sum(len(node.keywords) == 1 and node.keywords[0].arg == "timeout"
                   and named(node.keywords[0].value, "deadline") for node in waits) != 1
            or any(len(node.keywords) != 1 or node.keywords[0].arg != "timeout"
                   or not (named(node.keywords[0].value, "deadline")
                           or isinstance(node.keywords[0].value, ast.Constant)
                           and type(node.keywords[0].value.value) is int and node.keywords[0].value.value == 5)
                   for node in waits)):
        raise ValueError("waiting-adapter-effective-deadline-unbound")
    if b"stage_deadline_seconds" in prior_raw:
        raise ValueError("waiting-prior-audit-deadline-already-present")
    expected = prior_raw.replace(old, new).replace(field, field + b"'stage_deadline_seconds':deadline,")
    if current_raw != expected:
        raise ValueError("waiting-adapter-nonwaiting-change")
    prior_sha, current_sha = sha256_bytes(prior_raw), sha256_bytes(current_raw)
    inherited = [stage for stage in record["transport_stages"]
                 if json.loads(waiting_bound_bytes(base, stage["audit"])).get("adapter_sha256") == prior_sha]
    if inherited:
        original_reference = record.get("prior_waiting_record")
        original = json.loads(waiting_bound_bytes(base, original_reference))
        original_path = waiting_bound_path(base, original_reference["path"])
        if validate_transport_recovery(original_path.parent, original, TRANSPORT_RECOVERY_POLICY):
            raise ValueError("waiting-prior-record-not-qualified-transport")
        identity = ("case_id", "arm", "run_id", "repetition", "treatment",
                    "generation_session", "independent_review_session")
        if (any(key not in original or key not in record or original[key] != record[key] for key in identity)
                or not isinstance(original["run_id"], str)
                or re.fullmatch(r"[a-z0-9-]+", original["run_id"]) is None
                or original["arm"] not in ARMS
                or type(original["repetition"]) is not int or original["repetition"] < 1):
            raise ValueError("waiting-prior-trial-identity-changed")
        original_base = original_path.parent
        original_stages = original["transport_stages"]
        if len(record["transport_stages"]) < len(original_stages):
            raise ValueError("waiting-prior-stage-chain-shortened")
        for index, previous in enumerate(original_stages):
            current = record["transport_stages"][index]
            if set(current) != set(previous):
                raise ValueError("waiting-prior-stage-not-identical")
            for key, value in previous.items():
                if isinstance(value, dict):
                    if waiting_bound_bytes(original_base, value) != waiting_bound_bytes(base, current[key]):
                        raise ValueError("waiting-prior-stage-not-identical")
                elif current[key] != value:
                    raise ValueError("waiting-prior-stage-not-identical")
        actor_id = json.loads(waiting_bound_bytes(original_base, original_stages[0]["audit"]))["id"]
        peer_id = json.loads(waiting_bound_bytes(original_base, original_stages[1]["audit"]))["id"]
        if original["generation_session"] != actor_id or original["independent_review_session"] != peer_id:
            raise ValueError("waiting-prior-generation-identity-unbound")
        reservations = record.get("prior_waiting_attempts")
        if not isinstance(reservations, dict):
            raise ValueError("waiting-prior-reservations-unbound")
        names = {"actor": "actor", "peer": "peer", "repair": "repair", "recovery": "quota-recovery"}
        actual_slots = {role: original_base / (original["run_id"] + "-" + suffix + "-attempt.json")
                        for role, suffix in names.items()}
        safe_slots = {}
        for role, file in actual_slots.items():
            if file.is_symlink():
                raise ValueError("waiting-prior-reservation-symlink")
            if file.exists():
                safe = waiting_bound_path(original_base, file.name)
                if safe is None or not safe.is_file() or safe.stat().st_size > MAX_INPUT_BYTES:
                    raise ValueError("waiting-prior-reservation-path-invalid")
                safe_slots[role] = safe
        actual_slots = safe_slots
        if set(reservations) != set(actual_slots) or set(actual_slots) != {row["role"] for row in original_stages}:
            raise ValueError("waiting-prior-slots-not-fully-accounted")
        for previous in original_stages:
            role = previous["role"]
            raw = waiting_bound_bytes(base, reservations[role])
            actual_reference = {"path": actual_slots[role].name, "sha256": reservations[role]["sha256"]}
            if raw != waiting_bound_bytes(original_base, actual_reference):
                raise ValueError("waiting-prior-reservation-not-identical")
            attempt = json.loads(raw)
            audit = json.loads(waiting_bound_bytes(original_base, previous["audit"]))
            expected_status = "failed" if audit["status"] == "failed" else "completed"
            allowed = {expected_status, "completed-awaiting-factual-review"} if role == "recovery" else {expected_status}
            if (attempt.get("session") != audit["id"] or attempt.get("status") not in allowed
                    or attempt.get("audit_sha256", previous["audit"]["sha256"]) != previous["audit"]["sha256"]
                    or attempt.get("actual_provider_calls", audit["actual_upstream_calls"]) != audit["actual_upstream_calls"]):
                raise ValueError("waiting-prior-reservation-not-completed")
        if len(record["transport_stages"]) == len(original_stages):
            if (record["artifact_sha256"] != original["artifact_sha256"]
                    or waiting_bound_bytes(base, {"path": record["artifact_path"], "sha256": record["artifact_sha256"]})
                    != waiting_bound_bytes(original_base, {"path": original["artifact_path"], "sha256": original["artifact_sha256"]})):
                raise ValueError("waiting-prior-final-output-changed")
        for key in ("prompt_sha256", "snapshot_sha256", "model", "model_version",
                    "permissions_sha256", "tools_sha256"):
            if original["controls"].get(key) != record["controls"].get(key):
                raise ValueError("waiting-prior-semantic-controls-changed")
        if original["controls"]["retry_count"] > record["controls"]["retry_count"]:
            raise ValueError("waiting-prior-recovery-count-reset")
    elif record.get("prior_waiting_record") is not None or record.get("prior_waiting_attempts") is not None:
        raise ValueError("waiting-prior-record-unused")
    return prior_sha, current_sha


def validate_transport_recovery(base: Path, record: dict[str, Any], policy: Any, waiting_lineage: Any = None) -> list[str]:
    """Verify real dispatch/time counts and exact-input no-output denial recovery."""
    try:
        long_wait = canonical_sha256(policy) == canonical_sha256(WAITING_TRANSPORT_POLICY)
        if not long_wait and canonical_sha256(policy) != canonical_sha256(TRANSPORT_RECOVERY_POLICY):
            raise ValueError("policy-invalid")
        if not long_wait and waiting_lineage is not None:
            raise ValueError("waiting-lineage-with-default-policy")
        adapters = waiting_adapter_lineage(base, record, waiting_lineage) if long_wait else None
        read_bound = waiting_bound_bytes if long_wait else bound_bytes
        controls = record["controls"]
        if (type(controls["retry_budget"]) is not int or controls["retry_budget"] != 1
                or type(controls["retry_count"]) is not int or controls["retry_count"] not in (0, 1)
                or controls["call_budget"] != 8 or controls["time_budget_seconds"] != (4500 if long_wait else 2700)):
            raise ValueError("recovery-count-invalid")
        stages = record["transport_stages"]
        if not isinstance(stages, list):
            raise ValueError("stages-invalid")
        roles = [stage["role"] for stage in stages]
        if roles not in (["actor", "peer"], ["actor", "peer", "repair"],
                         ["actor", "peer", "repair", "recovery"]):
            raise ValueError("stage-order-invalid")
        if controls["retry_count"] != int("recovery" in roles):
            raise ValueError("recovery-count-mismatch")
        calls, elapsed, decoded, ids = 0, 0.0, [], set()
        for stage in stages:
            audit = json.loads(read_bound(base, stage["audit"]))
            if (not valid_sha256(audit.get("provider_config_sha256"))
                    or not valid_sha256(audit.get("adapter_sha256"))
                    or not nonempty(audit.get("engine"))
                    or not nonempty(audit.get("execution_mode"))):
                raise ValueError("actual-transport-profile-invalid")
            deadline = 900 if stage["role"] == "actor" else 600
            if long_wait:
                if audit.get("error") in ("engine-timeout", "transport-timeout"):
                    raise ValueError("waiting-timeout-not-recoverable")
                if audit["adapter_sha256"] not in adapters:
                    raise ValueError("waiting-actual-adapter-not-bound")
                if audit["adapter_sha256"] == adapters[1]:
                    deadline = 900 if stage["role"] == "actor" else 1200
                    if type(audit.get("stage_deadline_seconds")) is not int or audit["stage_deadline_seconds"] != deadline:
                        raise ValueError("waiting-actual-stage-deadline-invalid")
                elif audit.get("stage_deadline_seconds") not in (None, deadline):
                    raise ValueError("waiting-prior-deadline-changed")
            prompt = read_bound(base, stage["prompt"])
            ledger_raw = read_bound(base, stage["ledger"])
            ledger = [json.loads(line) for line in ledger_raw.splitlines()]
            dispatches = [row for row in ledger if row.get("event") == "upstream-dispatch"]
            cap = 5 if stage["role"] == "actor" else 1
            count = audit["actual_upstream_calls"]
            if (not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= cap
                    or len(dispatches) != count
                    or audit["maximum_provider_calls"] != cap
                    or audit["automatic_retries"] != 0
                    or audit["provider_request_ledger_sha256"] != sha256_bytes(ledger_raw)
                    or audit["prompt_sha256"] != sha256_bytes(prompt)
                    or audit["model"] != controls["model"]
                    or audit["global_provider_config_unchanged"] is not True
                    or audit["temporary_credentials_removed"] is not True
                    or audit.get("fresh_context") is not True
                    or audit["id"] in ids
                    or not finite_number(audit["elapsed_seconds"])
                    or not 0 <= audit["elapsed_seconds"] <= deadline):
                raise ValueError("stage-audit-invalid")
            if [row["ordinal"] for row in dispatches] != list(range(1, count + 1)):
                raise ValueError("dispatch-order-invalid")
            if any(row["model"] != controls["model"] for row in dispatches):
                raise ValueError("dispatch-model-invalid")
            if stage["role"] == "actor" and (audit.get("enabled_plugin_count") != 0
                    or audit.get("mcp_server_names") != ["audit_probe"]
                    or not set(audit.get("observed_tool_names", [])).issubset({
                        "mcp__audit_probe__read_snapshot", "mcp__audit_probe__trace"})):
                raise ValueError("actor-tools-or-plugins-invalid")
            if decoded and audit["provider_config_sha256"] != decoded[0][1]["provider_config_sha256"]:
                raise ValueError("stage-provider-configuration-changed")
            if audit.get("status") == "completed" and audit.get("observed_models") != [controls["model"]]:
                raise ValueError("stage-observed-model-invalid")
            ids.add(audit["id"])
            calls += count
            elapsed += audit["elapsed_seconds"]
            if stage["role"] != "actor" and audit.get("status") == "completed":
                if (audit.get("tool_execution_events") != 0
                        or audit.get("observed_tool_names") != []
                        or audit.get("enabled_plugin_count") != 0
                        or audit.get("mcp_server_connections") != 0
                        or audit.get("observed_models") != [controls["model"]]):
                    raise ValueError("closed-stage-tools-or-model-invalid")
            if audit.get("status") == "completed":
                stdout = read_bound(base, stage["stdout"])
                response = json.loads(stdout)
                if (audit.get("response_sha256") != sha256_bytes(stdout)
                        or not nonempty(audit.get("sessionId"))
                        or response.get("sessionId") != audit["sessionId"]):
                    raise ValueError("completed-stage-session-or-response-unbound")
            decoded.append((stage, audit, prompt, ledger))
        if any(audit["status"] != "completed" for stage, audit, _, _ in decoded
               if not (stage["role"] == "repair" and "recovery" in roles)):
            raise ValueError("stage-not-completed")
        if "recovery" in roles:
            original, recovered = decoded[-2:]
            stage, audit, prompt, ledger = original
            execution = json.loads(read_bound(base, stage["execution_events"]))
            if (not isinstance(execution, list)
                    or any(event.get("event", "").startswith(("tool.", "mcp.tool.", "mcp.server.connect.")) for event in execution)
                    or [event.get("context", {}).get("enabledPluginCount") for event in execution
                        if event.get("event") == "bootstrap.app.startup.plugins.completed"] != [0]):
                raise ValueError("refusal-stage-tools-or-plugins-invalid")
            if (audit["status"] != "failed"
                    or read_bound(base, stage["stdout"]).strip()
                    or recovered[2] != prompt):
                raise ValueError("refusal-or-exact-input-invalid")
            has_json = stage.get("refusal_json") is not None
            if has_json and stage.get("refusal_sse") is not None:
                raise ValueError("ambiguous-refusal-format")
            if has_json:
                raw = read_bound(base, stage["refusal_json"])
                errors = [row for row in ledger if row.get("event") == "upstream-http-error"]
                denial_dispatches = [row for row in ledger if row.get("event") == "upstream-dispatch"]
                if (len(errors) != 1 or errors[0].get("ordinal") != 1
                        or errors[0].get("status") != 429
                        or errors[0].get("response_sha256") != sha256_bytes(raw)
                        or errors[0].get("content_type", "").split(";", 1)[0].strip().lower() != "application/json"
                        or errors[0].get("content_encoding") not in (None, "identity")
                        or len(denial_dispatches) != 1 or denial_dispatches[0].get("upstream") != "api.z.ai"
                        or audit.get("provider") != "zai"
                        or any(row.get("event") == "upstream-completed" for row in ledger)):
                    raise ValueError("json-refusal-not-bound-to-dispatch")
                def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    result: dict[str, Any] = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError("json-refusal-duplicate-field")
                        result[key] = value
                    return result
                denial = json.loads(raw, object_pairs_hook=unique_fields)
                error = denial.get("error") if isinstance(denial, dict) else None
                if (not isinstance(denial, dict) or set(denial) != {"type", "error", "request_id"}
                        or denial.get("type") != "error" or not nonempty(denial.get("request_id"))
                        or not isinstance(error, dict) or set(error) != {"type", "code", "message"}
                        or error.get("type") != "rate_limit_error" or error.get("code") != "1302"
                        or not nonempty(error.get("message"))):
                    raise ValueError("json-refusal-has-output-or-unknown-shape")
            else:
                raw = read_bound(base, stage["refusal_sse"])
                completed = [row for row in ledger if row.get("event") == "upstream-completed"]
                if len(completed) != 1 or completed[0]["response_sha256"] != sha256_bytes(raw):
                    raise ValueError("refusal-not-bound-to-dispatch")
                # SSE data permits no space after ':' and multiple data lines per frame.
                # Parse every frame; never skip a generated, malformed, or unknown event.
                frames, data = [], []
                for line in raw.decode("utf-8").splitlines() + [""]:
                    if line == "":
                        if data:
                            frames.append("\n".join(data))
                            data = []
                    elif line.startswith(":") or line.startswith(("event:", "id:", "retry:")):
                        continue
                    elif line.startswith("data:"):
                        value = line[5:]
                        data.append(value[1:] if value.startswith(" ") else value)
                    else:
                        raise ValueError("refusal-sse-invalid")
                if not frames or frames[-1] != "[DONE]" or frames.count("[DONE]") != 1:
                    raise ValueError("refusal-sse-incomplete")
                events = [json.loads(frame) for frame in frames[:-1]]
                if (len(events) != 2 or events[0]["type"] != "response.failed"
                        or events[0]["response"]["error"]["code"] != "rate_limit_exceeded"
                        or events[0]["response"]["output"] != []
                        or events[0]["response"]["status"] != "failed"
                        or events[0]["response"]["usage"] is not None
                        or events[0]["response"]["model"] != controls["model"]
                        or events[1]["type"] != "error"
                        or events[1]["code"] != "rate_limit_exceeded"
                        or audit["status"] != "failed"
                        or read_bound(base, stage["stdout"]).strip()
                        or recovered[2] != prompt):
                    raise ValueError("refusal-or-exact-input-invalid")
            for field in ("provider_config_sha256", "adapter_sha256", "maximum_provider_calls"):
                if audit[field] != recovered[1][field]:
                    raise ValueError("recovery-configuration-changed")
        final_stage, final_audit, _, _ = decoded[-1]
        stdout = read_bound(base, final_stage["stdout"])
        if final_audit["response_sha256"] != sha256_bytes(stdout):
            raise ValueError("final-response-unbound")
        output = json.loads(stdout)["response"]
        artifact = read_bound(base, {"path": record["artifact_path"], "sha256": record["artifact_sha256"]})
        if not isinstance(output, str) or artifact.decode("utf-8") != output + "\n":
            raise ValueError("final-artifact-not-model-output")
        if (record["actual_provider_calls"] != calls or calls > controls["call_budget"]
                or not finite_number(record["elapsed_seconds"])
                or abs(record["elapsed_seconds"] - elapsed) > 0.002
                or elapsed > controls["time_budget_seconds"]):
            raise ValueError("dispatch-or-time-budget-invalid")
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, AttributeError, IndexError, OverflowError, SyntaxError) as exc:
        # Raw parser/I/O errors can contain private paths or source fragments.
        code = str(exc) if type(exc) is ValueError and re.fullmatch(r"[a-z][a-z-]+", str(exc)) else type(exc).__name__
        return ["transport-recovery:" + code]
    return []


def validate_judgment(
    judgment: dict[str, Any],
    case_id: str,
    run_ids: dict[str, list[str]],
    run_artifacts: dict[str, dict[str, str]],
    label: str,
) -> tuple[list[str], float | None]:
    problems: list[str] = []
    if judgment.get("schema_version") != 1:
        problems.append(f"{label}:schema-version-invalid")
    if judgment.get("case_id") != case_id:
        problems.append(f"{label}:case-id-mismatch")
    if judgment.get("blind") is not True or judgment.get("source_labels_hidden") is not True:
        problems.append(f"{label}:not-blind")
    if judgment.get("artifact_order_randomized") is not True:
        problems.append(f"{label}:order-not-randomized")
    if not valid_sha256(judgment.get("rubric_sha256")):
        problems.append(f"{label}:rubric-sha256-invalid")
    for field in ("judge_engine", "judge_model", "generated_at_utc"):
        if not nonempty(judgment.get(field)):
            problems.append(f"{label}:{field}-missing")

    judged_runs = judgment.get("run_ids")
    if not isinstance(judged_runs, dict):
        problems.append(f"{label}:run-ids-not-object")
    else:
        for arm in sorted(ARMS):
            if judged_runs.get(arm) != run_ids[arm]:
                problems.append(f"{label}:{arm}-run-ids-mismatch")

    judged_artifacts = judgment.get("run_artifacts")
    if not isinstance(judged_artifacts, dict):
        problems.append(f"{label}:run-artifacts-not-object")
    else:
        for arm in sorted(ARMS):
            if judged_artifacts.get(arm) != run_artifacts[arm]:
                problems.append(f"{label}:{arm}-artifact-binding-mismatch")

    critical_errors = judgment.get("critical_errors")
    if not isinstance(critical_errors, dict):
        problems.append(f"{label}:critical-errors-not-object")
    else:
        for arm in sorted(ARMS):
            value = critical_errors.get(arm)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                problems.append(f"{label}:{arm}-critical-errors-invalid")
            elif arm == "with-skill" and value != 0:
                problems.append(f"{label}:{arm}-critical-errors")

    target_scores = judgment.get("target_scores")
    gain: float | None = None
    if not isinstance(target_scores, dict):
        problems.append(f"{label}:target-scores-not-object")
    else:
        baseline = target_scores.get("baseline")
        with_skill = target_scores.get("with-skill")
        if not all(finite_number(value) for value in (baseline, with_skill)):
            problems.append(f"{label}:target-score-invalid")
        else:
            gain = float(with_skill) - float(baseline)
            if gain < 0:
                problems.append(f"{label}:target-regression")

    dimensions = judgment.get("dimensions")
    critical_seen = False
    if not isinstance(dimensions, dict) or not dimensions:
        problems.append(f"{label}:dimensions-missing")
    else:
        for name, detail in sorted(dimensions.items()):
            dimension_label = f"{label}:dimension:{name}"
            if not isinstance(detail, dict):
                problems.append(f"{dimension_label}:not-object")
                continue
            baseline = detail.get("baseline")
            with_skill = detail.get("with-skill")
            if not all(finite_number(value) for value in (baseline, with_skill)):
                problems.append(f"{dimension_label}:score-invalid")
                continue
            if detail.get("critical") is True:
                critical_seen = True
                if float(with_skill) < float(baseline):
                    problems.append(f"{dimension_label}:critical-regression")
    if not critical_seen:
        problems.append(f"{label}:critical-dimension-missing")
    return problems, gain


def validate_bundle(bundle_path: Path) -> dict[str, Any]:
    generated_at = utc_now()
    try:
        bundle = load_json(bundle_path)
        bundle_raw = bundle_path.read_bytes()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return {
            "schema_version": 1,
            "stage": "artifact-nondegradation",
            "verdict": "FAIL",
            "generated_at_utc": generated_at,
            "problems": [f"bundle-unreadable:{type(exc).__name__}"],
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "stage": "artifact-nondegradation",
        "candidate_tag": bundle.get("candidate_tag"),
        "candidate_commit": bundle.get("candidate_commit"),
        "skill_behavior_sha256": bundle.get("skill_behavior_sha256"),
        "evaluation_harness_sha256": bundle.get("evaluation_harness_sha256"),
        "engine": bundle.get("engine"),
        "model": bundle.get("model"),
        "model_version": bundle.get("model_version"),
        "generated_at_utc": bundle.get("generated_at_utc") or generated_at,
    }
    problems: list[str] = []
    if bundle.get("schema_version") != 1:
        problems.append("bundle:schema-version-invalid")
    if not isinstance(bundle.get("candidate_tag"), str) or TAG_RE.fullmatch(bundle["candidate_tag"]) is None:
        problems.append("bundle:candidate-tag-invalid")
    if not isinstance(bundle.get("candidate_commit"), str) or GIT_OID_RE.fullmatch(bundle["candidate_commit"]) is None:
        problems.append("bundle:candidate_commit-invalid")
    for field in ("skill_behavior_sha256", "evaluation_harness_sha256"):
        if not valid_sha256(bundle.get(field)):
            problems.append(f"bundle:{field}-invalid")
    for field in ("engine", "model", "model_version", "generated_at_utc"):
        if not nonempty(bundle.get(field)):
            problems.append(f"bundle:{field}-missing")
    minimum_runs = bundle.get("minimum_runs_per_arm")
    if not isinstance(minimum_runs, int) or isinstance(minimum_runs, bool) or minimum_runs < 2:
        problems.append("bundle:minimum-runs-invalid")
        minimum_runs = 2
    minimum_cases = bundle.get("minimum_case_count")
    if not isinstance(minimum_cases, int) or isinstance(minimum_cases, bool) or minimum_cases < 2:
        problems.append("bundle:minimum-case-count-invalid")
        minimum_cases = 2
    minimum_gain = bundle.get("minimum_mean_target_gain")
    if not finite_number(minimum_gain) or float(minimum_gain) <= 0:
        problems.append("bundle:minimum-gain-invalid")
        minimum_gain = 0.0

    cases = bundle.get("cases")
    if not isinstance(cases, list) or not cases:
        problems.append("bundle:cases-missing")
        cases = []
    elif len(cases) < minimum_cases:
        problems.append("bundle:cases-below-minimum")
    case_ids: set[str] = set()
    gains: list[float] = []
    run_count = 0
    base = bundle_path.parent
    transport_audits_seen: set[str] = set()
    transport_sessions_seen: set[str] = set()
    refusal_responses_seen: set[str] = set()
    engine_sessions_seen: set[str] = set()
    transport_profiles: dict[str, str] = {}
    for index, case in enumerate(cases):
        prefix = f"case:{index}"
        if not isinstance(case, dict):
            problems.append(f"{prefix}:not-object")
            continue
        case_id = case.get("id")
        if not nonempty(case_id):
            problems.append(f"{prefix}:id-missing")
            continue
        prefix = f"case:{case_id}"
        if case_id in case_ids:
            problems.append(f"{prefix}:id-duplicate")
            continue
        case_ids.add(case_id)
        runs = case.get("runs")
        if not isinstance(runs, list):
            problems.append(f"{prefix}:runs-not-list")
            runs = []
        run_ids: dict[str, list[str]] = {arm: [] for arm in ARMS}
        run_artifacts: dict[str, dict[str, str]] = {arm: {} for arm in ARMS}
        controls_digests: set[str] = set()
        seen_run_ids: set[str] = set()
        seen_repetitions: dict[str, set[int]] = {arm: set() for arm in ARMS}
        for run_index, attestation in enumerate(runs):
            run_label = f"{prefix}:run:{run_index}"
            if not isinstance(attestation, dict):
                problems.append(f"{run_label}:attestation-not-object")
                continue
            record, record_problems = load_bound_json(
                base,
                attestation.get("record_path"),
                attestation.get("record_sha256"),
                run_label,
            )
            problems.extend(record_problems)
            if record is None:
                continue
            if record.get("schema_version") != 1:
                problems.append(f"{run_label}:schema-version-invalid")
            if record.get("case_id") != case_id:
                problems.append(f"{run_label}:case-id-mismatch")
            arm = record.get("arm")
            if not isinstance(arm, str) or arm not in ARMS:
                problems.append(f"{run_label}:arm-invalid")
                continue
            run_id = record.get("run_id")
            if not nonempty(run_id) or run_id in seen_run_ids:
                problems.append(f"{run_label}:run-id-invalid-or-duplicate")
                continue
            repetition = record.get("repetition")
            if not isinstance(repetition, int) or isinstance(repetition, bool) or repetition <= 0:
                problems.append(f"{run_label}:repetition-invalid")
            elif repetition in seen_repetitions[arm]:
                problems.append(f"{run_label}:repetition-duplicate")
            else:
                seen_repetitions[arm].add(repetition)
            seen_run_ids.add(run_id)
            run_ids[arm].append(run_id)
            artifact_sha256 = record.get("artifact_sha256")
            if valid_sha256(artifact_sha256):
                run_artifacts[arm][run_id] = artifact_sha256
            controls = record.get("controls")
            problems.extend(validate_controls(controls, run_label))
            if isinstance(controls, dict):
                if "transport_recovery_policy" in bundle:
                    transport_problems = validate_transport_recovery(base, record, bundle["transport_recovery_policy"], bundle.get("waiting_adapter_lineage"))
                    problems.extend(f"{run_label}:{problem}" for problem in transport_problems)
                    if not transport_problems:
                        for stage in record["transport_stages"]:
                            digest = stage["audit"]["sha256"]
                            reader = waiting_bound_bytes if canonical_sha256(bundle["transport_recovery_policy"]) == canonical_sha256(WAITING_TRANSPORT_POLICY) else bound_bytes
                            audit = json.loads(reader(base, stage["audit"]))
                            session = audit["id"]
                            actual_session = audit.get("sessionId") if audit["status"] == "completed" else None
                            group = "actor" if stage["role"] == "actor" else "closed"
                            profile_fields = {key: audit.get(key) for key in (
                                "provider_config_sha256", "adapter_sha256", "engine", "execution_mode")}
                            if canonical_sha256(bundle["transport_recovery_policy"]) == canonical_sha256(WAITING_TRANSPORT_POLICY):
                                _, current_adapter = waiting_adapter_lineage(base, record, bundle["waiting_adapter_lineage"])
                                profile_fields["adapter_sha256"] = current_adapter
                            profile = canonical_sha256(profile_fields)
                            if group in transport_profiles and transport_profiles[group] != profile:
                                problems.append(f"{run_label}:actual-transport-profile-not-equivalent")
                            transport_profiles[group] = profile
                            if actual_session is not None:
                                if actual_session in engine_sessions_seen:
                                    problems.append(f"{run_label}:actual-engine-session-reused")
                                engine_sessions_seen.add(actual_session)
                            refusal = ((stage.get("refusal_json") or stage.get("refusal_sse"))["sha256"]
                                       if stage["role"] == "repair" and controls["retry_count"] == 1 else None)
                            if (digest in transport_audits_seen or session in transport_sessions_seen
                                    or refusal is not None and refusal in refusal_responses_seen):
                                problems.append(f"{run_label}:transport-session-reused")
                            transport_audits_seen.add(digest)
                            transport_sessions_seen.add(session)
                            if refusal is not None:
                                refusal_responses_seen.add(refusal)
                    configured = {key: value for key, value in controls.items() if key != "retry_count"}
                    controls_digests.add(canonical_sha256(configured))
                else:
                    controls_digests.add(canonical_sha256(controls))
                if controls.get("model") != bundle.get("model"):
                    problems.append(f"{run_label}:model-mismatch")
                if controls.get("model_version") != bundle.get("model_version"):
                    problems.append(f"{run_label}:model-version-mismatch")
            problems.extend(verify_artifact(base, record, run_label))
            run_count += 1
        for arm in sorted(ARMS):
            run_ids[arm].sort()
            if len(run_ids[arm]) < minimum_runs:
                problems.append(f"{prefix}:{arm}-runs-below-minimum")
        if len(controls_digests) != 1:
            problems.append(f"{prefix}:controls-not-equivalent")

        judgment, judgment_problems = load_bound_json(
            base,
            case.get("judgment_path"),
            case.get("judgment_sha256"),
            f"{prefix}:judgment",
        )
        problems.extend(judgment_problems)
        if judgment is not None:
            judgment_issues, gain = validate_judgment(
                judgment,
                case_id,
                run_ids,
                run_artifacts,
                f"{prefix}:judgment",
            )
            problems.extend(judgment_issues)
            if gain is not None:
                gains.append(gain)

    mean_gain = sum(gains) / len(gains) if gains and len(gains) == len(cases) else None
    if mean_gain is None:
        problems.append("bundle:mean-target-gain-not-computable")
    elif mean_gain < float(minimum_gain):
        problems.append("bundle:mean-target-gain-below-minimum")

    report.update(
        {
            "verdict": "PASS" if not problems else "FAIL",
            "case_count": len(case_ids),
            "run_count": run_count,
            "minimum_runs_per_arm": minimum_runs,
            "minimum_case_count": minimum_cases,
            "minimum_mean_target_gain": minimum_gain,
            "mean_target_gain": mean_gain,
            "critical_error_count": sum("critical-errors" in item for item in problems),
            "critical_regression_count": sum("critical-regression" in item for item in problems),
            "problems": problems,
            "audit": {
                "stage": "artifact-nondegradation",
                "generated_at_utc": generated_at,
                "engine": bundle.get("engine"),
                "model": bundle.get("model"),
                "model_version": bundle.get("model_version"),
                "evidence_bundle_sha256": sha256_bytes(bundle_raw),
            },
        }
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_bundle", type=Path, help="Private Tier 4 evidence bundle JSON")
    parser.add_argument("--output", type=Path, help="Write the redacted gate report here")
    args = parser.parse_args(argv)
    # Preserve the final path component so load_json can reject a bundle
    # symlink instead of silently following it before validation.
    report = validate_bundle(args.evidence_bundle.absolute())
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
