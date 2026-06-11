# Lab Validation Project — CCPM Schedule

## Key decisions

**Durations were NOT cut.** You said the estimates in tasks.csv are already aggressive (padding stripped), so I used them as-is as the 50%-confidence task durations and added all protection as explicit buffers on top. No task was shortened.

**Both reports are protected.** Since Report A and Report B are both committed deliverables, each endpoint gets its own project buffer rather than treating Report B as a mere feeding chain.

## Critical chain

After resource leveling (1 test engineer, 1 scientist — capacity 1 each), the critical chain is:

**P1 Procure rig (6d) → P3 Install rig (5d) → P4 Calibrate (4d) → P5 Run trial A (6d) → P7 Report A (3d) = 24 working days**

This chain alternates between the engineer and scientist with hand-offs, and contains both precedence and resource dependencies. The schedule has zero resource contention: while the scientist runs Trial A, the engineer runs Trial B in parallel, so the two trials do not queue behind each other.

## Buffers

| Buffer | Size | Protects | Sizing rule |
|---|---|---|---|
| PB-A (project buffer, Report A) | 12d | Report A delivery | 50% of critical chain (24d) |
| PB-B (project buffer, Report B) | 12d | Report B delivery | 50% of its longest chain P1→P3→P4→P6→P8 (23d), rounded up |
| FB1 (feeding buffer) | 2d | Trial start (day 15) from protocol delays | 50% of feeding chain P2 (4d) |

Note on P2 (Write protocol): CCPM normally late-starts feeding chains, but the scientist is fully booked from day 11 onward (Calibrate → Trial A → Report A). P2 is therefore scheduled at day 0, in parallel with rig procurement, which removes any resource contention and still leaves the 2-day feeding buffer plus 9 days of slack before the trials need it.

## Schedule (Day 0 = Mon 15 Jun 2026, working days Mon–Fri)

| Task | Resource | Dur | Days | Dates |
|---|---|---|---|---|
| P1 Procure rig | eng | 6 | 0–6 | 15 Jun – 22 Jun |
| P2 Write protocol | sci | 4 | 0–4 | 15 Jun – 18 Jun |
| P3 Install rig | eng | 5 | 6–11 | 23 Jun – 29 Jun |
| P4 Calibrate | sci | 4 | 11–15 | 30 Jun – 3 Jul |
| FB1 Feeding buffer | — | 2 | 13–15 | (slack before trials) |
| P5 Run trial A | sci | 6 | 15–21 | 6 Jul – 13 Jul |
| P6 Run trial B | eng | 5 | 15–20 | 6 Jul – 10 Jul |
| P8 Report B | eng | 3 | 20–23 | 13 Jul – 15 Jul |
| P7 Report A | sci | 3 | 21–24 | 14 Jul – 16 Jul |
| PB-B Project buffer B | — | 12 | 23–35 | 16 Jul – 31 Jul |
| PB-A Project buffer A | — | 12 | 24–36 | 17 Jul – 3 Aug |

## Commitments

- **Report B: Friday 31 July 2026** (aggressive finish 15 Jul + 12d buffer)
- **Report A / project complete: Monday 3 August 2026** (aggressive finish 16 Jul + 12d buffer)

Expect roughly half of each buffer to be consumed in normal execution — that is what it is for. Track buffer consumption vs. critical-chain progress (fever chart): green below ~1/3 consumed, act when consumption outpaces chain completion.

## Execution notes

- The engineer's procurement task P1 starts the critical chain — any slip there moves everything; consider expediting the rig order.
- Hand-offs at day 11 (eng→sci), day 15 (sci→both) and day 21/20 (trials→reports) are relay-race points: the incoming resource should be ready to start immediately.
- No multitasking is required of either resource at any point in this schedule.

Files: `schedule.csv` (full task/buffer table), `gantt.png` (chart).
