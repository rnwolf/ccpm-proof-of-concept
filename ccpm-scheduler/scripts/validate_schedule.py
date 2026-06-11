#!/usr/bin/env python3
"""Validate a CCPM schedule.csv against tasks.csv and resources.csv.

Usage: python validate_schedule.py schedule.csv tasks.csv resources.csv

Checks:
  1. Every input task appears exactly once in the schedule.
  2. finish == start + duration for every row.
  3. Precedence per link type (FS default): FS pred.finish+lag <= start;
     SS pred.start+lag <= start; FF pred.finish+lag <= finish;
     SF pred.start+lag <= finish. Notation: A, A:SS, A:FF+2, A:SF-1.
  4. Resource capacity never exceeded on any day.
  5. Exactly one project buffer, placed at the end of the critical chain.
  6. Feeding buffers sit between their chain's last task and the join point,
     and each feeding buffer's END is anchored to the start of a critical-chain
     task or the project buffer (the protected successor).
  7. No negative starts.
  8. Buffer link discipline: buffer rows attach via :PB / :FB links (not
     plain FS), PB/FB link types appear only on buffer rows, and buffers
     consume no resources. Buffers are not work - during execution their end
     stays anchored and slippage consumes them, so the type must be explicit.

Exit code 0 = valid, 1 = violations found (printed to stdout).
"""
import csv
import re
import sys
from collections import defaultdict

LINK_RE = re.compile(r"^(?P<id>[^:+\s]+)(?::(?P<type>FS|SS|FF|SF|PB|FB))?(?P<lag>[+-]\d+)?$", re.I)


def parse_links(s):
    """'A;B:SS+2' -> [('A','FS',0), ('B','SS',2)]"""
    out = []
    for tok in (s or "").replace(";", " ").replace(",", " ").split():
        m = LINK_RE.match(tok)
        if m:
            out.append((m.group("id"), (m.group("type") or "FS").upper(),
                        int(m.group("lag") or 0)))
    return out


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def split_ids(s):
    return [x for x in s.replace(";", " ").replace(",", " ").split() if x]


def main(schedule_path, tasks_path, resources_path):
    sched = read_csv(schedule_path)
    tasks = {t["id"]: t for t in read_csv(tasks_path)}
    resources = {r["id"]: int(r.get("capacity") or 1) for r in read_csv(resources_path)}
    errors = []

    rows = {}
    for r in sched:
        r["start"], r["finish"], r["duration"] = int(r["start"]), int(r["finish"]), int(r["duration"])
        if r["id"] in rows:
            errors.append(f"duplicate schedule row id {r['id']}")
        rows[r["id"]] = r

    # 1. coverage
    for tid in tasks:
        if tid not in rows:
            errors.append(f"task {tid} missing from schedule")
    # 2. arithmetic & 7. negative starts
    for r in sched:
        if r["finish"] != r["start"] + r["duration"]:
            errors.append(f"{r['id']}: finish != start + duration")
        if r["start"] < 0:
            errors.append(f"{r['id']}: negative start {r['start']}")

    # 3. precedence, by link type (prefer the schedule's own predecessors
    # column so buffers and normalized links are checked too)
    BOUNDS = {  # (pred attr, succ attr); PB/FB anchor like FS at plan time
        "FS": ("finish", "start"), "SS": ("start", "start"),
        "FF": ("finish", "finish"), "SF": ("start", "finish"),
        "PB": ("finish", "start"), "FB": ("finish", "start"),
    }
    BUFFER_LINK = {"project_buffer": "PB", "feeding_buffer": "FB"}
    for tid, r in rows.items():
        pred_spec = r.get("predecessors")
        if pred_spec is None and tid in tasks:
            pred_spec = tasks[tid].get("predecessors")
        for pid, ltype, lag in parse_links(pred_spec or ""):
            if pid not in rows:
                errors.append(f"{tid}: unknown predecessor {pid}")
                continue
            pa, sa = BOUNDS[ltype]
            if rows[pid][pa] + lag > r[sa]:
                errors.append(
                    f"{ltype} link violated: {pid}.{pa}={rows[pid][pa]}{lag:+d} "
                    f"> {tid}.{sa}={r[sa]}")
            # 8. buffer link discipline
            expected = BUFFER_LINK.get(r["type"])
            if expected and ltype != expected:
                errors.append(f"{tid}: buffer must attach via :{expected} link, got {ltype}")
            if ltype in ("PB", "FB") and r["type"] not in BUFFER_LINK:
                errors.append(f"{tid}: {ltype} link used on non-buffer row")

    # 4. resource capacity (day-by-day)
    usage = defaultdict(lambda: defaultdict(int))  # resource -> day -> demand
    for r in sched:
        if r["type"] != "task":
            continue
        for res in split_ids(r.get("resources") or ""):
            if res not in resources:
                errors.append(f"{r['id']}: unknown resource {res}")
                continue
            for day in range(r["start"], r["finish"]):
                usage[res][day] += 1
    for res, days in usage.items():
        for day, demand in sorted(days.items()):
            if demand > resources[res]:
                errors.append(f"resource {res} over capacity on day {day} ({demand} > {resources[res]})")
                break  # one report per resource is enough

    # 5. project buffer
    pbs = [r for r in sched if r["type"] == "project_buffer"]
    if len(pbs) != 1:
        errors.append(f"expected exactly 1 project buffer, found {len(pbs)}")
    else:
        cc_tasks = [r for r in sched if r["type"] == "task" and r["chain"] == "critical"]
        if cc_tasks:
            last_cc = max(r["finish"] for r in cc_tasks)
            if pbs[0]["start"] != last_cc:
                errors.append(f"project buffer starts {pbs[0]['start']}, last critical task finishes {last_cc}")

    # 8. buffers consume no resources
    for r in sched:
        if r["type"] in BUFFER_LINK and (r.get("resources") or "").strip():
            errors.append(f"{r['id']}: buffer must not consume resources")

    # 6. feeding buffers
    cc_starts = {r["start"] for r in sched if r["type"] == "task" and r["chain"] == "critical"}
    pb_starts = {r["start"] for r in sched if r["type"] == "project_buffer"}
    for fb in (r for r in sched if r["type"] == "feeding_buffer"):
        if fb["finish"] not in cc_starts | pb_starts:
            errors.append(
                f"{fb['id']}: end {fb['finish']} not anchored to a critical-chain "
                f"task start or the project buffer (its protected successor)")
        chain_tasks = [r for r in sched if r["type"] == "task" and r["chain"] == fb["chain"]]
        if not chain_tasks:
            errors.append(f"{fb['id']}: no tasks in chain {fb['chain']}")
            continue
        chain_end = max(r["finish"] for r in chain_tasks)
        if fb["start"] != chain_end:
            errors.append(f"{fb['id']}: starts {fb['start']} but chain {fb['chain']} ends {chain_end}")

    if errors:
        print(f"INVALID — {len(errors)} violation(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("VALID — all checks passed.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(*sys.argv[1:4]))
