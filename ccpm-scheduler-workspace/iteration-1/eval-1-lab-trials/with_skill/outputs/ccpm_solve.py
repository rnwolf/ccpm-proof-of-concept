#!/usr/bin/env python3
"""CCPM scheduler for the lab validation project.

Implements the deterministic spec in ccpm-scheduler/references/algorithm.md:
ALAP baseline -> resource leveling (earlier-only) -> critical chain trace
(precedence OR resource links) -> feeding chains -> 50%-rule buffers.

Durations in tasks.csv are ALREADY aggressive (user stripped padding),
so they are used as-is — no 50% cut is applied to task durations.

Usage: python ccpm_solve.py tasks.csv resources.csv schedule.csv
"""
import csv
import math
import sys
from collections import defaultdict


def split_ids(s):
    return [x for x in (s or "").replace(";", " ").replace(",", " ").split() if x]


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main(tasks_path, resources_path, out_path):
    raw = read_csv(tasks_path)
    resources = {r["id"]: int(r.get("capacity") or 1) for r in read_csv(resources_path)}

    tasks = {}
    for r in raw:
        tasks[r["id"]] = {
            "id": r["id"],
            "name": r["name"],
            # durations are already aggressive — use as given, do NOT cut
            "dur": int(r["duration_aggressive"]),
            "preds": split_ids(r.get("predecessors")),
            "res": split_ids(r.get("resources")),
        }

    # ---- Step 1: validate ----------------------------------------------
    errors = []
    for t in tasks.values():
        for p in t["preds"]:
            if p not in tasks:
                errors.append(f"{t['id']}: unknown predecessor {p}")
        for res in t["res"]:
            if res not in resources:
                errors.append(f"{t['id']}: unknown resource {res}")
        if t["dur"] <= 0:
            errors.append(f"{t['id']}: non-positive duration")
    # cycle check via topological sort
    indeg = {tid: len(t["preds"]) for tid, t in tasks.items()}
    succs = defaultdict(list)
    for t in tasks.values():
        for p in t["preds"]:
            succs[p].append(t["id"])
    queue = sorted([tid for tid, d in indeg.items() if d == 0])
    topo = []
    indeg2 = dict(indeg)
    while queue:
        n = queue.pop(0)
        topo.append(n)
        for s in sorted(succs[n]):
            indeg2[s] -= 1
            if indeg2[s] == 0:
                queue.append(s)
    if len(topo) != len(tasks):
        errors.append("dependency cycle detected")
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    # virtual END for multiple sinks
    sinks = [tid for tid in tasks if not succs[tid]]
    end_preds = sinks

    # ---- Step 2: ALAP baseline -----------------------------------------
    es, ef = {}, {}
    for tid in topo:
        t = tasks[tid]
        es[tid] = max((ef[p] for p in t["preds"]), default=0)
        ef[tid] = es[tid] + t["dur"]
    T = max(ef[s] for s in end_preds)
    ls, lf = {}, {}
    for tid in reversed(topo):
        t = tasks[tid]
        lf[tid] = min((ls[s] for s in succs[tid]), default=T)
        ls[tid] = lf[tid] - t["dur"]
    start = {tid: ls[tid] for tid in tasks}

    def finish(tid):
        return start[tid] + tasks[tid]["dur"]

    # longest precedence path through each task (aggressive durations)
    lp_to = {}    # longest path from any start ending at tid (inclusive)
    for tid in topo:
        lp_to[tid] = tasks[tid]["dur"] + max((lp_to[p] for p in tasks[tid]["preds"]), default=0)
    lp_from = {}  # longest path starting at tid (inclusive) to any sink
    for tid in reversed(topo):
        lp_from[tid] = tasks[tid]["dur"] + max((lp_from[s] for s in succs[tid]), default=0)
    path_through = {tid: lp_to[tid] + lp_from[tid] - tasks[tid]["dur"] for tid in tasks}

    # ---- Step 3: resource leveling (earlier-only) ------------------------
    def find_conflicts():
        conflicts = []
        for res, cap in resources.items():
            users = sorted([tid for tid in tasks if res in tasks[tid]["res"]])
            for i in range(len(users)):
                for j in range(i + 1, len(users)):
                    a, b = users[i], users[j]
                    if start[a] < finish(b) and start[b] < finish(a):
                        # capacity 1 assumed for pairwise conflicts; with cap>1
                        # check day-level demand
                        if cap > 1:
                            ov_lo = max(start[a], start[b])
                            ov_hi = min(finish(a), finish(b))
                            demand_ok = True
                            for day in range(ov_lo, ov_hi):
                                d = sum(1 for u in users if start[u] <= day < finish(u))
                                if d > cap:
                                    demand_ok = False
                                    break
                            if demand_ok:
                                continue
                        overlap_end = min(finish(a), finish(b))
                        conflicts.append((overlap_end, res, a, b))
        return conflicts

    def drag_preds(tid):
        for p in tasks[tid]["preds"]:
            if finish(p) > start[tid]:
                start[p] = start[tid] - tasks[p]["dur"]
                drag_preds(p)

    for _ in range(10000):
        conflicts = find_conflicts()
        if not conflicts:
            break
        # latest overlap end; tie-break resource id asc, then task ids asc
        conflicts.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
        _, res, a, b = conflicts[0]
        # keep the task with the longer total path through it
        ka, kb = path_through[a], path_through[b]
        if ka > kb:
            stay, move = a, b
        elif kb > ka:
            stay, move = b, a
        elif finish(a) != finish(b):
            stay, move = (a, b) if finish(a) > finish(b) else (b, a)
        else:
            stay, move = (a, b) if a < b else (b, a)
        start[move] = start[stay] - tasks[move]["dur"]
        drag_preds(move)
    else:
        print("leveling did not converge")
        sys.exit(1)

    # ---- Step 4: critical chain ------------------------------------------
    def chain_candidates(tid):
        cands = []
        for o in tasks:
            if o == tid or finish(o) != start[tid]:
                continue
            is_pred = o in tasks[tid]["preds"]
            shares = bool(set(tasks[o]["res"]) & set(tasks[tid]["res"]))
            if is_pred or shares:
                cands.append((o, is_pred))
        return cands

    reach_memo = {}

    def chain_reach(tid):
        """Earliest time the backward chain from tid extends to."""
        if tid in reach_memo:
            return reach_memo[tid]
        reach_memo[tid] = start[tid]  # guard against cycles
        cands = chain_candidates(tid)
        if cands:
            reach_memo[tid] = min(chain_reach(o) for o, _ in cands)
        return reach_memo[tid]

    # start at task with latest finish; tie-break: earliest chain reach, then id
    last = sorted(tasks, key=lambda t: (-finish(t), chain_reach(t), t))[0]
    chain = [last]
    cur = last
    while True:
        cands = chain_candidates(cur)
        if not cands:
            break
        # earliest reach; tie-break precedence link over resource, smaller id
        cands.sort(key=lambda c: (chain_reach(c[0]), not c[1], c[0]))
        cur = cands[0][0]
        chain.append(cur)
    critical = list(reversed(chain))
    cc_set = set(critical)

    # ---- Step 5: feeding chains -------------------------------------------
    # join point of a non-critical task: BFS over successors, stop at critical
    # tasks; earliest-start critical task reached, else END
    def join_of(tid):
        seen, frontier, joins = set(), [tid], []
        while frontier:
            n = frontier.pop(0)
            for s in succs[n]:
                if s in seen:
                    continue
                seen.add(s)
                if s in cc_set:
                    joins.append(s)
                else:
                    frontier.append(s)
        if joins:
            return min(joins, key=lambda j: (start[j], j))
        return "END"

    noncrit = [tid for tid in topo if tid not in cc_set]
    groups = defaultdict(list)
    for tid in noncrit:
        groups[join_of(tid)].append(tid)

    # within a group, maximal precedence paths; shared prefixes go to the
    # longest chain (tie-break smaller chain-head id)
    feeding = []  # list of (join, [task ids in topo order])
    for join, members in groups.items():
        mset = set(members)
        # build all maximal paths within the group
        heads = [m for m in members if not (set(tasks[m]["preds"]) & mset)]
        paths = []

        def extend(path):
            tails = [s for s in succs[path[-1]] if s in mset]
            if not tails:
                paths.append(path)
                return
            for s in sorted(tails):
                extend(path + [s])

        for h in sorted(heads):
            extend([h])
        # assign each task to exactly one chain: longest path first
        paths.sort(key=lambda p: (-sum(tasks[t]["dur"] for t in p), p[0]))
        assigned = set()
        for p in paths:
            exclusive = [t for t in p if t not in assigned]
            if exclusive:
                feeding.append((join, exclusive))
                assigned.update(exclusive)

    # number feeding chains by join-point start ascending
    def join_start(j):
        return T if j == "END" else start[j]

    feeding.sort(key=lambda fc: (join_start(fc[0]), fc[1][0]))

    # ---- Step 6: buffers ----------------------------------------------------
    cc_sum = sum(tasks[t]["dur"] for t in critical)
    PB = math.ceil(0.5 * cc_sum)
    project_end = max(finish(t) for t in critical)

    buffers = []
    chain_label = {t: "critical" for t in critical}
    notes = []
    for n, (join, members) in enumerate(feeding, 1):
        label = f"feeding-{n}"
        for t in members:
            chain_label[t] = label
        FB = math.ceil(0.5 * sum(tasks[t]["dur"] for t in members))
        jstart = project_end if join == "END" else start[join]
        chain_fin = max(finish(t) for t in members)
        need = chain_fin - (jstart - FB)
        if need > 0:
            # max uniform earlier shift limited by predecessors outside chain
            mset = set(members)
            allowed = need
            for t in members:
                ext = [finish(p) for p in tasks[t]["preds"] if p not in mset]
                if ext:
                    allowed = min(allowed, start[t] - max(ext))
            allowed = max(allowed, 0)
            for t in members:
                start[t] -= allowed
            if allowed < need:
                notes.append(
                    f"feeding chain {label} ({'->'.join(members)}) could only "
                    f"shift {allowed} of {need} days earlier (precedence-bound); "
                    f"its buffer extends past the join point into the project-"
                    f"buffer window")
            chain_fin = max(finish(t) for t in members)
        buffers.append({
            "id": f"FB{n}", "name": f"Feeding buffer {n}",
            "type": "feeding_buffer", "chain": label,
            "start": chain_fin, "finish": chain_fin + FB, "duration": FB,
            "resources": "",
        })

    # re-level moved tasks only (earlier-only) — simple recheck
    if find_conflicts():
        # resolve with the same loop (all moves are earlier-only)
        for _ in range(10000):
            conflicts = find_conflicts()
            if not conflicts:
                break
            conflicts.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
            _, res, a, b = conflicts[0]
            stay, move = (a, b) if path_through[a] >= path_through[b] else (b, a)
            start[move] = start[stay] - tasks[move]["dur"]
            drag_preds(move)

    project_end = max(finish(t) for t in critical)
    buffers.append({
        "id": "PB", "name": "Project buffer",
        "type": "project_buffer", "chain": "critical",
        "start": project_end, "finish": project_end + PB, "duration": PB,
        "resources": "",
    })

    # global right-shift if negative starts
    min_start = min(min(start.values()), min(b["start"] for b in buffers))
    if min_start < 0:
        for tid in start:
            start[tid] -= min_start
        for b in buffers:
            b["start"] -= min_start
            b["finish"] -= min_start

    # ---- Step 7: output -----------------------------------------------------
    rows = []
    for tid in tasks:
        rows.append({
            "id": tid, "name": tasks[tid]["name"], "type": "task",
            "chain": chain_label.get(tid, "none"),
            "start": start[tid], "finish": finish(tid),
            "duration": tasks[tid]["dur"],
            "resources": ";".join(tasks[tid]["res"]),
        })
    rows += buffers
    rows.sort(key=lambda r: (r["start"], r["finish"], r["id"]))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name", "type", "chain", "start", "finish", "duration", "resources"])
        w.writeheader()
        w.writerows(rows)

    print(f"critical chain: {' -> '.join(critical)} (length {cc_sum})")
    print(f"project buffer: {PB} days; promised completion: day {project_end + PB}")
    for n, (join, members) in enumerate(feeding, 1):
        print(f"feeding-{n}: {' -> '.join(members)} joins at {join}")
    for note in notes:
        print("NOTE:", note)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
