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


def _modes(data: Dict[str, Any]) -> List[str]:
    mode_summary = data.get("mode_summary") or {}
    preferred = ["text", "image", "both"]
    return [m for m in preferred if m in mode_summary]


def _save(fig: plt.Figure, output_dir: str, filename: str) -> str:
    out = os.path.join(output_dir, filename)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def chart_1_distribution(gemini: Dict[str, Any], basic: Dict[str, Any], out_dir: str) -> str:
    gm = gemini.get("mode_summary") or {}
    bm = basic.get("mode_summary") or {}
    modes = _modes(gemini)

    g_vals = [gm.get(m, {}).get("runs", 0) for m in modes]
    b_vals = [bm.get(m, {}).get("runs", 0) for m in modes]

    x = np.arange(len(modes))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, g_vals, width, label="gemini", color="#1d3557")
    ax.bar(x + width / 2, b_vals, width, label="basic", color="#2a9d8f")
    ax.set_title("1) Distribution of Query Runs by Input Mode")
    ax.set_ylabel("Runs")
    ax.set_xticks(x)
    ax.set_xticklabels(modes)
    ax.legend()

    return _save(fig, out_dir, "01_distribution_input_mode_basic_vs_gemini.png")


def chart_2_map(gemini: Dict[str, Any], basic: Dict[str, Any], out_dir: str) -> str:
    gm = gemini.get("mode_summary") or {}
    bm = basic.get("mode_summary") or {}
    modes = _modes(gemini)

    g_vals = [gm.get(m, {}).get("map@5", 0.0) for m in modes]
    b_vals = [bm.get(m, {}).get("map@5", 0.0) for m in modes]

    x = np.arange(len(modes))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9, 5))
    bars1 = ax.bar(x - width / 2, g_vals, width, label="gemini", color="#457b9d")
    bars2 = ax.bar(x + width / 2, b_vals, width, label="basic", color="#e76f51")
    ax.set_title("2) MAP@5 Comparison by Input Mode")
    ax.set_ylabel("MAP@5")
    ax.set_ylim(0, 1)
    ax.set_xticks(x)
    ax.set_xticklabels(modes)
    ax.legend()

    for bars in [bars1, bars2]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h, f"{h:.3f}", ha="center", va="bottom", fontsize=8)

    return _save(fig, out_dir, "02_map5_compare_by_mode_basic_vs_gemini.png")


def chart_3_processing_time(gemini: Dict[str, Any], basic: Dict[str, Any], out_dir: str) -> str:
    gm = gemini.get("mode_summary") or {}
    bm = basic.get("mode_summary") or {}
    modes = _modes(gemini)

    g_vals = [gm.get(m, {}).get("avg_client_total_ms", 0.0) for m in modes]
    b_vals = [bm.get(m, {}).get("avg_client_total_ms", 0.0) for m in modes]

    x = np.arange(len(modes))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, g_vals, width, label="gemini", color="#264653")
    ax.bar(x + width / 2, b_vals, width, label="basic", color="#2a9d8f")
    ax.set_title("3) Processing Time Comparison by Input Mode")
    ax.set_ylabel("Average client total time (ms)")
    ax.set_xticks(x)
    ax.set_xticklabels(modes)
    ax.legend()

    return _save(fig, out_dir, "03_processing_time_compare_by_mode_basic_vs_gemini.png")


def chart_4_phase_breakdown(gemini: Dict[str, Any], basic: Dict[str, Any], out_dir: str) -> str:
    gm = gemini.get("mode_summary") or {}
    bm = basic.get("mode_summary") or {}
    modes = _modes(gemini)

    x = np.arange(len(modes))
    width = 0.18

    g_model = np.array([gm.get(m, {}).get("avg_model_analysis_ms", 0.0) for m in modes])
    g_kg = np.array([gm.get(m, {}).get("avg_kg_query_ms", 0.0) for m in modes])
    b_model = np.array([bm.get(m, {}).get("avg_model_analysis_ms", 0.0) for m in modes])
    b_kg = np.array([bm.get(m, {}).get("avg_kg_query_ms", 0.0) for m in modes])

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(x - width, g_model, width, label="gemini model", color="#1d3557")
    ax.bar(x - width, g_kg, width, bottom=g_model, label="gemini KG", color="#a8dadc")

    ax.bar(x + width, b_model, width, label="basic model", color="#e76f51")
    ax.bar(x + width, b_kg, width, bottom=b_model, label="basic KG", color="#f4a261")

    ax.set_title("4) Phase-Level Processing Time by Mode")
    ax.set_ylabel("Milliseconds")
    ax.set_xticks(x)
    ax.set_xticklabels(modes)
    ax.legend(ncol=2, fontsize=8)

    return _save(fig, out_dir, "04_phase_time_analysis_basic_vs_gemini.png")


