"""A minimal broker-side scenario for three equal coding-agent peers.

Run from the package root:
    python3 examples/three_peer_coding_team.py

This is not an agent runtime. A host runtime should expose a brokered tool that
passes each extension event through ``ledger.accept`` before delivering its A2A
metadata to the other peers.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from a2a_adapter import PeerCollaborationLedger, answer_digest


def event(kind: str, schema_version="1.0", **fields: str) -> dict[str, str]:
    return {"schemaVersion": schema_version, "kind": kind, **fields}


def main() -> None:
    # The host application would retain this ledger at its collaboration broker.
    ledger = PeerCollaborationLedger()

    # Each peer owns a different task. Agent-1 remains responsible for task-42.
    ledger.accept("agent-1", event(
        "help.request",
        helpId="help-rounding-1",
        parentTaskId="task-42",
        question="Can this currency percentage calculation round incorrectly?",
        requestedOutput="One counterexample or a safety argument.",
        expiresAt="2026-08-11T12:00:00Z",
    ), observed_at=100.0)

    # Peers decide for themselves whether they have capacity to contribute.
    ledger.accept("agent-2", event(
        "help.claim", helpId="help-rounding-1", parentTaskId="task-42"
    ), observed_at=101.0)
    ledger.accept("agent-3", event(
        "help.claim", helpId="help-rounding-1", parentTaskId="task-42"
    ), observed_at=102.0)

    # More than one peer can contribute an answer. Neither gets authority over task-42.
    answer = event(
        "help.answer",
        schema_version="1.1",
        helpId="help-rounding-1",
        parentTaskId="task-42",
        answerId="answer-counterexample-1",
        summary="0.005 can round unexpectedly; normalize to currency precision first.",
    )
    answer["answerDigest"] = answer_digest(answer)
    ledger.accept("agent-2", answer, observed_at=105.0)
    ledger.accept("agent-3", event(
        "help.answer",
        helpId="help-rounding-1",
        parentTaskId="task-42",
        answerId="answer-test-1",
        summary="Add tests for 0, 0.005, and fractional-cent inputs.",
    ), observed_at=106.0)

    # Only the owner records whether each answer was adopted.
    code_snapshot = {"revision": "abc123", "diffHash": "a" * 64}
    evaluator_snapshot = {
        "evaluatorId": "example-tests", "evaluatorVersion": "1.0",
        "configurationHash": "b" * 64, "datasetHash": "c" * 64,
    }
    ledger.accept("agent-1", event(
        "help.receipt",
        schema_version="1.1",
        helpId="help-rounding-1",
        parentTaskId="task-42",
        receiptId="receipt-rounding-1",
        answerId="answer-counterexample-1",
        answerDigest=answer["answerDigest"],
        artifactHashes=[],
        codeSnapshot=code_snapshot,
        evaluatorSnapshot=evaluator_snapshot,
        outcome="used",
        detail="Used the counterexample to change the rounding rule and add a test.",
    ), observed_at=110.0)
    ledger.accept("agent-1", event(
        "help.receipt",
        helpId="help-rounding-1",
        parentTaskId="task-42",
        answerId="answer-test-1",
        outcome="rejected",
        detail="The test cases were already covered by the selected fix.",
    ), observed_at=111.0)

    # Learnings can be shared without a request, for use on other tasks.
    ledger.accept("agent-2", event(
        "learning.share",
        learningId="learning-currency-precision-1",
        parentTaskId="task-19",
        scope="run",
        summary="Normalize monetary inputs before percentage calculations.",
    ), observed_at=112.0)

    # An evaluator, not a peer, independently records the result on the same snapshots.
    ledger.accept("trusted-evaluator", event(
        "evaluation.attestation",
        schema_version="1.1",
        helpId="help-rounding-1",
        parentTaskId="task-42",
        attestationId="attestation-rounding-1",
        receiptId="receipt-rounding-1",
        answerId="answer-counterexample-1",
        evaluatorOutcome="passed",
        codeSnapshot=code_snapshot,
        evaluatorSnapshot=evaluator_snapshot,
    ), observed_at=113.0)

    print("Aggregate telemetry:")
    for name, value in ledger.telemetry().items():
        print(f"  {name}: {value}")
    print(f"Audit chain valid: {ledger.verify_audit_log()}")


if __name__ == "__main__":
    main()
