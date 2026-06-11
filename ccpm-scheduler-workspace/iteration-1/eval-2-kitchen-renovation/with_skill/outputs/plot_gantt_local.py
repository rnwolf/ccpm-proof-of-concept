#!/usr/bin/env python3
"""Render a CCPM schedule.csv as a buffer-aware Gantt chart PNG.

Usage: python plot_gantt.py schedule.csv gantt.png [--title "My project"]

Color code: critical chain = firebrick, feeding chains = steelblue shades,
buffers = gold with hatching, other tasks = grey.
"""
import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def main(schedule_path, out_path, title="CCPM Schedule"):
    with open(schedule_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["start"], r["finish"] = int(r["start"]), int(r["finish"])

    # order: by start, then finish — buffers stay next to their chains
    rows.sort(key=lambda r: (r["start"], r["finish"], r["id"]))

    feeding_chains = sorted({r["chain"] for r in rows if r["chain"].startswith("feeding")})
    feed_cmap = matplotlib.colormaps["tab10"]
    feed_color = {c: feed_cmap(2 + i % 8) for i, c in enumerate(feeding_chains)}

    fig, ax = plt.subplots(figsize=(11, 0.5 * len(rows) + 2))
    yticks, ylabels = [], []
    for i, r in enumerate(rows):
        y = len(rows) - i
        dur = r["finish"] - r["start"]
        if r["type"] == "project_buffer":
            color, hatch = "gold", "//"
        elif r["type"] == "feeding_buffer":
            color, hatch = "khaki", "//"
        elif r["chain"] == "critical":
            color, hatch = "firebrick", None
        elif r["chain"] in feed_color:
            color, hatch = feed_color[r["chain"]], None
        else:
            color, hatch = "grey", None
        ax.barh(y, dur, left=r["start"], height=0.6, color=color,
                hatch=hatch, edgecolor="black", linewidth=0.5)
        res = (r.get("resources") or "").replace(";", ",")
        if res:
            ax.text(r["finish"] + 0.2, y, res, va="center", fontsize=8, color="dimgrey")
        yticks.append(y)
        ylabels.append(f"{r['id']}  {r.get('name', '')}")

    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=9)
    ax.set_xlabel("Working day")
    ax.set_title(title)
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    ax.legend(handles=[
        Patch(facecolor="firebrick", label="Critical chain"),
        Patch(facecolor="steelblue", label="Feeding chain"),
        Patch(facecolor="gold", hatch="//", label="Project buffer"),
        Patch(facecolor="khaki", hatch="//", label="Feeding buffer"),
    ], loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    title = "CCPM Schedule"
    if "--title" in sys.argv:
        i = sys.argv.index("--title")
        title = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    main(sys.argv[1], sys.argv[2], title)