#!/usr/bin/env python3
"""CCPM scheduler — implements the ccpm-scheduler skill's deterministic spec
(references/algorithm.md): ALAP baseline, earlier-only resource leveling,
critical-chain trace over precedence+resource links, feeding chains,
50%-rule buffers with :PB/:FB attachment.

Usage: python solve_ccpm.py tasks.csv resources.csv schedule.csv
"""
import csv
import math
import re
import sys
from collections import defaultdict

LINK_RE = re.compile(r"^(?P<id>[^:+\s]+)(?::(?P<type>FS|SS|FF|SF))?(?P<lag>[+-]\d+)?$", re.I)


def parse_links(s):
    out = []
    for tok in (s or "").replace(";", " ").replace(",", " ").split():
        m = LINK_RE.match(tok)
        if not m:
            raise ValueError(f"bad link token {tok!r}")
        out.append((m.group("id"), (m.group("type") or "FS").upper(),
                    int(m.group("lag") or 0)))
    return out


def split_ids(s):
    return [x for x in (s or "").replace(";", " ").replace(",", " ").split() if x]


def main(tasks_path, resources_path, out_path):
    # ---------- parse ----------
    with open(tasks_path, newline="", encoding="utf-8-sig") as f:
        traw = list(csv.DictReader(f))
    with open(resources_path, newline="", encoding="utf-8-sig") as f:
        rraw = list(csv.DictReader(f))
    capacity = {r["id"]: int(r.get("capacity") or 1) for r in rraw}

    name, dur, safe, preds, res, pred_str = {}, {}, {}, {}, {}, {}
    for t in traw:
        tid = t["id"].strip()
        name[tid] = t["name"]
        safe[tid] = int(t["duration_safe"])
        agg = (t.get("duration_aggressive") or "").strip()
        dur[tid] = int(agg) if agg else math.ceil(safe[tid] / 2)  # 50% cut
        preds[tid] = parse_links(t.get("predecessors"))
        res[tid] = split_ids(t.get("resources"))
        pred_str[tid] = (t.get("predecessors") or "").strip()
    tasks = list(name)

    # ---------- validate ----------
    errors = []
    for tid in tasks:
        if dur[tid] <= 0:
            errors.append(f"{tid}: non-positive duration")
        for pid, _, _ in preds[tid]:
            if pid not in name:
                errors.append(f"{tid}: unknown predecessor {pid}")
        for r in res[tid]:
            if r not in capacity:
                errors.append(f"{tid}: unknown resource {r}")
    # topological order / cycle check
    succs = defaultdict(list)
    indeg = {t: 0 for t in tasks}
    for tid in tasks:
        for pid, typ, lag in preds[tid]:
            if pid in name:
                succs[pid].append((tid, typ, lag))
                indeg[tid] += 1
    order, queue = [], sorted(t for t in tasks if indeg[t] == 0)
    while queue:
        n = queue.pop(0)
        order.append(n)
        for s, _, _ in succs[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
        queue.sort()
    if len(order) != len(tasks):
        errors.append("dependency cycle detected among: "
                      + ", ".join(sorted(set(tasks) - set(order))))
    if errors:
        for e in errors:
            print("VALIDATION ERROR:", e)
        sys.exit(1)

    pred_ids = {t: {p for p, _, _ in preds[t]} for t in tasks}
    sinks = [t for t in tasks if not succs[t]]
    print(f"sinks (feed virtual END): {sinks}")

    # ---------- step 2: ALAP baseline ----------
    es, ef = {}, {}
    for t in order:
        s = 0
        for pid, typ, lag in preds[t]:
            if typ == "FS":
                s = max(s, ef[pid] + lag)
            elif typ == "SS":
                s = max(s, es[pid] + lag)
            elif typ == "FF":
                s = max(s, ef[pid] + lag - dur[t])
            elif typ == "SF":
                s = max(s, es[pid] + lag - dur[t])
        es[t], ef[t] = s, s + dur[t]
    T = max(ef[t] for t in sinks)  # virtual END at T

    ls = {}
    for t in reversed(order):
        l = T - dur[t] if t in sinks else 10**9
        if t in sinks:
            l = T - dur[t]
        for sid, typ, lag in succs[t]:
            if typ == "FS":
                l = min(l, ls[sid] - lag - dur[t])
            elif typ == "SS":
                l = min(l, ls[sid] - lag)
            elif typ == "FF":
                l = min(l, ls[sid] + dur[sid] - lag - dur[t])
            elif typ == "SF":
                l = min(l, ls[sid] + dur[sid] - lag)
        ls[t] = l
    start = dict(ls)
    fin = lambda t: start[t] + dur[t]
    print("ALAP starts:", {t: start[t] for t in order})

    # longest precedence path through each task (aggressive durations)
    down = {}
    for t in order:
        down[t] = dur[t] + max((down[p] for p in pred_ids[t]), default=0)
    up = {}
    for t in reversed(order):
        up[t] = dur[t] + max((up[s] for s, _, _ in succs[t]), default=0)
    through = {t: down[t] + up[t] - dur[t] for t in tasks}

    # ---------- step 3: resource leveling (earlier-only) ----------
    def drag_preds(t):
        """Shift predecessors of t earlier (recursively) until every link holds."""
        for pid, typ, lag in preds[t]:
            if typ == "FS":
                lim = start[t] - lag - dur[pid]
            elif typ == "SS":
                lim = start[t] - lag
            elif typ == "FF":
                lim = fin(t) - lag - dur[pid]
            else:  # SF
                lim = fin(t) - lag
            if start[pid] > lim:
                start[pid] = lim
                drag_preds(pid)

    def find_conflicts():
        out = []
        for rid, cap in capacity.items():
            users = sorted(t for t in tasks if rid in res[t])
            for i, a in enumerate(users):
                for b in users[i + 1:]:
                    if start[a] < fin(b) and start[b] < fin(a):
                        # capacity>1: only a conflict if peak demand exceeds cap
                        lo, hi = max(start[a], start[b]), min(fin(a), fin(b))
                        if cap > 1:
                            peak = max(sum(1 for t in users
                                           if start[t] <= d < fin(t))
                                       for d in range(lo, hi))
                            if peak <= cap:
                                continue
                        out.append((hi, rid, a, b))
        return out

    guard = 0
    while True:
        guard += 1
        assert guard < 10000, "leveling did not converge"
        confl = find_conflicts()
        if not confl:
            break
        # latest overlap end; tie: resource id asc, then task ids asc
        confl.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
        _, rid, a, b = confl[0]
        # keep the task with the longer total path through it
        ka = (through[a], fin(a), )
        kb = (through[b], fin(b), )
        if ka > kb or (ka == kb and a < b):
            stay, move = a, b
        else:
            stay, move = b, a
        start[move] = start[stay] - dur[move]
        print(f"level {rid}: move {move} earlier -> [{start[move]},{fin(move)}), {stay} stays")
        drag_preds(move)
    print("leveled starts:", {t: start[t] for t in order})

    # ---------- step 4: critical chain ----------
    memo = {}

    def chain_back(t):
        """Return (earliest extent, chain list ending at t)."""
        if t in memo:
            return memo[t]
        memo[t] = (start[t], [t])  # provisional (also guards recursion)
        cands = []
        for u in tasks:
            if u != t and fin(u) == start[t]:
                is_pred = u in pred_ids[t]
                shares = bool(set(res[u]) & set(res[t]))
                if is_pred or shares:
                    cands.append((u, is_pred))
        if cands:
            best = min(cands, key=lambda c: (chain_back(c[0])[0],
                                             0 if c[1] else 1, c[0]))
            ext, lst = chain_back(best[0])
            memo[t] = (ext, lst + [t])
        return memo[t]

    last = max(tasks, key=lambda t: (fin(t), t))
    _, cc = chain_back(last)
    cc_set = set(cc)
    print("critical chain:", " -> ".join(cc))

    # ---------- step 5: feeding chains ----------
    non_cc = [t for t in tasks if t not in cc_set]
    nsuccs = {t: [s for s, _, _ in succs[t]] for t in tasks}
    paths = []  # (path list, join id)

    def walk(path):
        t = path[-1]
        cc_next = sorted((s for s in nsuccs[t] if s in cc_set),
                         key=lambda s: (start[s], s))
        if cc_next:
            paths.append((list(path), cc_next[0]))
        for s in nsuccs[t]:
            if s in non_cc:
                walk(path + [s])
        if not nsuccs[t]:  # dead-ends at END
            paths.append((list(path), None))

    heads = [t for t in non_cc if not (pred_ids[t] & set(non_cc))]
    for h in sorted(heads):
        walk([h])

    paths.sort(key=lambda p: (-sum(dur[t] for t in p[0]), p[0][0]))
    assigned, chains = set(), []
    for path, _ in paths:
        excl = [t for t in path if t not in assigned]
        if not excl:
            continue
        assigned.update(excl)
        # join = nearest critical-chain task reachable from the chain's last task
        seen, frontier, reach = set(), [excl[-1]], []
        while frontier:
            n = frontier.pop()
            for s in nsuccs[n]:
                if s in cc_set:
                    reach.append(s)
                elif s not in seen:
                    seen.add(s)
                    frontier.append(s)
        join = min(reach, key=lambda s: (start[s], s)) if reach else None
        chains.append({"tasks": excl, "join": join})
    chains.sort(key=lambda c: (start[c["join"]] if c["join"] else 10**9))
    for i, c in enumerate(chains, 1):
        c["label"] = f"feeding-{i}"
        print(f"{c['label']}: {c['tasks']} joins {c['join']}")

    # ---------- step 6: buffers (50% rule) ----------
    pb_size = math.ceil(0.5 * sum(dur[t] for t in cc))
    for c in chains:
        c["fb"] = math.ceil(0.5 * sum(dur[t] for t in c["tasks"]))

    # shift feeding chains so each finishes >= FB before its join; ripple + re-level
    changed = True
    while changed:
        changed = False
        for c in chains:
            if not c["join"]:
                continue
            chain_fin = max(fin(t) for t in c["tasks"])
            req = start[c["join"]] - c["fb"]
            if chain_fin > req:
                delta = chain_fin - req
                for t in c["tasks"]:
                    start[t] -= delta
                for t in c["tasks"]:
                    drag_preds(t)
                print(f"shift {c['label']} earlier by {delta} for its buffer")
                changed = True
        if find_conflicts():
            # re-level (earlier-only moves; must not touch the critical chain)
            before = dict(start)
            while True:
                confl = find_conflicts()
                if not confl:
                    break
                confl.sort(key=lambda x: (-x[0], x[1], x[2], x[3]))
                _, rid, a, b = confl[0]
                ka, kb = (through[a], fin(a)), (through[b], fin(b))
                stay, move = (a, b) if (ka > kb or (ka == kb and a < b)) else (b, a)
                start[move] = start[stay] - dur[move]
                drag_preds(move)
            assert all(start[t] == before[t] for t in cc_set), \
                "re-leveling moved a critical-chain task; replan required"
            changed = True

    # place buffers in the gaps; global right-shift if anything is negative
    rows = []
    for t in tasks:
        chain = ("critical" if t in cc_set else
                 next((c["label"] for c in chains if t in c["tasks"]), "none"))
        rows.append(dict(id=t, name=name[t], type="task", chain=chain,
                         start=start[t], finish=fin(t), duration=dur[t],
                         resources=";".join(res[t]), predecessors=pred_str[t]))

    buf_rows = []
    for i, c in enumerate(chains, 1):
        if not c["join"]:
            continue
        chain_fin = max(fin(t) for t in c["tasks"])
        last_task = max(c["tasks"], key=lambda t: (fin(t), t))
        buf_rows.append(dict(id=f"FB{i}", name=f"Feeding buffer ({c['label']})",
                             type="feeding_buffer", chain=c["label"],
                             start=chain_fin, finish=start[c["join"]],
                             duration=start[c["join"]] - chain_fin,
                             resources="", predecessors=f"{last_task}:FB"))
    cc_fin = max(fin(t) for t in cc)
    buf_rows.append(dict(id="PB", name="Project buffer", type="project_buffer",
                         chain="critical", start=cc_fin, finish=cc_fin + pb_size,
                         duration=pb_size, resources="", predecessors=f"{cc[-1]}:PB"))
    rows += buf_rows

    offset = -min(r["start"] for r in rows)
    if offset > 0:
        print(f"shifting whole schedule right by {offset} (negative starts)")
        for r in rows:
            r["start"] += offset
            r["finish"] += offset

    rows.sort(key=lambda r: (r["start"], r["finish"], r["id"]))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "type", "chain", "start",
                                          "finish", "duration", "resources",
                                          "predecessors"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out_path}")

    pb = next(r for r in rows if r["type"] == "project_buffer")
    print(f"critical chain length: {sum(dur[t] for t in cc)}; "
          f"last task finishes day {max(r['finish'] for r in rows if r['type']=='task')}; "
          f"project buffer {pb_size}d; promised completion day {pb['finish']}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
