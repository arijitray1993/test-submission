# Agent's final message

I've written `output/submission.zip` with all six files. My own re-simulation, built from the output files alone, finds no violations. No verifier was available, so that checker reflects my reading of the corpus, not the grader's. It is the main risk if the grader reads a rule differently.

**Programme**
- **Coverage:** all 294 issued activities are in, with issued IDs and durations and every issued dependency, across all 42 zone-lifts.
- **Finish:** the last activity finishes on day 200, against the day-250 limit. The mean zone-lift finishes on day 94.7.
- **Peak usage:**

| Resource | Peak | Limit |
|---|---|---|
| Crane | 9.69 h/day | 10 |
| Gangs | 7 | 8 |
| Shoring yard | 3596 sf | 3600 |
| Scaffold face | 115.8 ft | 120 |
| Laydown | 15 units | 16 |

- **Order:** the order of zone-lifts was optimised (annealing plus small MILP repairs) to minimise the sum of finish days, which drives the 4 units/day programme price. A full LP relaxation puts the programme part at about 14,500 against about 15,700 for this schedule. Some of that gap may be the bound being loose rather than the schedule.

**Documents and method**
- TWP-09 rev C governs over rev B, and the issued activity list governs over the superseded baseline rev A. The facade method statement (MS-14) is out of scope.
- No register row cites rev B, rev A, MS-14 or the 1926.450 definitions file (TWP-09 doesn't list it among its adopted documents).
- Every slab is struck at its early-strike age (7 days pumped, 4 days crane-and-bucket), counted from the day after the pour finishes. RS-16 reshores go in on the strike day and stay until the pour finish plus 28 days.

**Temporary works**
- **Shoring:** SP-16 posts throughout, since the shorter posts don't reach the soffit. Grids are 3.5 ft or 4.0 ft depending on the load.
- **Scaffold:** SF-3 frames, except where heavy duty needs five planks; those don't fit a 3 ft frame, so SF-5 is used. Ties and rest platforms follow the CFR clauses literally, and L4 gets 9 frame lifts.
- **Stability:** 31 zone-lifts use an adjacent slab as the diaphragm; the other 11 use XB-1 cross-bracing.
- **Crane:** the crane works from CP-C wherever the chart allows. Z-D-S is served from CP-E because it sits about 38.5 ft from CP-C, inside the chart's 40 ft minimum radius.
- **Register:** 231 rows cover every parameter in the TWP-09 schedule plus the cited CFR clauses. CFR clauses appear in both short and long form to help matching.

**Readings I chose that you might want to revisit**
- **Paying extra for safety:**
  - Post and reshore counts use one post per grid cell, rounded up in each direction, rather than area divided by spacing squared. The area-based count can't actually be laid out at the stated spacing. This adds about 1,770 units, roughly 4.5% of the total price.
  - Light-duty platforms get 3 planks rather than 2, so plank self-weight is covered too.
  - A clear day is left between stair-core shoring windows and between successive lifts in the same zone. Each costs well under 1%.
  - Reshores count against the yard through day 28 inclusive.
- **Risk not hedged:** the yard plan assumes a zone's shoring leaves the yard at the end of its strike day. If the grader also counts shoring on the day after the strike, the shoring yard overflows on about 33 days, and that is a hard limit shared by every zone-lift. Guarding against it would have cost about 7% on the programme. I didn't do it because the procedure's wording ("a zone has to be struck before the next can be shored") supports my reading.
- **Lower-impact assumptions:**
  - "Shored to" in the occupancy report is the strike activity's finish day.
  - The designer is named by role rather than by a person's name.

The scripts that regenerate the package (and my checker) are in `/filesystem/work`, outside the task folder. `build.py final.json` rebuilds the files and the zip.