def _percentiles(values: List[float], ps: List[int]) -> List[float]:
    if not values:
        return [0.0 for _ in ps]
    arr = np.array(sorted(values), dtype=float)
    return [float(np.percentile(arr, p)) for p in ps]


def chart_5_latency_quantiles(gemini: Dict[str, Any], basic: Dict[str, Any], out_dir: str) -> str:
    ps = [50, 75, 90, 95]
    g_vals_raw = [float(r.get("client_total_ms")) for r in (gemini.get("runs") or []) if r.get("client_total_ms") is not None]
    b_vals_raw = [float(r.get("client_total_ms")) for r in (basic.get("runs") or []) if r.get("client_total_ms") is not None]

    g_vals = _percentiles(g_vals_raw, ps)
    b_vals = _percentiles(b_vals_raw, ps)

    x = np.arange(len(ps))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, g_vals, width, label="gemini", color="#457b9d")
    ax.bar(x + width / 2, b_vals, width, label="basic", color="#2a9d8f")

    ax.set_title("5) Latency Quantiles (Overall)")
    ax.set_ylabel("Milliseconds")
    ax.set_xticks(x)
    ax.set_xticklabels([f"P{p}" for p in ps])
    ax.legend()

    return _save(fig, out_dir, "05_latency_quantiles_basic_vs_gemini.png")


def chart_6_improvements(gemini: Dict[str, Any], basic: Dict[str, Any], out_dir: str) -> str:
    gm = gemini.get("mode_summary") or {}
    bm = basic.get("mode_summary") or {}
    modes = _modes(gemini)

    labels: List[str] = []
    scores: List[float] = []

    for m in modes:
        g_map = float(gm.get(m, {}).get("map@5", 0.0))
        b_map = float(bm.get(m, {}).get("map@5", 0.0))
        g_t = float(gm.get(m, {}).get("avg_client_total_ms", 0.0))
        b_t = float(bm.get(m, {}).get("avg_client_total_ms", 0.0))

        # Positive means basic improves speed over gemini
        speed_gain_pct = ((g_t - b_t) / g_t * 100.0) if g_t > 0 else 0.0
        quality_change = (b_map - g_map) * 100.0

        labels.append(f"{m}: speed gain (basic vs gemini)")
        scores.append(speed_gain_pct)

        labels.append(f"{m}: MAP change (basic-gemini)")
        scores.append(quality_change)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    y = np.arange(len(labels))
    colors = ["#2a9d8f" if s >= 0 else "#e63946" for s in scores]
    bars = ax.barh(y, scores, color=colors)

    ax.axvline(0, color="black", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Delta (%)")
    ax.set_title("6) Improvement Recommendations from Basic vs Gemini")

    for bar in bars:
        w = bar.get_width()
        x = w + (0.4 if w >= 0 else -0.4)
        ha = "left" if w >= 0 else "right"
        ax.text(x, bar.get_y() + bar.get_height() / 2, f"{w:.2f}%", va="center", ha=ha, fontsize=8)

    return _save(fig, out_dir, "06_improvement_recommendations_basic_vs_gemini.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 6 comparison charts for basic vs gemini benchmark reports")
    parser.add_argument("--gemini-json", required=True)
    parser.add_argument("--basic-json", required=True)
    parser.add_argument("--output-dir", default="benchmark_charts_compare_basic_vs_gemini")
    args = parser.parse_args()

    gemini = _load_json(args.gemini_json)
    basic = _load_json(args.basic_json)

    _ensure_dir(args.output_dir)

    outputs = [
        chart_1_distribution(gemini, basic, args.output_dir),
        chart_2_map(gemini, basic, args.output_dir),
        chart_3_processing_time(gemini, basic, args.output_dir),
        chart_4_phase_breakdown(gemini, basic, args.output_dir),
        chart_5_latency_quantiles(gemini, basic, args.output_dir),
        chart_6_improvements(gemini, basic, args.output_dir),
    ]

    print("Generated comparison charts:")
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
