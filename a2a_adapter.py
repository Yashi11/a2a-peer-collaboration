"""Reference helpers for an A2A peer-collaboration extension.

All agents are peers.  A peer continues to own its primary task, may publish a
learning for others, and may claim or answer another peer's bounded help
request when it has capacity.  Claims are non-exclusive; multiple perspectives
are allowed. This module validates the auditable message lifecycle. It is not
an A2A transport or an authorization system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import time
from typing import Any

EXTENSION_URI = "urn:collab-mesh:a2a:peer-collaboration:1"
SCHEMA_VERSION = "1.0"
EVENT_KINDS = frozenset({"help.request", "help.claim", "help.answer", "help.receipt", "learning.share", "learning.ack"})
VISIBILITIES = frozenset({"task", "run", "private"})


class ExtensionValidationError(ValueError):
    """An event is malformed or violates the peer-collaboration lifecycle."""


def agent_card_extension(actions, skills=(), max_concurrent_helps=1, accepted_artifact_types=None):
    """Return the optional extension declaration for an A2A Agent Card.

    ``skills`` are discoverability hints only, never a hierarchy or a trust
    claim. Any peer can publish a learning or respond to help when available.
    """
    if not isinstance(max_concurrent_helps, int) or max_concurrent_helps < 0:
        raise ExtensionValidationError("max_concurrent_helps must be a non-negative integer")
    actions = list(actions)
    if not set(actions).issubset(EVENT_KINDS):
        raise ExtensionValidationError("unknown extension action")
    return {
        "uri": EXTENSION_URI,
        "description": "Auditable peer collaboration: shared learnings and non-exclusive bounded help",
        "required": False,
        "metadata": {EXTENSION_URI: {"capability": {
            "actions": actions, "skills": list(skills),
            "maxConcurrentHelps": max_concurrent_helps,
            "acceptedArtifactTypes": list(accepted_artifact_types or ["text/plain", "application/json"]),
        }}},
    }


def to_a2a_metadata(event: dict[str, Any]) -> dict[str, Any]:
    validate_event(event)
    return {EXTENSION_URI: event}


def from_a2a_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    event = metadata.get(EXTENSION_URI)
    if event is None:
        return None
    validate_event(event)
    return event


def validate_event(event: dict[str, Any]) -> None:
    if not isinstance(event, dict):
        raise ExtensionValidationError("event must be an object")
    _require(event, "schemaVersion", "kind")
    if event["schemaVersion"] != SCHEMA_VERSION:
        raise ExtensionValidationError("unsupported schemaVersion")
    kind = event["kind"]
    if kind not in EVENT_KINDS:
        raise ExtensionValidationError("unknown event kind")
    if kind.startswith("help."):
        _require_strings(event, "helpId", "parentTaskId")
        if kind == "help.request":
            _require_strings(event, "question", "requestedOutput", "expiresAt")
        elif kind == "help.answer":
            _require_strings(event, "answerId", "summary")
        elif kind == "help.receipt":
            _require_strings(event, "answerId", "detail")
            if event.get("outcome") not in {"used", "rejected"}:
                raise ExtensionValidationError("receipt outcome must be used or rejected")
    else:
        _require_strings(event, "learningId", "summary")
        if event.get("scope") not in {"task", "run"}:
            raise ExtensionValidationError("learning scope must be task or run")
        if kind == "learning.ack":
            _require_strings(event, "acknowledgement")
    if "evidence" in event:
        if not isinstance(event["evidence"], list):
            raise ExtensionValidationError("evidence must be a list")
        for reference in event["evidence"]:
            validate_artifact_reference(reference)


def _require(event: dict[str, Any], *fields: str) -> None:
    missing = set(fields) - event.keys()
    if missing:
        raise ExtensionValidationError(f"missing required fields: {sorted(missing)}")


def _require_strings(event: dict[str, Any], *fields: str) -> None:
    for field_name in fields:
        if not isinstance(event.get(field_name), str) or not event[field_name].strip():
            raise ExtensionValidationError(f"{field_name} must be a non-empty string")


def artifact_reference(path, artifact_id, visibility="task", media_type="text/plain"):
    if visibility not in VISIBILITIES:
        raise ExtensionValidationError("invalid visibility")
    if not artifact_id or not media_type:
        raise ExtensionValidationError("artifact_id and media_type are required")
    payload = Path(path).read_bytes()
    return {"artifactId": artifact_id, "mediaType": media_type,
            "sha256": hashlib.sha256(payload).hexdigest(), "visibility": visibility}


def validate_artifact_reference(reference: dict[str, Any]) -> None:
    if not isinstance(reference, dict):
        raise ExtensionValidationError("artifact reference must be an object")
    expected = {"artifactId", "mediaType", "sha256", "visibility"}
    if set(reference) != expected:
        raise ExtensionValidationError("artifact reference has missing or unknown fields")
    if not all(isinstance(reference[key], str) and reference[key] for key in expected):
        raise ExtensionValidationError("artifact reference fields must be non-empty strings")
    if len(reference["sha256"]) != 64 or any(ch not in "0123456789abcdef" for ch in reference["sha256"]):
        raise ExtensionValidationError("artifact sha256 must be lowercase hexadecimal")
    if reference["visibility"] not in VISIBILITIES:
        raise ExtensionValidationError("invalid artifact visibility")


def verify_artifact(path, reference: dict[str, Any]) -> bool:
    validate_artifact_reference(reference)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() == reference["sha256"]


@dataclass
class AnswerRecord:
    sender: str
    answered_at: float
    receipt_outcome: str | None = None


@dataclass
class HelpRecord:
    requester: str
    parent_task_id: str
    requested_at: float
    claims: set[str] = field(default_factory=set)
    answers: dict[str, AnswerRecord] = field(default_factory=dict)


@dataclass
class PeerCollaborationLedger:
    """In-memory lifecycle guard and aggregate trace collector for peers."""
    records: dict[str, HelpRecord] = field(default_factory=dict)
    learnings: dict[str, str] = field(default_factory=dict)
    trace: list[dict[str, str | float]] = field(default_factory=list)

    def accept(self, sender_agent_id: str, event: dict[str, Any], observed_at: float | None = None) -> dict[str, Any]:
        validate_event(event)
        observed_at = time.time() if observed_at is None else observed_at
        kind = event["kind"]
        if kind.startswith("help."):
            self._accept_help(sender_agent_id, event, observed_at)
            identity, parent = event["helpId"], event["parentTaskId"]
        else:
            self._accept_learning(sender_agent_id, event)
            identity, parent = event["learningId"], event.get("parentTaskId", "")
        self.trace.append({"kind": kind, "eventId": identity, "parentTaskId": parent,
                           "senderAgentId": sender_agent_id, "observedAt": observed_at})
        return to_a2a_metadata(event)

    def _accept_help(self, sender: str, event: dict[str, Any], observed_at: float) -> None:
        help_id, kind = event["helpId"], event["kind"]
        record = self.records.get(help_id)
        if kind == "help.request":
            if record:
                raise ExtensionValidationError("helpId already exists")
            self.records[help_id] = HelpRecord(sender, event["parentTaskId"], observed_at)
            return
        if not record:
            raise ExtensionValidationError("help event has no prior request")
        if record.parent_task_id != event["parentTaskId"]:
            raise ExtensionValidationError("parentTaskId does not match request")
        if kind == "help.claim":
            if sender == record.requester:
                raise ExtensionValidationError("requester cannot claim its own request")
            record.claims.add(sender)  # Non-exclusive; peers may independently offer a view.
        elif kind == "help.answer":
            if sender == record.requester:
                raise ExtensionValidationError("requester cannot answer its own request")
            answer_id = event["answerId"]
            if answer_id in record.answers:
                raise ExtensionValidationError("answerId already exists for this request")
            record.answers[answer_id] = AnswerRecord(sender, observed_at)
        elif kind == "help.receipt":
            if sender != record.requester:
                raise ExtensionValidationError("only requester may issue a receipt")
            answer = record.answers.get(event["answerId"])
            if not answer or answer.receipt_outcome is not None:
                raise ExtensionValidationError("receipt must refer once to an existing answer")
            answer.receipt_outcome = event["outcome"]

    def _accept_learning(self, sender: str, event: dict[str, Any]) -> None:
        learning_id, kind = event["learningId"], event["kind"]
        if kind == "learning.share":
            if learning_id in self.learnings:
                raise ExtensionValidationError("learningId already exists")
            self.learnings[learning_id] = sender
        elif learning_id not in self.learnings:
            raise ExtensionValidationError("learning acknowledgement has no shared learning")

    def telemetry(self) -> dict[str, int | float]:
        answers = [answer for record in self.records.values() for answer in record.answers.values()]
        latencies = [answer.answered_at - record.requested_at for record in self.records.values()
                     for answer in record.answers.values()]
        return {
            "helpRequests": len(self.records),
            "helpClaims": sum(len(record.claims) for record in self.records.values()),
            "answers": len(answers),
            "receipts": sum(answer.receipt_outcome is not None for answer in answers),
            "usedReceipts": sum(answer.receipt_outcome == "used" for answer in answers),
            "rejectedReceipts": sum(answer.receipt_outcome == "rejected" for answer in answers),
            "sharedLearnings": len(self.learnings),
            "meanResponseLatencySeconds": sum(latencies) / len(latencies) if latencies else 0.0,
            "traceEvents": len(self.trace),
        }
