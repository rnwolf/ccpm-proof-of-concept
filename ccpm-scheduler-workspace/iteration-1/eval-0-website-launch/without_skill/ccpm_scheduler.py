#!/usr/bin/env python3
"""CCPM scheduler for the website relaunch project.

Method:
1. Cut 'safe' (90%-confidence) estimates to focused 50% estimates (the classic
   CCPM cut-and-paste / half-duration rule).
2. Build a resource-levelled ASAP schedule (each resource has capacity 1).
3. Identify the critical chain = longest path of dependency AND resource links.
4. Project buffer = 50% of critical chain length, appended at the end.
5. Feeding buffers = 50% of each feeding chain, inserted where the chain joins
   the critical chain (truncated if there is not enough slack).
"""
import csv, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
INP = "/sessions/upbeat-fervent-fermat/mnt/ccpm-proof-of-concept/ccpm-scheduler-workspace/inputs/website-launch"
OUT = os.path.join(HERE, "outputs")

# ---------- load ----------
tasks = {}
order = []
with open(os.path.join(INP, "tasks.csv")) as f:
    for row in csv.DictReader(f):
        if not row["id"]:
            continue
        tid = row["id"].strip()
        tasks[tid] = {
            "name": row["name"].strip(),
            "safe": float(row["duration_safe"]),
            "focused": float(row["duration_safe"]) / 2.0,   # 50% cut
            "preds": [p.strip() for p in row["predecessors"].split(";") if p.strip()],
            "resource": row["resources"].strip(),
        }
        order.append(tid)

resources = {}
with open(os.path.join(INP, "resources.csv")) as f:
    for row in csv.DictReader(f):
        if row["id"]:
            resources[row["id"].strip()] = int(row["capacity"])

# ---------- resource-levelled ASAP schedule ----------
# capacity is 1 everywhere; greedy: at each step schedule the ready task with
# the earliest feasible start; ties broken by longest remaining downstream work.
succs = defaultdict(list)
for tid, t in tasks.items():
    for p in t["preds"]:
        succs[p].append(tid)

def downstream(tid, memo={}):
    if tid in memo:
        return memo[tid]
    memo[tid] = tasks[tid]["focused"] + max((downstream(s) for s in succs[tid]), default=0.0)
    return memo[tid]

res_free = defaultdict(float)          # when each (unit-capacity) resource is next free
res_last = {}                          # last task scheduled on each resource
start, end, res_link = {}, {}, {}      # res_link: task -> task it waited on for the resource
unscheduled = set(tasks)
while unscheduled:
    ready = [t for t in unscheduled if all(p in end for p in tasks[t]["preds"])]
    def est(t):
        dep = max((end[p] for p in tasks[t]["preds"]), default=0.0)
        return max(dep, res_free[tasks[t]["resource"]])
    ready.sort(key=lambda t: (est(t), -downstream(t)))
    t = ready[0]
    dep_ready = max((end[p] for p in tasks[t]["preds"]), default=0.0)
    r = tasks[t]["resource"]
    s = max(dep_ready, res_free[r])
    if res_free[r] > dep_ready and r in res_last:
        res_link[t] = res_last[r]      # start was driven by the resource, not a predecessor
    start[t], end[t] = s, s + tasks[t]["focused"]
    res_free[r] = end[t]
    res_last[r] = t
    unscheduled.discard(t)

# ---------- critical chain ----------
final = max(end, key=end.get)
cc = [final]
cur = final
while True:
    drivers = [p for p in tasks[cur]["preds"] if abs(end[p] - start[cur]) < 1e-9]
    if not drivers and cur in res_link and abs(end[res_link[cur]] - start[cur]) < 1e-9:
        drivers = [res_link[cur]]
    if not drivers:
        break
    cur = max(drivers, key=lambda p: end[p] - 0)  # any zero-slack driver
    cc.append(cur)
cc.reverse()
cc_len = sum(tasks[t]["focused"] for t in cc)
project_buffer = cc_len * 0.5
promised = end[final] + project_buffer

# ---------- feeding chains & buffers ----------
cc_set = set(cc)
feeding = []  # (chain list, joins_into, buffer_size, gap_available)
def chain_back(tid):
    """walk back through non-CC predecessors picking the driving path"""
    chain = [tid]
    cur = tid
    while True:
        preds = [p for p in tasks[cur]["preds"] if p not in cc_set]
        if not preds:
            break
        cur = max(preds, key=lambda p: end[p])
        chain.append(cur)
    chain.reverse()
    return chain

seen = set()
for c in cc:
    for p in tasks[c]["preds"]:
        if p not in cc_set and p not in seen:
            ch = chain_back(p)
            seen.update(ch)
            length = sum(tasks[t]["focused"] for t in ch)
            fb = length * 0.5
            gap = start[c] - end[p]
            feeding.append({"chain": ch, "into": c, "size": fb, "gap": gap,
                            "placed": min(fb, gap)})

