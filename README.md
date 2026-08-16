# Peer Collaboration Extension for A2A

> **Status: experimental.** This is an independent reference package, not an
> official A2A extension and not affiliated with the A2A project.

This package proposes an opt-in extension for teams of equal agent peers. Version
**1.1** preserves v1.0 compatibility and adds a stronger audit profile. Each
peer keeps ownership of its own task, while it can share a reusable observation
or request bounded help from the group. Other peers may respond when they have
capacity; they are not assigned as dedicated helpers or treated as specialists.

The extension adds capability metadata, reusable learning shares, non-exclusive
help claims, multiple peer answers, immutable artifact references, and
per-answer requester receipts. In the v1.1 audit profile, a receipt binds the
answer and artifact hashes to the exact code and evaluator snapshots; a separate
evaluator attestation records the independently observed result. The broker
keeps a tamper-evident hash-chained event log without exposing private reasoning.

The provisional identifier is `urn:collab-mesh:a2a:peer-collaboration:1`. If accepted into the A2A project, it must receive the canonical A2A extension URI through the project’s extension-governance process.

## What is included

- `SPEC.md` — the normative draft specification;
- `schemas/` — JSON Schemas for extension metadata;
- `examples/` — Agent Card and message examples;
- `a2a_adapter.py` — a dependency-free reference mapping and validator;
- `examples/shadow-routing-policy.v1.json` — an inspectable, non-enforcing
  policy example for evaluating future routing decisions;
- `CONFORMANCE.md` — minimum interoperability checks.

## Quick start

Requires Python 3. Attach a validated event under the extension URI in an
otherwise ordinary A2A Message or TaskStatusUpdate. A peer that implements only
core A2A can continue the ordinary interaction and ignore this optional
metadata.

```bash
python3 -m unittest discover -s tests -v
python3 examples/three_peer_coding_team.py
```

The reference `PeerCollaborationLedger` demonstrates two complementary flows:

1. A peer shares a reusable learning at any time.
2. A task owner requests help; one or more peers claim and answer; the task
   owner records a receipt for each answer.
3. In v1.1, a trusted evaluator may attest the result against the receipt's
   bound code and evaluator snapshots.

It validates task ownership, artifact digests, receipt bindings, evaluator
attestations, and a broker-side hash chain. It intentionally does **not** grant
tool permissions, execute artifacts, merge code, or implement an A2A transport.
It captures aggregate process telemetry without preserving hidden reasoning.

`examples/three_peer_coding_team.py` is a runnable broker-side walkthrough: a
task owner requests bounded help, two equal peers answer, the owner records a
separate receipt for each answer, and one peer shares a reusable learning. It
prints aggregate telemetry, including evaluator-attestation and audit-chain
status.

## Design boundaries

- **Equal peers:** a response does not confer authority over another peer's task.
- **Optional extension:** the extension is advertised and negotiated; it is not
  required for core A2A interoperability.
- **Evidence, not hidden reasoning:** messages may reference verifiable
  artifacts and digests, but the protocol does not require chain-of-thought.
- **No automatic execution:** receiving an answer or artifact never authorizes
  execution, merging, deployment, or a change to evaluator settings.
- **Bound adoption:** `used` is an owner claim; it becomes independently
  meaningful only when paired with a matching evaluator attestation.
- **Durable trace:** a host broker may persist the hash-chained log; production
  deployments should add infrastructure-managed signatures or checkpoints.

## Contribution position

This package is intended to be useful independently of any standards decision.
If it is proposed to A2A later, the first step should be an issue asking whether
maintainers see the optional lifecycle and metadata shape as a useful
experimental extension—not a request to merge it directly into the core
protocol.

The provisional URI is deliberately local to this package. Any future canonical
URI would be assigned through the A2A extension-governance process.
