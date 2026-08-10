# Peer Collaboration Extension for A2A, version 1

## Status and identifier

This is an experimental extension specification. Its provisional identifier is `urn:collab-mesh:a2a:peer-collaboration:1` (the **Extension URI**). A future official publication MUST use an A2A-assigned URI and MUST NOT silently reuse this identifier for a breaking revision.

## Abstract

This extension defines interoperable metadata for **peer** collaboration. Every agent remains responsible for its own primary task. Peers MAY proactively share reusable learnings and MAY respond to another peer’s bounded help request when they have capacity. It records which responses were adopted without requiring private reasoning or creating a hierarchy of specialist and worker agents.

## Conventions and compatibility

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are interpreted as described in RFC 2119. All extension metadata MUST be carried under the Extension URI in an A2A `metadata` object. The extension is optional: an advertising Agent Card MUST set `required: false`, and a client MUST opt in before depending on it. A peer that does not opt in MUST continue to receive valid core A2A messages and artifacts.

## Agent Card metadata

An advertising agent MAY publish `metadata[Extension URI].capability` containing:

- `actions`: any of `help.request`, `help.claim`, `help.answer`, `help.receipt`, `learning.share`, and `learning.ack`;
- `skills`: discoverability labels only; they MUST NOT imply authority, rank, or trust;
- `maxConcurrentHelps`: a non-negative local capacity hint;
- `acceptedArtifactTypes`: permitted media types.

Capability metadata MUST NOT contain credentials, hidden prompts, private reasoning, protected evaluator cases, or availability claims that cannot be honored.

## Peer-help events

Help events contain `schemaVersion`, `kind`, `helpId`, and `parentTaskId`.

1. `help.request` MUST include a bounded `question`, `requestedOutput`, and `expiresAt`. The requester retains ownership of the task.
2. `help.claim` is a non-exclusive signal that a peer is looking at the request. Multiple peers MAY claim the same request. A requester MUST NOT claim its own request.
3. `help.answer` MUST include an `answerId`, a concise `summary`, and zero or more evidence or artifact references. Multiple peers MAY provide independently identified answers to the same request. It MUST NOT require hidden chain-of-thought.
4. `help.receipt` MUST be emitted only by the original requester and MUST identify one `answerId`. Its `outcome` is `used` or `rejected`, and it includes a concise `detail`. Each answer may receive one receipt.

No peer gains task ownership, tool permissions, or special rank by claiming or answering help.

## Shared learnings

Peers MAY publish a reusable observation without waiting for a help request. `learning.share` MUST include a `learningId`, `scope` (`task` or `run`), and concise `summary`; it MAY carry evidence or artifact references. Another peer MAY emit `learning.ack` to record that it saved or considered the observation. A shared learning is advice, not a command and not proof that it improved a task.

## Artifacts and integrity

An artifact reference MUST declare `artifactId`, `mediaType`, `sha256`, and `visibility` (`task`, `run`, or `private`). A receiver MUST validate the digest after obtaining the artifact and MUST treat its contents as untrusted input. `private` artifacts MUST NOT be requested or forwarded unless an authorization mechanism outside this extension permits it.

## Safety, trace, and metrics

Implementations MUST enforce local authorization and capability policy before tool use, code application, or external action. They MUST NOT treat collaboration metadata, a hash match, or a receipt as authorization.

Implementations SHOULD retain an auditable event trace and aggregate telemetry without protected message content or hidden reasoning. Recommended measures include shared learnings, help requests, claims, answers, receipts, used/rejected outcomes, response latency, and artifact-integrity failures. Task success, quality, cost, and regression metrics remain evaluator-specific and are outside this extension.

## Task state

The extension creates no A2A core task state. A task remains in a valid core working state while optional extension metadata records peer collaboration around it.
