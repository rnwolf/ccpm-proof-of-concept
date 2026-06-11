#!/usr/bin/env python3
"""Render a CCPM schedule.csv as a buffer-aware Gantt chart PNG with
dependency-link arrows and a resource-utilization sub-chart on the same
time axis.

Usage: python plot_gantt.py schedule.csv gantt.png [--title "My project"]
                            [--resources resources.csv] [--no-utilization]
                            [--no-links]

Dependency links are read from an optional `predecessors` column in
schedule.csv. Link notation: `A` (Finish-to-Start, the default), `A:SS`,
`A:FF`, `A:SF`, with optional lag, e.g. `A:SS+2`. Multiple links are
separated by `;`. Arrows are drawn for every link; non-FS links carry a
small SS/FF/SF label since readers assume FS by default.

Buffer attachments use the CCPM-specific types `:PB` (project buffer) and
`:FB` (feeding buffer). They are drawn dashed, because a buffer is not work
driven by its predecessor: during execution the buffer's END stays anchored
(to the commitment date for PB, to the protected critical-chain task for FB)
and predecessor slippage consumes the buffer from the left instead of pushing
it. Buffer bars get a "<id> <n>d" label and the project buffer ends in a
commitment-date diamond.

The utilization panel shows, per resource per day, how much capacity is used.
Within capacity = steelblue; over capacity = red (a red block means the
leveling step failed). Pass --resources to use real capacities; default is 1.

Color code (Gantt): critical chain = firebrick, feeding chains = colored,
buffers = gold/khaki with hatching, other tasks = grey.
"""
import csv
import re
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

LINK_RE = re.compile(r"^(?P<id>[^:+\s]+)(?::(?P<type>FS|SS|FF|SF|PB|FB))?(?P<lag>[+-]\d+)?$", re.I)


def split_ids(s):
    return [x for x in (s or "").replace(";", " ").replace(",", " ").split() if x]


def parse_links(s):
    """'A;B:SS+2' -> [('A','FS',0), ('B','SS',2)]"""
    links = []
    for tok in split_ids(s):
        m = LINK_RE.match(tok)
        if not m:
            continue
        links.append((m.group("id"), (m.group("type") or "FS").upper(),
                      int(m.group("lag") or 0)))
    return links


