# Agent's final message

I've written **Line2_Record_Set_Reconciliation.docx** (saved at `/filesystem/`), with the three sections you asked for. None of the five drawings can go into Simone's pack on its current issue. Four need re-issuing as as-built drawings, checked by 08/14 and issued by Denise on 08/17, so she starts prep on 08/18 with a finished set.

## The calls

| Drawing | Call | Into Simone's pack as |
|---|---|---|
| Power schematic (PWR-002) Rev C | Re-issue as Rev D | Rev D (Rev C kept only with RFI-014 as the change history) |
| Priya's field markup, 07/09 | Retire it to the change history | Change history only |
| MCC general arrangement (MCC-001) Rev B | Re-issue as Rev C | Rev C |
| Cable schedule (CBL-001) Rev B | Re-issue as Rev C | Rev C |
| Device list (DEV-001) Rev B | Re-issue as Rev C | Rev C |

## Why not present Rev C with RFI-014 and the markup

The standard allows that route, but it can't work here:
- **The markup isn't on a true print of Rev C.** It shows a different incomer and puts the press, sander and conveyor on the wrong MCC sections. It also gives the fuse as "Bussmann-style" rather than the fitted Bramble BFW-80aR, and nobody has checked it.
- **Every drawing leaves out installed equipment, and no RFI covers it.** Eleven drives are installed; the general arrangement and device list show four, the schematic five and the cable schedule six. Simone's Item 2 would fail on the device list alone.
- **Idris's booking asks for the controlled schematic matching the as-built.** A markup doesn't give him that.

## What has to happen before the drawings, all by 08/14
- **Screen bonding (RFI-025):** close it this Monday. The drawings already say 360° bonding at both ends; Priya's notes show screens bonded at one end only, by pigtail. The field gets fixed, not the drawings.
- **Refiner feeder:** on the cable schedule's own figures, 6 mm² fails derating (64.7 A needed against 49 A). Dougie needs to confirm what's actually installed. If it is 6 mm², it gets re-cabled under its own RFI.
- **Vendor RFIs:** Callan has to get DriveTec's answers on RFI-022 (refiner motor cable about 6 m longer than scheduled) and RFI-031 (EMC filter placement).
- **Denise's records:** she has to send the decisions on RFI-017, 021 and 029, and confirm what was issued as MCC-001 "Rev B". Documents dated before 07/08 already cite a Rev B, which suggests the letter was used twice.

## Not in Dougie's queue
- **Refiner motor replacement.** The drive's own 08/06 export still holds the factory-template motor data (30 kW / 58 A), and that's what the failed tunes ran against. Callan's email says nameplate values were entered the day before; the export doesn't show that, so check before authorising the order.
- **Sander cable re-pull.** The IR record says the sander's drive-output conductors were "not disturbed", unlike the other twelve circuits. Re-test properly before deciding anything. If a re-pull is needed, the spare cable in Rack 12-A is unscreened and can't go on a drive output.

If any re-issue isn't checked by 08/14, the file note records escalation to Grainne that day under §7 of the restart criteria.

I drafted the covering note and file note in your name as Red James. I treated the markup as the fifth drawing, since it's the fifth file in Engineering/Drawings. The covering note also lists, for Denise's awareness, problems she'll hit in the non-drawing records at pack assembly: the drive parameter record, the sander IR fail and the isolation log.
