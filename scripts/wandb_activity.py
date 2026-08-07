#!/usr/bin/env python3
"""Render a GitHub-style contribution heatmap of Weights & Biases runs.

Walks every project belonging to an entity, buckets run creation times by
day, and writes an SVG grid to disk. Run with --placeholder to emit an empty
grid without touching the network (useful before the API key is configured).

    python scripts/wandb_activity.py --entity yandabao --out wandb-activity.svg
"""

import argparse
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta

WEEKS = 53
CELL = 11
GAP = 3
PITCH = CELL + GAP
PAD_LEFT = 30
PAD_TOP = 20

# GitHub's own contribution palettes, light and dark.
LIGHT = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
DARK = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def sunday_index(d):
    """Row position in the grid: Sunday is 0, Saturday is 6."""
    return (d.weekday() + 1) % 7


def window(today):
    """The inclusive date range the grid covers, ending on a full week."""
    end = today + timedelta(days=6 - sunday_index(today))
    return end - timedelta(days=WEEKS * 7 - 1), end


def level(count):
    if count == 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 9:
        return 3
    return 4


def fetch_counts(entity, start):
    """Map of date -> number of runs created that day, across all projects."""
    import wandb

    api = wandb.Api(timeout=60)
    cutoff = f"{start.isoformat()}T00:00:00Z"
    counts = Counter()
    projects = 0

    for project in api.projects(entity):
        projects += 1
        runs = api.runs(
            f"{entity}/{project.name}",
            filters={"createdAt": {"$gte": cutoff}},
            per_page=500,
        )
        for run in runs:
            raw = run.created_at
            if not raw:
                continue
            # created_at is ISO 8601, sometimes with a trailing Z.
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            counts[stamp.date()] += 1

    print(f"scanned {projects} projects, {sum(counts.values())} runs", file=sys.stderr)
    return counts


def render(counts, start, end, entity):
    width = PAD_LEFT + WEEKS * PITCH + 10
    height = PAD_TOP + 7 * PITCH + 34

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Weights &amp; Biases run activity for {entity}">',
        "<style>",
        "  text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', "
        "Helvetica, Arial, sans-serif; font-size: 9px; fill: #656d76; }",
    ]
    for i, color in enumerate(LIGHT):
        out.append(f"  .l{i} {{ fill: {color}; }}")
    out.append("  @media (prefers-color-scheme: dark) {")
    out.append("    text { fill: #7d8590; }")
    for i, color in enumerate(DARK):
        out.append(f"    .l{i} {{ fill: {color}; }}")
    out.append("  }")
    out.append("</style>")

    # Day-of-week labels, matching GitHub's every-other-row convention.
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = PAD_TOP + row * PITCH + CELL - 2
        out.append(f'<text x="0" y="{y}">{label}</text>')

    total = 0
    seen_months = set()
    day = start
    while day <= end:
        col = (day - start).days // 7
        row = sunday_index(day)
        x = PAD_LEFT + col * PITCH
        y = PAD_TOP + row * PITCH

        # Month label sits above the first column that month appears in.
        if day.month not in seen_months and day.day <= 7 and col < WEEKS - 1:
            seen_months.add(day.month)
            out.append(f'<text x="{x}" y="{PAD_TOP - 6}">{MONTHS[day.month - 1]}</text>')

        count = counts.get(day, 0)
        total += count
        noun = "run" if count == 1 else "runs"
        out.append(
            f'<rect class="l{level(count)}" x="{x}" y="{y}" width="{CELL}" '
            f'height="{CELL}" rx="2" ry="2">'
            f"<title>{count} {noun} on {day.isoformat()}</title></rect>"
        )
        day += timedelta(days=1)

    # Footer: total on the left, Less/More legend on the right.
    base = PAD_TOP + 7 * PITCH + 13
    out.append(f'<text x="{PAD_LEFT}" y="{base}">{total} runs in the last year</text>')

    legend_x = width - 10 - (5 * PITCH + 62)
    out.append(f'<text x="{legend_x}" y="{base}">Less</text>')
    for i in range(5):
        x = legend_x + 26 + i * PITCH
        out.append(
            f'<rect class="l{i}" x="{x}" y="{base - 9}" width="{CELL}" '
            f'height="{CELL}" rx="2" ry="2"/>'
        )
    out.append(f'<text x="{legend_x + 26 + 5 * PITCH + 3}" y="{base}">More</text>')

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entity", default=os.environ.get("WANDB_ENTITY", "yandabao"))
    parser.add_argument("--out", default="wandb-activity.svg")
    parser.add_argument("--placeholder", action="store_true",
                        help="render an empty grid without calling the API")
    args = parser.parse_args()

    start, end = window(date.today())
    counts = {} if args.placeholder else fetch_counts(args.entity, start)

    with open(args.out, "w") as fh:
        fh.write(render(counts, start, end, args.entity))
    print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
