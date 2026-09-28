# Signed release-evaluation evidence

This directory contains redacted, machine-verifiable release declarations.
Raw prompts, model responses, fixtures, and per-case details remain outside the
public repository and are represented here only by SHA-256 digests.

Each `v<semver>.json` declaration is canonicalized by
`scripts/evidence_signature.py` and signed with RSA/SHA-256. The private key is
stored only as the GitHub Actions secret
`EVALUATION_SIGNING_PRIVATE_KEY_B64`; `trusted-signers.pem` is the sole trusted
public key. Editing any signed field invalidates the release gate.

For reuse releases, the signed declaration binds all nine required PASS stage
attestations, their private artifact hashes, source tag and commit, source
behavior/harness fingerprints, candidate tag, and candidate fingerprints. The
gate independently recomputes Git commits and fingerprints from the checkout.

For fresh minor/major releases, the declaration and its nine referenced
artifacts must be produced after the release-subject commit exists. Every
artifact is bound to the exact candidate tag, full subject commit SHA, stage,
verdict, engine, model, timestamp, behavior fingerprint, and
evaluation-harness fingerprint. The final tag may point to a later attestation
commit only when the entire subject-to-tag diff consists of that tag's
`v<semver>*.json` files in this directory and `EVALUATIONS.md`; behavior and
harness fingerprints must remain byte-identical. This two-commit protocol
avoids an impossible commit-hash self-reference without weakening binding.

Unsigned fresh declarations are validated and signed by
`.github/workflows/sign-release-evidence.yml`. The workflow is read-only,
restricted to the repository owner, and can run only from the default branch.
It executes the default branch's trusted signer and public key against a
separate read-only candidate checkout, verifies the attestation scope before
using the secret, and publishes only the signed declaration as a short-lived
Actions artifact. Candidate-branch code never runs with the signing secret.
