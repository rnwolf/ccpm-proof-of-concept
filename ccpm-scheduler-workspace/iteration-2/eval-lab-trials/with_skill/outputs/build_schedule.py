#!/usr/bin/env python3
"""Build a CCPM schedule per ccpm-scheduler/references/algorithm.md.

Steps: normalize -> validate -> ALAP baseline -> resource leveling (earlier
only, deterministic tie-breaks) -> critical chain trace (precedence OR
resource links) -> feeding chains -> 50%-rule buffers -> schedule.csv.

Usage: python build_schedule.py tasks.csv resources.csv schedule.csv
"""
import csv
import math
import re
import sys
from collections import defaultdict

LINK_RE = re.compile(r"^(?P<id>[^:+\s]+)(?::(?P<type>FS|SS|FF|SF))?(?P<lag>[+-]\d+)?$", re.I)
END = "__END__"


def parse_links(s):
    out = []
    for tok in (s or "").replace(";", " ").replace(",", " ").split():
        m = LINK_RE.match(tok)
        if not m:
            raise ValueError(f"bad link token: {tok}")
        out.append((m.group("id"), (m.group("type") or "FS").upper(),
                    int(m.group("lag") or 0)))
    return out


def main(tasks_path, resources_path, out_path):
    with open(tasks_path, newline="", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    with open(resources_path, newline="", encoding="utf-8-sig") as f:
        cap = {r["id"]: int(r.get("capacity") or 1) for r in csv.DictReader(f)}

    # ---- Step 0: normalize ----
    tasks = {}
    for r in raw:
        if (r.get("duration_aggressive") or "").strip():
            dur = int(r["duration_aggressive"])
        else:
            dur = math.ceil(int(r["duration_safe"]) / 2)
        tasks[r["id"]] = dict(
            id=r["id"], name=r["name"], dur=dur,
            preds=parse_links(r.get("predecessors")),
            res=[x for x in (r.get("resources") or "").replace(";", " ").split() if x],
            pred_str=(r.get("predecessors") or "").strip())

    # ---- Step 1: validate ----
    errs, warns = [], []
    for t in tasks.values():
        for pid, _, _ in t["preds"]:
            if pid not in tasks:
                errs.append(f"{t['id']}: unknown predecessor {pid}")
        for res in t["res"]:
            if res not in cap:
                errs.append(f"{t['id']}: unknown resource {res}")
        if t["dur"] <= 0:
            errs.append(f"{t['id']}: non-positive duration {t['dur']}")
        if not t["res"]:
            warns.append(f"{t['id']}: no resources assigned")
    for rid, c in cap.items():
        if c > 1:
            warns.append(f"resource {rid}: capacity {c} > 1 (unusual in CCPM)")

    succs = defaultdict(list)
    for t in tasks.values():
        for pid, _, _ in t["preds"]:
            if pid in tasks:
                succs[pid].append(t["id"])
    # virtual END milestone over all sinks
    sinks = sorted(tid for tid in tasks if not succs[tid])
    tasks[END] = dict(id=END, name="", dur=0, preds=[(s, "FS", 0) for s in sinks],
                      res=[], pred_str="")
    for s in sinks:
        succs[s].append(END)

    # topological order (cycle check)
    indeg = {tid: len([p for p, _, _ in tasks[tid]["preds"] if p in tasks])
             for tid in tasks}
    queue = sorted(tid for tid, d in indeg.items() if d == 0)
    topo = []
    while queue:
        tid = queue.pop(0)
        topo.append(tid)
        for s in sorted(succs[tid]):
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
        queue.sort()
    if len(topo) != len(tasks):
        errs.append("dependency cycle detected")
    if errs:
        for e in errs:
            print("ERROR:", e)
        sys.exit(1)
    for w in warns:
        print("WARN:", w)

    # ---- Step 2: ALAP baseline ----
    ES, EF = {}, {}
    for tid in topo:
        t = tasks[tid]
        es = 0
        for pid, lt, lag in t["preds"]:
            if lt == "FS":
                es = max(es, EF[pid] + lag)
            elif lt == "SS":
                es = max(es, ES[pid] + lag)
            elif lt == "FF":
                es = max(es, EF[pid] + lag - t["dur"])
            elif lt == "SF":
                es = max(es, ES[pid] + lag - t["dur"])
        ES[tid], EF[tid] = es, es + t["dur"]
    T = max(EF.values())
    LF, LS = {}, {}
    for tid in reversed(topo):
        t = tasks[tid]
        lf = T
        for sid in succs[tid]:
            for pid, lt, lag in tasks[sid]["preds"]:
                if pid != tid:
                    continue
                if lt == "FS":
                    lf = min(lf, LS[sid] - lag)
                elif lt == "SS":
                    lf = min(lf, LS[sid] - lag + t["dur"])
                elif lt == "FF":
                    lf = min(lf, LF[sid] - lag)
                elif lt == "SF":
                    lf = min(lf, LF[sid] - lag + t["dur"])
        LF[tid], LS[tid] = lf, lf - t["dur"]
    start = {tid: LS[tid] for tid in tasks}

    def fin(tid):
        return start[tid] + tasks[tid]["dur"]

    # longest path through each task (aggressive durations) = leveling priority
    head, tail = {}, {}
    for tid in topo:
        head[tid] = tasks[tid]["dur"] + max(
            [head[p] for p, _, _ in tasks[tid]["preds"]] or [0])
    for tid in reversed(topo):
        tail[tid] = tasks[tid]["dur"] + max([tail[s] for s in succs[tid]] or [0])
    through = {tid: head[tid] + tail[tid] - tasks[tid]["dur"] for tid in tasks}

    # ---- Step 3: resource leveling (earlier only) ----
    def drag_preds(tid):
        """Recursively shift predecessors earlier (minimum amount) to satisfy links."""
        for pid, lt, lag in tasks[tid]["preds"]:
            if lt == "FS":
                req = start[tid] - lag - tasks[pid]["dur"]
            elif lt == "SS":
                req = start[tid] - lag
            elif lt == "FF":
                req = fin(tid) - lag - tasks[pid]["dur"]
            else:  # SF
                req = fin(tid) - lag
            if start[pid] > req:
                start[pid] = req
                drag_preds(pid)

    def conflicts():
        out = []
        by_res = defaultdict(list)
        for tid, t in tasks.items():
            for r in t["res"]:
                by_res[r].append(tid)
        for r in sorted(by_res):
            assert cap[r] == 1 or len(by_res[r]) <= cap[r], \
                f"capacity>1 leveling not needed for this input ({r})"
            tids = sorted(by_res[r])
            for i in range(len(tids)):
                for j in range(i + 1, len(tids)):
                    a, b = tids[i], tids[j]
                    lo, hi = max(start[a], start[b]), min(fin(a), fin(b))
                    if lo < hi:
                        out.append((hi, r, a, b))
        return out

    for _ in range(10000):
        cons = conflicts()
        if not cons:
            break
        cons.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
        _, _, a, b = cons[0]
        ka, kb = (through[a], fin(a)), (through[b], fin(b))
        if ka > kb:
            stay, move = a, b
        elif kb > ka:
            stay, move = b, a
        else:
            stay, move = (a, b) if a < b else (b, a)
        start[move] = start[stay] - tasks[move]["dur"]
        drag_preds(move)
    else:
        sys.exit("leveling did not converge")

    # ---- Step 4: critical chain ----
    pred_ids = {tid: {p for p, _, _ in tasks[tid]["preds"]} for tid in tasks}

    def candidates(tid):
        out = []
        for oid in tasks:
            if oid == tid:
                continue
            if fin(oid) == start[tid] and (
                    oid in pred_ids[tid]
                    or set(tasks[oid]["res"]) & set(tasks[tid]["res"])):
                out.append(oid)
        return out

    def chain_pred(tid):
        cands = candidates(tid)
        if not cands:
            return None
        return min(cands, key=lambda c: (reach(c),
                                         0 if c in pred_ids[tid] else 1, c))

    def reach(tid):
        cp = chain_pred(tid)
        return start[tid] if cp is None else reach(cp)

    chain = []
    cur = END
    while True:
        cp = chain_pred(cur)
        if cp is None:
            break
        chain.append(cp)
        cur = cp
    cc = list(reversed(chain))  # END excluded by construction
    cc_set = set(cc)

    # ---- Step 5: feeding chains ----
    noncrit = [tid for tid in tasks if tid not in cc_set and tid != END]

    def join_of(tid):
        seen, q = set(), [tid]
        while q:
            x = q.pop(0)
            for s in sorted(succs[x]):
                if s in cc_set:
                    return s
                if s not in seen and s != END:
                    seen.add(s)
                    q.append(s)
        return END

    groups = defaultdict(list)
    for tid in sorted(noncrit):
        groups[join_of(tid)].append(tid)

    pb_start = max(fin(t) for t in cc)
    join_start_of = {j: (pb_start if j == END else start[j]) for j in groups}
    feeding = []  # (join, [chain tasks in precedence order])
    for j in sorted(groups, key=lambda j: (join_start_of[j], str(j))):
        members = set(groups[j])
        # maximal precedence paths within the group, longest first; tasks
        # belong to exactly one chain (shared prefix -> longest chain)
        paths = []

        def walk(tid, acc):
            nxt = [s for s in sorted(succs[tid]) if s in members]
            if not nxt:
                paths.append(acc)
            for s in nxt:
                walk(s, acc + [s])

        heads = [m for m in sorted(members)
                 if not (pred_ids[m] & members)]
        for h in heads:
            walk(h, [h])
        paths.sort(key=lambda p: (-sum(tasks[t]["dur"] for t in p), p[0]))
        assigned = set()
        for p in paths:
            excl = [t for t in p if t not in assigned]
            if excl:
                feeding.append((j, excl))
                assigned |= set(excl)

    feeding.sort(key=lambda f: (join_start_of[f[0]], str(f[0]), f[1][0]))

    # ---- Step 6: buffers (50% rule) ----
    cc_sum = sum(tasks[t]["dur"] for t in cc)
    pb_size = math.ceil(0.5 * cc_sum)
    buffers = []  # rows
    chain_label = {t: "critical" for t in cc}
    notes = []

    for n, (j, members) in enumerate(feeding, start=1):
        label = f"feeding-{n}"
        for t in members:
            chain_label[t] = label
        fb_size = math.ceil(0.5 * sum(tasks[t]["dur"] for t in members))
        js = join_start_of[j]
        chain_end = max(fin(t) for t in members)
        need = chain_end - (js - fb_size)
        if need > 0:
            # max uniform shift allowed by predecessors outside the chain
            feasible = need
            for t in members:
                floor = 0
                for pid, lt, lag in tasks[t]["preds"]:
                    if pid in members:
                        continue
                    if lt == "FS":
                        floor = max(floor, fin(pid) + lag)
                    elif lt == "SS":
                        floor = max(floor, start[pid] + lag)
                feasible = min(feasible, start[t] - floor)
            shift = max(0, feasible)
            for t in members:
                start[t] -= shift
        chain_end = max(fin(t) for t in members)
        fb_dur = js - chain_end
        last = max(members, key=lambda t: (fin(t), t))
        if fb_dur < fb_size:
            notes.append(f"FB{n} squeezed: computed {fb_size}d, only {fb_dur}d "
                         f"fits (chain {'->'.join(members)} is precedence-bound)")
        elif fb_dur > fb_size:
            notes.append(f"FB{n} enlarged: computed {fb_size}d, gap of {fb_dur}d "
                         f"left by resource leveling is absorbed into the buffer")
        buffers.append(dict(id=f"FB{n}", name=f"Feeding buffer {n}",
                            type="feeding_buffer", chain=label,
                            start=chain_end, finish=js, duration=fb_dur,
                            resources="", predecessors=f"{last}:FB"))

    # re-level moved tasks (earlier only) if shifts created conflicts
    if conflicts():
        sys.exit("feeding-buffer insertion created resource conflicts; "
                 "extend script to re-level")

    buffers.append(dict(id="PB", name="Project buffer", type="project_buffer",
                        chain="critical", start=pb_start,
                        finish=pb_start + pb_size, duration=pb_size,
                        resources="", predecessors=f"{cc[-1]}:PB"))

    # shift right if anything went negative
    m = min(min(start[t] for t in tasks), min(b["start"] for b in buffers))
    if m < 0:
        for t in tasks:
            start[t] -= m
        for b in buffers:
            b["start"] -= m
            b["finish"] -= m

    # ---- Step 7: output ----
    rows = []
    for tid in tasks:
        if tid == END:
            continue
        t = tasks[tid]
        rows.append(dict(id=tid, name=t["name"], type="task",
                         chain=chain_label.get(tid, "none"),
                         start=start[tid], finish=fin(tid), duration=t["dur"],
                         resources=";".join(t["res"]),
                         predecessors=t["pred_str"]))
    rows += buffers
    rows.sort(key=lambda r: (r["start"], r["finish"], r["id"]))
    cols = ["id", "name", "type", "chain", "start", "finish", "duration",
            "resources", "predecessors"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"critical chain: {' -> '.join(cc)} (sum {cc_sum}d)")
    print(f"project buffer: {pb_size}d at {pb_start}-{pb_start + pb_size}")
    for b in buffers[:-1]:
        print(f"{b['id']}: {b['duration']}d at {b['start']}-{b['finish']} "
              f"(chain {b['chain']})")
    for n in notes:
        print("NOTE:", n)
    print(f"promised completion: day {pb_start + pb_size}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
