import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).parents[1] / "a2a_adapter.py"
SPEC = importlib.util.spec_from_file_location("peer_collaboration", MODULE)
adapter = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = adapter
SPEC.loader.exec_module(adapter)


def help_event(kind, **values):
    payload = {"schemaVersion": "1.0", "kind": kind, "helpId": "help-7", "parentTaskId": "task-4"}
    payload.update(values)
    return payload


def v11_answer(answer_id="answer-b"):
    payload = help_event("help.answer", schemaVersion="1.1", answerId=answer_id, summary="Normalize first")
    payload["answerDigest"] = adapter.answer_digest(payload)
    return payload


def snapshots():
    return (
        {"revision": "abc123", "diffHash": "a" * 64},
        {"evaluatorId": "evalplus", "evaluatorVersion": "0.3", "configurationHash": "b" * 64, "datasetHash": "c" * 64},
    )


class AdapterTests(unittest.TestCase):
    def test_multiple_peer_answers_and_per_answer_receipts(self):
        ledger = adapter.PeerCollaborationLedger()
        ledger.accept("agent-a", help_event("help.request", question="Check boundary", requestedOutput="Counterexample", expiresAt="2026-08-10T00:00:00Z"), observed_at=10)
        ledger.accept("agent-b", help_event("help.claim"), observed_at=11)
        ledger.accept("agent-c", help_event("help.claim"), observed_at=12)
        ledger.accept("agent-b", help_event("help.answer", answerId="answer-b", summary="Round first"), observed_at=16)
        metadata = ledger.accept("agent-c", help_event("help.answer", answerId="answer-c", summary="Add the fractional test"), observed_at=18)
        self.assertEqual(adapter.from_a2a_metadata(metadata)["kind"], "help.answer")
        ledger.accept("agent-a", help_event("help.receipt", answerId="answer-b", outcome="used", detail="Applied rounding guard"), observed_at=20)
        ledger.accept("agent-a", help_event("help.receipt", answerId="answer-c", outcome="rejected", detail="Already covered"), observed_at=21)
        report = ledger.telemetry()
        self.assertEqual(report["answers"], 2)
        self.assertEqual(report["usedReceipts"], 1)
        self.assertEqual(report["rejectedReceipts"], 1)
        self.assertEqual(report["meanResponseLatencySeconds"], 7.0)

    def test_any_peer_can_share_learning_without_a_help_request(self):
        ledger = adapter.PeerCollaborationLedger()
        event = {"schemaVersion": "1.0", "kind": "learning.share", "learningId": "learning-2", "scope": "run", "summary": "Normalize currency before percentage calculations"}
        ledger.accept("agent-c", event, observed_at=10)
        ledger.accept("agent-a", {**event, "kind": "learning.ack", "acknowledgement": "Saved for my task"}, observed_at=11)
        self.assertEqual(ledger.telemetry()["sharedLearnings"], 1)

    def test_requester_cannot_answer_and_only_requester_can_receipt(self):
        ledger = adapter.PeerCollaborationLedger()
        ledger.accept("agent-a", help_event("help.request", question="Q", requestedOutput="A", expiresAt="2026-08-10T00:00:00Z"))
        with self.assertRaises(adapter.ExtensionValidationError):
            ledger.accept("agent-a", help_event("help.answer", answerId="bad", summary="answer"))
        ledger.accept("agent-b", help_event("help.answer", answerId="answer-b", summary="answer"))
        with self.assertRaises(adapter.ExtensionValidationError):
            ledger.accept("agent-c", help_event("help.receipt", answerId="answer-b", outcome="used", detail="no"))

    def test_artifact_digest_verification_and_core_only_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.txt"
            path.write_text("evidence")
            reference = adapter.artifact_reference(path, "artifact-1")
            self.assertTrue(adapter.verify_artifact(path, reference))
        self.assertIsNone(adapter.from_a2a_metadata({"some.core.field": "value"}))

    def test_v11_receipt_binds_answer_artifacts_code_and_evaluator_then_attests(self):
        ledger = adapter.PeerCollaborationLedger()
        ledger.accept("agent-a", help_event("help.request", question="Q", requestedOutput="A", expiresAt="2026-08-10T00:00:00Z"), observed_at=10)
        answer = v11_answer()
        ledger.accept("agent-b", answer, observed_at=11)
        code_snapshot, evaluator_snapshot = snapshots()
        receipt = help_event(
            "help.receipt", schemaVersion="1.1", receiptId="receipt-1", answerId="answer-b",
            answerDigest=answer["answerDigest"], artifactHashes=[], codeSnapshot=code_snapshot,
            evaluatorSnapshot=evaluator_snapshot, outcome="used", detail="Applied it",
        )
        ledger.accept("agent-a", receipt, observed_at=12)
        attestation = help_event(
            "evaluation.attestation", schemaVersion="1.1", attestationId="attest-1", receiptId="receipt-1",
            answerId="answer-b", evaluatorOutcome="passed", codeSnapshot=code_snapshot,
            evaluatorSnapshot=evaluator_snapshot,
        )
        ledger.accept("trusted-evaluator", attestation, observed_at=13)
        self.assertTrue(ledger.verify_audit_log())
        self.assertEqual(ledger.telemetry()["passedAttestations"], 1)

    def test_v11_rejects_unbound_receipt_and_changed_evaluator_snapshot(self):
        ledger = adapter.PeerCollaborationLedger()
        ledger.accept("agent-a", help_event("help.request", question="Q", requestedOutput="A", expiresAt="2026-08-10T00:00:00Z"))
        answer = v11_answer()
        ledger.accept("agent-b", answer)
        code_snapshot, evaluator_snapshot = snapshots()
        with self.assertRaises(adapter.ExtensionValidationError):
            ledger.accept("agent-a", help_event(
                "help.receipt", schemaVersion="1.1", receiptId="receipt-1", answerId="answer-b",
                answerDigest="0" * 64, artifactHashes=[], codeSnapshot=code_snapshot,
                evaluatorSnapshot=evaluator_snapshot, outcome="used", detail="Applied it",
            ))

    def test_hash_chain_is_durable_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "broker-audit.ndjson"
            ledger = adapter.PeerCollaborationLedger(audit_log_path=log_path)
            ledger.accept("agent-a", help_event("help.request", question="Q", requestedOutput="A", expiresAt="2026-08-10T00:00:00Z"), observed_at=10)
            ledger.accept("agent-b", help_event("help.claim"), observed_at=11)
            self.assertEqual(len(log_path.read_text().splitlines()), 2)
            self.assertTrue(ledger.verify_audit_log())
            ledger.audit_log[1].event["helpId"] = "tampered"
            self.assertFalse(ledger.verify_audit_log())

    def test_shadow_routing_policy_is_explicit_and_never_changes_routing(self):
        ledger = adapter.PeerCollaborationLedger()
        ledger.accept("agent-a", help_event("help.request", question="Q", requestedOutput="A", expiresAt="2026-08-10T00:00:00Z"))
        answer = v11_answer()
        ledger.accept("agent-b", answer)
        code_snapshot, evaluator_snapshot = snapshots()
        ledger.accept("agent-a", help_event(
            "help.receipt", schemaVersion="1.1", receiptId="receipt-1", answerId="answer-b",
            answerDigest=answer["answerDigest"], artifactHashes=[], codeSnapshot=code_snapshot,
            evaluatorSnapshot=evaluator_snapshot, outcome="used", detail="Applied it",
        ))
        ledger.accept("trusted-evaluator", help_event(
            "evaluation.attestation", schemaVersion="1.1", attestationId="attest-1", receiptId="receipt-1",
            answerId="answer-b", evaluatorOutcome="failed", codeSnapshot=code_snapshot,
            evaluatorSnapshot=evaluator_snapshot,
        ))
        policy = {
            "policyVersion": "shadow-routing.v1", "mode": "shadow", "minimumAttestations": 1,
            "minimumAdoptionRate": 0.5, "minimumEvaluationPassRate": 0.8, "reducedRoutingWeight": 0.5,
        }
        [recommendation] = ledger.routing_recommendations(policy)
        self.assertEqual(recommendation["action"], "would_reduce_routing_weight")
        self.assertEqual(recommendation["mode"], "shadow")
        self.assertEqual(recommendation["recommendedRoutingWeight"], 0.5)


if __name__ == "__main__":
    unittest.main()
