#!/usr/bin/env python3
"""Grade CCPM eval runs. Usage: python3 grader.py <iteration_dir>
Writes grading.json into each <eval>/<config>/ directory."""
import csv, json, math, os, sys
from collections import defaultdict

IT = sys.argv[1]


def load_schedule(path):
    """Normalize any reasonable schedule.csv into rows with
    id,name,start,finish,duration,critical,is_buffer,buffer_kind,resources."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    rows = []
    for r in raw:
        low = {k.strip().lower(): (v or "").strip() for k, v in r.items()}

        def pick(*keys):
            for k in keys:
                for cand in low:
                    if cand == k or cand.startswith(k):
                        if low[cand] != "":
                            return low[cand]
            return None

        start = pick("start (day", "start_day", "start")
        finish = pick("finish (day", "end_day", "finish", "end (day", "end")
        dur = pick("duration_focused", "focused duration", "duration_days", "duration (day", "duration")
        typ = (pick("type") or "task").lower()
        chain = (pick("chain", "on_critical_chain") or "").lower()
        name = pick("name", "task") or ""
        tid = pick("id") or name
        res = pick("resources", "resource") or ""
        is_buffer = "buffer" in typ or "buffer" in name.lower()
        buffer_kind = ("project" if ("project" in typ or "project" in name.lower())
                       else "feeding" if is_buffer else None)
        critical = ("critical" in chain or "critical" in typ
                    or chain in ("yes", "y", "true", "1")) and not is_buffer
        if start is None or finish is None:
            continue
        rows.append(dict(id=tid, name=name, start=float(start), finish=float(finish),
                         duration=float(dur) if dur else float(finish) - float(start),
                         critical=critical, is_buffer=is_buffer,
                         buffer_kind=buffer_kind, resources=res.lower()))
    return rows


def find(rows, key):
    key = key.lower()
    for r in rows:
        if r["id"].lower() == key or key in r["name"].lower():
            return r
    return None


def no_overlap(rows, errlist):
    busy = defaultdict(list)
    for r in rows:
        if r["is_buffer"]:
            continue
        for res in r["resources"].replace(";", " ").replace(",", " ").split():
            busy[res].append(r)
    ok = True
    for res, tasks in busy.items():
        tasks.sort(key=lambda r: r["start"])
        for a, b in zip(tasks, tasks[1:]):
            if b["start"] < a["finish"] - 1e-9:
                errlist.append(f"{res}: {a['id']} and {b['id']} overlap")
                ok = False
    return ok


def precedence_ok(rows, pairs, errlist):
    ok = True
    for p, s in pairs:
        rp, rs = find(rows, p), find(rows, s)
        if not rp or not rs:
            errlist.append(f"missing task {p if not rp else s}")
            ok = False
        elif rp["finish"] > rs["start"] + 1e-9:
            errlist.append(f"{p} finishes {rp['finish']} after {s} starts {rs['start']}")
            ok = False
    return ok


def durations_match(rows, expected, errlist):
    ok = True
    for key, d in expected.items():
        r = find(rows, key)
        if not r:
            errlist.append(f"missing {key}")
            ok = False
        elif abs(r["duration"] - d) > 0.51:
            errlist.append(f"{key}: duration {r['duration']} expected {d}")
            ok = False
    return ok


def pb_checks(rows):
    """Return (single_pb, pb_at_end, pb_sized, evidence)."""
    pbs = [r for r in rows if r["buffer_kind"] == "project"]
    ev = f"{len(pbs)} project buffer(s)"
    if not pbs:
        return False, False, False, ev
    single = len(pbs) == 1
    pb = max(pbs, key=lambda r: r["finish"])
    sched_end = max(r["finish"] for r in rows)
    at_end = abs(pb["finish"] - sched_end) < 1e-9
    cc_len = sum(r["duration"] for r in rows if r["critical"])
    sized = cc_len > 0 and abs(pb["duration"] - 0.5 * cc_len) <= 1.01
    ev += f"; pb={pb['duration']}, cc_len={cc_len}, end={pb['finish']}/{sched_end}"
    return single, at_end, sized, ev


def png_valid(path):
    try:
        with open(path, "rb") as f:
            return f.read(8) == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def grade(eval_dir, config, checks):
    out = os.path.join(IT, eval_dir, config, "outputs")
    sched_path = os.path.join(out, "schedule.csv")
    results = []
    rows = []
    try:
        rows = load_schedule(sched_path)
        parse_ok = len(rows) > 0
        parse_ev = f"parsed {len(rows)} rows"
    except Exception as e:
        parse_ok, parse_ev = False, f"parse error: {e}"
    results.append(dict(text="schedule.csv exists and parses into start/finish/duration rows",
                        passed=parse_ok, evidence=parse_ev))
    for text, fn in checks:
        if not parse_ok:
            results.append(dict(text=text, passed=False, evidence="schedule unparsable"))
            continue
        errs = []
        try:
            passed = fn(rows, errs)
            ev = "; ".join(errs) if errs else "ok"
        except Exception as e:
            passed, ev = False, f"grader exception: {e}"
        results.append(dict(text=text, passed=bool(passed), evidence=ev))
    g_ok = png_valid(os.path.join(out, "gantt.png"))
    results.append(dict(text="gantt.png exists and is a valid PNG", passed=g_ok,
                        evidence="valid PNG header" if g_ok else "missing or invalid"))
    with open(os.path.join(IT, eval_dir, config, "grading.json"), "w") as f:
        json.dump(dict(expectations=results), f, indent=2)
    npass = sum(r["passed"] for r in results)
    print(f"{eval_dir}/{config}: {npass}/{len(results)} passed")


# ---------------- eval 0: website launch ----------------
W_PREC = [("W1", "W2"), ("W1", "W3"), ("W3", "W4"), ("W4", "W6"), ("W5", "W6"),
          ("W2", "W7"), ("W6", "W8"), ("W7", "W8"), ("W8", "W9")]
W_AGG = dict(W1=3, W2=5, W3=4, W4=6, W5=8, W6=4, W7=3, W8=2, W9=3)
ev0 = [
    ("safe durations cut to ceil(safe/2) aggressive durations",
     lambda rows, e: durations_match(rows, W_AGG, e)),
    ("all precedence constraints respected",
     lambda rows, e: precedence_ok(rows, W_PREC, e)),
    ("no resource double-booking (capacity 1)",
     lambda rows, e: no_overlap(rows, e)),
    ("exactly one project buffer, placed at schedule end",
     lambda rows, e: pb_checks(rows)[0] and pb_checks(rows)[1] or e.append(pb_checks(rows)[3])),
    ("project buffer sized ~50% of critical chain",
     lambda rows, e: pb_checks(rows)[2] or e.append(pb_checks(rows)[3])),
    ("critical chain reflects dev resource link (W4 and W5 both critical)",
     lambda rows, e: (find(rows, "W4") or {}).get("critical") and (find(rows, "W5") or {}).get("critical")
     or e.append(f"W4 critical={(find(rows,'W4') or {}).get('critical')}, W5 critical={(find(rows,'W5') or {}).get('critical')}")),
    ("at least one feeding buffer protects a non-critical chain",
     lambda rows, e: any(r["buffer_kind"] == "feeding" for r in rows)
     or e.append("no feeding buffer found")),
]

# ---------------- eval 1: lab trials ----------------
P_PREC = [("P1", "P3"), ("P3", "P4"), ("P2", "P5"), ("P4", "P5"), ("P2", "P6"),
          ("P4", "P6"), ("P5", "P7"), ("P6", "P8")]
P_DUR = dict(P1=6, P2=4, P3=5, P4=4, P5=6, P6=5, P7=3, P8=3)
ev1 = [
    ("durations used as given (already aggressive, NOT cut again)",
     lambda rows, e: durations_match(rows, P_DUR, e)),
    ("all precedence constraints respected",
     lambda rows, e: precedence_ok(rows, P_PREC, e)),
    ("no resource double-booking (eng/sci capacity 1)",
     lambda rows, e: no_overlap(rows, e)),
    ("exactly one project buffer, placed at schedule end",
     lambda rows, e: pb_checks(rows)[0] and pb_checks(rows)[1] or e.append(pb_checks(rows)[3])),
    ("project buffer sized ~50% of critical chain",
     lambda rows, e: pb_checks(rows)[2] or e.append(pb_checks(rows)[3])),
    ("secondary deliverable branch (P6->P8) protected by a buffer",
     lambda rows, e: any(r["is_buffer"] and r["start"] >= (find(rows, "P8") or {"finish": 1e9})["finish"] - 1e-9
                         for r in rows) or any(r["buffer_kind"] == "feeding" and r["start"] >= (find(rows, "P6") or {"finish": 0})["finish"] - 1e-9 for r in rows)
     or e.append("no buffer after P8/P6 branch")),
]

# ---------------- eval 2: kitchen ----------------
K_PREC = [("Demolition", "Electric"), ("Demolition", "Plumbing"), ("Electric", "Cabinet"),
          ("Plumbing", "Cabinet"), ("Cabinet", "Worktop"), ("Plumbing", "Tiling")]
K_DUR = {"Demolition": 4, "Electric": 3, "Plumbing": 3, "Cabinet": 5, "Worktop": 3, "Tiling": 4}
ev2 = [
    ("prose input normalized: all 6 tasks scheduled with 50%-cut durations",
     lambda rows, e: durations_match(rows, K_DUR, e)),
    ("all precedence constraints respected",
     lambda rows, e: precedence_ok(rows, K_PREC, e)),
    ("single builder never double-booked",
     lambda rows, e: no_overlap(rows, e)),
    ("exactly one project buffer, placed at schedule end",
     lambda rows, e: pb_checks(rows)[0] and pb_checks(rows)[1] or e.append(pb_checks(rows)[3])),
    ("project buffer sized ~50% of critical chain",
     lambda rows, e: pb_checks(rows)[2] or e.append(pb_checks(rows)[3])),
    ("Tiling on the critical chain (builder resource link)",
     lambda rows, e: (find(rows, "Tiling") or {}).get("critical")
     or e.append(f"Tiling critical={(find(rows,'Tiling') or {}).get('critical')}")),
]

CASES = [("eval-0-website-launch", ev0), ("eval-1-lab-trials", ev1),
         ("eval-2-kitchen-renovation", ev2)]
for eval_dir, checks in CASES:
    for config in ("with_skill", "without_skill"):        grade(eval_dir, config, checks)

