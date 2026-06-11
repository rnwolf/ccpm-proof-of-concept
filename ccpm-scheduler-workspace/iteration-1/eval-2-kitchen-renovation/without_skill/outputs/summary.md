# Kitchen Renovation — Critical Chain Schedule

## Headline

**Plan to finish in 29 working days** (about 6 weeks): a 19-day critical chain plus a 10-day project buffer. The 19-day target is aggressive by design — you should expect to dip into the buffer, and that's fine. The buffer is there to absorb it.

## How the schedule was built (CCPM method)

1. **Cut the padded estimates in half.** You said your estimates were comfortable with slack built in. Critical Chain takes that slack out of each task and pools it where it actually protects the project — at the end. Each task gets a "focused" duration of 50% of your estimate.
2. **Resolved the resource contention.** The builder is your constraint: they do Demolition, Tiling, Cabinets, and Worktops. Although Tiling and Cabinets could overlap on paper (different dependency paths), one builder can't do both, so they were sequenced.
3. **Identified the critical chain** (longest path including resource dependencies):
   **Demolition → Plumbing → Tiling → Cabinets → Worktops & finishing = 19 focused days.**
4. **Added buffers.** Project buffer = 50% of the critical chain (10 days) at the end. A 2-day feeding buffer protects the Cabinets start from any delay in Electrics (the only non-critical task).

## The schedule

| Task | Resource | Your estimate | Focused duration | Start day | Finish day | Chain |
|---|---|---|---|---|---|---|
| Demolition | Builder | 8d | 4d | 0 | 4 | Critical |
| Electrics | Electrician | 6d | 3d | 4 | 7 | Feeding |
| Plumbing | Plumber | 6d | 3d | 4 | 7 | Critical |
| Feeding buffer (Electrics) | — | — | 2d | 7 | 9 | Buffer |
| Tiling | Builder | 8d | 4d | 7 | 11 | Critical |
| Cabinets | Builder | 10d | 5d | 11 | 16 | Critical |
| Worktops & finishing | Builder | 6d | 3d | 16 | 19 | Critical |
| Project buffer | — | — | 10d | 19 | 29 | Buffer |

(Days are working days from project start; day 0 = morning of day 1.)

## Key scheduling decision: Tiling before Cabinets

Tiling only needs Plumbing finished, so the builder tiles on days 7–11 (which would otherwise be dead time), then fits Cabinets and Worktops behind it. This keeps the builder continuously busy from day 7 onward and gives Electrics genuine slack: it finishes day 7 but isn't needed until Cabinets start on day 11 — that slack is where its 2-day feeding buffer sits. Sequencing Tiling last gives the same 19-day chain but leaves no slack anywhere, so tiling-first is the more robust ordering. The builder does have an unavoidable 3-day gap (days 4–7) while the electrician and plumber work — worth telling the builder up front so they can plan around it.

## How to run it

- **Treat focused durations as targets, not commitments.** Roughly half of tasks will overrun them — that's expected and absorbed by the project buffer.
- **Relay-race behaviour:** start each task as soon as its predecessor hands over, and have the next trade ready. Pre-book the electrician and plumber for day 4 (with a heads-up if demolition runs fast or slow).
- **Monitor buffer consumption, not task dates.** Rough traffic lights for the 10-day project buffer:
  - 0–3 days consumed: green, no action
  - 4–7 days consumed: amber, plan recovery options
  - 8+ days consumed: red, act (extra hands, weekend work, descope finishing touches)
- **Watch Electrics:** it only has a 2-day feeding buffer plus 2 days of slack. If the electrician slips more than ~4 days, it starts pushing Cabinets and eats project buffer.

## Files

- `schedule.csv` — the full task table with both estimate sets, dates, and dependencies
- `gantt.png` — Gantt chart with the critical chain in red and buffers hatched
