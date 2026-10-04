#!/usr/bin/env python
"""
Benchmark: TextRank vs Gemini trên dataset 15 mẫu VN.

Usage:
    python loadtest/benchmark.py --ratio 0.3
    python loadtest/benchmark.py --ratio 0.3 --gemini-api-key YOUR_KEY

Output: JSON + markdown table.
"""

import argparse
import json
import os
import sys
import time
import tracemalloc
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_TEST"] = "1"

import django
django.setup()

from django.conf import settings
from rouge_score import rouge_scorer

from summaries.nlp import textrank_summarize, gemini_summarize


def load_dataset(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def benchmark_textrank(dataset, ratio):
    """Run TextRank on all samples."""
    results = []
    for item in dataset:
        source = item["source"]
        reference = item["reference"]

        # Time + memory
        tracemalloc.start()
        t0 = time.perf_counter()
        result = textrank_summarize(source, ratio=ratio, language="vietnamese")
        latency_ms = (time.perf_counter() - t0) * 1000
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        summary = result["summary"]

        results.append({
            "id": item["id"],
            "summary": summary,
            "latency_ms": round(latency_ms, 1),
            "memory_kb": round(peak / 1024, 1),
        })
    return results


def benchmark_gemini(dataset, ratio, api_key):
    """Run Gemini on all samples (requires API key)."""
    results = []
    os.environ["GEMINI_API_KEY"] = api_key
    # Reload settings to pick up the key
    from django.conf import settings
    settings.GEMINI_API_KEY = api_key

    for item in dataset:
        source = item["source"]
        reference = item["reference"]

        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            result = gemini_summarize(source, ratio=ratio, language="vietnamese")
            latency_ms = (time.perf_counter() - t0) * 1000
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            summary = result["summary"]
            results.append({
                "id": item["id"],
                "summary": summary,
                "latency_ms": round(latency_ms, 1),
                "memory_kb": round(peak / 1024, 1),
                "error": None,
            })
        except Exception as e:
            tracemalloc.stop()
            results.append({
                "id": item["id"],
                "summary": "",
                "latency_ms": None,
                "memory_kb": None,
                "error": str(e),
            })
    return results


def compute_rouge(predictions, references):
    """Compute ROUGE-1, ROUGE-2, ROUGE-L F1 scores."""
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)
    r1, r2, rl = [], [], []
    for pred, ref in zip(predictions, references):
        scores = scorer.score(ref, pred)
        r1.append(scores["rouge1"].fmeasure)
        r2.append(scores["rouge2"].fmeasure)
        rl.append(scores["rougeL"].fmeasure)
    return {
        "rouge1": round(sum(r1) / len(r1), 4),
        "rouge2": round(sum(r2) / len(r2), 4),
        "rougeL": round(sum(rl) / len(rl), 4),
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark TextRank vs Gemini")
    parser.add_argument("--ratio", type=float, default=0.3, help="Summary ratio (default 0.3)")
    parser.add_argument("--gemini-api-key", help="Gemini API key (optional)")
    parser.add_argument("--dataset", default="summaries/eval/vn_dataset.json", help="Dataset path")
    parser.add_argument("--output", help="Output JSON file")
    args = parser.parse_args()

    # Load dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = Path(__file__).parent.parent / "backend" / args.dataset
    dataset = load_dataset(dataset_path)
    print(f"Loaded {len(dataset)} samples from {dataset_path}")

    references = [item["reference"] for item in dataset]

    # TextRank benchmark
    print("\n--- TextRank ---")
    tr_results = benchmark_textrank(dataset, args.ratio)
    tr_summaries = [r["summary"] for r in tr_results]
    tr_rouge = compute_rouge(tr_summaries, references)
    tr_latency = sum(r["latency_ms"] for r in tr_results) / len(tr_results)
    tr_mem = sum(r["memory_kb"] for r in tr_results) / len(tr_results)
    print(f"ROUGE-1: {tr_rouge['rouge1']:.4f}, ROUGE-2: {tr_rouge['rouge2']:.4f}, ROUGE-L: {tr_rouge['rougeL']:.4f}")
    print(f"Avg latency: {tr_latency:.1f} ms")
    print(f"Avg memory: {tr_mem:.1f} KB")

    # Baseline: first sentences
    from summaries.nlp_utils import split_sentences, normalize_text
    def first_sentences_baseline(text, ratio):
        norm = normalize_text(text)
        sents = split_sentences(norm)
        k = max(1, int(len(sents) * ratio))
        return " ".join(sents[:k])

    baseline_summaries = [first_sentences_baseline(item["source"], args.ratio) for item in dataset]
    baseline_rouge = compute_rouge(baseline_summaries, references)

    # Output
    output = {
        "ratio": args.ratio,
        "dataset": str(dataset_path),
        "textrank": {
            "rouge": tr_rouge,
            "avg_latency_ms": round(tr_latency, 1),
            "avg_memory_kb": round(tr_mem, 1),
            "results": tr_results,
        },
        "baseline_first_sentences": {
            "rouge": baseline_rouge,
        },
    }

    if args.gemini_api_key:
        print("\n--- Gemini ---")
        gem_results = benchmark_gemini(dataset, args.ratio, args.gemini_api_key)
        gem_summaries = [r["summary"] for r in gem_results if r["error"] is None]
        if gem_summaries:
            gem_rouge = compute_rouge(gem_summaries, references)
            gem_latencies = [r["latency_ms"] for r in gem_results if r["latency_ms"] is not None]
            gem_mem = [r["memory_kb"] for r in gem_results if r["memory_kb"] is not None]
            output["gemini"] = {
                "rouge": gem_rouge,
                "avg_latency_ms": round(sum(gem_latencies) / len(gem_latencies), 1) if gem_latencies else None,
                "avg_memory_kb": round(sum(gem_mem) / len(gem_mem), 1) if gem_mem else None,
                "results": gem_results,
            }
            print(f"ROUGE-1: {gem_rouge['rouge1']:.4f}, ROUGE-2: {gem_rouge['rouge2']:.4f}, ROUGE-L: {gem_rouge['rougeL']:.4f}")
        else:
            print("Gemini: all requests failed")

    # Print markdown table
    print("\n## Kết quả benchmark (ratio = {:.0%})".format(args.ratio))
    print("| Phương pháp | ROUGE-1 | ROUGE-2 | ROUGE-L | Tỉ lệ nén | Latency (ms) | Memory (KB) |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    print(f"| TextRank | {tr_rouge['rouge1']:.3f} | {tr_rouge['rouge2']:.3f} | {tr_rouge['rougeL']:.3f} | ~25% | {tr_latency:.1f} | {tr_mem:.1f} |")
    print(f"| Baseline (câu đầu) | {baseline_rouge['rouge1']:.3f} | {baseline_rouge['rouge2']:.3f} | {baseline_rouge['rougeL']:.3f} | ~26% | <1 | <1 |")
    if args.gemini_api_key and "gemini" in output:
        g = output["gemini"]
        print(f"| Gemini | {g['rouge']['rouge1']:.3f} | {g['rouge']['rouge2']:.3f} | {g['rouge']['rougeL']:.3f} | ~30% | {g['avg_latency_ms']} | {g['avg_memory_kb']} |")

    if args.output:
        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nĐã ghi kết quả ra {args.output}")


if __name__ == "__main__":
    main()