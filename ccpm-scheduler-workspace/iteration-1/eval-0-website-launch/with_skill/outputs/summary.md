# Website relaunch — CCPM schedule

## Headline

**Promised completion: end of working day 36** (day 0 = project start, durations in working days).

The work itself is scheduled to finish on day 24; the remaining 12 days are the project buffer. You commit to day 36, and any task overruns eat buffer instead of slipping the promise.

## Assumptions

- Your CSV durations were treated as **safe estimates**, as you said. Each was cut to the classic aggressive estimate of `ceil(safe / 2)` (e.g. Build backend 16 -> 8 days). The removed safety is pooled into the buffers below — don't re-pad the task estimates.
- All five resources (writer, designer, dev, editor, qa) can do one task at a time.

## Critical chain

**W5 Build backend -> W4 Build frontend -> W6 Integrate -> W8 Load content -> W9 Launch QA** — 23 working days of aggressive-duration work.

Note the chain is not a plain critical path: W5 -> W4 is a **resource link**, not a precedence link. Both need the developer, and after resource leveling it is the dev's continuous workload (backend, then frontend, then integration) that actually bounds the project. The developer is your most constrained resource — protect their focus.

## Buffers

| Buffer | Protects | Size | Placement |
|--------|----------|------|-----------|
| PB (project buffer) | Critical chain (23d) | 12 days | Days 24-36, after Launch QA |
| FB1 | Design mockups (W3) feeding Build frontend | 2 days | Days 7-9 |
| FB2 | Content outline -> Draft copy -> Edit copy (W1->W2->W7) feeding Load content | 6 days | Days 13-19 |

Buffers are scheduled blocks of calendar time, not slack: the promise date is the end of the project buffer.

## Schedule

| id | Task | Chain | Start | Finish | Duration | Resource |
|----|------|-------|------:|-------:|---------:|----------|
| W1 | Content outline | feeding-2 | 0 | 3 | 3 | writer |
| W5 | Build backend | critical | 1 | 9 | 8 | dev |
| W3 | Design mockups | feeding-1 | 3 | 7 | 4 | designer |
| W2 | Draft copy | feeding-2 | 5 | 10 | 5 | writer |
| FB1 | Feeding buffer 1 | feeding-1 | 7 | 9 | 2 | — |
| W4 | Build frontend | critical | 9 | 15 | 6 | dev |
| W7 | Edit copy | feeding-2 | 10 | 13 | 3 | editor |
| FB2 | Feeding buffer 2 | feeding-2 | 13 | 19 | 6 | — |
| W6 | Integrate | critical | 15 | 19 | 4 | dev |
| W8 | Load content | critical | 19 | 21 | 2 | writer |
| W9 | Launch QA | critical | 21 | 24 | 3 | qa |
| PB | Project buffer | critical | 24 | 36 | 12 | — |

The schedule passes the skill's validator: precedence, resource capacity (no double-booking of writer or dev), buffer placement, and chain continuity all check out.

## Files

- `schedule.csv` — machine-readable schedule (this table)
- `gantt.png` — buffer-aware Gantt chart (critical chain in red, feeding chains in colour, buffers hatched gold)

## Reading the plan

- **Day 36 is the date to promise externally.** Internally, drive to day 24.
- Backend build starts day 1, not day 0 — CCPM schedules as late as possible so work flows continuously once started; starting earlier would just create idle waiting at integration.
- If design or copy run late, they consume their feeding buffer first (2 and 6 days respectively) without touching the critical chain.
- During execution, track project-buffer consumption vs. critical-chain progress (fever chart) — that's the follow-on step once you begin, outside this planning exercise.
