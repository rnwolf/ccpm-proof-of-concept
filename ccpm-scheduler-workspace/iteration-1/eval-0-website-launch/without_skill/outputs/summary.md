# Website Relaunch — Critical Chain (CCPM) Schedule

## The headline

**Promised completion: working day 34.5 — commit to day 35.**

The critical chain itself finishes on day 23; the remaining 11.5 days is the
project buffer that protects the commitment. Compare that with a traditional
plan built on the safe estimates, which would run roughly 46 days — CCPM gets
you the same statistical protection in ~25% less calendar time, and the buffer
is shared instead of hidden inside every task.

## How the schedule was built

1. **Cut the safety out of the estimates.** Your durations are "safe"
   (high-confidence) estimates. CCPM plans with focused, 50%-confidence
   durations — each task was cut to 50% of its safe estimate.
2. **Resource-levelled the plan.** Each role has capacity 1, so tasks sharing
   a person cannot overlap. The developer is the busiest resource: backend
   (W5), frontend (W4) and integration (W6) had to be sequenced.
3. **Identified the critical chain** — the longest path through *both*
   dependency links and resource links:

   **W5 Build backend → W4 Build frontend → W6 Integrate → W8 Load content → W9 Launch QA = 23 days**

   Note that the W5 → W4 link is a *resource* link (same developer), not a
   logical dependency — this is exactly what classic critical-path analysis
   misses.
4. **Sized the buffers** at 50% of the chain they protect:
   - **Project buffer: 11.5 days** after W9 → promise = day 23 + 11.5 = **34.5**.
   - **Feeding buffer into W8: 5.5 days** protecting the content chain
     (W1 → W2 → W7, 11 days of work).
   - **Feeding buffer into W4: 1 day** (truncated). The design chain
     (W1 → W3) wanted 3.5 days of buffer but only 1 day of slack exists before
     the developer becomes available at day 8. **This makes W1 → W3 the
     riskiest feeding path — watch it closely**, since any slip beyond 1 day
     there eats directly into the project buffer.

## The schedule (working days from project start)

| ID | Task | Resource | Safe est. | Focused | Start | End | Critical chain |
|----|------|----------|----------:|--------:|------:|----:|:--------------:|
| W1 | Content outline | writer | 6 | 3 | 0 | 3 | |
| W5 | Build backend | dev | 16 | 8 | 0 | 8 | **CC** |
| W2 | Draft copy | writer | 10 | 5 | 3 | 8 | |
| W3 | Design mockups | designer | 8 | 4 | 3 | 7 | |
| — | Feeding buffer → W4 | | | 1 | 7 | 8 | |
| W4 | Build frontend | dev | 12 | 6 | 8 | 14 | **CC** |
| W7 | Edit copy | editor | 6 | 3 | 8 | 11 | |
| — | Feeding buffer → W8 | | | 5.5 | 11 | 16.5 | |
| W6 | Integrate | dev | 8 | 4 | 14 | 18 | **CC** |
| W8 | Load content | writer | 4 | 2 | 18 | 20 | **CC** |
| W9 | Launch QA | qa | 6 | 3 | 20 | 23 | **CC** |
| — | **Project buffer** | | | **11.5** | 23 | **34.5** | **CC** |

## How to run it

- **Don't manage task due dates** — tasks have no individual deadlines in
  CCPM. People work at focused pace and hand off as soon as they finish
  (relay-runner behaviour). Early finishes must be passed on immediately.
- **Manage by buffer consumption.** Track what fraction of the 11.5-day
  project buffer has been eaten versus how far along the critical chain you
  are. Green (<33% consumed): do nothing. Yellow (33–67%): plan recovery.
  Red (>67%): act.
- **Protect the developer.** Dev is on the chain from day 0 to day 18 —
  keep them free of multitasking and interruptions; any dev delay is a
  project delay, day for day.

## Files

- `schedule.csv` — full task/buffer schedule with safe vs focused durations
- `gantt.png` — Gantt chart (red = critical chain, blue = feeding tasks, amber = feeding buffers, green = project buffer)
