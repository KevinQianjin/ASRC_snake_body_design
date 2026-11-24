# NiTi supplier and product specification report

**Prepared 24 November 2026 · For the ASRC U4+M2 school TAM consultation**

## Executive summary

The design calls for two distinct NiTi product forms: four spring strips in each of four U modules (16 total; approximately 94 mm long × 6 mm wide × 1.03–1.18 mm thick as read from current CAD sections), and one straight Ø1.80 mm × 96 mm backbone rod in each of two M modules. The strip geometry is the procurement constraint: current stock catalogs often offer rolled strip substantially thinner than 1 mm, so confirm that dimension against CAD and expect custom material or redesign if it is correct.

For parts cycled by mechanical bending, begin by asking for **superelastic, straight-annealed/straightened stock characterized at the expected use temperature**. Do not order “actuator wire” on the assumption it is automatically suitable: Fort Wayne Metals’ actuator data describe thermally driven shape-memory cycling. That is a different mode and fatigue metric from mechanically bending a superelastic leaf or backbone.

No catalog data found here certifies fatigue life for this robot geometry. A supplier’s ASTM F2516 tension result is useful for screening and lot control, but it does not establish bending fatigue, shape-set durability, cut-edge performance, or PA12 bond life. Obtain a lot-specific material certificate and test representative springs, rods, and end attachments.

## Design requirements from project files

| Part | Current design requirement | What the requirement does not yet tell us |
|---|---|---|
| U-module leaves | 16 NiTi leaves, each about 94 × 6 × 1.03–1.18 mm; four per U module | Confirm whether 1.03–1.18 mm is actual thickness, variable section, or a CAD envelope; required curvature, preload, strain history, and shape-setting method are not fully specified. |
| M-module backbones | Two straight rods, Ø1.80 × 96 mm; fixed at both end disks and guided laterally | Exact delivered condition, working curvature/mean strain, end-bond process, allowable permanent set, and fatigue life are unknown. |

The solver used 40 and 75 GPa modulus cases for rods and explicitly omitted phase transformation and hysteresis. These are model assumptions, not a purchase specification or material guarantee. [Project model data](simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md)

## Supplier landscape and fit to this project

