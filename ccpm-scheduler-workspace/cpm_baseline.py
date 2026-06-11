#!/usr/bin/env python3
"""Traditional CPM baseline scheduler — the thing CCPM improves on.

Usage: python3 cpm_baseline.py tasks.csv out_schedule.csv

Deliberately naive, as classic CPM is:
  - uses the safe (padded) estimates as-is, no 50% cut
  - ASAP forward pass on precedence only (FS/SS/FF/SF + lag honored)
  - completely IGNORES resource capacity (no leveling)
  - no project buffer, no feeding buffers; promise date = last finish
  - critical path = zero-total-float tasks (chain='critical')

Output uses the same schedule.csv schema as the ccpm-scheduler skill so the
same plot script can render it; the utilization sub-chart will show red
over-capacity blocks wherever CPM double-books a resource.
"""
import csv
import re
import sys
from collections import defaultdict

LINK_RE = re.compile(r"^(?P<id>[^:+\s]+)(?::(?P<type>FS|SS|FF|SF))?(?P<lag>[+-]\d+)?$", re.I)


def parse_links(s):
    out = []
    for tok in (s or "").replace(";", " ").replace(",", " ").split():
        m = LINK_RE.match(tok)
        if m:
            out.append((m.group("id"), (m.group("type") or "FS").upper(),
                        int(m.group("lag") or 0)))
    return out


def main(tasks_path, out_path):
    with open(tasks_path, newline="", encoding="utf-8-sig") as f:
        tasks = list(csv.DictReader(f))
    dur, preds = {}, {}
    for t in tasks:
        d = t.get("duration_safe") or t.get("duration_aggressive") or t.get("duration")
        dur[t["id"]] = int(d)
        preds[t["id"]] = parse_links(t.get("predecessors"))
    succs = defaultdict(list)
    for tid, links in preds.items():
        for pid, lt, lag in links:
            succs[pid].append((tid, lt, lag))

    # forward pass (ASAP), iterate to fixed point (handles SS/FF/SF too)
    es = {tid: 0 for tid in dur}
    for _ in range(len(dur) + 1):
        changed = False
        for tid, links in preds.items():
            lo = 0
            for pid, lt, lag in links:
                pa = es[pid] + (dur[pid] if lt in ("FS", "FF") else 0) + lag
                lo = max(lo, pa - (dur[tid] if lt in ("FF", "SF") else 0))
            if lo > es[tid]:
                es[tid], changed = lo, True
        if not changed:
            break
    T = max(es[t] + dur[t] for t in dur)

    # backward pass for float
    lf = {tid: T for tid in dur}
    for _ in range(len(dur) + 1):
        changed = False
        for tid in dur:
            hi = T
            for sid, lt, lag in succs[tid]:
                if lt == "FS":
                    hi = min(hi, lf[sid] - dur[sid] - lag)
                elif lt == "SS":
                    hi = min(hi, lf[sid] - dur[sid] - lag + dur[tid])
                elif lt == "FF":
                    hi = min(hi, lf[sid] - lag)
                elif lt == "SF":
                    hi = min(hi, lf[sid] - lag + dur[tid])
            if hi < lf[tid]:
                lf[tid], changed = hi, True
        if not changed:
            break

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "type", "chain", "start", "finish",
                    "duration", "resources", "predecessors"])
        for t in tasks:
            tid = t["id"]
            crit = (lf[tid] - (es[tid] + dur[tid])) == 0
            w.writerow([tid, t.get("name", tid), "task",
                        "critical" if crit else "none",
                        es[tid], es[tid] + dur[tid], dur[tid],
                        t.get("resources", ""), t.get("predecessors", "")])
    print(f"wrote {out_path}  (CPM length {T}, no buffers, resources ignored)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
