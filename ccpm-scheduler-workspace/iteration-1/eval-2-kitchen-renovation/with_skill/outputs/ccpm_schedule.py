#!/usr/bin/env python3
"""CCPM scheduler for the kitchen renovation, per references/algorithm.md."""
import csv, math, sys
from collections import defaultdict

OUT = "/sessions/upbeat-fervent-fermat/mnt/ccpm-proof-of-concept/ccpm-scheduler-workspace/iteration-1/eval-2-kitchen-renovation/with_skill/outputs/"

def read_csv(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def split_ids(s):
    return [x for x in (s or "").replace(";", " ").replace(",", " ").split() if x]

# ---- Step 0: normalize ----
tasks = {}
for r in read_csv(OUT + "tasks.csv"):
    safe = int(r["duration_safe"])
    agg = int(r["duration_aggressive"]) if r.get("duration_aggressive") else math.ceil(safe / 2)
    tasks[r["id"]] = dict(id=r["id"], name=r["name"], safe=safe, dur=agg,
                          preds=split_ids(r["predecessors"]), res=split_ids(r["resources"]))
resources = {r["id"]: int(r.get("capacity") or 1) for r in read_csv(OUT + "resources.csv")}

# ---- Step 1: validate ----
errors = []
for t in tasks.values():
    for p in t["preds"]:
        if p not in tasks: errors.append(f"unknown predecessor {p} of {t['id']}")
    for res in t["res"]:
        if res not in resources: errors.append(f"unknown resource {res} of {t['id']}")
    if t["dur"] <= 0: errors.append(f"non-positive duration on {t['id']}")
# cycle check (Kahn)
indeg = {tid: len(t["preds"]) for tid, t in tasks.items()}
succ = defaultdict(list)
for tid, t in tasks.items():
    for p in t["preds"]: succ[p].append(tid)
queue = [tid for tid, d in indeg.items() if d == 0]
seen = 0
q = list(queue)
while q:
    n = q.pop(); seen += 1
    for s in succ[n]:
        indeg[s] -= 1
        if indeg[s] == 0: q.append(s)
if seen != len(tasks): errors.append("dependency cycle detected")
if errors:
    print("VALIDATION ERRORS:"); [print(" -", e) for e in errors]; sys.exit(1)

# virtual END
sinks = [tid for tid in tasks if not succ[tid]]

# ---- Step 2: ALAP baseline ----
# forward pass
ES, EF = {}, {}
def es(tid):
    if tid in ES: return ES[tid]
    t = tasks[tid]
    ES[tid] = max((ef(p) for p in t["preds"]), default=0)
    return ES[tid]
def ef(tid):
    if tid in EF: return EF[tid]
    EF[tid] = es(tid) + tasks[tid]["dur"]
    return EF[tid]
T = max(ef(tid) for tid in tasks)
# backward pass
LF, LS = {}, {}
def lf(tid):
    if tid in LF: return LF[tid]
    LF[tid] = min((ls(s) for s in succ[tid]), default=T)
    return LF[tid]
def ls(tid):
    if tid in LS: return LS[tid]
    LS[tid] = lf(tid) - tasks[tid]["dur"]
    return LS[tid]
start = {tid: ls(tid) for tid in tasks}

def fin(tid): return start[tid] + tasks[tid]["dur"]

# longest precedence path through a task (aggressive durations), to END
# path_through = longest path from any start to tid + longest from tid to END (counting tid once)
memo_fwd, memo_bwd = {}, {}
def longest_to(tid):  # longest path ending at tid inclusive
    if tid in memo_fwd: return memo_fwd[tid]
    memo_fwd[tid] = tasks[tid]["dur"] + max((longest_to(p) for p in tasks[tid]["preds"]), default=0)
    return memo_fwd[tid]
def longest_from(tid):  # longest path starting at tid inclusive
    if tid in memo_bwd: return memo_bwd[tid]
    memo_bwd[tid] = tasks[tid]["dur"] + max((longest_from(s) for s in succ[tid]), default=0)
    return memo_bwd[tid]
def path_through(tid):
    return longest_to(tid) + longest_from(tid) - tasks[tid]["dur"]

# ---- Step 3: resource leveling (earlier only) ----
def drag_preds(tid):
    """Recursively shift predecessors earlier if precedence violated."""
    for p in tasks[tid]["preds"]:
        if fin(p) > start[tid]:
            start[p] = start[tid] - tasks[p]["dur"]
            drag_preds(p)

def find_conflicts():
    confs = []
    by_res = defaultdict(list)
    for tid, t in tasks.items():
        for r in t["res"]:
            by_res[r].append(tid)
    for r, tids in by_res.items():
        if resources[r] == 1:
            for i in range(len(tids)):
                for j in range(i + 1, len(tids)):
                    a, b = sorted([tids[i], tids[j]])
                    if start[a] < fin(b) and start[b] < fin(a):
                        ov_end = min(fin(a), fin(b))
                        confs.append((ov_end, r, a, b))
        # capacity>1 generalization omitted (all capacity 1 here)
    return confs

iter_guard = 0
while True:
    confs = find_conflicts()
    if not confs: break
    iter_guard += 1
    assert iter_guard < 1000, "leveling did not converge"
    # latest overlap end; tie-break resource id asc, then task ids asc
    confs.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
    _, r, a, b = confs[0]
    pa, pb = path_through(a), path_through(b)
    if pa > pb: stay, move = a, b
    elif pb > pa: stay, move = b, a
    elif fin(a) > fin(b): stay, move = a, b
    elif fin(b) > fin(a): stay, move = b, a
    else: stay, move = (a, b) if a < b else (b, a)
    start[move] = start[stay] - tasks[move]["dur"]
    drag_preds(move)

# ---- Step 4: critical chain ----
def chain_back_start(tid, memo=None):
    """Earliest time reached by the backward chain from tid (recursive rule)."""
    cands = chain_pred_candidates(tid)
    if not cands: return start[tid]
    return min(chain_back_start(c) for c, _ in cands)

def chain_pred_candidates(tid):
    out = []
    for o in tasks:
        if o == tid: continue
        if fin(o) == start[tid]:
            is_pred = o in tasks[tid]["preds"]
            shares = bool(set(tasks[o]["res"]) & set(tasks[tid]["res"]))
            if is_pred or shares:
                out.append((o, is_pred))
    return out

last = max(tasks, key=lambda tid: (fin(tid), tid))
chain = [last]
cur = last
while True:
    cands = chain_pred_candidates(cur)
    if not cands: break
    # pick candidate whose backward chain extends earliest; tie: precedence over resource, then smaller id
    cands.sort(key=lambda c: (chain_back_start(c[0]), not c[1], c[0]))
    cur = cands[0][0]
    chain.append(cur)
critical = list(reversed(chain))
cc_set = set(critical)

# ---- Step 5: feeding chains ----
# for each non-critical task follow successors to a CC task (join point) or END
def join_point(tid):
    # BFS through successors until hitting a critical task
    seen, q = set(), [tid]
    while q:
        n = q.pop(0)
        for s in succ[n]:
            if s in cc_set: return s
            if s not in seen:
                seen.add(s); q.append(s)
    return None  # joins at END

noncrit = [tid for tid in tasks if tid not in cc_set]
# group by join point; each maximal precedence path within group = feeding chain
groups = defaultdict(list)
for tid in noncrit:
    groups[join_point(tid)].append(tid)

feeding = []  # list of (join, [chain task ids in order])
for join, members in groups.items():
    mset = set(members)
    # maximal paths within the member subgraph
    heads = [m for m in members if not any(p in mset for p in tasks[m]["preds"])]
    paths = []
    def extend(path):
        tail = path[-1]
        nexts = [s for s in succ[tail] if s in mset]
        if not nexts:
            paths.append(path)
        else:
            for s in sorted(nexts): extend(path + [s])
    for h in sorted(heads): extend([h])
    # assign shared prefixes to longest chain (by agg duration), tie: smaller head id
    paths.sort(key=lambda p: (-sum(tasks[x]["dur"] for x in p), p[0]))
    assigned = set()
    for p in paths:
        excl = [x for x in p if x not in assigned]
        if excl:
            feeding.append((join, excl))
            assigned.update(excl)

# ---- Step 6: buffers ----
PB = math.ceil(0.5 * sum(tasks[t]["dur"] for t in critical))
buffers = []  # rows
# order feeding chains by join-point start ascending for numbering
feeding.sort(key=lambda fc: (start[fc[0]] if fc[0] else T, fc[1][0]))
fb_rows = []
for i, (join, members) in enumerate(feeding, 1):
    FB = math.ceil(0.5 * sum(tasks[t]["dur"] for t in members))
    join_start = start[join] if join else T
    chain_finish = max(fin(t) for t in members)
    overlap = chain_finish + FB - join_start
    if overlap > 0:
        for t in members:
            start[t] -= overlap
            drag_preds(t)
        chain_finish = max(fin(t) for t in members)
    fb_rows.append(dict(id=f"FB{i}", name=f"Feeding buffer {i}", type="feeding_buffer",
                        chain=f"feeding-{i}", start=chain_finish, finish=chain_finish + FB,
                        duration=FB, resources="", members=members))

# re-run leveling restricted check (moved tasks may only move earlier) — full recheck
while True:
    confs = find_conflicts()
    if not confs: break
    confs.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
    _, r, a, b = confs[0]
    pa, pb = path_through(a), path_through(b)
    if pa > pb: stay, move = a, b
    elif pb > pa: stay, move = b, a
    elif fin(a) > fin(b): stay, move = a, b
    elif fin(b) > fin(a): stay, move = b, a
    else: stay, move = (a, b) if a < b else (b, a)
    start[move] = start[stay] - tasks[move]["dur"]
    drag_preds(move)
    # re-position any feeding buffer whose chain moved
    for fb in fb_rows:
        cf = max(fin(t) for t in fb["members"])
        fb["start"], fb["finish"] = cf, cf + fb["duration"]

cc_finish = max(fin(t) for t in critical)
pb_row = dict(id="PB", name="Project buffer", type="project_buffer", chain="critical",
              start=cc_finish, finish=cc_finish + PB, duration=PB, resources="")

# shift right if negative starts
min_start = min(min(start.values()), min(fb["start"] for fb in fb_rows) if fb_rows else 0)
if min_start < 0:
    shift = -min_start
    for tid in start: start[tid] += shift
    for fb in fb_rows:
        fb["start"] += shift; fb["finish"] += shift
    pb_row["start"] += shift; pb_row["finish"] += shift

# ---- Step 7: outputs ----
chain_of = {}
for t in critical: chain_of[t] = "critical"
for fb in fb_rows:
    for t in fb["members"]: chain_of[t] = fb["chain"]

rows = []
for tid in sorted(tasks, key=lambda x: (start[x], fin(x), x)):
    t = tasks[tid]
    rows.append(dict(id=tid, name=t["name"], type="task", chain=chain_of.get(tid, "none"),
                     start=start[tid], finish=fin(tid), duration=t["dur"],
                     resources=";".join(t["res"])))
rows.extend(fb_rows)
rows.append(pb_row)
rows.sort(key=lambda r: (r["start"], r["finish"], r["id"]))

with open(OUT + "schedule.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "name", "type", "chain", "start", "finish", "duration", "resources"],
                       extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print("Critical chain:", " -> ".join(critical))
print("CC length (aggressive):", sum(tasks[t]['dur'] for t in critical))
print("Project buffer:", PB)
for fb in fb_rows:
    print(f"{fb['id']}: chain {fb['members']} buffer {fb['duration']} at [{fb['start']},{fb['finish']})")
print("Last task finishes:", max(r["finish"] for r in rows if r["type"] == "task"))
print("Promised completion (end of PB):", pb_row["finish"])
for r in rows:
    print(f"{r['id']:>4} {r['name']:<24} {r['chain']:<10} {r['start']:>3} {r['finish']:>3} {r['duration']:>3} {r['resources']}")
