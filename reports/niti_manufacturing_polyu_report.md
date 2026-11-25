# NiTi part manufacturing plan for PolyU IC

**Prepared 25 November 2026 · For the ASRC U4+M2 inspection-robot project**

## Executive summary

The project needs two different NiTi components:

- **16 U-module leaf springs**: four per U module, each about 94 mm long. The current CAD section notes show about 6 mm width and 1.03–1.18 mm thickness through the flexible span, with enlarged formed ends around 7.05 × 6.33 mm. Confirm this section interpretation against the native STEP/CAD and with the adviser before ordering stock. [Spring section data](cad/lanes_u4m2/guides_v2/spring_strip.json)
- **Two M-module backbone rods**: straight superelastic NiTi round stock, Ø1.80 × 96 mm each, one per M module. [Model data](simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md)

The PolyU IC public facilities pages list a metal laser cutter (0.7–2 mm for named materials including titanium), 4-axis wire EDM, abrasive waterjet machines, and a 5-axis CNC mill. The metallic laser is geometrically interesting for the leaf thickness, but the published compatible-material list does **not** name NiTi. Therefore no one should assume a machine is approved for NiTi until IC staff check the alloy, stock condition, machine, process, and safety requirements.

**Most practical development route to ask IC about:** first machine a small NiTi test coupon using the technician’s recommended process, then assess cut quality and spring response; for the leaf outline, ask first about the metallic laser (conditional on explicit NiTi approval) and wire EDM (including finish passes). Waterjet is another cold-cutting candidate, but the public PolyU listing does not publish its kerf/edge tolerance for this alloy. For the Ø1.8 mm rods, buy certified straight NiTi stock and ask staff to recommend a cutoff and end-finishing operation. Do not machine the rods from a large block.

## PolyU IC facilities found

| Facility | What PolyU publicly lists | Relevance and open question |
|---|---|---|
| **Metallic Laser Machining, W401j** | Cutting listed for stainless steel, galvanized iron, mild steel, carbon steel, and titanium; 0.7–2 mm material thickness; 600 × 600 mm work area; DXF, CDR, AI. | The spring’s flexible section thickness is within the listed thickness range, and titanium is named, but NiTi is a distinct alloy and not expressly listed. Ask if the specific NiTi grade/condition is allowed, whether staff will run a test coupon, what edge/HAZ cleanup is needed, and whether they produce the toolpath. [Official page](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/scn/metalliclasermachiningfacilities/) |
| **4-axis wirecut EDM, U004** | Agie Charmilles Robofil 240SL; 4-axis; 350/220/220 mm X/Y/Z and 350/220 mm U/V travel; metal contour cutting, suitable for hard metals; consultation booking requested. | A strong candidate for a precise 2D outline in conducting NiTi. Ask the technician about stock condition, start holes/tabs/fixturing, rough and finish passes, edge integrity, and which CAM/controller software and input they accept. EDM can create a recast layer; finish-pass options matter for fatigue-sensitive edges. [Official page](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/pmf/4axiswirecutedm/) |
| **Abrasive waterjet, W001** | 2-axis ProtoMAX: 300 × 300 mm envelope, up to 25 mm thickness, listed linear position accuracy ±0.15 mm. 5-axis OMAX 5555: 1.21 × 1.21 m envelope, listed ±0.025 mm linear position accuracy. Listed for metals and other materials; consultation e-booking requested. | A low-thermal-input profile-cutting candidate. Published linear accuracy is not a guarantee of edge quality, kerf, or tolerance for a small, thin NiTi leaf. Ask whether NiTi can be cut, which machine is appropriate, how thin stock is held, whether edges need finishing, and whether it can make the formed-end features accurately. [Official page](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/pmf/waterjet/) |
| **3–5-axis CNC milling, U004** | MIKRON HPM 600U 5-axis; 20,000 rpm; mainly copper, aluminium, steel, and titanium; prismatic and freeform machining; consultation booking requested. | Could machine a prototype from plate or a shaped blank, but machining NiTi can be difficult due to work hardening, cutting forces, and tool wear. Ask staff before generating a milling path; this is not the first-choice route for a thin spring outline. [Official page](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/pmf/3-5axiscnc/) |
| **9-axis CNC turn-mill / conventional lathe** | The general IC facility catalogue lists a 9-axis turn-mill and conventional machining facilities; exact model/process capability should be confirmed with IC. | Potentially relevant only for cutoff/end finishing of purchased Ø1.8 mm rod, not for milling a small rod from a large block. Confirm gripping method, cut length, burr control, and whether heat or work-hardening can damage the rod ends. [Facility catalogue](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/) |

