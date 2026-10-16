The package is complete at `output/submission.zip`. It contains, for each of CUP, ANNEX and LAB, `CT_SCHEDULE_P.dxf` and `CT_CALC_P.xlsx`, plus `constraint_register.csv` (298 rows) and `design_basis.md`. Everything was checked with my own parser, since no grader is available: schema, keys, all values numeric, 180 off-design rows totalling 8,760 h, and one closed outline per cell. The real risk is not format; it is how closely my re-implementation of the simulation matches the grader's (see the last section).

## Selected designs

| | CUP | ANNEX | LAB |
|---|---|---|---|
| Cells | 4 × CTX-0600-S | 4 × CTX-0600-S | 3 × CTX-0900-H |
| Total flow (gpm) | 1,802 | 1,801 | 2,027 |
| Reset floor / offset (°F) | 65.5 / 11.4 | 79.35 / 11.6 | 57.5 / 8.75 |
| Cycles of concentration | 4.14 | 4.00 | 3.88 |
| Evaporation method declared | loss-factor | saturated-exit | loss-factor |
| Peak demand / spare (kW) | 515.1 / 528 | 571.1 / 590 | 634.1 / 641.1 |
| Net savings vs. basic design | $245k | $261k | $296k |
| Governing constraint (margin) | structural, 0.025 | water allocation, 0.001 | electrical, 0.011 |

All plants use SS-304 casings, DE-2 eliminators, premium 20 hp TEFC motors on VFDs, equalising lines, automatic blowdown and no basin heater.

## Key decisions

- **Weather basis:** design wet bulb is 75 °F + 5 °F = 80 °F (UFC 3-410-01 2-4.2.4). The failure case uses 76 °F + 5 °F = 81 °F (P100 5.1.3, RFI-031). The 99.6 % dry bulb is 41 °F, so no basin heater is needed.
- **Flow:** the lowest net cost comes from the minimum flow that keeps every operating cell at the 0.75 water-flow floor when only one chiller runs.
- **Why these cells:** larger cells don't fit the Rev C zones with clearances, and the CTX-1800-S is too loud. At LAB, the standard 0900-S casing exceeds the motor control centre spare (reduced per RFI-034); the high-efficiency 0900-H fits under it.
- **Cycles of concentration** are the scaling-index limit (≥ 5.60 at the design return temperature) truncated to two decimals.
- **Evaporation method differs by plant:**
  - ANNEX had to be saturated-exit: under loss-factor, no design with positive savings meets its 12,600 kgal allocation.
  - CUP and LAB use loss-factor for more margin; both also pass their allocations under saturated-exit.
  - The cost analysis prices saturated-exit water for every design, as EC-01 requires.
- **Conflict lines:** UFC 3-410-01 2-4.2.4 over P100 5.3.1; UFM 3-230-13 (2026) over UFC 3-230-13 (2023); M-401 Rev C over Rev B.

## Where it could still fail

- **ANNEX water allocation.** The best ANNEX design sits right on the allocation limit. I left about 0.1 % margin, which costs roughly 0.6 % of net savings. If the grader's saturated-exit annual makeup comes out more than ~0.1 % higher than mine, the allocation check fails. If it comes out materially lower, my net savings may fall more than 1 % short of the grader's best. Either outcome blocks the objective credit for all three plants.
- **CUP and LAB.** Their optima are not pinned to a limit and the cost surface is flat. Leaving out the 0.97 drive efficiency did not move them.
- **Smaller thin margins:**
  - Cycles of concentration are within 0.0005–0.003 of the allowable, plus the grader's 0.01 tolerance.
  - LAB peak demand has 1.1 % electrical margin.
  - One LAB bin (65 °F wet bulb / 97.5 °F dry bulb, 73 h) runs two chillers with only 0.08 % capacity to spare. If the grader stages a third there, it shifts annual energy slightly for any design near mine.

My working scripts are in `/work`; `designs.json` holds the design choices and re-running `final.py` then `docs.py` rebuilds the zip.