"""Reference helpers for the A2A peer-collaboration extension.

Version 1.1 adds an opt-in audit path.  A receipt can bind an adopted answer to
its exact digest, artifacts, code snapshot, and evaluator snapshot.  A later
evaluator attestation records the independently observed result.  The broker
records accepted events in a hash chain so a changed or removed record is
detectable.  This module is not an A2A transport or authorization system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import time
from typing import Any

EXTENSION_URI = "urn:collab-mesh:a2a:peer-collaboration:1"
SCHEMA_VERSION = "1.1"
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0", "1.1"})
EVENT_KINDS = frozenset({
    "help.request", "help.claim", "help.answer", "help.receipt",
    "learning.share", "learning.ack", "evaluation.attestation",
})
VISIBILITIES = frozenset({"task", "run", "private"})
_SHA256_LENGTH = 64


class ExtensionValidationError(ValueError):
    """An event is malformed or violates the peer-collaboration lifecycle."""


def agent_card_extension(actions, skills=(), max_concurrent_helps=1, accepted_artifact_types=None):
    """Return the optional extension declaration for an A2A Agent Card."""
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
            "actions": actions,
            "skills": list(skills),
            "maxConcurrentHelps": max_concurrent_helps,
            "acceptedArtifactTypes": list(accepted_artifact_types or ["text/plain", "application/json"]),
            "supportedSchemaVersions": sorted(SUPPORTED_SCHEMA_VERSIONS),
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


def canonical_json(value: Any) -> str:
    """Stable JSON serialization used for hashes in this reference package."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def answer_digest(event: dict[str, Any]) -> str:
    """Digest the answer payload, excluding its self-referential digest field."""
    if event.get("kind") != "help.answer":
        raise ExtensionValidationError("answer_digest requires a help.answer event")
    return sha256_json({key: value for key, value in event.items() if key != "answerDigest"})


def validate_event(event: dict[str, Any]) -> None:
    if not isinstance(event, dict):
        raise ExtensionValidationError("event must be an object")
    _require(event, "schemaVersion", "kind")
    version, kind = event["schemaVersion"], event["kind"]
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ExtensionValidationError("unsupported schemaVersion")
    if kind not in EVENT_KINDS:
        raise ExtensionValidationError("unknown event kind")
    if kind.startswith("help.") or kind == "evaluation.attestation":
        _require_strings(event, "helpId", "parentTaskId")
        if kind == "help.request":
            _require_strings(event, "question", "requestedOutput", "expiresAt")
        elif kind == "help.answer":
            _require_strings(event, "answerId", "summary")
            if version == "1.1":
                _require_strings(event, "answerDigest")
                if event["answerDigest"] != answer_digest(event):
                    raise ExtensionValidationError("answerDigest does not match answer payload")
        elif kind == "help.receipt":
            _require_strings(event, "answerId", "detail")
            if event.get("outcome") not in {"used", "rejected"}:
                raise ExtensionValidationError("receipt outcome must be used or rejected")
            if version == "1.1":
                _require_strings(event, "receiptId", "answerDigest")
                _validate_snapshot(event.get("codeSnapshot"), "codeSnapshot", {"revision", "diffHash"})
                _validate_snapshot(event.get("evaluatorSnapshot"), "evaluatorSnapshot", {
                    "evaluatorId", "evaluatorVersion", "configurationHash", "datasetHash",
                })
                _validate_hashes(event.get("artifactHashes"), "artifactHashes")
        elif kind == "evaluation.attestation":
            _require_strings(event, "attestationId", "receiptId", "answerId")
            if event.get("evaluatorOutcome") not in {"passed", "failed", "inconclusive"}:
                raise ExtensionValidationError("invalid evaluatorOutcome")
            _validate_snapshot(event.get("codeSnapshot"), "codeSnapshot", {"revision", "diffHash"})
            _validate_snapshot(event.get("evaluatorSnapshot"), "evaluatorSnapshot", {
                "evaluatorId", "evaluatorVersion", "configurationHash", "datasetHash",
            })
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


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == _SHA256_LENGTH and all(
        char in "0123456789abcdef" for char in value
    )


