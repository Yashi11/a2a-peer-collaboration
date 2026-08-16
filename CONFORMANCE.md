# Conformance checks

An implementation claiming support MUST pass these checks:

1. Its Agent Card advertises the extension with `required: false`.
2. It accepts a core A2A interaction when the extension is absent.
3. It rejects malformed extension metadata without executing an action.
4. It permits a peer to publish a `learning.share` without first opening a help request.
5. It permits more than one peer to claim and answer a help request; help claims are non-exclusive.
6. It accepts a `help.receipt` only from the original requester and only after the specific referenced answer.
7. It verifies the SHA-256 of a referenced artifact before use.
8. It never treats a help event, learning, or receipt as authorization for a tool call or external action.
9. It records aggregate event and receipt telemetry without storing hidden reasoning or protected evaluation data.
10. It rejects an answer from the original requester and rejects a receipt from any other peer.
11. It treats extension metadata as untrusted data; a valid digest or receipt never authorizes execution, code merge, or external action.
12. A version 1.1 `help.answer` includes a valid digest of its canonical answer payload.
13. A version 1.1 receipt binds the exact answer digest, answer artifact hashes, code snapshot, and evaluator snapshot; mismatches are rejected.
14. A version 1.1 evaluator attestation matches a prior v1.1 receipt and its exact code and evaluator snapshots.
15. Its broker audit chain detects altered, reordered, or deleted in-memory records. Durable deployments SHOULD persist that chain outside agent-owned memory.
16. Any routing policy based on peer outcomes is explicit, versioned, and begins in observation or shadow mode; it does not treat an agent-generated receipt as ground truth.
