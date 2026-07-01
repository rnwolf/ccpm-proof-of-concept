# Worked example — 6-task network, one resource conflict

Input (`examples/tasks.csv`, `examples/resources.csv`):

| id | name      | duration_safe | predecessor_ids | resource_ids |
|----|-----------|---------------|-----------------|--------------|
| A  | Spec      | 10            |                 | blue         |
| B  | Build     | 20            | A               | green        |
| C  | Design    | 10            | A               | blue         |
| D  | Integrate | 20            | B               | blue         |
| E  | Test rig  | 10            | C               | green        |
| F  | Commission| 10            | D;E             | red          |

Resources: blue, green, red — capacity 1 each.

(The example CSVs also carry an optional `url` column on tasks and resources — a link to each item's detail page. It plays no part in the computation and is omitted from the tables below; it simply passes through to `schedule.csv` and becomes markdown links in the summary. There is also an `examples/calendar.csv` with availability overrides — green in training days 2–4, red on another project days 0–10. Both outages fall where those resources have no work in this schedule, so every step below is unchanged; they exist to show the format and to render as grey "unavailable" blocks on the chart.)

## Step 0 — Aggressive durations (50% cut)

A=5, B=10, C=5, D=10, E=5, F=5.

## Step 2 — ALAP baseline

Forward pass: longest path A→B→D→F = 5+10+10+5 = 30 = T.
Backward pass (late starts): F 25–30, D 15–25, B 5–15, A 0–5, E 20–25, C 15–20.

## Step 3 — Resource leveling

Conflict: C (blue, 15–20) overlaps D (blue, 15–25). Total path through D (A→B→D→F) = 30; through C (A→C→E→F) = 20. D is more critical and stays; C shifts earlier so it finishes at D's start: **C 10–15**. C's predecessor A finishes at 5 ≤ 10, no ripple. No further conflicts (blue: A 0–5, C 10–15, D 15–25; green: B 5–15, E 20–25).

## Step 4 — Critical chain

Latest finish: F (30). F.start = 25 → who finishes at 25? D (precedence pred) and E (precedence pred). Both precedence: pick longer path back — D (A→B→D = 25) over E (A→C→E = 15). D.start = 15 → B finishes 15 → B. B.start = 5 → A finishes 5 → A.

**Critical chain: A → B → D → F** (length 30).

## Step 5 — Feeding chain

C and E are non-critical; they reach the chain at F. **Feeding chain: C → E**, join point F (start 25).

## Step 6 — Buffers

- Project buffer: ceil(0.5 × 30) = **15**. Placed 30–45. Promised completion: **day 45**.
- Feeding buffer (C→E): ceil(0.5 × 10) = **5**. E must finish by 25 − 5 = 20 → shift chain earlier: **E 15–20, C 10–15** (C unchanged). FB1 occupies 20–25. New conflicts? green: B 5–15, E 15–20 — none. No negative starts.

## Final schedule

| id  | name       | type           | chain     | start | finish | duration | resource_ids | predecessor_ids |
|-----|------------|----------------|-----------|-------|--------|----------|--------------|-----------------|
| A   | Spec       | task           | critical  | 0     | 5      | 5        | blue         |                 |
| B   | Build      | task           | critical  | 5     | 15     | 10       | green        | A               |
| C   | Design     | task           | feeding-1 | 10    | 15     | 5        | blue         | A               |
| D   | Integrate  | task           | critical  | 15    | 25     | 10       | blue         | B               |
| E   | Test rig   | task           | feeding-1 | 15    | 20     | 5        | green        | C               |
| FB1 | Feed buffer| feeding_buffer | feeding-1 | 20    | 25     | 5        |              | E:FB            |
| F   | Commission | task           | critical  | 25    | 30     | 5        | red          | D;E             |
| PB  | Proj buffer| project_buffer | critical  | 30    | 45     | 15       |              | F:PB            |

Task-to-task links here are plain FS; the buffers attach with the CCPM-specific `:FB` / `:PB` types, drawn as dashed arrows. FB1's end (25) is anchored to F's start — the task it protects; PB's end (45) is the commitment date. If the input used typed links (`A:SS+2` etc.) they would appear unchanged in this column and as labeled arrows on the Gantt.

Project duration without buffer: 30 days. Promised completion: day 45.
