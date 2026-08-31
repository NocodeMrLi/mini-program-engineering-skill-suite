# Signed release-evaluation evidence

This directory contains redacted, machine-verifiable release declarations.
Raw prompts, model responses, fixtures, and per-case details remain outside the
public repository and are represented here only by SHA-256 digests.

Each `v<semver>.json` declaration is canonicalized by
`scripts/evidence_signature.py` and signed with RSA/SHA-256. The private key is
stored only as the GitHub Actions secret
`EVALUATION_SIGNING_PRIVATE_KEY_B64`; `trusted-signers.pem` is the sole trusted
public key. Editing any signed field invalidates the release gate.

For reuse releases, the signed declaration binds all eight required PASS stage
attestations, their private artifact hashes, source tag and commit, source
behavior/harness fingerprints, candidate tag, and candidate fingerprints. The
gate independently recomputes Git commits and fingerprints from the checkout.

For fresh minor/major releases, the declaration and its eight referenced
artifacts must be produced after the candidate commit exists. Every artifact is
bound to the exact candidate tag, full commit SHA, stage, verdict, engine,
model, timestamp, behavior fingerprint, and evaluation-harness fingerprint.