def _validate_hashes(value: Any, field_name: str) -> None:
    if not isinstance(value, list) or not all(_is_sha256(item) for item in value):
        raise ExtensionValidationError(f"{field_name} must be a list of SHA-256 hashes")
    if value != sorted(set(value)):
        raise ExtensionValidationError(f"{field_name} must be sorted and unique")


def _validate_snapshot(value: Any, field_name: str, required: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != required:
        raise ExtensionValidationError(f"{field_name} has missing or unknown fields")
    for name, item in value.items():
        if name.endswith("Hash"):
            if not _is_sha256(item):
                raise ExtensionValidationError(f"{field_name}.{name} must be a SHA-256 hash")
        elif not isinstance(item, str) or not item:
            raise ExtensionValidationError(f"{field_name}.{name} must be a non-empty string")


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
    if not _is_sha256(reference["sha256"]):
        raise ExtensionValidationError("artifact sha256 must be lowercase hexadecimal")
    if reference["visibility"] not in VISIBILITIES:
        raise ExtensionValidationError("invalid artifact visibility")


def verify_artifact(path, reference: dict[str, Any]) -> bool:
    validate_artifact_reference(reference)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() == reference["sha256"]


@dataclass
class ReceiptRecord:
    receipt_id: str | None
    outcome: str
    answer_digest: str | None = None
    artifact_hashes: tuple[str, ...] = ()
    code_snapshot: dict[str, str] | None = None
    evaluator_snapshot: dict[str, str] | None = None


@dataclass
class AnswerRecord:
    sender: str
    answered_at: float
    answer_digest: str | None = None
    artifact_hashes: tuple[str, ...] = ()
    receipt: ReceiptRecord | None = None
    evaluator_outcome: str | None = None


@dataclass
class HelpRecord:
    requester: str
    parent_task_id: str
    requested_at: float
    claims: set[str] = field(default_factory=set)
    answers: dict[str, AnswerRecord] = field(default_factory=dict)


@dataclass
class AuditRecord:
    sequence: int
    previous_hash: str
    event_hash: str
    broker_timestamp: float
    sender_agent_id: str
    event: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "previousHash": self.previous_hash,
            "brokerTimestamp": self.broker_timestamp,
            "senderAgentId": self.sender_agent_id,
            "event": self.event,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "eventHash": self.event_hash}