| Supplier / product evidence | Published offering relevant to design | Fit and limitation |
|---|---|---|
| **Fort Wayne Metals (FWM)** — superelastic NiTi, strip, bar, shape-set services | Publishes superelastic grade data and transformation ranges; strip is straight-annealed, oxide finish, 2.03–12.7 mm width and below 0.63 mm thick; bar listing spans 0.559–12.7 mm diameter, 304–3708 mm lengths, and identifies NiTi as an available material. | Strong candidate to ask about custom U leaves and Ø1.8 mm bar. Published strip thickness is below the project’s stated 1.03–1.18 mm, so standard strip does not fit. Ask about custom rolled strip / flat bar and actual size/tolerance capability. Its grade data are reference values; request a quote-specific certificate. [Superelastic NiTi](https://fwmetals.com/what-we-do/materials/nitinol/superelastic-nitinol) · [Strip](https://fwmetals.com/what-we-do/materials/nitinol/nitinol-strip) · [Bar](https://fwmetals.com/what-we-do/products/bar) |
| **Lumenous Device Technologies** — flat and round superelastic NiTi wire | Flat wire has stated width/thickness ratios, dimensions, tolerances, superelastic properties and ASTM F2516 test temperature of 22 ± 2 °C. Round-wire page lists straightened superelastic stock, sizes/tolerances, UTS, upper plateau, residual set after 6%, and active Af by product code. | Useful benchmark for the thin strip concept and well-structured specification disclosure. Their listed flat product range is up to 0.8 mm thick; it does not meet a confirmed 1.03–1.18 mm thickness. Round-wire/flat-wire datasheet doesn’t establish a 1.8 mm rod offering. Ask for custom form limits. [Flat wire](https://lumenous.com/nitinol-flat-wire/) · [Round wire](https://lumenous.com/nitinol-round-wires/) |
| **GEE SMA** — superelastic wire and strip | Publishes superelastic strip and wire, active Af range, dimensions, and a grade table with F2516-based plateau/residual-set entries at 22 ± 2 °C. A published geometry page gives strip thickness up to 2.0 mm and width up to 20 mm. | Potential geometric fit for a 6 mm × ~1 mm leaf. Published grade table is for wire; do not assume the same data apply to thick strip or your shape-set part. Request strip-specific, lot-specific F2516/tensile and fatigue data and confirm 1.8 mm rod supply. [Superelastic wire](https://www.geesma.com/nitinol-wire/nitinol-super-elastic-wire.html) · [Strip/sheet/tube](https://www.geenitinol.com/strip-sheet-and-tube) |
| **Resonetics** — NiTi mill products, wire/sheet, testing and development | Publishes material-form guidance, strip manufacturing notes, DSC/BFR/F2516 methods and a 2025 peer-reviewed study showing processing and heat-treatment history can alter transformation temperatures and plateau stresses. | Valuable technical contact for advice or custom development; public pages do not establish stock at the project’s exact strip/rod sizes. Their recent study is strong evidence to control heat-setting recipes and not specify only Af. [Intro to NiTi](https://resonetics.com/wp-content/uploads/2025/11/Introduction_to_Nitinol_Wp_v5.pdf) · [2025 TTT/TTS study](https://doi.org/10.1007/s40830-025-00541-0) |
| **Furukawa Electric** — fine NiTi wire | Datasheet gives fine round wire down to 0.015 mm, conditions, example superelastic properties, an ingot Af by DSC, and ASTM F2063-18 reference. | Useful evidence of clear form/condition-specific data disclosure, but ultra-fine wire is irrelevant to the 1.8 mm rod and 6 mm-wide thick leaf. It illustrates why material data must match product form. [Ultra-thin wire datasheet](https://www.furukawa-ftm.com/tokusyu/chinese/wp-content/themes/furukawa/assets/pdf/Thin_wire_20260126_en.pdf) |

Supplier pages are leads, not availability, price, lead-time, or qualification confirmation. Ask suppliers directly for sample quantities and quote-specific documents.

## What the published properties mean for selection

1. **Specify the behavior and product condition.** For passive bending, request superelastic (straight-annealed/straightened) material, if that is the intended mechanism. Shape-memory actuator wire often starts in martensite and is trained to contract when heated; vendor cycle-life data for that application should not be treated as passive mechanical-bending fatigue data. FWM describes actuator wire as thermally cycled between phases and recommends loading parameters for actuation. [FWM actuator information](https://fwmetals.com/resources/nitinol-actuator-technical-information)
2. **Transformation temperature alone is insufficient.** Active Af and the test method matter. Ask for DSC and/or active bend-and-free-recovery (BFR) results on the delivered material or representative finished geometry, and report the method. Resonetics explains BFR measures recovery under a deformation history and can produce an active Af different from DSC. [Resonetics NiTi guide](https://resonetics.com/wp-content/uploads/2025/11/Introduction_to_Nitinol_Wp_v5.pdf)
3. **Ask for stress–strain results at the operating temperature.** ASTM F2516-style upper and lower plateau stress, permanent set/residual elongation, UTS, and elongation give useful comparisons for superelastic tension. Require temperature and specimen condition. They do not directly rate flexural leaves or fatigue life.
4. **Surface and edge condition are structural variables.** Request finish, oxide/etched/polished state, edge radius/burr control, cutting method, and whether post-cut processing or shape-setting changes the properties. A sharp cut edge or heat-affected region can become a crack initiator; the effect must be assessed on the actual cut/process.
5. **Control process history.** A 2025 study of wire and tube found heat-treatment modality/time/temperature, starting material and processing history affect transformation temperature and plateau stress; matching Af alone did not ensure matching mechanical performance. Do not copy its recipes to your parts. [Robertson et al. 2025](https://doi.org/10.1007/s40830-025-00541-0)

## Recommended supplier inquiry (ready to send)

> We are prototyping a mechanically cycled inspection robot, not an electrically heated actuator. Please advise whether you can supply and characterize (A) superelastic NiTi leaf stock for 16 parts, approximately 94 mm long × 6 mm wide × 1.03–1.18 mm thick per CAD, and (B) two straight Ø1.80 mm × 96 mm NiTi backbone rods. Please flag immediately if the strip thickness needs to be reinterpreted or custom-produced.
>
> For each proposed product, please provide: product form and alloy/grade; delivered condition and complete prior heat-treatment/straightening history; lot-specific certificate; dimensional tolerances and surface/edge finish; active Af and method (DSC or BFR) plus other transformation temperatures if available; ASTM F2516 stress–strain results at a stated temperature (upper/lower plateau, residual set after specified strain, UTS and elongation); allowable cutting, deburring, forming and shape-setting methods; and fatigue data with strain or curvature amplitude, mean strain, temperature, surface condition, cycle waveform, sample count, and failure/runout definition. Please distinguish thermal-actuation cycle data from mechanical bending-fatigue data.
>
> Our parts are bonded or retained at ends inside printed PA12 modules. Can you recommend an end-preparation/attachment approach or suitable sample coupons? Can you supply short prototype lengths for matched bending and bond tests?

## TAM decisions and first development tests

- Confirm the CAD section thickness and required spring profile before selecting suppliers. If 1.03–1.18 mm is correct, ask FWM and GEE SMA first about custom strip/flat bar; use Lumenous as a thinner strip data benchmark, not as a dimensional match.
- Select rod and strip separately; they may need different grades or processing. Avoid assuming one vendor lot or one Af target is optimal for both.
- Have the supplier provide material samples with the same finish and condition as the quote. Record lot, geometry and actual dimensions.
- Test representative leaves and rods in the intended fixtures: force–curvature and unloading/recovery at room temperature and expected use temperature; measure residual set after each stage; then cycle at measured mission curvature/strain with intervals for crack inspection. Use sacrificial duplicates for destructive limits.
- Test cut-edge and formed parts, not only unprocessed stock coupons. Test the actual PA12 end attachment separately for bond slip, peel, and failure mode.
- Ask the TAM to set safe fixture/load ranges, instrumentation, sample count, guarding, cycle frequency, and stop criteria. Do not derive operating strain or life from tensile coupon data alone.

## Sources

- [Fort Wayne Metals: superelastic NiTi properties and grade comparisons](https://fwmetals.com/what-we-do/materials/nitinol/superelastic-nitinol)
- [Fort Wayne Metals: NiTi strip size/condition information](https://fwmetals.com/what-we-do/materials/nitinol/nitinol-strip)
- [Fort Wayne Metals: bar products and size range](https://fwmetals.com/what-we-do/products/bar)
- [Lumenous: flat NiTi wire dimensions and mechanical data](https://lumenous.com/nitinol-flat-wire/)
- [Lumenous: round NiTi wire dimensions and mechanical data](https://lumenous.com/nitinol-round-wires/)
- [GEE SMA: superelastic NiTi grade data](https://www.geesma.com/nitinol-wire/nitinol-super-elastic-wire.html)
- [GEE SMA: strip dimensions](https://www.geenitinol.com/strip-sheet-and-tube)
- [Resonetics: Introduction to Nitinol](https://resonetics.com/wp-content/uploads/2025/11/Introduction_to_Nitinol_Wp_v5.pdf)
- [Robertson et al., 2025: post-shape-setting TTT/TTS properties](https://doi.org/10.1007/s40830-025-00541-0)
- [Furukawa: NiTi ultra-thin wire datasheet](https://www.furukawa-ftm.com/tokusyu/chinese/wp-content/themes/furukawa/assets/pdf/Thin_wire_20260126_en.pdf)
- [Fort Wayne Metals: actuator wire technical information](https://fwmetals.com/resources/nitinol-actuator-technical-information)
