# Machine retrofit — CCPM schedule summary

**Inputs:** `tasks.csv` (safe estimates), `resources.csv` (4 crew members, capacity 1 each).
**Method:** durations cut 50% (`ceil(safe/2)`) to aggressive; ALAP baseline; deterministic
earlier-only resource leveling; critical chain traced over precedence **and** resource links;
50%-rule buffers. Schedule verified with `validate_schedule.py` — **all checks passed**.
Times are working-day offsets from day 0.

## Headline numbers

| Metric | Value |
|---|---|
| Critical chain length | **23 working days** |
| Last task finishes | day 23 |
| Project buffer | **12 days** (ceil(0.5 x 23)) |
| **Promised completion** | **day 35** (end of project buffer — this is the commitment date) |

## Critical chain

> **R1 Strip down -> R4 Paint frame -> R7 Install panels -> R3 Refurbish spindle -> R6 Install spindle -> R9 Commission -> R10 Document & handover**

The chain is genuinely a *resource-leveled* critical chain, not the CPM critical path:

- The mechanical fitter carries 18 of the 23 task days (R1, R7, R3, R6, R9) — the project drum.
- Leveling found the fitter double-booked (first R7 vs R6, then R7 vs R3) and pulled
  **R7 Install panels earlier**, into the fitter's only idle window (days 7–9, while the frame
  is being painted on days 4–7).
- Consequently the chain runs **through the paint task** (R1 -> R4 -> R7) and contains a pure
  **resource link R7 -> R3** (no precedence arrow — just the shared fitter). A plain CPM trace
  would have missed both.

## Buffers

| Buffer | Protects | Span | Size | Sizing |
|---|---|---|---|---|
| **PB** (project buffer) | Commitment date | 23 -> 35 | 12d | 50% of critical chain (23d) |
| **FB1** (feeding-1: R2 Order parts) | R6 Install spindle start (day 15) | 9 -> 15 | 6d | 50% rule = 1d; grew to 6d because R2 must also finish by day 9 to feed R8 |
| **FB2** (feeding-2: R5 Upgrade wiring -> R8 Wire cabinet) | R9 Commission start (day 18) | 13 -> 18 | 5d | ceil(0.5 x 9d) |

Buffers attach with the CCPM-specific `:PB` / `:FB` link types (not FS): their **ends are
anchored** (day-35 commitment for PB; protected task starts for the FBs). If a task slips during
execution, the buffer is consumed from the left — the promise date does not move until its
buffer is exhausted.

## Schedule (from `schedule.csv`)

| id | name | chain | start | finish | dur | resources |
|---|---|---|---|---|---|---|
| R1 | Strip down machine | critical | 0 | 4 | 4 | mech |
| R4 | Paint frame | critical | 4 | 7 | 3 | paint |
| R5 | Upgrade wiring | feeding-2 | 4 | 9 | 5 | elec |
| R2 | Order parts | feeding-1 | 7 | 9 | 2 | plan |
| R7 | Install panels | critical | 7 | 9 | 2 | mech |
| R8 | Wire cabinet | feeding-2 | 9 | 13 | 4 | elec |
| FB1 | Feeding buffer | feeding-1 | 9 | 15 | 6 | — |
| R3 | Refurbish spindle | critical | 9 | 15 | 6 | mech |
| FB2 | Feeding buffer | feeding-2 | 13 | 18 | 5 | — |
| R6 | Install spindle | critical | 15 | 18 | 3 | mech |
| R9 | Commission | critical | 18 | 21 | 3 | elec; mech |
| R10 | Document and handover | critical | 21 | 23 | 2 | plan |
| PB | Project buffer | critical | 23 | 35 | 12 | — |

## Reading the Gantt (`gantt.png`)

- Dark red = critical chain; colored bars = feeding chains; hatched gold = buffers; the diamond
  at day 35 is the commitment date.
- The resource-utilization panel shows the fitter solidly booked days 0–4 and 7–21 with **no red
  blocks** — leveling holds, the crew is never over capacity.

## Execution notes

- Tasks use aggressive (50%) durations on purpose — about half will overrun individually; that
  is what the 12-day project buffer absorbs. Manage by buffer consumption, not task due dates.
- Start R5 (wiring) and R2 (parts order) no earlier than scheduled; their feeding buffers
  already protect the chain, and earlier starts just add WIP.
