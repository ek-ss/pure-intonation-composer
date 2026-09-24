"""Create an offline SVG/HTML atlas of symbolic cluster distributions."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from tools.cluster_symbolic_songs import distance_symbolic  # noqa: E402


def _principal_axes(values: list[list[float]]) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    """PCA of standardized distances to medoids; no external plotting package."""
    n, width = len(values), len(values[0])
    means = [sum(row[j] for row in values) / n for j in range(width)]
    scales = [math.sqrt(sum((row[j] - means[j]) ** 2 for row in values) / n) or 1.0
              for j in range(width)]
    centered = [[(row[j] - means[j]) / scales[j] for j in range(width)] for row in values]
    covariance = [[sum(row[a] * row[b] for row in centered) / n
                   for b in range(width)] for a in range(width)]
    trace = sum(covariance[i][i] for i in range(width)) or 1.0
    axes: list[list[float]] = []
    eigenvalues = []
    for index in range(2):
        vector = [math.sin((j + 1) * (index + 1) * 1.37) for j in range(width)]
        for _ in range(160):
            next_vector = [sum(covariance[j][k] * vector[k] for k in range(width))
                           for j in range(width)]
            for previous in axes:
                projection = sum(a * b for a, b in zip(previous, next_vector))
                next_vector = [value - projection * previous[j]
                               for j, value in enumerate(next_vector)]
            length = math.sqrt(sum(value * value for value in next_vector))
            if length < 1e-12:
                vector = [0.0] * width
                break
            vector = [value / length for value in next_vector]
        anchor = max(range(width), key=lambda j: abs(vector[j]))
        if vector[anchor] < 0:
            vector = [-value for value in vector]
        axes.append(vector)
        eigenvalues.append(max(0.0, sum(vector[a] * covariance[a][b] * vector[b]
                                        for a in range(width) for b in range(width))))
    points = [(sum(value * axis for value, axis in zip(row, axes[0])),
               sum(value * axis for value, axis in zip(row, axes[1])))
              for row in centered]
    return points, (eigenvalues[0] / trace, eigenvalues[1] / trace)


def _style_key(boundary: list) -> tuple[int, int, int, str]:
    return tuple(boundary)


def visualize(cluster_path: Path, listening_path: Path, output: Path) -> dict:
    report = json.loads(cluster_path.read_text())
    listening = json.loads(listening_path.read_text())
    groups = report["clusters"]
    rows = report["rows"]
    if not rows or not groups:
        raise ValueError("empty cluster report")
    selected = {item["cluster_medoid_seed"]: item for item in listening["rows"]}
    if set(selected) != {item["representative_seed"] for item in groups}:
        raise ValueError("listening set does not match cluster medoids")
    members = {seed: group["representative_seed"] for group in groups for seed in group["member_seeds"]}
    by_seed = {row["seed"]: row for row in rows}
    if set(members) != set(by_seed):
        raise ValueError("cluster membership does not partition rows")
    anchors = [by_seed[group["representative_seed"]]["features"] for group in groups]
    distances = [[distance_symbolic(row["features"], anchor) for anchor in anchors] for row in rows]
    raw_points, explained = _principal_axes(distances)
    minima = [min(point[axis] for point in raw_points) for axis in range(2)]
    maxima = [max(point[axis] for point in raw_points) for axis in range(2)]
    def pixel(point: tuple[float, float]) -> tuple[int, int]:
        return (round(90 + 720 * (point[0] - minima[0]) / (maxima[0] - minima[0] or 1)),
                round(630 - 480 * (point[1] - minima[1]) / (maxima[1] - minima[1] or 1)))
    points = {row["seed"]: pixel(point) for row, point in zip(rows, raw_points, strict=True)}
    colors = {group["representative_seed"]: f"hsl({round(360 * i / len(groups))},66%,42%)"
              for i, group in enumerate(groups)}
    opening = sorted({_style_key(row["features"]["opening"]) for row in rows})
    closure = sorted({_style_key(row["features"]["closure"]) for row in rows})
    pair_counts = Counter((_style_key(row["features"]["opening"]),
                           _style_key(row["features"]["closure"])) for row in rows)
    maximum_cell = max(pair_counts.values(), default=1)
    def label(boundary: tuple) -> str:
        return f"{boundary[0]} bars / {boundary[3]}"
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'width="1420" height="1320" viewBox="0 0 1420 1320" role="img" '
        'aria-label="Symbolic song cluster distribution">',
        '<rect width="1420" height="1320" fill="#f8fafc"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#17212f} .small{font-size:13px} '
        '.muted{fill:#526075} .heading{font-weight:700;font-size:22px} '
        '.panel{fill:white;stroke:#d9e1eb;stroke-width:1.5} '
        'a:hover circle{stroke:#17212f;stroke-width:2.5}</style>',
        '<text x="48" y="45" class="heading">1,000-seed composition: symbolic cluster atlas</text>',
        f'<text x="48" y="73" class="small muted">1,000 attempted · {report["compiled_count"]} compiled · '
        f'{len(rows)} symbolically valid · {len(groups)} clusters · {listening["success_count"]} listening WAVs</text>',
        '<rect x="48" y="100" width="800" height="590" rx="12" class="panel"/>',
        '<rect x="868" y="100" width="504" height="590" rx="12" class="panel"/>',
        '<text x="68" y="132" font-size="17" font-weight="700">Feature-distance projection</text>',
        f'<text x="68" y="155" class="small muted">Distance-to-medoid PCA: axis 1 {explained[0]*100:.1f}%, '
        f'axis 2 {explained[1]*100:.1f}% of landmark variance</text>',
        '<text x="68" y="675" class="small muted">Each dot = one Project. Axes are relative; 2D distances can distort the clustering metric.</text>',
        '<rect x="83" y="142" width="735" height="500" fill="none" stroke="#e4eaf1"/>',
    ]
    for row in rows:
        seed = row["seed"]
        cx, cy = points[seed]
        medoid = members[seed]
        exposed = row["features"]["lattice_exposure_q"] / 100
        tooltip = html.escape(f"seed {seed} · cluster {medoid} · lattice exposure {exposed:.1f}%")
        pieces.append(f'<circle class="data-point" cx="{cx}" cy="{cy}" r="4.4" '
                      f'fill="{colors[medoid]}" fill-opacity="0.53"><title>{tooltip}</title></circle>')
    for group in groups:
        seed = group["representative_seed"]
        cx, cy = points[seed]
        pieces.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="white" '
                      f'stroke="{colors[seed]}" stroke-width="3"><title>cluster medoid {seed}</title></circle>')
    pieces.extend((
        '<text x="890" y="132" font-size="17" font-weight="700">Clusters · medoid → audio seed</text>',
        '<text x="890" y="155" class="small muted">Filled dots are members; outlined dots are medoids</text>',
    ))
    for index, group in enumerate(groups):
        medoid = group["representative_seed"]
        audio = selected[medoid]
        seed = audio["seed"]
        expanded = audio["receipt"].get("expanded_frequency_envelope", False)
        y = 180 + index * 29
        pieces.append(f'<circle cx="891" cy="{y}" r="6" fill="{colors[medoid]}"/>')
        pieces.append(f'<text x="908" y="{y+5}" font-size="14">{medoid} → {seed} · {group["member_count"]} songs'
                      f'{" · preview" if expanded else ""}</text>')
        pieces.append(f'<a href="seed-{seed:04d}/reference.wav" xlink:href="seed-{seed:04d}/reference.wav">'
                      f'<rect x="1274" y="{y-12}" width="75" height="24" rx="6" fill="#e8f1ff"/>'
                      f'<text x="1288" y="{y+5}" font-size="13" fill="#145db5">Play ↗</text></a>')
    pieces += [
        '<rect x="48" y="710" width="600" height="565" rx="12" class="panel"/>',
        '<rect x="668" y="710" width="704" height="565" rx="12" class="panel"/>',
        '<text x="70" y="746" font-size="17" font-weight="700">Opening × closure · valid Project counts</text>',
        '<text x="70" y="771" class="small muted">Only 245 symbolically valid songs; brighter cells contain more</text>',
    ]
    cell_w, cell_h = 103, 80
    for index, intro in enumerate(opening):
        pieces.append(f'<text x="{248+index*cell_w}" y="802" class="small" '
                      f'text-anchor="middle">{html.escape(label(intro))}</text>')
    for yindex, outro in enumerate(closure):
        y = 822 + yindex * cell_h
        pieces.append(f'<text x="185" y="{y+44}" class="small" '
                      f'text-anchor="end">{html.escape(label(outro))}</text>')
        for xindex, intro in enumerate(opening):
            x = 200 + xindex * cell_w
            count = pair_counts[intro, outro]
            alpha = 0.08 + 0.80 * count / maximum_cell
            pieces.append(f'<rect x="{x}" y="{y}" width="96" height="72" rx="6" '
                          f'fill="#2563eb" fill-opacity="{alpha:.3f}"/>')
            pieces.append(f'<text x="{x+48}" y="{y+43}" text-anchor="middle" '
                          f'font-weight="700" font-size="20">{count}</text>')
    pieces += [
        '<text x="70" y="1245" class="small muted">Coverage describes generated successes, not all 1,000 attempts.</text>',
        '<text x="690" y="746" font-size="17" font-weight="700">Cluster size and 12-EDO distance</text>',
        '<text x="690" y="771" class="small muted">Bar = members · right value = median ≥10¢ voice-time share</text>',
    ]
    max_size = max(group["member_count"] for group in groups)
    for index, group in enumerate(groups):
        medoid = group["representative_seed"]
        exposures = sorted(by_seed[seed]["features"]["lattice_exposure_q"]
                           for seed in group["member_seeds"])
        median = exposures[len(exposures)//2] / 100
        y = 802 + index * 26
        width = round(360 * group["member_count"] / max_size)
        pieces.extend((
            f'<text x="690" y="{y+10}" class="small">{medoid}</text>',
            f'<rect x="738" y="{y-2}" width="{width}" height="16" rx="3" '
            f'fill="{colors[medoid]}" fill-opacity="0.75"/>',
            f'<text x="1110" y="{y+10}" class="small">{group["member_count"]} · {median:.1f}%</text>',
        ))
    pieces.append('<text x="690" y="1245" class="small muted">Higher lattice exposure is not automatically better.</text>')
    pieces.append('</svg>')
    svg = '\n'.join(pieces) + '\n'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'distribution.svg').write_text(svg, encoding='utf-8')
    page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<title>Section cluster distribution</title><body style="margin:0;background:#f8fafc">'
            + svg + '<p style="font:14px system-ui;margin:0 48px 32px">'
            '<a href="listening_index.md">Listening index</a> · '
            '<a href="representatives.m3u">Playlist</a> · '
            f'Cluster report: {html.escape(report["report_hash"])}'
            '</p></body></html>')
    (output / 'distribution.html').write_text(page, encoding='utf-8')
    return {'songs': len(rows), 'clusters': len(groups), 'opening_styles': len(opening),
            'closure_styles': len(closure), 'landmark_variance_percent':
            [round(value * 100, 1) for value in explained],
            'svg_sha256': hashlib.sha256(svg.encode()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clusters', type=Path, required=True)
    parser.add_argument('--listening-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = visualize(args.clusters, args.listening_report, args.output)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
