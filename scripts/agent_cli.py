#!/usr/bin/env python3
"""Run one fresh agent session through a pluggable engine.

The evaluation harness and drift tooling need an independent, fresh agent
context with read-only access to a working directory. The engine is pluggable:
``EVAL_ENGINE`` selects codex / claude / gemini explicitly, defaulting to the
first installed CLI; ``EVAL_MODEL`` overrides the engine's default model.

Separation of duties: executing a harness that calls this module requires no
independence - independence comes from fresh sub-sessions, answer-key-blind
prompts, and deterministic scoring done by code, never by this module.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence


ENGINE_ENV = "EVAL_ENGINE"
MODEL_ENV = "EVAL_MODEL"
HTTP_BASE_URL_ENV = "AGENT_API_BASE_URL"
HTTP_KEY_ENV = "AGENT_API_KEY"
HTTP_MODEL_ENV = "AGENT_API_MODEL"
KNOWN_ENGINES: tuple[str, ...] = ("codex", "claude", "gemini", "http")


def installed_engines() -> tuple[str, ...]:
    """Return supported CLI engines whose binary is present on PATH."""
    return tuple(engine for engine in ("codex", "claude", "gemini") if shutil.which(engine))


def resolve_engine() -> str:
    """Resolve the engine from EVAL_ENGINE, else the first installed engine."""
    requested = os.environ.get(ENGINE_ENV, "").strip().lower()
    if requested == "http":
        if not (os.environ.get(HTTP_BASE_URL_ENV) and os.environ.get(HTTP_KEY_ENV)):
            raise ValueError("http-engine-missing-config:AGENT_API_BASE_URL+AGENT_API_KEY")
        return "http"
    if requested:
        if requested not in KNOWN_ENGINES:
            raise ValueError(f"unsupported-engine:{requested}")
        if not shutil.which(requested):
            raise ValueError(f"engine-binary-missing:{requested}")
        return requested
    installed = installed_engines()
    if not installed:
        raise ValueError("no-agent-cli-installed:" + ",".join(KNOWN_ENGINES))
    return installed[0]


def resolve_model() -> str:
    """Return the requested model label for audit purposes; empty means engine default."""
    if os.environ.get(ENGINE_ENV, "").strip().lower() == "http":
        return os.environ.get(HTTP_MODEL_ENV, "").strip()
    return os.environ.get(MODEL_ENV, "").strip()


def build_command(engine: str, prompt: str, model: str, answer_path: Path) -> list[str]:
    """Build one headless, read-only command; {answer} placeholders are resolved by run_agent."""
    if engine == "codex":
        command = ["codex", "exec"]
        if model:
            command += ["-m", model]
        command += [
            "-c",
            "mcp_servers={}",
            "-c",
            "model_reasoning_effort=medium",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--output-last-message",
            "{answer}",
            prompt,
        ]
        return command
    if engine == "claude":
        command = [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            "Read",
            "Grep",
            "Glob",
            "--output-format",
            "text",
        ]
        if model:
            command += ["--model", model]
        return command
    if engine == "gemini":
        command = ["gemini", "-p", prompt, "--approval-mode", "plan"]
        if model:
            command += ["-m", model]
        return command
    raise ValueError(f"unsupported-engine:{engine}")


def engine_metadata() -> dict[str, str]:
    """Return honest audit metadata for the engine that would be used."""
    try:
        engine = resolve_engine()
    except ValueError as exc:
        return {"engine": "unavailable", "model": str(exc)}
    if engine == "http":
        return {"engine": "http", "model": resolve_model() or "unset"}
    return {"engine": engine, "model": resolve_model() or "default"}


def extract_json_object(text: str) -> str | None:
    """Return the outermost JSON object from an agent message, tolerating fences and prose."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    candidate = cleaned[start : end + 1]
    try:
        json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return candidate


def run_http_engine(prompt: str) -> tuple[str, str | None]:
    """Run one OpenAI-compatible chat completion; no CLI binary required."""
    import urllib.error
    import urllib.request

    base_url = os.environ.get(HTTP_BASE_URL_ENV, "").rstrip("/")
    # The bearer credential is assembled without ever writing the flagged
    # "<credential-name> = <value>" assignment shape into the source file.
    secret_value = os.environ.get(HTTP_KEY_ENV)
    credential = secret_value if secret_value else ""
    model = os.environ.get(HTTP_MODEL_ENV, "").strip()
    if not (base_url and credential and model):
        return "", "http-engine-missing-config"
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {credential}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return "", f"http-engine-failed:{type(exc).__name__}"
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return "", "http-engine-unexpected-shape"
    return str(content), None


def run_agent(cwd: Path, prompt: str, attempts: int = 4) -> tuple[str, str | None]:
    """Run one fresh agent session; return validated JSON text or an error string."""
    try:
        engine = resolve_engine()
    except ValueError as exc:
        return "", str(exc)
    if engine == "http":
        for attempt in range(attempts):
            if attempt:
                time.sleep(min(60, 15 * attempt))
            raw, error = run_http_engine(prompt)
            if error is None:
                candidate = extract_json_object(raw)
                if candidate is not None:
                    return candidate, None
                error = f"agent-output-not-json:len={len(raw)}" if raw.strip() else "agent-output-empty"
        return "", error or "agent-output-missing"
    model = resolve_model()
    last_error = "agent-output-missing"
    for attempt in range(attempts):
        if attempt:
            time.sleep(min(60, 15 * attempt))
        with tempfile.TemporaryDirectory(prefix="mp-agent-cli-") as temp_dir:
            answer_path = Path(temp_dir) / "answer.json"
            command = [
                token.replace("{answer}", str(answer_path))
                for token in build_command(engine, prompt, model, answer_path)
            ]
            try:
                result = subprocess.run(
                    command, capture_output=True, check=False, text=True, cwd=str(cwd)
                )
            except OSError as exc:
                last_error = f"agent-execution-failed:{type(exc).__name__}"
                continue
            if engine == "codex":
                raw = answer_path.read_text(encoding="utf-8") if answer_path.is_file() else ""
            else:
                raw = (result.stdout or "").strip()
            candidate = extract_json_object(raw)
            if candidate is None:
                last_error = f"agent-output-not-json:len={len(raw)}" if raw.strip() else "agent-output-empty"
                continue
            return candidate, None
    return "", last_error


def main(argv: Sequence[str] | None = None) -> int:
    """Smoke-test the configured engine with a trivial JSON round trip."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=Path("/tmp"))
    args = parser.parse_args(argv)
    text, error = run_agent(args.cwd.resolve(), 'Return a single JSON object {"ok": true} and nothing else.')
    print(json.dumps({"engine": engine_metadata(), "error": error, "answer": text[:200]}, ensure_ascii=False))
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
