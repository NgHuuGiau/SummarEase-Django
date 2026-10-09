"""Kiểm thử lệnh đánh giá chất lượng tóm tắt."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class EvaluateCommandTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.dataset = Path(self.temp_dir.name) / "dataset.json"
        self.dataset.write_text(
            json.dumps(
                [
                    {"id": "a", "source": "Câu đầu. Câu sau.", "reference": "Câu đầu."},
                    {"id": "b", "source": "Bắt đầu. Kết thúc.", "reference": "Kết thúc."},
                ]
            ),
            encoding="utf-8",
        )

    def test_failures_remain_paired_with_their_sample_and_are_excluded_from_mean(self):
        output = Path(self.temp_dir.name) / "nested" / "report.json"
        with patch(
            "summaries.management.commands.evaluate.textrank_summarize",
            side_effect=[{"summary": "Câu đầu."}, ValueError("internal detail")],
        ):
            call_command(
                "evaluate",
                dataset=str(self.dataset),
                method="textrank",
                ratio=0.5,
                output=str(output),
                stdout=None,
            )

        report = json.loads(output.read_text(encoding="utf-8"))
        samples = report["results"]["textrank"]["samples"]
        self.assertEqual([sample["id"] for sample in samples], ["a", "b"])
        self.assertEqual(samples[1]["error"], "ValueError")
        self.assertNotIn("internal detail", output.read_text(encoding="utf-8"))
        self.assertEqual(report["results"]["textrank"]["summary"]["successes"], 1)
        self.assertEqual(report["results"]["textrank"]["summary"]["failures"], 1)

    def test_rejects_invalid_ratio(self):
        with self.assertRaises(CommandError):
            call_command("evaluate", dataset=str(self.dataset), ratio=0)

    def test_rejects_duplicate_dataset_ids(self):
        self.dataset.write_text(
            json.dumps(
                [
                    {"id": "same", "source": "Nguồn A", "reference": "Tóm tắt A"},
                    {"id": "same", "source": "Nguồn B", "reference": "Tóm tắt B"},
                ]
            ),
            encoding="utf-8",
        )
        with self.assertRaises(CommandError):
            call_command("evaluate", dataset=str(self.dataset))
