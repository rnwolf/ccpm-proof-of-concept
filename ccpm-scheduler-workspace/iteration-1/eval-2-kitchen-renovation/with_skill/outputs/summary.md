# Kitchen Renovation — Critical Chain Schedule

## Assumptions

- Your estimates (8, 6, 6, 10, 6, 8 days) are **safe** estimates — you said they're comfortable with slack built in — so per CCPM practice the schedule uses **aggressive durations at the classic 50% cut**: Demolition 4, Electrics 3, Plumbing 3, Cabinets 5, Worktops 3, Tiling 4. The removed safety is pooled into shared buffers instead of being hidden inside each task.
- One builder, one electrician, one plumber, each able to do one task at a time.
- Times are working-day offsets from day 0.

## The critical chain

**Demolition → Plumbing → Tiling → Cabinets → Worktops & finishing** (19 working days of task time)

Note this is *not* the classic critical path (which would be Demolition → Electrics/Plumbing → Cabinets → Worktops, 15 days). The builder is the constraining resource: Tiling and Cabinets both need the builder, so Tiling sits **on** the critical chain via a resource link — Cabinets can't start until the builder finishes Tiling, even though there's no precedence arrow between them. This is exactly the kind of dependency ordinary CPM misses.

## Schedule

| ID  | Task                   | Chain     | Start | Finish | Duration | Resource    |
|-----|------------------------|-----------|------:|-------:|---------:|-------------|
| DEM | Demolition             | critical  | 0     | 4      | 4        | builder     |
| PLU | Plumbing               | critical  | 4     | 7      | 3        | plumber     |
| ELE | Electrics              | feeding-1 | 6     | 9      | 3        | electrician |
| TIL | Tiling                 | critical  | 7     | 11     | 4        | builder     |
| FB1 | Feeding buffer 1       | feeding-1 | 9     | 11     | 2        |             |
| CAB | Cabinets               | critical  | 11    | 16     | 5        | builder     |
| WOR | Worktops and finishing | critical  | 16    | 19     | 3        | builder     |
| PB  | Project buffer         | critical  | 19    | 29     | 10       |             |

## Buffers

- **Project buffer: 10 days** (half the 19-day critical chain, rounded up), placed after Worktops. The **promised completion is day 29**, not day 19 — the buffer is real calendar time that protects the commitment against overruns anywhere on the chain.
- **Feeding buffer 1: 2 days** protecting Electrics (the only non-critical task) where it feeds into Cabinets. Electrics is scheduled days 6–9 so even a 2-day electrical overrun won't delay the cabinet start on day 11.

## How to read this in practice

- Tell the trades the aggressive durations and expect roughly half of tasks to overrun them — that's normal and what the buffers absorb.
- Watch **project buffer consumption** as the leading indicator of project health, not individual task dates.
- The plumber's work (day 4–7) gates both Tiling and Cabinets; the electrician has a comfortable window (any 3 days inside days 4–9 still beats the feeding buffer).
- Compared with a traditional plan that takes each padded estimate at face value sequentially, you commit to **29 working days** with explicit, visible protection instead of ~38 days of hidden padding.

Files: `schedule.csv` (machine-readable schedule), `gantt.png` (buffer-aware Gantt chart), `tasks.csv` / `resources.csv` (normalized inputs), `ccpm_schedule.py` (reproducible scheduling script). Validation: `validate_schedule.py` reports **VALID — all checks passed**.
