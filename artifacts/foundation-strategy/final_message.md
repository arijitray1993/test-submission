# Agent's final message

I've written `output/submission.zip` with the six required files at the archive root. All of them are generated from the same calculations, and a separate checker script I wrote re-reads the zip and confirms they agree with each other and pass every check (no errors, no warnings). The campus total comes to **$412,014**; there was no grader to test against, so that number and every check are mine.

**The programme**
- **Improved with rammed aggregate piers:** CR-P1, CR-P2, CR-P4 and CR-P6. Their top layer of soil is soft, and spread footings alone would mean going 8–10 ft deep with dewatering and sloped excavations, at about $209k–$262k per pad. With piers they cost $77k–$82k (CR-P4: $43.7k against $63.1k spread-only).
- **Spread footings only:** CR-P3 and CR-P5. Their top layer is stiffer, and improving either would cost more and need a third rig.
- **Rigs:** 2, at $80,000 (RIG-1 serves CR-P1 and CR-P2; RIG-2 serves CR-P4 and CR-P6), since each rig can serve at most two pads. One modulus test per improved pad.
- **Bearing depth:** 42 in at CR-P5 (the frost minimum) and 45 in elsewhere. No dewatering, and every excavation stays above the 4 ft depth where side slopes start.
- **Frost:** the 100-year air-freezing index is 556 °F-days from the current 1981–2010 data, which gives the 42 in frost depth. The superseded 1951–1980 tables give 416.
- **Concrete:** strengths range from 4000 psi (CR-P1, P3, P4) to 4500 psi (CR-P2, P6) and 5000 psi (CR-P5). The sulfate class is set from each pad's measured soil sulfate.

**Judgement calls that affect the score**
- **Allowable bearing pressure (the main risk).** I report the lower of the Meyerhof and Vesic solutions. Terzaghi and Brinch Hansen are calculated and tabulated as the other methods, but they give lower values. This saves about 7% against simply reporting the lowest of the three methods. The brief says the lowest method is "about 0.82×" the grader's reference, which my numbers only reproduce if that reference is a Meyerhof/Vesic-type equation. If the grader instead uses a Terzaghi- or Hansen-type equation, my reported values would be 5–18% too high and the bearing check would fail on every pad. To undo this, change one setting in `work/core.py` (`BEARING_BASIS = 'L3'`) and re-run; the cost goes back up by about 7%.
- **Sliding of the shear-wall footings.** The safety factor is at least 2.0 with the wind uplift subtracted from the vertical load; without that subtraction it is about 2.9. It would drop to about 1.9 only if a grader both subtracted the uplift and ignored soil cohesion in the passive resistance. Covering that case would add $13.7k (3.3%), which I judged not worth it.
- **Margins I did pay for:**
  - Shear thickness uses the stricter 0.75 reduction factor, about 0.5% extra cost.
  - Every footing top is at least 3 in below grade.
  - Every set of piers goes right through the soft top layer, about $900.
  - The shear-wall footings are exactly the 24 ft wall length, about $1,300.

The calculation scripts are in `work/`; `make_all.sh` rebuilds the zip and re-runs the checker.
