# Lab validation project — CCPM schedule summary

**Inputs:** `tasks.csv` (8 tasks), `resources.csv` (eng, sci — capacity 1 each).
Durations were supplied as **already-aggressive** estimates and were used as-is — no further 50% cut was applied; protection comes entirely from the buffers.
Both reports (P7 Report A, P8 Report B) are project deliverables; they were tied to a virtual end milestone so each is buffer-protected.

## Critical chain

**P1 Procure rig → P3 Install rig → P4 Calibrate → P5 Run trial A → P7 Report A** — 24 working days.

Note this chain alternates resources (eng → eng → sci → sci → sci): P4 follows P3 by precedence, and the leveling pass resolved the scientist conflict between P2 (Write protocol) and P4 (Calibrate) by shifting P2 earlier to days 7–11, since the path through P4 (24d) dominates the path through P2 (13d).

## Buffers

| Buffer | Protects | Computed (50% rule) | Placed | Position |
|--------|----------|--------------------:|-------:|----------|
| PB  | Project commitment | 12d | 12d | days 24–36 |
| FB1 | P5 start, from feeding chain P2 | 2d | 4d | days 11–15 |
| FB2 | Project end, from feeding chain P6 → P8 | 4d | 1d | days 23–24 |

- **FB1 (4d placed vs 2d computed):** resource leveling forces P2 to finish by day 11 (the scientist is then booked solid on P4 → P5 → P7), leaving a 4-day gap to P5's start. The whole gap is absorbed as buffer — Write protocol has 4 days of protection before it can threaten Trial A.
- **FB2 (1d placed vs 4d computed) — watch this chain.** Run trial B → Report B cannot shift earlier than day 15 because Trial B needs the calibrated rig (P4, critical chain, finishes day 15). Only 1 day of feeding buffer fits. The B branch (P4 → P6 → P8 = 23d through the network vs 24d critical) is near-critical: any slip on Trial B or Report B beyond 1 day starts consuming the **project buffer** directly. In execution, monitor P6/P8 with nearly the same attention as the critical chain.

## Key dates (working-day offsets, day 0 = project start)

- Last critical-chain task (Report A) finishes: **day 24**
- **Promised completion (end of project buffer): day 36**
- Report B finishes day 23 (+1d feeding buffer); Report A finishes day 24 — both reports land before the buffer, and both are protected by the 12-day project buffer.

## Schedule

| id  | name             | type           | chain     | start | finish | dur | resources | predecessors |
|-----|------------------|----------------|-----------|------:|-------:|----:|-----------|--------------|
| P1  | Procure rig      | task           | critical  | 0     | 6      | 6   | eng       |              |
| P3  | Install rig      | task           | critical  | 6     | 11     | 5   | eng       | P1           |
| P2  | Write protocol   | task           | feeding-1 | 7     | 11     | 4   | sci       |              |
| FB1 | Feeding buffer 1 | feeding_buffer | feeding-1 | 11    | 15     | 4   |           | P2:FB        |
| P4  | Calibrate        | task           | critical  | 11    | 15     | 4   | sci       | P3           |
| P6  | Run trial B      | task           | feeding-2 | 15    | 20     | 5   | eng       | P2;P4        |
| P5  | Run trial A      | task           | critical  | 15    | 21     | 6   | sci       | P2;P4        |
| P8  | Report B         | task           | feeding-2 | 20    | 23     | 3   | eng       | P6           |
| P7  | Report A         | task           | critical  | 21    | 24     | 3   | sci       | P5           |
| FB2 | Feeding buffer 2 | feeding_buffer | feeding-2 | 23    | 24     | 1   |           | P8:FB        |
| PB  | Project buffer   | project_buffer | critical  | 24    | 36     | 12  |           | P7:PB        |

Buffers attach via `:FB` / `:PB` link types (ends anchored; predecessor slippage consumes the buffer rather than pushing the commitment date). Validation: `validate_schedule.py` — **VALID, all checks passed** (precedence, resource capacity, buffer placement, no negative starts). Resource utilization in `gantt.png` confirms eng and sci never exceed capacity 1.

## Execution notes

- The commitment date is **day 36**; the day-24 finish of Report A is the plan, not the promise. Track buffer consumption, not task due dates.
- Relay risk on the scientist: sci runs back-to-back from day 7 to day 24 (P2 → P4 → P5 → P7). Make sure the scientist is protected from multitasking during this window.
- FB2 is thin (1d). Treat P6/P8 as near-critical during execution.
