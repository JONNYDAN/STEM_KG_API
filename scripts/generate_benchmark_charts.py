import argparse
import json
import os
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _mode_order(data: Dict[str, Any]) -> List[str]:
    mode_summary = data.get("mode_summary") or {}
    preferred = ["text", "image", "both"]
    return [m for m in preferred if m in mode_summary] + [m for m in mode_summary if m not in preferred]


def _save(fig: plt.Figure, output_dir: str, filename: str) -> str:
    out_path = os.path.join(output_dir, filename)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def chart_1_query_distribution(data: Dict[str, Any], output_dir: str) -> str:
    mode_summary = data.get("mode_summary") or {}
    modes = _mode_order(data)
    counts = [mode_summary[m].get("runs", 0) for m in modes]
    total = sum(counts) or 1
    percents = [c * 100.0 / total for c in counts]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(modes, counts, color=["#4e79a7", "#f28e2b", "#59a14f"][: len(modes)])
    ax.set_title("Query Distribution by Input Mode")
    ax.set_ylabel("Number of Queries")

    for bar, pct in zip(bars, percents):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{pct:.1f}%", ha="center", va="bottom")

    return _save(fig, output_dir, "01_query_distribution_by_input_mode.png")


def chart_2_map_comparison(data: Dict[str, Any], output_dir: str) -> str:
    mode_summary = data.get("mode_summary") or {}
    top_k = data.get("config", {}).get("top_k", 5)
    metric_key = f"map@{top_k}"

    modes = _mode_order(data)
    values = [mode_summary[m].get(metric_key, 0.0) for m in modes]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(modes, values, color=["#2a9d8f", "#e76f51", "#264653"][: len(modes)])
    ax.set_title(f"MAP@{top_k} by Input Mode")
    ax.set_ylabel(f"MAP@{top_k}")
    ax.set_ylim(0, 1)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val, f"{val:.3f}", ha="center", va="bottom")

    return _save(fig, output_dir, "02_map_at_5_by_input_mode.png")


def chart_3_processing_time_by_mode(data: Dict[str, Any], output_dir: str) -> str:
    mode_summary = data.get("mode_summary") or {}
    modes = _mode_order(data)

    avg_client = [mode_summary[m].get("avg_client_total_ms", 0.0) for m in modes]
    p90_client = [mode_summary[m].get("p90_client_total_ms", 0.0) for m in modes]

    x = np.arange(len(modes))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9, 5))
    b1 = ax.bar(x - width / 2, avg_client, width, label="Avg client total (ms)")
    b2 = ax.bar(x + width / 2, p90_client, width, label="P90 client total (ms)")

    ax.set_title("Processing Time Comparison by Input Mode")
    ax.set_ylabel("Milliseconds")
    ax.set_xticks(x)
    ax.set_xticklabels(modes)
    ax.legend()

    for bars in [b1, b2]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h, f"{h:.0f}", ha="center", va="bottom", fontsize=8)

    return _save(fig, output_dir, "03_processing_time_comparison_by_mode.png")


def chart_4_phase_breakdown(data: Dict[str, Any], output_dir: str) -> str:
    mode_summary = data.get("mode_summary") or {}
    modes = _mode_order(data)

    model_ms = np.array([mode_summary[m].get("avg_model_analysis_ms", 0.0) for m in modes])
    kg_ms = np.array([mode_summary[m].get("avg_kg_query_ms", 0.0) for m in modes])

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(modes, model_ms, label="Model analysis (ms)", color="#457b9d")
    ax.bar(modes, kg_ms, bottom=model_ms, label="KG query (ms)", color="#a8dadc")

    ax.set_title("Phase-Level Processing Time by Input Mode")
    ax.set_ylabel("Milliseconds")
    ax.legend()

    totals = model_ms + kg_ms
    for idx, total in enumerate(totals):
        ax.text(idx, total, f"{total:.0f}", ha="center", va="bottom")

    return _save(fig, output_dir, "04_phase_time_breakdown.png")


