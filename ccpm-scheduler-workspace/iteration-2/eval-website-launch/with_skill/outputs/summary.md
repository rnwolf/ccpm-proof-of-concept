# Website relaunch — CCPM schedule summary

## Promised completion: **day 36** (end of project buffer)

All times are integer working-day offsets from day 0. The input `tasks.csv` contained safe
estimates only, so aggressive durations were derived with the classic 50% cut
(`ceil(duration_safe / 2)`); the removed safety is pooled into the buffers below.

## Critical chain

**W5 Build backend → W4 Build frontend → W6 Integrate → W8 Load content → W9 Launch QA**
(aggressive sum = 23 days; last task finishes day 24, project buffer runs to day 36)

Note the chain's first link is a **resource dependency, not a precedence arrow**: W4 (Build
frontend) waits for W5 (Build backend) only because both need the single developer. After
resource leveling, that resource link — not the W3→W4 precedence link — is what bounds W4's
start, so W5 is on the critical chain.

## Buffers

| Buffer | Protects | Size | Placement | Anchor (end) |
|--------|----------|------|-----------|--------------|
| PB | Critical chain (23d × 50%) | 12d | day 24–36 | Commitment date, day 36 |
| FB1 | feeding-1: W3 Design mockups (4d × 50%) | 2d | day 7–9 | Start of W4 (critical) |
| FB2 | feeding-2: W1→W2→W7 Content outline → Draft copy → Edit copy (11d × 50%) | 6d | day 13–19 | Start of W8 (critical) |

Buffers attach with `:PB` / `:FB` link types (not plain FS): their **ends are the anchors**.
If a predecessor slips, the buffer is consumed from the left — the commitment date (PB) and
the protected critical-chain task starts (FB) do not move until a buffer is fully consumed.

## Schedule

| id | name | type | chain | start | finish | dur | resources |
|----|------|------|-------|------:|-------:|----:|-----------|
| W1 | Content outline | task | feeding-2 | 0 | 3 | 3 | writer |
| W5 | Build backend | task | critical | 1 | 9 | 8 | dev |
| W3 | Design mockups | task | feeding-1 | 3 | 7 | 4 | designer |
| W2 | Draft copy | task | feeding-2 | 5 | 10 | 5 | writer |
| FB1 | Feeding buffer 1 | feeding_buffer | feeding-1 | 7 | 9 | 2 | — |
| W4 | Build frontend | task | critical | 9 | 15 | 6 | dev |
| W7 | Edit copy | task | feeding-2 | 10 | 13 | 3 | editor |
| FB2 | Feeding buffer 2 | feeding_buffer | feeding-2 | 13 | 19 | 6 | — |
| W6 | Integrate | task | critical | 15 | 19 | 4 | dev |
| W8 | Load content | task | critical | 19 | 21 | 2 | writer |
| W9 | Launch QA | task | critical | 21 | 24 | 3 | qa |
| PB | Project buffer | project_buffer | critical | 24 | 36 | 12 | — |

## How it was built

1. **ALAP baseline** (backward pass, aggressive durations): raw CPM length 22 days.
2. **Resource leveling**: W4 and W5 both demanded the developer on days 7–13; W4 carries the
   longer path through it (22 vs 17), so W5 shifted earlier to finish exactly at W4's start.
3. **Critical chain** traced back from W9 through precedence *and* resource links (W5 enters
   via the shared developer).
4. **Feeding buffers** inserted where the two feeding chains join the critical chain; the
   content chain (W1→W2→W7) and the design task (W3) were shifted earlier to make room,
   then the whole schedule was shifted right 2 days so the earliest start is day 0.
5. **Validated** with `scripts/validate_schedule.py` — all checks passed (precedence,
   resource capacity, buffer placement and link discipline, chain continuity, no negative
   starts).

## Reading the plan

- **Work the critical chain without interruption**: the developer (W5→W4→W6), then writer
  (W8), then QA (W9) are the relay runners — hand off immediately, no multitasking.
- Aggressive durations will be overrun about half the time — **that is expected and fine**.
  Overruns eat buffer; they do not change the day-36 promise until the buffer runs dry.
- The critical chain starts on day 1, not day 0 (the writer must start W1 a day before the
  backend work begins, so feeding chain 2 finishes in time for its buffer).