# ---------- write schedule.csv ----------
rows = []
for tid in order:
    t = tasks[tid]
    rows.append({
        "id": tid, "name": t["name"], "resource": t["resource"],
        "duration_safe": t["safe"], "duration_focused": t["focused"],
        "start_day": start[tid], "end_day": end[tid],
        "on_critical_chain": "yes" if tid in cc_set else "no",
        "type": "task",
    })
for fb in feeding:
    rows.append({
        "id": f"FB-{fb['into']}", "name": f"Feeding buffer ({'+'.join(fb['chain'])} -> {fb['into']})",
        "resource": "", "duration_safe": "", "duration_focused": fb["placed"],
        "start_day": end[fb["chain"][-1]], "end_day": end[fb["chain"][-1]] + fb["placed"],
        "on_critical_chain": "no", "type": "feeding_buffer",
    })
rows.append({
    "id": "PB", "name": "Project buffer", "resource": "",
    "duration_safe": "", "duration_focused": project_buffer,
    "start_day": end[final], "end_day": promised,
    "on_critical_chain": "yes", "type": "project_buffer",
})
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "schedule.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# ---------- Gantt chart ----------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

plot_rows = []  # (label, start, dur, color, hatch)
C_CC, C_NORM, C_FB, C_PB = "#d62728", "#1f77b4", "#ffbf00", "#2ca02c"
for tid in sorted(order, key=lambda t: (start[t], end[t])):
    t = tasks[tid]
    col = C_CC if tid in cc_set else C_NORM
    plot_rows.append((f"{tid} {t['name']} [{t['resource']}]", start[tid],
                      t["focused"], col, None))
    # insert feeding buffer bar right after the last task of its chain
    for fb in feeding:
        if fb["chain"][-1] == tid and fb["placed"] > 0:
            plot_rows.append((f"FB → {fb['into']} (feeding buffer)",
                              end[tid], fb["placed"], C_FB, "//"))
plot_rows.append(("PB Project buffer", end[final], project_buffer, C_PB, "//"))

fig, ax = plt.subplots(figsize=(11, 0.55 * len(plot_rows) + 2))
for i, (label, s, d, col, hatch) in enumerate(plot_rows):
    ax.barh(i, d, left=s, height=0.6, color=col, hatch=hatch,
            edgecolor="black", linewidth=0.6)
    ax.text(s + d / 2, i, f"{d:g}d", va="center", ha="center",
            fontsize=8, color="white" if hatch is None else "black", fontweight="bold")
ax.set_yticks(range(len(plot_rows)))
ax.set_yticklabels([r[0] for r in plot_rows], fontsize=9)
ax.invert_yaxis()
ax.set_xlabel("Working day")
ax.axvline(promised, color=C_PB, linestyle="--", linewidth=1.2)
ax.text(promised, -0.8, f"  Promised: day {promised:g}", color=C_PB, fontsize=9, fontweight="bold")
ax.axvline(end[final], color=C_CC, linestyle=":", linewidth=1.2)
ax.text(end[final], len(plot_rows) - 0.2, f"CC ends: day {end[final]:g} ", color=C_CC,
        fontsize=9, ha="right")
ax.set_xlim(0, math.ceil(promised) + 1)
ax.grid(axis="x", alpha=0.3)
ax.set_title("Website relaunch — Critical Chain (CCPM) schedule\n"
             "Focused durations = 50% of safe estimates; buffers absorb the removed safety")
ax.legend(handles=[Patch(color=C_CC, label="Critical chain"),
                   Patch(color=C_NORM, label="Feeding task"),
                   Patch(facecolor=C_FB, hatch="//", edgecolor="black", label="Feeding buffer"),
                   Patch(facecolor=C_PB, hatch="//", edgecolor="black", label="Project buffer")],
          loc="lower left", fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(OUT, "gantt.png"), dpi=150)

# ---------- console report ----------
print("Critical chain:", " -> ".join(cc), f"({cc_len:g} days)")
print(f"Project buffer: {project_buffer:g} days")
print(f"Critical chain finishes day {end[final]:g}; promised completion day {promised:g}")
for fb in feeding:
    print(f"Feeding chain {'+'.join(fb['chain'])} -> {fb['into']}: "
          f"buffer wanted {fb['size']:g}, gap {fb['gap']:g}, placed {fb['placed']:g}")
for tid in order:
    print(f"{tid:3s} {tasks[tid]['name']:18s} {tasks[tid]['resource']:9s} "
          f"start {start[tid]:5.1f}  end {end[tid]:5.1f}  "
          f"{'CC' if tid in cc_set else ''}")