@dataclass
class PeerCollaborationLedger:
    """Lifecycle guard, append-only hash-chain collector, and telemetry source.

    ``audit_log_path`` is optional durable NDJSON storage owned by the broker.
    A hash chain detects altered or deleted records; deployments that require
    non-repudiation should additionally sign checkpoints outside this module.
    """
    audit_log_path: Path | None = None
    records: dict[str, HelpRecord] = field(default_factory=dict)
    learnings: dict[str, str] = field(default_factory=dict)
    attestations: dict[str, dict[str, Any]] = field(default_factory=dict)
    trace: list[dict[str, str | float]] = field(default_factory=list)
    audit_log: list[AuditRecord] = field(default_factory=list)

    def accept(self, sender_agent_id: str, event: dict[str, Any], observed_at: float | None = None) -> dict[str, Any]:
        validate_event(event)
        observed_at = time.time() if observed_at is None else observed_at
        kind = event["kind"]
        if kind.startswith("help.") or kind == "evaluation.attestation":
            self._accept_help(sender_agent_id, event, observed_at)
            identity, parent = self._identity(event), event["parentTaskId"]
        else:
            self._accept_learning(sender_agent_id, event)
            identity, parent = event["learningId"], event.get("parentTaskId", "")
        self.trace.append({"kind": kind, "eventId": identity, "parentTaskId": parent,
                           "senderAgentId": sender_agent_id, "observedAt": observed_at})
        self._append_audit_record(sender_agent_id, event, observed_at)
        return to_a2a_metadata(event)

    @staticmethod
    def _identity(event: dict[str, Any]) -> str:
        return event.get("attestationId") or event.get("receiptId") or event.get("answerId") or event["helpId"]

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
            record.claims.add(sender)
        elif kind == "help.answer":
            if sender == record.requester:
                raise ExtensionValidationError("requester cannot answer its own request")
            answer_id = event["answerId"]
            if answer_id in record.answers:
                raise ExtensionValidationError("answerId already exists for this request")
            evidence_hashes = tuple(sorted(reference["sha256"] for reference in event.get("evidence", [])))
            record.answers[answer_id] = AnswerRecord(sender, observed_at, event.get("answerDigest"), evidence_hashes)
        elif kind == "help.receipt":
            if sender != record.requester:
                raise ExtensionValidationError("only requester may issue a receipt")
            answer = record.answers.get(event["answerId"])
            if not answer or answer.receipt is not None:
                raise ExtensionValidationError("receipt must refer once to an existing answer")
            if event["schemaVersion"] == "1.1":
                if answer.answer_digest != event["answerDigest"]:
                    raise ExtensionValidationError("receipt answerDigest does not match answer")
                if answer.artifact_hashes != tuple(event["artifactHashes"]):
                    raise ExtensionValidationError("receipt artifactHashes do not match answer evidence")
                if any(attestation.get("receiptId") == event["receiptId"] for attestation in self.attestations.values()):
                    raise ExtensionValidationError("receiptId already exists")
            answer.receipt = ReceiptRecord(
                event.get("receiptId"), event["outcome"], event.get("answerDigest"),
                tuple(event.get("artifactHashes", [])), event.get("codeSnapshot"), event.get("evaluatorSnapshot"),
            )
        elif kind == "evaluation.attestation":
            if event["attestationId"] in self.attestations:
                raise ExtensionValidationError("attestationId already exists")
            answer = record.answers.get(event["answerId"])
            if not answer or not answer.receipt or not answer.receipt.receipt_id:
                raise ExtensionValidationError("attestation requires a version 1.1 receipt")
            receipt = answer.receipt
            if receipt.receipt_id != event["receiptId"]:
                raise ExtensionValidationError("attestation receiptId does not match receipt")
            if receipt.code_snapshot != event["codeSnapshot"] or receipt.evaluator_snapshot != event["evaluatorSnapshot"]:
                raise ExtensionValidationError("attestation snapshots do not match receipt")
            if any(attestation.get("receiptId") == event["receiptId"] for attestation in self.attestations.values()):
                raise ExtensionValidationError("receipt already has an evaluator attestation")
            answer.evaluator_outcome = event["evaluatorOutcome"]
            self.attestations[event["attestationId"]] = {
                "receiptId": event["receiptId"], "answerId": event["answerId"],
                "outcome": event["evaluatorOutcome"], "sender": sender,
            }

    def _accept_learning(self, sender: str, event: dict[str, Any]) -> None:
        learning_id, kind = event["learningId"], event["kind"]
        if kind == "learning.share":
            if learning_id in self.learnings:
                raise ExtensionValidationError("learningId already exists")
            self.learnings[learning_id] = sender
        elif learning_id not in self.learnings:
            raise ExtensionValidationError("learning acknowledgement has no shared learning")

    def _append_audit_record(self, sender: str, event: dict[str, Any], observed_at: float) -> None:
        previous_hash = self.audit_log[-1].event_hash if self.audit_log else "0" * _SHA256_LENGTH
        record = AuditRecord(len(self.audit_log) + 1, previous_hash, "", observed_at, sender, dict(event))
        record.event_hash = sha256_json(record.payload())
        self.audit_log.append(record)
        if self.audit_log_path:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_log_path.open("a", encoding="utf-8") as stream:
                stream.write(canonical_json(record.to_dict()) + "\n")

    def verify_audit_log(self) -> bool:
        previous_hash = "0" * _SHA256_LENGTH
        for sequence, record in enumerate(self.audit_log, start=1):
            if record.sequence != sequence or record.previous_hash != previous_hash:
                return False
            if record.event_hash != sha256_json(record.payload()):
                return False
            previous_hash = record.event_hash
        return True

    def telemetry(self) -> dict[str, int | float]:
        answers = [answer for record in self.records.values() for answer in record.answers.values()]
        latencies = [answer.answered_at - record.requested_at for record in self.records.values()
                     for answer in record.answers.values()]
        receipts = [answer.receipt for answer in answers if answer.receipt]
        return {
            "helpRequests": len(self.records),
            "helpClaims": sum(len(record.claims) for record in self.records.values()),
            "answers": len(answers),
            "receipts": len(receipts),
            "usedReceipts": sum(receipt.outcome == "used" for receipt in receipts),
            "rejectedReceipts": sum(receipt.outcome == "rejected" for receipt in receipts),
            "evaluatorAttestations": len(self.attestations),
            "passedAttestations": sum(item["outcome"] == "passed" for item in self.attestations.values()),
            "failedAttestations": sum(item["outcome"] == "failed" for item in self.attestations.values()),
            "sharedLearnings": len(self.learnings),
            "meanResponseLatencySeconds": sum(latencies) / len(latencies) if latencies else 0.0,
            "traceEvents": len(self.trace),
            "auditChainValid": self.verify_audit_log(),
        }

    def peer_outcomes(self) -> dict[str, dict[str, int | float]]:
        """Aggregate answer outcomes by peer for an external routing policy.

        Receipt outcomes remain agent-provided evidence.  Evaluation pass/fail
        values are only counted when a bound evaluator attestation exists.
        """
        outcomes: dict[str, dict[str, int | float]] = {}
        for record in self.records.values():
            for answer in record.answers.values():
                report = outcomes.setdefault(answer.sender, {
                    "answers": 0, "usedReceipts": 0, "rejectedReceipts": 0,
                    "attestations": 0, "passedAttestations": 0, "failedAttestations": 0,
                })
                report["answers"] += 1
                if answer.receipt:
                    if answer.receipt.outcome == "used":
                        report["usedReceipts"] += 1
                    else:
                        report["rejectedReceipts"] += 1
                if answer.evaluator_outcome:
                    report["attestations"] += 1
                    if answer.evaluator_outcome == "passed":
                        report["passedAttestations"] += 1
                    elif answer.evaluator_outcome == "failed":
                        report["failedAttestations"] += 1
        for report in outcomes.values():
            receipts = report["usedReceipts"] + report["rejectedReceipts"]
            attestations = report["attestations"]
            report["adoptionRate"] = report["usedReceipts"] / receipts if receipts else 0.0
            report["evaluationPassRate"] = report["passedAttestations"] / attestations if attestations else 0.0
        return outcomes

    def routing_recommendations(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        """Evaluate a transparent *shadow-mode* policy without changing routing.

        The host runtime may later consume these recommendations.  This method
        deliberately never grants, denies, or reroutes access itself.
        """
        required = {"policyVersion", "mode", "minimumAttestations", "minimumAdoptionRate", "minimumEvaluationPassRate", "reducedRoutingWeight"}
        if set(policy) != required or policy["mode"] != "shadow":
            raise ExtensionValidationError("invalid shadow routing policy")
        for key in ("minimumAttestations",):
            if not isinstance(policy[key], int) or policy[key] < 1:
                raise ExtensionValidationError(f"{key} must be a positive integer")
        for key in ("minimumAdoptionRate", "minimumEvaluationPassRate", "reducedRoutingWeight"):
            if not isinstance(policy[key], (int, float)) or not 0 <= policy[key] <= 1:
                raise ExtensionValidationError(f"{key} must be between zero and one")
        recommendations = []
        for peer, metrics in sorted(self.peer_outcomes().items()):
            if metrics["attestations"] < policy["minimumAttestations"]:
                action, reason = "observe_only", "insufficient evaluator attestations"
            elif metrics["adoptionRate"] < policy["minimumAdoptionRate"] or metrics["evaluationPassRate"] < policy["minimumEvaluationPassRate"]:
                action, reason = "would_reduce_routing_weight", "adoption or evaluator pass rate below policy threshold"
            else:
                action, reason = "keep_routing_weight", "peer meets policy thresholds"
            recommendations.append({
                "peer": peer, "policyVersion": policy["policyVersion"], "policyHash": sha256_json(policy),
                "mode": "shadow", "metrics": metrics, "action": action, "reason": reason,
                "recommendedRoutingWeight": policy["reducedRoutingWeight"] if action == "would_reduce_routing_weight" else 1.0,
            })
        return recommendations
