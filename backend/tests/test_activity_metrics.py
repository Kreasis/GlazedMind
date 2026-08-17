import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import activity


class ActivityMetricsTests(unittest.TestCase):
    def test_metrics_count_only_real_acknowledgments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ack = root / "ack.json"
            followup = root / "followup.json"
            log = root / "activity.json"
            knowledge = root / "knowledge"
            knowledge.mkdir()
            (knowledge / "guide.docx").write_bytes(b"docx")
            ack.write_text(json.dumps({"tickets": {
                "baseline": {"acknowledgment_posted": True, "status_updated": True},
                "live": {"message": "ack", "update_id": "1", "status_updated": True},
            }}), encoding="utf-8")
            followup.write_text(json.dumps({"tickets": {
                "live": {"followup_count": 3, "resolved": True},
            }}), encoding="utf-8")
            with patch.object(activity, "_ack_path", ack), patch.object(activity, "_followup_path", followup), patch.object(activity, "_activity_path", log), patch.object(activity, "_knowledge_path", knowledge):
                metrics = activity.impact_metrics()
            self.assertEqual(metrics["tickets_acknowledged"], 1)
            self.assertEqual(metrics["followups_sent"], 3)
            self.assertEqual(metrics["tickets_auto_resolved"], 1)
            self.assertEqual(metrics["automated_actions"], 6)
            self.assertEqual(metrics["knowledge_documents"], 1)

    def test_timeline_is_scoped_to_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ack = root / "ack.json"
            followup = root / "followup.json"
            log = root / "activity.json"
            ack.write_text(json.dumps({"tickets": {}}), encoding="utf-8")
            followup.write_text(json.dumps({"tickets": {}}), encoding="utf-8")
            log.write_text(json.dumps({"events": [
                {"id": "1", "ticket_id": "A", "event_type": "status_changed", "title": "A event", "detail": "A", "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                {"id": "2", "ticket_id": "B", "event_type": "status_changed", "title": "B event", "detail": "B", "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
            ]}), encoding="utf-8")
            with patch.object(activity, "_ack_path", ack), patch.object(activity, "_followup_path", followup), patch.object(activity, "_activity_path", log):
                result = activity.timeline("A")
            self.assertEqual([event["title"] for event in result], ["A event"])

    def test_repeated_procedure_updates_one_activity_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "activity.json"
            with patch.object(activity, "_activity_path", log):
                for _ in range(2):
                    activity.append_activity("A", "knowledge_retrieved", "Verified procedure prepared", "8 steps", metadata={"steps": 8, "sources": ["Guide"]}, dedupe_key="procedure:8:Guide")
                events = activity._events()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["metadata"]["run_count"], 2)

    def test_compaction_drops_empty_and_collapses_legacy_procedures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "activity.json"
            log.write_text(json.dumps({"events": [
                {"id": "1", "ticket_id": "A", "event_type": "knowledge_retrieved", "metadata": {"steps": 0, "sources": []}},
                {"id": "2", "ticket_id": "A", "event_type": "knowledge_retrieved", "metadata": {"steps": 8, "sources": ["Guide"]}},
                {"id": "3", "ticket_id": "A", "event_type": "knowledge_retrieved", "metadata": {"steps": 8, "sources": ["Guide"]}},
                {"id": "4", "ticket_id": "A", "event_type": "status_changed", "metadata": {}},
            ]}), encoding="utf-8")
            with patch.object(activity, "_activity_path", log):
                result = activity.compact_activity_log()
                events = activity._events()
            self.assertEqual(result, {"before": 4, "after": 2, "removed": 2})
            self.assertEqual(events[0]["metadata"]["run_count"], 2)


if __name__ == "__main__":
    unittest.main()
