"""Quản lý: đánh giá chất lượng tóm tắt bằng ROUGE."""

import json
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from summaries.nlp import textrank_summarize
from summaries.nlp_utils import normalize_text

try:
    from rouge_score import rouge_scorer
except ImportError:
    rouge_scorer = None


class Command(BaseCommand):
    help = "Đánh giá chất lượng tóm tắt (TextRank vs baseline) bằng ROUGE-1/2/L"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            default="summaries/eval/vn_dataset.json",
            help="Đường dẫn file JSON dataset (mặc định: summaries/eval/vn_dataset.json)",
        )
        parser.add_argument(
            "--method",
            choices=["textrank", "first_sentences", "all"],
            default="all",
            help="Phương pháp tóm tắt để đánh giá",
        )
        parser.add_argument(
            "--ratio",
            type=float,
            default=0.3,
            help="Tỉ lệ tóm tắt cho TextRank (mặc định 0.3)",
        )
        parser.add_argument(
            "--output",
            help="Ghi kết quả ra file JSON",
        )

    def handle(self, *args, **opts):
        if rouge_scorer is None:
            self.stderr.write("Thiếu thư viện rouge-score. Cài: pip install rouge-score")
            sys.exit(1)

        dataset_path = Path(opts["dataset"])
        if not dataset_path.is_absolute():
            dataset_path = settings.BACKEND_DIR / dataset_path

        with dataset_path.open(encoding="utf-8") as f:
            dataset = json.load(f)

        self.stdout.write(f"Đánh giá trên {len(dataset)} mẫu...")

        scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)

        methods = ["textrank", "first_sentences"] if opts["method"] == "all" else [opts["method"]]

        keys = ["rouge1", "rouge2", "rougeL", "compression"]
        results = {m: {k: [] for k in keys} for m in methods}

        for item in dataset:
            source = item["source"]
            reference = item["reference"]

            for method in methods:
                if method == "textrank":
                    result = textrank_summarize(source, ratio=opts["ratio"], language="vietnamese")
                    summary = result["summary"]
                else:  # first_sentences
                    summary = self._first_sentences_baseline(source, opts["ratio"])

                # ROUGE so với reference
                scores = scorer.score(reference, summary)
                results[method]["rouge1"].append(scores["rouge1"].fmeasure)
                results[method]["rouge2"].append(scores["rouge2"].fmeasure)
                results[method]["rougeL"].append(scores["rougeL"].fmeasure)

                # Tỉ lệ nén
                compression = len(summary) / len(source) if source else 0
                results[method]["compression"].append(compression)

        # In bảng tóm tắt
        self.stdout.write("\n=== KẾT QUẢ ROUGE (F1) ===")
        self.stdout.write(
            f"{'Phương pháp':<18} {'ROUGE-1':>10} {'ROUGE-2':>10} {'ROUGE-L':>10} {'Nén':>8}"
        )
        self.stdout.write("-" * 56)

        for method in methods:
            r1 = sum(results[method]["rouge1"]) / len(results[method]["rouge1"])
            r2 = sum(results[method]["rouge2"]) / len(results[method]["rouge2"])
            rl = sum(results[method]["rougeL"]) / len(results[method]["rougeL"])
            comp = sum(results[method]["compression"]) / len(results[method]["compression"])
            self.stdout.write(f"{method:<18} {r1:>10.4f} {r2:>10.4f} {rl:>10.4f} {comp:>7.2%}")

        # Chi tiết từng mẫu (tùy chọn verbose)
        if opts.get("verbosity", 1) >= 2:
            for i, item in enumerate(dataset):
                self.stdout.write(f"\n--- Mẫu {i + 1}: {item['id']} ---")
                self.stdout.write(f"Nguồn: {item['source'][:80]}...")
                self.stdout.write(f"Tham chiếu: {item['reference']}")
                for method in methods:
                    if method == "textrank":
                        result = textrank_summarize(
                            item["source"], ratio=opts["ratio"], language="vietnamese"
                        )
                        summary = result["summary"]
                    else:
                        summary = self._first_sentences_baseline(item["source"], opts["ratio"])
                    self.stdout.write(f"  {method}: {summary}")

        # Ghi file output
        if opts["output"]:
            out = {
                "dataset": str(dataset_path),
                "ratio": opts["ratio"],
                "results": {
                    m: {
                        "rouge1": results[m]["rouge1"],
                        "rouge2": results[m]["rouge2"],
                        "rougeL": results[m]["rougeL"],
                        "compression": results[m]["compression"],
                        "mean": {
                            "rouge1": sum(results[m]["rouge1"]) / len(results[m]["rouge1"]),
                            "rouge2": sum(results[m]["rouge2"]) / len(results[m]["rouge2"]),
                            "rougeL": sum(results[m]["rougeL"]) / len(results[m]["rougeL"]),
                            "compression": sum(results[m]["compression"])
                            / len(results[m]["compression"]),
                        },
                    }
                    for m in methods
                },
            }
            Path(opts["output"]).write_text(
                json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.stdout.write(f"\nĐã ghi chi tiết ra {opts['output']}")

    def _first_sentences_baseline(self, text: str, ratio: float) -> str:
        """Baseline: chọn N câu đầu tiên theo tỉ lệ."""
        from summaries.nlp_utils import split_sentences

        norm = normalize_text(text)
        sentences = split_sentences(norm)
        total = len(sentences)
        if total <= 1:
            return text
        k = max(1, int(total * ratio))
        return " ".join(sentences[:k])