def main(schedule_path, out_path, title="CCPM Schedule",
         resources_path=None, show_util=True, show_links=True):
    with open(schedule_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["start"], r["finish"] = int(r["start"]), int(r["finish"])

    capacity = {}
    if resources_path:
        with open(resources_path, newline="", encoding="utf-8-sig") as f:
            for rr in csv.DictReader(f):
                capacity[rr["id"]] = int(rr.get("capacity") or 1)

    # daily demand per resource (tasks only - buffers consume no resources)
    demand = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["type"] != "task":
            continue
        for res in split_ids(r.get("resources")):
            for day in range(r["start"], r["finish"]):
                demand[res][day] += 1
    resources = sorted(set(demand) | set(capacity))
    show_util = show_util and bool(resources)

    rows.sort(key=lambda r: (r["start"], r["finish"], r["id"]))
    feeding_chains = sorted({r["chain"] for r in rows if r["chain"].startswith("feeding")})
    feed_cmap = matplotlib.colormaps["tab10"]
    feed_color = {c: feed_cmap(2 + i % 8) for i, c in enumerate(feeding_chains)}

    t_end = max(r["finish"] for r in rows)
    n_res = len(resources)
    if show_util:
        fig, (ax, axu) = plt.subplots(
            2, 1, sharex=True,
            figsize=(11, 0.5 * len(rows) + 0.45 * n_res + 3),
            gridspec_kw={"height_ratios": [len(rows), max(n_res, 2)],
                         "hspace": 0.12})
    else:
        fig, ax = plt.subplots(figsize=(11, 0.5 * len(rows) + 2))
        axu = None

    # ---------------- Gantt panel ----------------
    ypos = {}
    yticks, ylabels = [], []
    for i, r in enumerate(rows):
        y = len(rows) - i
        ypos[r["id"]] = y
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
                hatch=hatch, edgecolor="black", linewidth=0.5, zorder=2)
        res = (r.get("resources") or "").replace(";", ",")
        if res:
            ax.text(r["finish"] + 0.2, y, res, va="center", fontsize=8,
                    color="dimgrey", zorder=3)
        if r["type"] in ("project_buffer", "feeding_buffer"):
            ax.text(r["start"] + dur / 2, y, f"{r['id']} {dur}d",
                    ha="center", va="center", fontsize=7.5, zorder=3)
            if r["type"] == "project_buffer":
                ax.plot([r["finish"]], [y], marker="D", color="black",
                        markersize=7, zorder=5)
                ax.text(r["finish"], y - 0.45, "commitment",
                        ha="right", va="top", fontsize=7, color="black", zorder=5)
        yticks.append(y)
        ylabels.append(f"{r['id']}  {r.get('name', '')}")

    # ---------------- dependency arrows ----------------
    if show_links:
        byid = {r["id"]: r for r in rows}
        for r in rows:
            for pid, ltype, lag in parse_links(r.get("predecessors", "")):
                p = byid.get(pid)
                if p is None:
                    continue
                # anchor x on each bar depends on link type
                x_from = p["finish"] if ltype in ("FS", "FF", "PB", "FB") else p["start"]
                x_to = r["start"] if ltype in ("FS", "SS", "PB", "FB") else r["finish"]
                y_from, y_to = ypos[pid], ypos[r["id"]]
                going_down = y_to < y_from
                # leave pred horizontally, arrive succ vertically at bar edge
                edge = 0.3 if going_down else -0.3
                if ltype in ("SS", "SF"):
                    y_from -= edge  # exit along the pred bar edge facing the successor
                buffer_link = ltype in ("PB", "FB")
                ax.annotate(
                    "", xy=(x_to, y_to + edge), xytext=(x_from, y_from),
                    arrowprops=dict(arrowstyle="->", color="0.25", lw=1.0,
                                    linestyle=(0, (3, 2)) if buffer_link else "solid",
                                    shrinkA=0, shrinkB=0,
                                    connectionstyle="angle,angleA=0,angleB=90,rad=2"),
                    zorder=4)
                if ltype != "FS" or lag:
                    lbl = ltype if ltype != "FS" else ""
                    if lag:
                        lbl += f"{lag:+d}"
                    ax.text(x_to + 0.15, (y_from + y_to + edge) / 2, lbl,
                            fontsize=6.5, color="0.25", va="center", zorder=4)

    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=9)
    ax.set_title(title, loc="left")
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    ax.set_xlim(0, t_end + 1)
    ax.set_ylim(0.3, len(rows) + 0.7)
    ax.legend(handles=[
        Patch(facecolor="firebrick", label="Critical chain"),
        Patch(facecolor="steelblue", label="Feeding chain"),
        Patch(facecolor="gold", hatch="//", label="Project buffer"),
        Patch(facecolor="khaki", hatch="//", label="Feeding buffer"),
    ], loc="lower right", bbox_to_anchor=(1.0, 1.02), ncol=4, fontsize=8, frameon=False)

    # ---------------- Resource utilization panel ----------------
    if axu is not None:
        for j, res in enumerate(resources):
            y = n_res - j
            cap = capacity.get(res, 1)
            for day in range(t_end):
                d = demand[res].get(day, 0)
                if d == 0:
                    continue
                over = d > cap
                axu.barh(y, 1, left=day, height=0.7,
                         color="red" if over else "steelblue",
                         alpha=min(1.0, 0.45 + 0.55 * d / max(cap, 1)),
                         edgecolor="white", linewidth=0.3)
                if cap > 1 or over:
                    axu.text(day + 0.5, y, str(d), ha="center", va="center",
                             fontsize=6, color="white")
        axu.set_yticks([n_res - j for j in range(n_res)])
        axu.set_yticklabels(
            [f"{r} (cap {capacity.get(r, 1)})" for r in resources], fontsize=9)
        axu.set_ylim(0.4, n_res + 0.6)
        axu.set_title("Resource utilization", fontsize=10)
        axu.grid(axis="x", linestyle=":", alpha=0.5)
        axu.set_xlabel("Working day")
    else:
        ax.set_xlabel("Working day")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    argv = sys.argv
    if len(argv) < 3:
        print(__doc__)
        sys.exit(2)
    title, resources_path, show_util, show_links = "CCPM Schedule", None, True, True
    if "--title" in argv:
        i = argv.index("--title"); title = argv[i + 1]; del argv[i:i + 2]
    if "--resources" in argv:
        i = argv.index("--resources"); resources_path = argv[i + 1]; del argv[i:i + 2]
    if "--no-utilization" in argv:
        argv.remove("--no-utilization"); show_util = False
    if "--no-links" in argv:
        argv.remove("--no-links"); show_links = False
    main(argv[1], argv[2], title, resources_path, show_util, show_links)
