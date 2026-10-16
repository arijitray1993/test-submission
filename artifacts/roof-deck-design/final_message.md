I've written `output/submission.zip` with the four files at its root. The design passes every check in my own re-analysis, which follows the model the criteria and lateral report describe. No verifier was available, so that is the only check it has had. Installed cost at the cost-plan rates is **$229,687**.

**Design.** 22 ga and 18 ga, 3 attachment patterns, 4 zones, 14 rectangles, all on the 6 ft grid. Deck area is 42,192 sf: 34,344 sf of 18 ga and 7,848 sf of 22 ga. No zone goes over a framed opening, and every cell an opening touches is left out.

| Zone | Spec | Rectangles | What drives it |
|---|---|---|---|
| DZ-1 | 18 ga, 36/9, 5 SCREW-10 | SW, NW corners and the whole east strip | Corner uplift of 101.2 psf, east-wall diaphragm shear of about 980 plf, and the drifts at the ends of the east screen wall SCR-E |
| DZ-2 | 22 ga, 36/9, 3 button punch | South and north perimeter strips, strip below RO-1 | Deliberately flexible south perimeter between the south frames, so the collector force stays down |
| DZ-3 | 22 ga, 36/9, 5 SCREW-10 | West wall strip | West-wall shear and stiffness |
| DZ-4 | 18 ga, 36/7, 3 SCREW-10 | Seven rectangles framing the three openings | Drifts from the enclosure, screens and rooftop units, too scattered to isolate within 14 rectangles |

**Key results**
- **Collector (seismic x, amplified ×2.0):** 51.2 kip against the 58 kip splice. A uniformly stiff deck pushes this past 58, which is why the south perimeter is kept flexible.
- **Diaphragm deflection (seismic y):** 1.41 in against the 1.60 in limit.
- **Diaphragm shear:** at most 95% of φSn in every zone.
- **Chord force:** at most 28.6 kip against 38 kip.
- **Classification:** semi-rigid in every lateral case.
- **Gravity:** at least 1 psf margin everywhere. For 22 ga I used the lower of the table value (106 psf) and the value recomputed from the catalogue formula (106.4 psf).

**Documents that governed**
- **Criteria:** EOR-DC-RD-01 Rev 2. Rev 1 is withdrawn, so the deck gets the unreduced 20 psf roof live load and the seismic weight includes 20% of the snow load.
- **Geometry:** the Rev C structural model. I used the relocated SCR-N position and ignored A-201 Rev B.
- **Ground snow:** 63 psf from the case study, with the importance factor applied once.
- **Gages:** 16 gage is a 14-week mill order against the 9-week allowance, so it is excluded.

**Basis values.** Flat roof snow pf = 43.66 psf; effective seismic weight W = 26.73 psf; roof diaphragm force Fpx = 195.4 kip.

**Interpretation choices that could differ from the grader's**
- **Cells on a drift-band edge:** I checked both readings — a drift band ending exactly on a cell line either loads only the cell it enters or both neighbours. The design passes both. Covering the "both cells" reading cost about $8,500 (≈4%) over the $221,187 alternative, which passes only the narrower reading.
- **Thin-wall end drifts:** I gave the ends of the screen walls their own drifts.
- **Superposition:** I separately checked drifts from different obstructions superimposed within one wind direction.
- **Windward drift width:** I took it as 4 × 0.75 hd, i.e. based on the windward drift height. If the grader uses the full hd, about 47 cells would need heavier deck and some would fail.
- **Diaphragm deflection:** reported as deflection relative to the braced-frame lines. Total displacement is about 2.9 in in seismic y, which no available deck can bring under 1.60 in.

Cost is about 24% above the rough lower bound I worked out (~$185k, ignoring the rectangle limit). The 14-rectangle limit is the main reason. My optimiser only searched layouts formed by repeated straight cuts; a faster search over other layouts was tried and abandoned as too slow.

The register has 99 rows. Each cites one current document and only numbers that document states.

Files are in `output/submission.zip`:
- `deck_design.xlsx`
- `roof_deck_plan.dxf`
- `constraint_register.xlsx`
- `design_basis.md`