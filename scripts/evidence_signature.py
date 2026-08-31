#!/usr/bin/env python3
"""Canonical JSON signatures for release-governance evidence.

Only the public key is committed. Signing happens outside the repository with
the private key stored in GitHub Actions secrets. Verification deliberately
uses OpenSSL rather than a Python package so the public suite keeps its
standard-library-only runtime contract.
"""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SIGNATURE_ALGORITHM = "rsa-sha256"


class SignatureError(ValueError):
    """Raised when signed governance evidence is malformed or untrusted."""


def canonical_payload(document: dict[str, Any]) -> bytes:
    """Return stable UTF-8 JSON bytes, excluding the detached signature."""
    unsigned = {key: value for key, value in document.items() if key != "signature"}
    return json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _run_openssl(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["openssl", *args],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SignatureError("openssl-not-available") from exc


def verify_signed_document(
    document: dict[str, Any],
    public_key: Path,
    *,
    expected_key_id: str | None = None,
) -> str:
    """Verify a detached RSA/SHA-256 signature and return its key id."""
    signature = document.get("signature")
    if not isinstance(signature, dict):
        raise SignatureError("signature-missing")
    if signature.get("algorithm") != SIGNATURE_ALGORITHM:
        raise SignatureError("signature-algorithm-invalid")
    key_id = signature.get("key_id")
    if not isinstance(key_id, str) or not key_id.strip():
        raise SignatureError("signature-key-id-missing")
    if expected_key_id is not None and key_id != expected_key_id:
        raise SignatureError("signature-key-id-untrusted")
    value = signature.get("value")
    if not isinstance(value, str) or not value.strip():
        raise SignatureError("signature-value-missing")
    if not public_key.is_file():
        raise SignatureError(f"trusted-public-key-missing:{public_key}")
    try:
        signature_bytes = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise SignatureError("signature-base64-invalid") from exc

    with tempfile.TemporaryDirectory(prefix="evidence-verify-") as directory:
        temp = Path(directory)
        payload_path = temp / "payload.json"
        signature_path = temp / "signature.bin"
        payload_path.write_bytes(canonical_payload(document))
        signature_path.write_bytes(signature_bytes)
        result = _run_openssl([
            "dgst",
            "-sha256",
            "-verify",
            str(public_key),
            "-signature",
            str(signature_path),
            str(payload_path),
        ])
    if result.returncode != 0:
        raise SignatureError("signature-verification-failed")
    return key_id


def sign_document(document: dict[str, Any], private_key: Path, key_id: str) -> dict[str, Any]:
    """Return a signed copy. Intended for controlled tooling and test fixtures."""
    if not private_key.is_file():
        raise SignatureError(f"private-key-missing:{private_key}")
    signed = {key: value for key, value in document.items() if key != "signature"}
    with tempfile.TemporaryDirectory(prefix="evidence-sign-") as directory:
        temp = Path(directory)
        payload_path = temp / "payload.json"
        signature_path = temp / "signature.bin"
        payload_path.write_bytes(canonical_payload(signed))
        result = _run_openssl([
            "dgst",
            "-sha256",
            "-sign",
            str(private_key),
            "-out",
            str(signature_path),
            str(payload_path),
        ])
        if result.returncode != 0:
            raise SignatureError("signature-generation-failed")
        encoded = base64.b64encode(signature_path.read_bytes()).decode("ascii")
    signed["signature"] = {
        "algorithm": SIGNATURE_ALGORITHM,
        "key_id": key_id,
        "value": encoded,
    }
    return signed
