"""Đánh giá các phương pháp tóm tắt trên dataset có bản tham chiếu."""

import json
import math
import statistics
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from summaries.nlp import gemini_summarize, textrank_summarize
from summaries.nlp_utils import normalize_text, split_sentences

try:
    from rouge_score import rouge_scorer
except ImportError:
    rouge_scorer = None


class Command(BaseCommand):
    help = "Compare TextRank, first-sentence baseline, and Gemini summaries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            default="summaries/eval/vn_dataset.json",
            help="JSON dataset with id, source, and reference fields",
        )
        parser.add_argument(
            "--method",
            choices=["textrank", "first_sentences", "gemini", "all"],
            default="all",
            help="Method to evaluate; all skips Gemini to avoid API charges",
        )
        parser.add_argument(
            "--ratio", type=float, default=0.3, help="Summary ratio between 0 and 1"
        )
        parser.add_argument("--output", help="Write per-sample and aggregate results to JSON")

    def handle(self, *args, **opts):
        if rouge_scorer is None:
            raise CommandError("Missing rouge-score. Install dependencies from requirements.txt.")

        ratio = opts["ratio"]
        if not math.isfinite(ratio) or not 0 < ratio <= 1:
            raise CommandError("--ratio must be greater than 0 and at most 1.")

        methods = ["textrank", "first_sentences"] if opts["method"] == "all" else [opts["method"]]
        if "gemini" in methods and not settings.GEMINI_API_KEY:
            raise CommandError("Set GEMINI_API_KEY in the environment to evaluate Gemini.")

        dataset_path = Path(opts["dataset"])
        if not dataset_path.is_absolute():
            dataset_path = settings.BACKEND_DIR / dataset_path
        try:
            dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read dataset: {dataset_path}") from exc
        self._validate_dataset(dataset)

        scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)
        results = {method: [] for method in methods}
        for item in dataset:
            for method in methods:
                started = time.perf_counter()
                try:
                    summary = self._summarize(method, item["source"], ratio)
                    latency_ms = round((time.perf_counter() - started) * 1000, 2)
                    scores = scorer.score(item["reference"], summary)
                    sample = {
                        "id": item["id"],
                        "reference": item["reference"],
                        "summary": summary,
                        "latency_ms": latency_ms,
                        "compression": len(summary) / len(item["source"]),
                        "rouge": {key: score.fmeasure for key, score in scores.items()},
                        "error": None,
                    }
                except Exception as exc:  # Keep failed API samples paired with their own reference.
                    sample = {
                        "id": item["id"],
                        "reference": item["reference"],
                        "summary": "",
                        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                        "compression": None,
                        "rouge": None,
                        "error": type(exc).__name__,
                    }
                results[method].append(sample)

        report = {
            "dataset": str(dataset_path),
            "sample_count": len(dataset),
            "ratio": ratio,
            "methods": methods,
            "gemini_model": settings.GEMINI_MODEL if "gemini" in methods else None,
            "results": {
                method: {
                    "summary": self._aggregate(samples),
                    "samples": samples,
                }
                for method, samples in results.items()
            },
        }

        self.stdout.write("\n=== SUMMARY EVALUATION (ROUGE F1) ===")
        self.stdout.write(
            f"{'Method':<18} {'ROUGE-1':>9} {'ROUGE-2':>9} {'ROUGE-L':>9} "
            f"{'Compress':>8} {'Latency':>12} {'Errors':>5}"
        )
        for method, data in report["results"].items():
            summary = data["summary"]
            self.stdout.write(
                f"{method:<18} {self._fmt(summary['rouge1']):>9} "
                f"{self._fmt(summary['rouge2']):>9} {self._fmt(summary['rougeL']):>9} "
                f"{self._fmt(summary['compression'], percent=True):>8} "
                f"{self._fmt(summary['avg_latency_ms'], suffix=' ms'):>12} "
                f"{summary['failures']:>5}"
            )

        if opts["output"]:
            output_path = Path(opts["output"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.stdout.write(f"\nReport written: {output_path}")

    def _validate_dataset(self, dataset):
        if not isinstance(dataset, list) or not dataset:
            raise CommandError("Dataset must be a non-empty JSON list.")
        seen = set()
        for index, item in enumerate(dataset, start=1):
            if not isinstance(item, dict) or not all(
                isinstance(item.get(key), str) and item[key].strip()
                for key in ("id", "source", "reference")
            ):
                raise CommandError(
                    f"Sample {index} needs non-empty string fields: id, source, reference."
                )
            if item["id"] in seen:
                raise CommandError(f"Duplicate sample id: {item['id']}")
            seen.add(item["id"])

    def _summarize(self, method, source, ratio):
        if method == "textrank":
            return textrank_summarize(source, ratio=ratio, language="vietnamese")["summary"]
        if method == "gemini":
            return gemini_summarize(
                source,
                ratio=ratio,
                language="vietnamese",
                user_api_key=settings.GEMINI_API_KEY,
            )["summary"]

        sentences = split_sentences(normalize_text(source))
        count = max(1, int(len(sentences) * ratio))
        return " ".join(sentences[:count])

    def _aggregate(self, samples):
        successful = [sample for sample in samples if sample["error"] is None]
        metrics = ["rouge1", "rouge2", "rougeL", "compression"]
        summary = {
            metric: statistics.mean(
                [
                    sample["rouge"][metric] if metric.startswith("rouge") else sample[metric]
                    for sample in successful
                ]
            )
            if successful
            else None
            for metric in metrics
        }
        summary.update(
            {
                "sample_count": len(samples),
                "successes": len(successful),
                "failures": len(samples) - len(successful),
                "avg_latency_ms": statistics.mean([sample["latency_ms"] for sample in successful])
                if successful
                else None,
            }
        )
        return summary

    def _fmt(self, value, suffix="", percent=False):
        if value is None:
            return "N/A"
        return f"{value:.2%}" if percent else f"{value:.4f}{suffix}"
