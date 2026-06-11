#!/usr/bin/env python3
"""CCPM scheduler per ccpm-scheduler skill references/algorithm.md.

Usage: python ccpm_schedule.py tasks.csv resources.csv schedule.csv
"""
import csv
import math
import sys
from collections import defaultdict

END = "__END__"


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def split_ids(s):
    return [x for x in (s or "").replace(";", " ").replace(",", " ").split() if x]


def main(tasks_path, resources_path, out_path):
    raw_tasks = read_csv(tasks_path)
    raw_res = read_csv(resources_path)
    resources = {r["id"]: int(r.get("capacity") or 1) for r in raw_res}

    # ---- Step 0: normalize ----
    tasks = {}
    for t in raw_tasks:
        tid = t["id"].strip()
        safe = int(t["duration_safe"])
        agg_raw = (t.get("duration_aggressive") or "").strip()
        dur = int(agg_raw) if agg_raw else math.ceil(safe / 2)
        tasks[tid] = {
            "id": tid, "name": t["name"], "dur": dur, "safe": safe,
            "preds": split_ids(t.get("predecessors")),
            "res": split_ids(t.get("resources")),
        }

    # ---- Step 1: validate ----
    errors = []
    for t in tasks.values():
        for p in t["preds"]:
            if p not in tasks:
                errors.append(f"{t['id']}: unknown predecessor {p}")
        for r in t["res"]:
            if r not in resources:
                errors.append(f"{t['id']}: unknown resource {r}")
        if t["dur"] <= 0:
            errors.append(f"{t['id']}: non-positive duration")
    # cycle check (Kahn)
    indeg = {tid: 0 for tid in tasks}
    succs = defaultdict(list)
    for t in tasks.values():
        for p in t["preds"]:
            if p in tasks:
                succs[p].append(t["id"])
                indeg[t["id"]] += 1
    queue = [tid for tid, d in indeg.items() if d == 0]
    seen = 0
    deg = dict(indeg)
    while queue:
        n = queue.pop()
        seen += 1
        for s in succs[n]:
            deg[s] -= 1
            if deg[s] == 0:
                queue.append(s)
    if seen != len(tasks):
        errors.append("dependency cycle detected")
    if errors:
        for e in errors:
            print("VALIDATION ERROR:", e)
        sys.exit(1)

    sinks = [tid for tid in tasks if not succs[tid]]
    all_succs = dict(succs)

    # ---- Step 2: ALAP baseline ----
    # forward pass (topological)
    order = []
    deg = dict(indeg)
    queue = sorted([tid for tid, d in deg.items() if d == 0])
    while queue:
        n = queue.pop(0)
        order.append(n)
        for s in succs[n]:
            deg[s] -= 1
            if deg[s] == 0:
                queue.append(s)
        queue.sort()
    es = {}
    for tid in order:
        t = tasks[tid]
        es[tid] = max((es[p] + tasks[p]["dur"] for p in t["preds"]), default=0)
    T = max(es[tid] + tasks[tid]["dur"] for tid in tasks)
    lf = {}
    for tid in reversed(order):
        sl = [lf[s] - tasks[s]["dur"] for s in succs[tid]]
        lf[tid] = min(sl) if sl else T
    start = {tid: lf[tid] - tasks[tid]["dur"] for tid in tasks}

    def finish(tid):
        return start[tid] + tasks[tid]["dur"]

    # longest precedence path through each task (aggressive durations)
    # path_through = longest_to_start + dur + longest_to_end
    memo_fwd, memo_bwd = {}, {}

    def longest_before(tid):  # longest path of durations strictly before tid
        if tid not in memo_fwd:
            memo_fwd[tid] = max((longest_before(p) + tasks[p]["dur"] for p in tasks[tid]["preds"]), default=0)
        return memo_fwd[tid]

    def longest_after(tid):
        if tid not in memo_bwd:
            memo_bwd[tid] = max((longest_after(s) + tasks[s]["dur"] for s in succs[tid]), default=0)
        return memo_bwd[tid]

    def path_through(tid):
        return longest_before(tid) + tasks[tid]["dur"] + longest_after(tid)

    # ---- Step 3: resource leveling ----
    def shift_earlier(tid, new_start):
        """Move task earlier to new_start, dragging predecessors recursively."""
        start[tid] = new_start
        for p in tasks[tid]["preds"]:
            if finish(p) > start[tid]:
                shift_earlier(p, start[tid] - tasks[p]["dur"])

    def find_conflicts(restrict=None):
        confs = []
        by_res = defaultdict(list)
        for tid, t in tasks.items():
            for r in t["res"]:
                by_res[r].append(tid)
        for r, tids in by_res.items():
            cap = resources[r]
            if cap == 1:
                tids_sorted = sorted(tids)
                for i in range(len(tids_sorted)):
                    for j in range(i + 1, len(tids_sorted)):
                        a, b = tids_sorted[i], tids_sorted[j]
                        if restrict and a not in restrict and b not in restrict:
                            continue
                        if start[a] < finish(b) and start[b] < finish(a):
                            ov_end = min(finish(a), finish(b))
                            confs.append((ov_end, r, a, b))
            else:
                # capacity > 1: day-by-day demand
                days = defaultdict(list)
                for tid in tids:
                    for d in range(start[tid], finish(tid)):
                        days[d].append(tid)
                for d in sorted(days, reverse=True):
                    if len(days[d]) > cap:
                        involved = sorted(days[d])
                        confs.append((d + 1, r, involved[0], involved[1]))
                        break
        return confs

    def level(restrict=None):
        while True:
            confs = find_conflicts(restrict)
            if not confs:
                break
            # latest overlap end; tie-break resource id asc, then task ids asc
            confs.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
            _, r, a, b = confs[0]
            pa, pb = path_through(a), path_through(b)
            if pa > pb:
                stay, move = a, b
            elif pb > pa:
                stay, move = b, a
            elif finish(a) != finish(b):
                stay, move = (a, b) if finish(a) > finish(b) else (b, a)
            else:
                stay, move = (a, b) if a < b else (b, a)
            shift_earlier(move, start[stay] - tasks[move]["dur"])

    level()

    # ---- Step 4: critical chain ----
    chain_reach_memo = {}

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

    def chain_reach(tid):
        """Earliest time the backward chain from tid reaches."""
        if tid in chain_reach_memo:
            return chain_reach_memo[tid]
        chain_reach_memo[tid] = start[tid]  # guard against cycles
        best = start[tid]
        for o, _ in chain_candidates(tid):
            best = min(best, chain_reach(o))
        chain_reach_memo[tid] = best
        return best

    last = max(tasks, key=lambda tid: (finish(tid), -ord(tid[0])))
    # deterministic: latest finish, tie-break smaller id
    last = sorted(tasks, key=lambda tid: (-finish(tid), tid))[0]
    cc = [last]
    cur = last
    while True:
        cands = chain_candidates(cur)
        cands = [c for c in cands if c[0] not in cc]
        if not cands:
            break
        # earliest reach; tie-break precedence over resource, then smaller id
        cands.sort(key=lambda c: (chain_reach(c[0]), not c[1], c[0]))
        cur = cands[0][0]
        cc.append(cur)
    cc.reverse()
    cc_set = set(cc)

    # ---- Step 5: feeding chains ----
    # Enumerate maximal precedence paths over non-critical tasks. Each path's
    # join point is the earliest-starting critical successor of its last task
    # (or None = END). Longest path (sum of aggressive durations) claims shared
    # tasks; shorter branches keep only their exclusive tasks.
    noncrit = set(tid for tid in tasks if tid not in cc_set)
    paths = []

    def extend(path):
        tail = path[-1]
        nexts = [s for s in all_succs.get(tail, []) if s in noncrit]
        if not nexts:
            paths.append(list(path))
            return
        for s in sorted(nexts):
            extend(path + [s])

    heads = [m for m in sorted(noncrit) if not any(p in noncrit for p in tasks[m]["preds"])]
    for h in heads:
        extend([h])

    def path_join(p):
        crit_succs = [s for s in all_succs.get(p[-1], []) if s in cc_set]
        if not crit_succs:
            return None
        return sorted(crit_succs, key=lambda j: (start[j], j))[0]

    paths.sort(key=lambda p: (-sum(tasks[x]["dur"] for x in p), p[0]))
    chains = []  # (join, [exclusive task ids in precedence order])
    claimed = set()
    for p in paths:
        exclusive = [x for x in p if x not in claimed]
        if exclusive:
            claimed.update(exclusive)
            chains.append((path_join(p), exclusive))

    # number chains by join-point start ascending (END joins last)
    chains.sort(key=lambda c: (start[c[0]] if c[0] else 10**9, c[1][0]))
    feeding = []
    for i, (join, members) in enumerate(chains, 1):
        feeding.append({"n": i, "join": join, "tasks": members})

    # ---- Step 6: buffers ----
    pb_size = math.ceil(0.5 * sum(tasks[t]["dur"] for t in cc))
    buffers = []
    for fc in feeding:
        fb = math.ceil(0.5 * sum(tasks[t]["dur"] for t in fc["tasks"]))
        join = fc["join"]
        deadline = start[join] - fb if join else max(finish(t) for t in tasks if t in cc_set) - fb
        # shift the chain's terminal tasks earlier by the overlap; predecessors
        # (inside or outside the chain) are dragged only by the minimum needed
        # (cf. worked example: C unchanged when E shifts)
        cset = set(fc["tasks"])
        terminals = [t for t in fc["tasks"] if not any(s in cset for s in all_succs.get(t, []))]
        for t in terminals:
            if finish(t) > deadline:
                shift_earlier(t, deadline - tasks[t]["dur"])
        fc["fb"] = fb
        # re-level restricted to moved tasks (may only move earlier)
        level(restrict=cset)
        fc["fb_start"] = max(finish(t) for t in fc["tasks"])
        buffers.append(fc)

    cc_finish = max(finish(t) for t in cc)
    pb_start = cc_finish

    # global shift so min start = 0
    min_start = min(min(start.values()), min(b["fb_start"] for b in buffers) if buffers else 0)
    if min_start < 0:
        d = -min_start
        for tid in start:
            start[tid] += d
        for b in buffers:
            b["fb_start"] += d
        pb_start += d

    # ---- Step 7: output ----
    chain_of = {}
    for t in cc:
        chain_of[t] = "critical"
    for b in buffers:
        for t in b["tasks"]:
            chain_of[t] = f"feeding-{b['n']}"

    rows = []
    for tid in sorted(tasks, key=lambda x: (start[x], finish(x), x)):
        t = tasks[tid]
        rows.append({
            "id": tid, "name": t["name"], "type": "task",
            "chain": chain_of.get(tid, "none"),
            "start": start[tid], "finish": finish(tid), "duration": t["dur"],
            "resources": ";".join(t["res"]),
        })
    for b in buffers:
        rows.append({
            "id": f"FB{b['n']}", "name": f"Feeding buffer {b['n']}",
            "type": "feeding_buffer", "chain": f"feeding-{b['n']}",
            "start": b["fb_start"], "finish": b["fb_start"] + b["fb"],
            "duration": b["fb"], "resources": "",
        })
    rows.append({
        "id": "PB", "name": "Project buffer", "type": "project_buffer",
        "chain": "critical", "start": pb_start, "finish": pb_start + pb_size,
        "duration": pb_size, "resources": "",
    })
    rows.sort(key=lambda r: (r["start"], r["finish"], r["id"]))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "type", "chain", "start", "finish", "duration", "resources"])
        w.writeheader()
        w.writerows(rows)

    print("Critical chain:", " -> ".join(cc))
    print("CC aggressive sum:", sum(tasks[t]["dur"] for t in cc))
    print("Project buffer:", pb_size, f"({pb_start}..{pb_start + pb_size})")
    for b in buffers:
        print(f"Feeding chain {b['n']} (join {b['join']}):", " -> ".join(b["tasks"]),
              f"FB={b['fb']} ({b['fb_start']}..{b['fb_start'] + b['fb']})")
    print("Last task finishes:", max(r["finish"] for r in rows if r["type"] == "task"))
    print("Promised completion: day", pb_start + pb_size)


if __name__ == "__main__":
    main(*sys.argv[1:4])
