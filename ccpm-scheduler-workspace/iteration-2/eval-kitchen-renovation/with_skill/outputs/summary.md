# Kitchen renovation — CCPM schedule

## Assumptions

- You said the estimates are comfortable ones with slack built in, so they were treated as **safe** durations and cut 50% to aggressive durations (`ceil(safe / 2)`). The removed safety is pooled into the buffers below — individual tasks are scheduled at the aggressive durations.
- Durations are working days; the schedule uses integer day offsets from day 0 (project start).
- Buffer sizing: 50% rule (buffer = half the protected chain's aggressive work, rounded up).

## Critical chain

**K1 Demolition → K3 Plumbing → K6 Tiling → K4 Cabinets → K5 Worktops and finishing** — 19 working days of aggressive work.

Note the chain runs through Plumbing and Tiling, not Electrics. The K6 → K4 link is a **resource dependency**: Tiling and Cabinets have no precedence arrow between them, but both need the single builder, so Tiling directly bounds when Cabinets can start. A plain critical-path analysis would miss this.

## Buffers

| Buffer | Protects | Size | Position |
|--------|----------|------|----------|
| PB (project buffer) | Critical chain (19d of work) | 10d | days 19–29, ends at the commitment date |
| FB1 (feeding buffer) | K2 Electrics (3d) feeding into K4 Cabinets | 2d | days 9–11, end anchored to K4's start |

## Schedule

| id | name | type | chain | start | finish | duration | resources |
|----|------|------|-------|-------|--------|----------|-----------|
| K1 | Demolition | task | critical | 0 | 4 | 4 | builder |
| K3 | Plumbing | task | critical | 4 | 7 | 3 | plumber |
| K2 | Electrics | task | feeding-1 | 6 | 9 | 3 | electrician |
| K6 | Tiling | task | critical | 7 | 11 | 4 | builder |
| FB1 | Feeding buffer | feeding_buffer | feeding-1 | 9 | 11 | 2 | — |
| K4 | Cabinets | task | critical | 11 | 16 | 5 | builder |
| K5 | Worktops and finishing | task | critical | 16 | 19 | 3 | builder |
| PB | Project buffer | project_buffer | critical | 19 | 29 | 10 | — |

## Headline numbers

- **Work finishes (if nothing slips): day 19**
- **Promised completion: day 29** (end of the project buffer — this is the date to commit to)
- For comparison, a schedule built from the original safe estimates would have planned roughly 38 days of sequential work along this chain; the buffered critical-chain plan promises day 29 while still carrying 10 days of explicit, visible protection.

## How to read it in execution

- The day-29 commitment is the fixed anchor. If a critical-chain task runs long, the project buffer is consumed from the left — the promise date does not move until the buffer is fully eaten.
- Likewise FB1's end stays glued to the start of Cabinets (day 11): if Electrics slips, it eats FB1 before it can delay the critical chain.
- Start tasks as scheduled in this as-late-as-possible plan and run them at full focus — don't pad them back up; the buffers carry the safety.

Validation: `validate_schedule.py` reports **VALID** — precedence, resource capacity (builder, electrician, plumber all ≤ 1 task at a time), buffer placement and link discipline all check out.

Files: `schedule.csv` (machine-readable schedule, buffers attached via `:PB`/`:FB` link types), `gantt.png` (Gantt with dependency arrows + resource-utilization panel).
