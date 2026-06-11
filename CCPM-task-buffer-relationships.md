When building your own CCPM-aware Gantt charting logic, it is usually best to treat Project Buffers and Feeding Buffers as a distinct dependency type rather than as ordinary FS links.

Using plain FS relationships alone is usually not enough to reproduce CCPM behavior correctly.

### Why normal Gantt rules are insufficient

A conventional Gantt engine assumes:

1. Tasks are real activities.
2. Predecessor dates directly drive successor dates.
3. Slack/float is implicit and usually collapses when predecessors slip.

Buffers behave differently:

| Aspect | Normal Task | CCPM Buffer |
| --- | --- | --- |
| Consumes resources? | Yes | No |
| Represents work? | Yes | No |
| Moves when predecessor slips? | Usually yes | No (buffer shrinks instead) |
| Purpose | Deliver work | Protect schedule |

If you model a Project Buffer as a normal FS successor task, many gantt plotting engines will do the wrong thing visually:

- shift the buffer block later,
- move the project end date,
- or recalculate float incorrectly.

That breaks the core CCPM rule: the committed project finish date stays fixed while buffer is consumed.

### Recommended approach

### Add a CCPM-specific relationship type

In your data model, keep standard CPM links, but add CCPM-aware ones.

For example:

| Code | Meaning | Behavior |
| --- | --- | --- |
| FS | Finish-to-Start | Normal CPM logic |
| SS | Start-to-Start | Normal CPM logic |
| FF | Finish-to-Finish | Normal CPM logic |
| SF | Start-to-Finish | Normal CPM logic |
| PB | Project Buffer link | Protects project end date |
| FB | Feeding Buffer link | Protects Critical Chain task |

Making reationships explicit helps both scheduling logic and visualization.

### Scheduling semantics

### Project Buffer (PB)

A PB relationship means:

- the predecessor task is on the Critical Chain,
- the buffer duration is reserved time,
- the project commitment date is fixed,
- late finish consumes buffer instead of moving the buffer.

Pseudo-rule:

Project Buffer rule

If Critical Chain task finishes late, reduce remaining project buffer by the delay. Do not move the project finish milestone unless remaining buffer &lt; 0.

Visually, the buffer bar stays anchored to the project completion milestone.

### Feeding Buffer (FB)

An FB relationship means:

- a non-critical feeder path merges into the Critical Chain,
- the buffer protects the downstream Critical Chain task,
- delays on the feeder path consume the feeding buffer first.

Pseudo-rule:

Feeding Buffer rule

If feeder path finishes late, reduce remaining feeding buffer by the delay. Only when the feeding buffer is exhausted may the protected Critical Chain task shift.

Visually, the Feeding Buffer is anchored to the protected Critical Chain task, not freely floating.

### How to plot the Gantt correctly

### Data model example

| TaskID | Duration | PredID | RelType |
| --- | --- | --- | --- |
| A | 10d |  |  |
| B | 8d | A | FS |
| PB1 | 5d | B | PB |

### Rendering logic

1. Schedule normal tasks using standard CPM rules.
2. For PB:

    - place the buffer immediately before the fixed project finish milestone,
    - do not reschedule it when predecessors slip,
    - instead track remaining buffer separately.

3. For FB:

    - place the buffer immediately before the protected Critical Chain task,
    - allow feeder-path slippage to consume the buffer before shifting the protected task.

### Visual distinction matters

Users should be able to see that buffers are different from tasks. Common conventions:

- different color (e.g., orange or gray),
- dashed outline,
- label showing remaining buffer (e.g., “PB 3d remaining”),
- no resource assignment.

This prevents people from treating buffers as work packages.

### Important nuance

You can still store buffers as rows in the same table as tasks. The key is that the relationship semantics and scheduling rules are different.

Better ot have a distinct relationship type (or at least a distinct task type with special dependency logic) is the right way to ensure CCPM buffers are plotted and updated correctly in a Gantt chart.

Trying to force CCPM buffers into ordinary FS logic usually leads to incorrect movement of buffers and thus a misleading project date.