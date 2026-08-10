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
