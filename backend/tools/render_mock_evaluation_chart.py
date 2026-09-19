"""Render a self-contained SVG comparison chart from a mock archive report."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


LABELS = {
    "genre_similarity_q": "Genre similarity (mock)",
    "native_ji.coherence": "Native JI coherence",
    "pil_genre.typicality_q": "PIL typicality",
    "pil_genre.idiomaticity_q": "PIL idiomaticity",
    "pil_genre.inverse_cliche_q": "PIL inverse cliche",
}
COLORS = ("#2563eb", "#ea580c", "#16a34a", "#9333ea", "#dc2626", "#0891b2")


def render(report: dict) -> str:
    metrics = report["quality_metric_ids"]
    rows = sorted(report["rows"], key=lambda row: row["seed"])
    width, left, right, top = 1040, 210, 40, 76
    group_height, bar_height, gap = 106, 13, 4
    plot_width = width - left - right
    height = top + len(metrics) * group_height + 50
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Mock evaluation comparison by seed</title>',
        '<desc id="desc">Five values from zero to ten thousand. Genre similarity is non-authoritative.</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="30" font-family="sans-serif" font-size="20" font-weight="600">Mock evaluation comparison</text>',
        '<text x="24" y="53" font-family="sans-serif" font-size="12" fill="#555">Non-authoritative · production decisions prohibited · higher is better</text>',
    ]
    for tick in range(0, 10001, 2000):
        x = left + plot_width * tick / 10000
        parts.append(f'<line x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" y2="{height - 36}" stroke="#dddddd" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{height - 16}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#444">{tick}</text>')
    for metric_index, metric in enumerate(metrics):
        y0 = top + metric_index * group_height
        label = html.escape(LABELS.get(metric, metric))
        parts.append(f'<text x="24" y="{y0 + 13}" font-family="sans-serif" font-size="13" fill="#111">{label}</text>')
        for row_index, row in enumerate(rows):
            value = row["quality"][metric_index]
            y = y0 + 23 + row_index * (bar_height + gap)
            bar_width = plot_width * value / 10000
            color = COLORS[row_index % len(COLORS)]
            parts.append(f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" fill="{color}"/>')
            parts.append(f'<text x="{left - 9}" y="{y + 11}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#333">seed {row["seed"]}</text>')
            value_x = min(left + bar_width + 6, width - 35)
            parts.append(f'<text x="{value_x:.1f}" y="{y + 11}" font-family="sans-serif" font-size="11" fill="#111">{value}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = json.loads(arguments.report.read_text(encoding="utf-8"))
    if report.get("schema") != "cps.mock-sample-archive-trial-report":
        parser.error("report is not a mock sample/archive trial")
    arguments.output.write_text(render(report), encoding="utf-8")


if __name__ == "__main__":
    main()
