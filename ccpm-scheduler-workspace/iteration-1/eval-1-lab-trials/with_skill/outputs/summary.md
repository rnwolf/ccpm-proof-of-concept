# Lab validation project — CCPM schedule

**Promised completion: working day 36** (end of the project buffer). The work itself ends on day 24; the 12-day project buffer absorbs the variation that the aggressive estimates no longer carry.

As requested, your durations were treated as **already aggressive — no further cut was applied**. Buffers were sized from those durations using the standard 50% rule.

## Critical chain

**P1 Procure rig → P3 Install rig → P4 Calibrate → P5 Run trial A → P7 Report A** — 24 working days.

Note the chain runs through both the engineer (procure/install) and the scientist (calibrate/trial A/report A). Trial A is on the chain rather than trial B because the scientist is busier overall (protocol, calibration, trial A, report A all need `sci`).

## Schedule

| id  | name             | type           | chain     | start | finish | dur | resources |
|-----|------------------|----------------|-----------|-------|--------|-----|-----------|
| P1  | Procure rig      | task           | critical  | 0     | 6      | 6   | eng |
| P3  | Install rig      | task           | critical  | 6     | 11     | 5   | eng |
| P2  | Write protocol   | task           | feeding-1 | 7     | 11     | 4   | sci |
| FB1 | Feeding buffer 1 | feeding_buffer | feeding-1 | 11    | 13     | 2   |     |
| P4  | Calibrate        | task           | critical  | 11    | 15     | 4   | sci |
| P6  | Run trial B      | task           | feeding-2 | 15    | 20     | 5   | eng |
| P5  | Run trial A      | task           | critical  | 15    | 21     | 6   | sci |
| P8  | Report B         | task           | feeding-2 | 20    | 23     | 3   | eng |
| P7  | Report A         | task           | critical  | 21    | 24     | 3   | sci |
| FB2 | Feeding buffer 2 | feeding_buffer | feeding-2 | 23    | 27     | 4   |     |
| PB  | Project buffer   | project_buffer | critical  | 24    | 36     | 12  |     |

## Buffers

- **Project buffer (PB): 12 days** (50% of the 24-day critical chain), days 24–36. The completion you commit to externally is **day 36**, not day 24.
- **Feeding buffer 1 (FB1): 2 days**, protecting *Write protocol* (P2) where it feeds *Run trial A*. P2 is scheduled late-as-possible (days 7–11) but still finishes 4 days before the trial needs it — 2 days of buffer plus 2 days of natural gap.
- **Feeding buffer 2 (FB2): 4 days**, protecting the trial-B branch (P6 → P8) where it merges with project completion. You said both reports matter, so this branch gets its own protection: Report B is due to finish day 23, with 4 buffer days carrying it to day 27 — still well inside the day-36 promise.

## Notes and caveats

- **Resource leveling shaped this plan.** *Write protocol* (P2) was pulled earlier (days 7–11) because the scientist is needed for *Calibrate* on days 11–15 — its naive late start would have collided. After leveling there are no resource conflicts: the engineer and scientist each have a clean, single-tasked sequence.
- **FB2 extends 3 days past the bare project end (day 24 → 27).** Trial B cannot start before calibration finishes (day 15), so its chain could only shift 1 of the 4 needed days earlier. The overrun simply sits inside the project-buffer window — both reports remain fully protected by the day-36 commitment. If Report B has its own external deadline earlier than day 27 plus slip, say so and that branch can be re-examined.
- **Run trials A and B in parallel (days 15–21)** — they use different people (sci vs eng). If in reality both trials need the same rig exclusively, add a `rig` resource to tasks.csv and re-level; that would lengthen the chain.
- **How to read this plan:** start tasks when their predecessor finishes (relay-runner style), report remaining duration daily, and track buffer consumption. Don't treat day 24 as the deadline and don't pad individual tasks — the buffers are the protection.
- Schedule validated with the skill's checker (`validate_schedule.py`): precedence, resource capacity, and buffer placement all pass.

Files: `schedule.csv`, `gantt.png`, solver script `ccpm_solve.py` (reproducible: `python ccpm_solve.py tasks.csv resources.csv schedule.csv`).