def _percentiles(values: List[float], ps: List[float]) -> List[float]:
    if not values:
        return [0.0 for _ in ps]
    arr = np.array(sorted(values), dtype=float)
    return [float(np.percentile(arr, p)) for p in ps]


def chart_5_latency_percentiles(data: Dict[str, Any], output_dir: str) -> str:
    runs = data.get("runs") or []
    modes = _mode_order(data)
    ps = [50, 75, 90, 95]

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(ps))
    width = 0.22 if len(modes) >= 3 else 0.3

    color_map = {"text": "#1d3557", "image": "#e63946", "both": "#2a9d8f"}

    for idx, mode in enumerate(modes):
        vals = [
            float(r.get("client_total_ms"))
            for r in runs
            if r.get("input_mode") == mode and r.get("client_total_ms") is not None
        ]
        pvals = _percentiles(vals, ps)
        offset = (idx - (len(modes) - 1) / 2.0) * width
        bars = ax.bar(x + offset, pvals, width, label=mode, color=color_map.get(mode))
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h, f"{h:.0f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([f"P{int(p)}" for p in ps])
    ax.set_ylabel("Milliseconds")
    ax.set_title("Latency Percentiles by Input Mode")
    ax.legend()

    return _save(fig, output_dir, "05_latency_percentiles.png")


def chart_6_improvement_recommendations(data: Dict[str, Any], output_dir: str) -> str:
    mode_summary = data.get("mode_summary") or {}

    text_stats = mode_summary.get("text", {})
    image_stats = mode_summary.get("image", {})
    both_stats = mode_summary.get("both", {})

    text_map = float(text_stats.get("map@5", 0.0))
    image_map = float(image_stats.get("map@5", 0.0))
    both_map = float(both_stats.get("map@5", 0.0))

    text_latency = float(text_stats.get("avg_client_total_ms", 0.0))
    image_latency = float(image_stats.get("avg_client_total_ms", 0.0))
    both_latency = float(both_stats.get("avg_client_total_ms", 0.0))

    max_latency = max([text_latency, image_latency, both_latency, 1.0])

    score_image_quality = max(0.0, (text_map - image_map) * 100.0)
    score_multimodal_speed = max(0.0, (both_latency - text_latency) * 100.0 / max_latency)
    score_multimodal_quality = max(0.0, (text_map - both_map) * 100.0)
    score_kg_phase = max(0.0, float(data.get("overall_summary", {}).get("avg_kg_query_ms", 0.0)) * 100.0 / max_latency)

    labels = [
        "Improve image GT coverage",
        "Optimize multimodal latency",
        "Lift multimodal quality",
        "Optimize KG query stage",
    ]
    scores = [score_image_quality, score_multimodal_speed, score_multimodal_quality, score_kg_phase]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    y = np.arange(len(labels))
    bars = ax.barh(y, scores, color=["#e76f51", "#f4a261", "#2a9d8f", "#457b9d"])
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Priority score (higher = should improve first)")
    ax.set_title("Recommended Improvement Priorities")

    for bar in bars:
        w = bar.get_width()
        ax.text(w, bar.get_y() + bar.get_height() / 2, f" {w:.1f}", va="center")

    return _save(fig, output_dir, "06_improvement_recommendations.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate benchmark charts from benchmark JSON report")
    parser.add_argument("--input-json", required=True, help="Path to benchmark JSON report")
    parser.add_argument(
        "--output-dir",
        default="benchmark_charts",
        help="Directory to save chart PNG files",
    )
    args = parser.parse_args()

    data = _load_json(args.input_json)
    _ensure_dir(args.output_dir)

    outputs = [
        chart_1_query_distribution(data, args.output_dir),
        chart_2_map_comparison(data, args.output_dir),
        chart_3_processing_time_by_mode(data, args.output_dir),
        chart_4_phase_breakdown(data, args.output_dir),
        chart_5_latency_percentiles(data, args.output_dir),
        chart_6_improvement_recommendations(data, args.output_dir),
    ]

    print("Generated chart files:")
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