PolyU says students should consult technical staff if unsure which process to use, that facility users need appropriate training/skill, and that bookings should be made in advance. The facilities FAQ lists eligible users and notes that some consumables such as laser cutting and EDM wire may be charged. [Booking FAQ](https://www.polyu.edu.hk/ic/research-and-project-support/facilities-booking-faq/)

## Recommended process plan

### A. U-module leaf springs

1. **Confirm the source geometry.** Open the U spring solids (solids 2–5) in `cad/modules/UniDirectional_96.step` and compare against [`U_leaf_springs.stl`](cad/lanes_u4m2/guides_v2/U_leaf_springs.stl) and [section JSON](cad/lanes_u4m2/guides_v2/spring_strip.json). The STL is for viewing/mesh reference; it is not a dimensioned 2D toolpath drawing. Ask the adviser to verify whether 1.03–1.18 mm is the material thickness and how the enlarged ends are formed.
2. **Do not start from a bulk block.** The spring is a slender profile. If it is intended to be constant-thickness strip with enlarged formed ends, buy strip/flat stock close to the flexible-section thickness and use a near-net-shape cutting method; machining from a thick block wastes material and makes the spring’s microstructure/surface history less predictable.
3. **Ask IC to rank approved routes for a small coupon first.** Candidate order: (a) metallic laser if IC explicitly approves NiTi and a trial cut shows acceptable edge integrity; (b) wire EDM with finish/trim pass and documented edge finishing; (c) abrasive waterjet if the technician confirms thin-stock support, kerf/tolerance, and a clean edge. CNC milling is a staff-guided fallback if profile cutting is unsuitable.
4. **Control the cut edge and forming history.** NiTi is sensitive to processing. Laser and EDM are thermal processes; papers report cut-zone HAZ/recast and fatigue effects that vary with machine and settings. One NiTi WEDM fatigue study found finish trim cuts improved fatigue life relative to the main cut for its tested material/conditions; this is a reason to ask about finish passes, not a transferable life multiplier. [WEDM fatigue study](https://doi.org/10.1177/09544054211028844) · [Laser microcutting surface integrity study](https://doi.org/10.1007/s00170-025-16528-1)
5. **Shape setting is a separate operation.** If the leaf ends or flexible span need a preset shape, ask the supplier or IC materials staff to define and validate the fixture, temperature-time recipe, atmosphere, and cooldown for the exact alloy/lot and desired superelastic behavior. Do not use a generic home-made heat recipe. A 2025 study shows that heat-setting history and starting material can alter transformation temperatures and plateau stresses. [Robertson et al., 2025](https://doi.org/10.1007/s40830-025-00541-0)
6. **Inspect and test before installing 16 pieces.** First make one or two sacrificial leaves and a small edge/process coupon. Measure critical dimensions, inspect cut edges under magnification, record any polishing/etching/finish pass, check spring force–curvature and recovery, then conduct a small cyclic test in a guarded fixture. Only proceed to the full set once the adviser approves the process and acceptance checks.

### B. M-module backbone rods

1. Ask the NiTi supplier for straight superelastic rod/wire of the correct alloy/condition and diameter, with a lot certificate and active transformation-temperature/test data.
2. Buy stock in straight lengths with enough allowance for cutoff and end finishing. The design uses Ø1.80 × 96 mm finished pieces; do not assume exact final length from supplier stock length.
3. Ask IC staff which approved saw, cutoff, lathe, or other operation can cut 1.8 mm NiTi without bending the rod, leaving a burr, or locally altering the heat treatment. Use a soft, length-controlled fixture to avoid nicking or scratching the highly cycled rod.
4. Deburr/polish only by a process the supplier/adviser approves. Inspect ends and measure diameter/length. Test the actual rod/end-bond or mechanical-retention joint separately from bare stock.

## Which software do you need?

There is **no single “CNC software”** that will program every IC machine. PolyU’s student computer rooms list AutoCAD and SOLIDWORKS among available engineering software, but the public pages do not disclose the CAM software, postprocessors, or controller workflow for the laser, EDM, waterjet, and mill. [IC software rooms](https://www.polyu.edu.hk/ic/study/learning-support/)

| Route | What you should prepare | What the machine/staff workflow usually does | Confirm with IC |
|---|---|---|---|
| Metallic laser | Clean 1:1 2D DXF profile plus material, thickness, quantity, tolerances, and grain/orientation note if relevant. PolyU lists DXF/CDR/AI. | Import geometry, set machine-specific kerf/lead-in/nesting and cutting parameters, then staff-approved machine program. | Are NiTi alloy and thickness approved? Do they want a DXF, and do they prefer to generate the cutting job themselves? What are layer/color/line-width rules, units, kerf and hold tabs? |
| Wire EDM | 2D DXF/DWG or STEP plus stock drawing, start-hole/fixture concept, thickness and tolerance targets. | Staff CAM/controller generates a machine-specific wire path; may require threading/start feature and rough/trim pass strategy. | Exact accepted format, controller software, whether they create CAM, start-hole requirements, trim-pass availability, and finishing spec. |
| Waterjet | 1:1 2D DXF profile and thickness/grade/quantity/tolerance. | OMAX machines typically use OMAX IntelliMAX (Layout/Make) for drawing import, toolpath and machine control; verify IC’s installed setup. [OMAX software](https://www.omax.com/en/intellimax-software/) | Does IC’s OMAX machine use IntelliMAX? What DXF version, units, kerf/lead-in, hold tabs, minimum feature size and thin-stock support? |
| CNC mill / turn-mill | Native CAD or neutral STEP model with fully dimensioned drawing, material stock size, datum plan, tolerance, and workholding concept. | CAM toolpaths are postprocessed for the exact controller. A controller-specific postprocessor is mandatory; generic G-code is not an appropriate deliverable. | Exact CAD/CAM package, controller, postprocessor, who creates/approves code, tooling/workholding, and approved parameters for NiTi. |

**Recommended starting software:** use SOLIDWORKS (available in PolyU’s IC computer rooms) or your existing CAD to inspect the STEP, then create a clean 2D drawing/DXF only after staff confirms the process. For the OMAX waterjet, ask if they use IntelliMAX. For CNC/EDM, ask the operator which CAM and postprocessor they require. Do not buy or install commercial CAM software before they answer.


## Files prepared for a self-managed CAD/CAM workflow

The pre-CAM spring package is now in [`cad/manufacturing_setup/`](cad/manufacturing_setup/README.md). Download [`U_leaf_preCAM_handoff.zip`](cad/manufacturing_setup/U_leaf_preCAM_handoff.zip) to get the four isolated, validated STEP leaves, geometry audit, handoff PDF, and preparation checklist. The STEP leaves preserve the source assembly placements and each re-imports as a single solid with volume matching the source to numerical precision. The [PDF](cad/manufacturing_setup/U_leaf_spring_geometry_handoff.pdf) is useful as a quick dimension/process handoff; the native [assembly STEP](cad/modules/UniDirectional_96.step) remains the overall context.

The ZIP is **pre-CAM**, not a machine-ready NC program. No controller-specific code was fabricated because the exact machine and postprocessor are unknown; the STEP geometry also contains a substantial variable thickness (about 6.33 mm at ends and 1.03–1.18 mm through the flexible section), which a 2D outline alone cannot create. Use the included checklist to identify process, stock/condition, tolerance, datum, fixture, CAM/controller and machine post before making any coupon.

## Questions to send to PolyU IC before preparing a machine file

1. I have NiTi (Nitinol) stock and need to cut a 2D leaf spring profile. Which machine and process in IC is approved for this exact NiTi alloy and condition?
2. Is the W401j metallic laser approved for NiTi, not just titanium? If yes, will IC run a small trial coupon, and what edge cleanup or post-process is required for fatigue-loaded springs?
3. Would the U004 Agie Charmilles Robofil 240SL wire EDM or W001 ProtoMAX/OMAX waterjet give a better first prototype? Can staff cut a test coupon and explain the limits for thin stock?
4. Which file should I provide for each route: 2D DXF, STEP, or both? What units, DXF version, line/layer convention, drawing dimensions, tolerances, and datum scheme do you want?
5. Which CAM program and machine controller/postprocessor are actually installed for the chosen machine? Does IC staff generate and verify the toolpath, or do students need to submit a postprocessed program?
6. Can the process accommodate the enlarged formed ends (about 7.05 × 6.33 mm) and flexible section (about 6 mm wide × 1.03–1.18 mm thick)? What kerf, minimum feature, hold-tab, and edge tolerance should the design use?
7. Can IC or the material supplier perform/advise the controlled shape-setting operation for the exact NiTi lot? What data should accompany it (target shape, condition, Af/DSC or BFR, fixture, temperature-time record)?
8. For the two Ø1.80 × 96 mm rods, which cutoff/end-finishing method should I use, and how do we avoid bending, scoring, or heat-damaging the rod?
9. What staff review, training, booking, cost, stock format, safety information, and lead time are needed? Can you recommend a simple inspection and spring cycling test before making all 16 leaves?

## Documents to bring

- This report and the existing [NiTi supplier report](niti_supplier_report.md).
- Native U-module CAD: [`UniDirectional_96.step`](cad/modules/UniDirectional_96.step), plus the U spring mesh [`U_leaf_springs.stl`](cad/lanes_u4m2/guides_v2/U_leaf_springs.stl) and dimensions [`spring_strip.json`](cad/lanes_u4m2/guides_v2/spring_strip.json).
- A one-page drawing showing overall profile, flexible-section dimensions, end geometry, datum, quantity, target tolerance, material lot/condition, and whether the shape is cut flat or requires forming.
- One sample NiTi strip/rod or the supplier datasheet/certificate, if available.

## Important limits

This is a process-selection and software handoff report, not a release-to-manufacture package. The robot design and NiTi stock lot are not qualified. Public IC pages do not confirm NiTi approval for its laser, exact software/postprocessors, or the available shape-setting capability. The 94 mm spring profile and 1.03–1.18 mm section need confirmation against the CAD before any DXF is generated. A university technician must review the file, fixture, process, and safe operating plan.

## Primary sources

- [PolyU IC metallic laser facilities](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/scn/metalliclasermachiningfacilities/)
- [PolyU IC 4-axis wirecut EDM](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/pmf/4axiswirecutedm/)
- [PolyU IC 3–5-axis CNC milling](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/pmf/3-5axiscnc/)
- [PolyU IC waterjet machining](https://www.polyu.edu.hk/ic/research-and-project-support/list-of-facilities/pmf/waterjet/)
- [PolyU IC software rooms](https://www.polyu.edu.hk/ic/study/learning-support/)
- [PolyU IC facility booking FAQ](https://www.polyu.edu.hk/ic/research-and-project-support/facilities-booking-faq/)
- [OMAX IntelliMAX overview](https://www.omax.com/en/intellimax-software/)
- [Liu et al.: WEDM and NiTi fatigue](https://doi.org/10.1177/09544054211028844)
- [Robertson et al. 2025: NiTi shape-setting TTT/TTS](https://doi.org/10.1007/s40830-025-00541-0)
- [NiTi fiber-laser microcutting surface integrity study](https://doi.org/10.1007/s00170-025-16528-1)
