# Changelog

## v1.1.0 — 2026-08-17

### Added

- Backward-compatible `schemaVersion: "1.1"` audit profile; version 1.0 events
  remain supported.
- Bound receipts: answer digest, answer artifact hashes, code snapshot, and
  evaluator snapshot.
- `evaluation.attestation` events, which record an evaluator result only when
  the receipt and its snapshots match exactly.
- Broker-side append-only, hash-chained audit records and verification.
- Peer outcome aggregates and an explicit, versioned **shadow-mode** routing
  recommendation API. It reports what a policy would do but never reroutes an
  agent itself.
- Runnable v1.1 example, sample receipt, and sample routing-policy file.

### Important boundaries

- A `used` receipt remains requester-provided evidence, not proof of quality.
- The reference hash chain detects tampering; deployments that require
  non-repudiation should sign broker checkpoints using infrastructure-managed
  keys.
- Tool permissions, code application, evaluator protection, and any live
  routing decision remain responsibilities of the host runtime.
