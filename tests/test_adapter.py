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


if __name__ == "__main__":
    unittest.main()
