#!/usr/bin/env python3
"""Grade iteration-2: CCPM-with-skill vs traditional-CPM baseline.

The question is not "did Claude schedule" but "is the CCPM schedule a real
CCPM schedule, and does the CPM baseline exhibit the failure modes CCPM
exists to fix" — chiefly resource overloading and an unprotected promise.

Usage: python3 grader_it2.py <iteration_dir> <inputs_dir>
"""
import csv, json, math, os, sys
from collections import defaultdict

IT, INP = sys.argv[1], sys.argv[2]
EVALS = ["eval-website-launch", "eval-lab-trials",
         "eval-kitchen-renovation", "eval-equipment-retrofit"]
INPUT_DIR = {"eval-website-launch": "website-launch", "eval-lab-trials": "lab-trials",
             "eval-kitchen-renovation": "kitchen-renovation",
             "eval-equipment-retrofit": "equipment-retrofit"}


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["start"], r["finish"] = int(float(r["start"])), int(float(r["finish"]))
        r["duration"] = int(float(r.get("duration") or (r["finish"] - r["start"])))
    return rows


def capacities(eval_dir):
    caps = {}
    with open(os.path.join(INP, INPUT_DIR[eval_dir], "resources.csv"),
              newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            caps[r["id"]] = int(r.get("capacity") or 1)
    return caps


def overloaded_days(rows, caps):
    demand = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["type"] != "task":
            continue
        for res in (r.get("resources") or "").replace(";", " ").split():
            for day in range(r["start"], r["finish"]):
                demand[res][day] += 1
    return sum(1 for res, days in demand.items()
               for d, n in days.items() if n > caps.get(res, 1))


def grade(eval_dir, config):
    out = os.path.join(IT, eval_dir, config, "outputs")
    caps = capacities(eval_dir)
    results, rows = [], []
    try:
        rows = load(os.path.join(out, "schedule.csv"))
        ok, ev = len(rows) > 0, f"parsed {len(rows)} rows"
    except Exception as e:
        ok, ev = False, str(e)
    results.append(dict(text="schedule.csv parses", passed=ok, evidence=ev))
    over = overloaded_days(rows, caps) if rows else -1
    pbs = [r for r in rows if r["type"] == "project_buffer"]
    fbs = [r for r in rows if r["type"] == "feeding_buffer"]
    end = max((r["finish"] for r in rows), default=0)

    if config == "with_skill":
        results += [
            dict(text="CCPM: zero overloaded resource-days (leveling worked)",
                 passed=over == 0, evidence=f"{over} overloaded resource-days"),
            dict(text="CCPM: exactly one project buffer ending the schedule",
                 passed=len(pbs) == 1 and pbs[0]["finish"] == end,
                 evidence=f"{len(pbs)} PB(s), end {pbs[0]['finish'] if pbs else '-'} vs {end}"),
            dict(text="CCPM: feeding buffer(s) protect non-critical chains",
                 passed=len(fbs) >= 1, evidence=f"{len(fbs)} feeding buffer(s)"),
            dict(text="CCPM: buffers attached via :PB/:FB link types",
                 passed=all((":PB" in (r.get("predecessors") or "")) for r in pbs)
                 and all((":FB" in (r.get("predecessors") or "")) for r in fbs),
                 evidence="; ".join(f"{r['id']}={r.get('predecessors')}" for r in pbs + fbs)),
            dict(text="CCPM: project buffer ~50% of critical chain",
                 passed=bool(pbs) and abs(pbs[0]["duration"] - 0.5 * sum(
                     r["duration"] for r in rows
                     if r["type"] == "task" and r["chain"] == "critical")) <= 1.01,
                 evidence=f"PB={pbs[0]['duration'] if pbs else '-'}, "
                          f"CC={sum(r['duration'] for r in rows if r['type']=='task' and r['chain']=='critical')}"),
        ]
    else:  # cpm_baseline — assert the failure modes are visible
        results += [
            dict(text="CPM: resource overloading visible (the CCPM contrast)",
                 passed=over > 0, evidence=f"{over} overloaded resource-days"),
            dict(text="CPM: no buffers anywhere (promise date unprotected)",
                 passed=not pbs and not fbs,
                 evidence=f"{len(pbs)} PB, {len(fbs)} FB"),
        ]
    g_ok = False
    try:
        with open(os.path.join(out, "gantt.png"), "rb") as f:
            g_ok = f.read(8) == b"\x89PNG\r\n\x1a\n"
    except OSError:
        pass
    results.append(dict(text="gantt.png exists and is a valid PNG", passed=g_ok,
                        evidence="ok" if g_ok else "missing/invalid"))

    passed = sum(r["passed"] for r in results)
    g = dict(expectations=results,
             summary=dict(passed=passed, failed=len(results) - passed,
                          total=len(results), pass_rate=round(passed / len(results), 4)))
    tpath = os.path.join(IT, eval_dir, config, "timing.json")
    if os.path.exists(tpath):
        t = json.load(open(tpath))
        g["timing"] = {"total_duration_seconds": t["total_duration_seconds"],
                       "total_tokens": t["total_tokens"]}
    json.dump(g, open(os.path.join(IT, eval_dir, config, "grading.json"), "w"), indent=2)
    r1 = os.path.join(IT, eval_dir, config, "run-1")
    os.makedirs(r1, exist_ok=True)
    json.dump(g, open(os.path.join(r1, "grading.json"), "w"), indent=2)
    if os.path.exists(tpath):
        json.dump(json.load(open(tpath)), open(os.path.join(r1, "timing.json"), "w"))
    print(f"{eval_dir}/{config}: {passed}/{len(results)}  (overloaded days={over})")
    return rows, over, end, pbs


comparison = []
for e in EVALS:
    ccpm, c_over, c_end, c_pbs = grade(e, "with_skill")
    cpm, p_over, p_end, _ = grade(e, "cpm_baseline")
    work_end = max((r["finish"] for r in ccpm if r["type"] == "task"), default=0)
    comparison.append({
        "eval": e, "cpm_overloaded_resource_days": p_over,
        "ccpm_overloaded_resource_days": c_over,
        "cpm_promise_unprotected": p_end,
        "ccpm_work_finish": work_end, "ccpm_promise_buffered": c_end})
json.dump(comparison, open(os.path.join(IT, "comparison.json"), "w"), indent=2)
print(json.dumps(comparison, indent=2))
