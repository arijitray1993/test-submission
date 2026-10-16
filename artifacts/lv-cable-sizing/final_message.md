# Agent's final message

I've written `output/submission.zip` with the five files at the top level. The package comes to **$148,640.96 installed** ($95,156 material, $53,485 labour). My own re-check of the zipped files, which recomputes everything from the submitted values, finds no errors, but there is no grader here, so that is the only verification it has had.

**Readings I took from the data room**
- **Codes:** NFPA 70 2023 and IBC 2024, adopted by UFC 1-200-01 (Change 4). Where documents disagree, the most restrictive governs. EDS-26 Rev 2 and E-601 Rev A are superseded and were not used.
- **Temperatures:** outdoor design 42 °C, roof 46 °C, earth 27.45 °C, all derived from the NOAA station record by the design standard's method. Interior ambients come from the mechanical memo: 40 °C ceiling cavity, 45 °C for MCC-1, the fire pump and the MCC-1 motor circuits.
- **Ground:** 0.60 K·m/W for the thermal backfill. The native-soil value of 0.95 was considered and rejected, and has its own row on the front sheet.
- **Voltage drop:** counted from the T-1 secondary lugs, with no restart at either low-voltage transformer. Limits are 3% cumulative on feeders, 3% on each branch circuit and 5% total; the fire pump is checked at 15% locked-rotor and 5% running.
- **Service entrance:** sized to the 2000 A main bus, not the 1600 A breaker. The result is 6 sets of copper 500 kcmil, giving 348 A per set by the duct-bank calculation.

**Main design results**
- **Service duct bank:** 10 ducts are available; I used 8 and left D3 and D7 empty as a thermal buffer. That spacing is what lets F-10 be aluminium 500 kcmil instead of copper.
- **The 208 V lighting panel is the critical path:** it reaches 2.77% at LP-1, so eight of its branch circuits were upsized to #8 or #6, with their grounding conductors increased in proportion.
- **F-05 (to Building 4212):** 3 sets of aluminium 600 kcmil, driven by B-17 (the shop compressor), which can't exceed #6 at its terminals.
- **Standardisation and discount:** exactly five sizes above #1 are used (4/0, 300, 400, 500, 600 kcmil). Total conductor length is 40,888 ft, so the 6% campus quantity break applies.
- **Optimality:** the optimiser searched every allowed five-size set, and a final check found no cheaper single or paired change that still complies.

**Judgement calls that could be graded differently**
- **Service voltage-drop load:** I used the 1600 A breaker rating, which the standard explicitly accepts. Using 2000 A instead would have cost about $20k more.
- **F-05 grounding conductor (3/0):** the "ampacity-alone" size it is scaled from respects the five-size limit, as the standard's wording says. If a reviewer ignores that limit, it would need to be 250 kcmil, about $2.1k more.
- **Size count:** I counted conductor sizes regardless of material. Counting copper and aluminium of the same size separately would mean six sizes, and meeting that stricter reading costs about $4.5k more.
- **Motor currents:** taken from the motor schedule. If the national code's table value were used for B-17, it would fail 3% at its #6 terminal limit.
- **Tight margins:**
  - F-10 sits only 0.7% above its required ampacity (302 A against 300 A per set). It stays above 300 A under every alternative reading of the duct-bank formula I tried.
  - B-15 meets its requirement exactly (65 A against 65 A).
- **Schedule columns:**
  - The design current is reported as the circuit total.
  - The current-carrying conductor count for the four roof-tray circuits is 18, the tray total used in the derating.
  - Tray fill (12.21 in against 16.2 in allowed) includes the grounding conductors.

These choices, and the rule behind each, are also written up in the design basis.
