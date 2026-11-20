# Second extreme-test round for the 500 g U4+M2 front

The [engineering report](../../../../reports/daily/Extreme_Simulation_Round_2_2026_11_19.md) gives the results and decisions. The [test programme](../../../../nextstep/README.md) connects them to the planned measurements. This directory contains numerical studies. The inputs are the original 500 g head and adapter, four U units with four NiTi blades each, two independently backed M units, twelve 2 mm ropes and the [0.25 mm M6 candidate guide sockets](../../../../cad/lanes_u4m2/m6_bond_gap_20261119/README.md). The archived 3,405-state round trip includes both yaw turns, both vertical pitch turns and their returns.

## What was solved

| Study | Inputs and method | Evidence |
|---|---|---|
| Both M6 stations, full mission | Refine all triangles of the actual M6 body to a maximum 0.5 mm axial edge span before deformation. The rod map is affine in transverse coordinates at fixed axial distance. A swept bounding box includes every archived strain state. Only triangles certified farther than 0.6 mm from every guide part can be excluded. FCL checks triangle collision and distance for the guide, caps and wire envelope. Exactly equal final-module strains may share a result. | [Every step, pair, witness and gap](results/m6_all_steps.csv.gz) · [Counts and minima](results/m6_full.json) · [Conventional finer meshes](results/m6_fine_exact.json) |
| Bonded M6 lands | Cut the M6 STL at a radial rib plane, measure thickness from the solid, condense membrane and Mindlin plate degrees of freedom, then assemble eight ribs and two rigid guide plates. Four side-wall pads per seat have 5.67 mm² effective area each. Integrate normal and shear tractions at sixteen points per pad. Sweep bond thickness 0.15/0.25 mm and assumed shear modulus 500/1,500 MPa. Both station wrenches and the local rod-mapped fit mismatch act simultaneously. The incremental disk motion is fixed. | [Stiffness, 96 land wrenches and perturbed CAD gaps](results/m6_support.json) · [Refined plate mesh](results/m6_support_refined.json) |
| Displaced rope bores and disturbed holds | Use the CAD throat and flared mouth. Intersect each oblique 2 mm rope with the bore sections before and after centring the span on the moving holes. Transfer the three changed C-rope spans and their virtual work to the whole rod. Re-equilibrate at the original winch lengths and then apply bounded local pointing and tension feedback. Test fixture tilt, lateral force, a transverse head mass offset and release of the most heavily loaded line separately. | [Finite-rope geometry](results/m6_bores.json) · [27 hold cases and feedback increments](results/disturbed_holds.json) |
| Twelve-rope reversal and feedback | Store unstretched material on the internal and free side of an effective friction site for each rope. Hold its material split while the static capstan inequality is satisfied. On slip, solve for both tensions with material length conserved. Apply drum play and compare unchanged commands, one-observation-delayed distal tension feedback and friction/backlash compensation. Three loops solve all rod degrees of freedom and recompute tank and M5 guide loads at each archived substep. The total wrap input follows the original mission. | [Seventeen fixed-shape cases](results/transmission_sensitivity.json) · [Unchanged commands](results/coupled_s0.15_k0.15_b0.1_open.csv.gz) · [Distal feedback](results/coupled_s0.15_k0.15_b0.1_feedback.csv.gz) · [Compensated feedback](results/coupled_s0.15_k0.15_b0.1_compensated.csv.gz) · [Independent equilibrium and tangent checks](results/replay_tangents.json) |
| Taking up motion before a reversal | At the preceding pose, move the drum to the new side of the static-friction interval before advancing the target. Each take-up and interpolated move has a bounded winch increment. Compare three assumed coefficients against the same modelled plant. Check the whole-rod residual on the 3,405 original poses for the matched case. Replay two precomputed schedules on the free rod, allowing every inserted pose to re-equilibrate with persistent friction, recalculating twelve forces at both ends, tank margin and M5 wrenches. | [Sensitivity and substep counts](results/takeup.json) · [Matched endpoint forces and ropes](results/takeup_endpoints.csv.gz) · [Free rod, matched schedule](results/takeup_plant_mu0.15.json) · [Free rod, lower friction estimate](results/takeup_plant_mu0.12.json) |
| U cage, tabs and all four installed blades | Continue the nonlinear three-dimensional free-span solutions at prescribed transverse motion and end rotation over axial shifts. Allow each end tab to move axially against a spring. Balance the four blades and a cage spring against the distal whole-rod axial resultant. Estimate an upper cage stiffness from the CAD area integral with constrained PA12 modulus. Sweep its assumed fraction and tab stiffness. | [CAD blade curves](results/u_blade_curves.json) · [Assembly and tab slip](results/u_assembly.json) · [Independent off-grid solutions](results/u_interpolation_check.json) |
| M5 relieved hole and elastic steel pin | Repeat the nonlinear rib shell at the two actual mission states to recover the moving pin frame and web orientation. Carry the strongest pin load at the specified station to the existing supported-pin/relieved-web contact model. Load ranges from 0.5 to 2 times the service vector at each state on two local meshes. | [Moving frames and loads](results/m5_moving_frames.json) · [Sixteen contact solutions or explicit solver failures](results/m5_local.json) · [Proof-load table](results/proof_loads.json) · [Conditional yield brackets](results/pin_yield_brackets.json) |
| Combined pointing and insertion | Eleven yaw slices start from the existing direction at +20° elevation. Twelve winches steer to successively higher and lower pitch and then retrace the accepted commands. At −15, +15 and +45 mm clamp coordinates, score both directions with the 63 mm envelope and 1.5 mm allowance. Check sampled depth crossings at 1 mm and the connection to the existing withdrawal path. | [Path outcomes](results/pose_paths.json) · [Pose, all ropes, equilibrium and depth samples](results/pose_steps.csv.gz) · [Boundary and withdrawal checks](results/pose_boundary_checks.json) |
| Timed winch disturbance | At two loaded poses calculate a conditional generalized mass matrix from distributed module mass, trial cylindrical rotational inertia and a 500 g tip point mass. Linearize the actual winch-controlled tangent and retain 24 or 48 modes. Apply a 0.25 mm C-up pull and return at three ramp times, with two assumed damping, winch lag and delay combinations. | [Modes, tracking and ring-down](results/timed_response.json) |
| Duty and resistance | Count open-history rainflow ranges and means at fixed material locations and on each rope. Use signed fixed-fibre rod strains, an axial M5 virtual gauge, linearized curved U blades and the finite M6 bond pads. Report material transfer travel and four hypothetical dwell contributions. Invert a family of trial amplitude-life slopes to express the endurance that the specimens would have to demonstrate. | [Mission channels](results/duty_channels.csv.gz) · [Range, mean and cycle count](results/rainflow.csv.gz) · [Required amplitudes](results/endurance_requirements.csv.gz) · [Sites, travel and dwell](results/duty.json) · [Required static resistance](results/required_strength.csv.gz) |

## Interpretation

The body-only M6 stiffness increment compares the same eight ribs with and without the bonded plates. The two other guide stations and the NiTi core are outside this incremental stiffness comparison. The local contact probes apply the motion of the guide relative to its witness web to the archived triangles. Other webs can move differently. The shell uses a transported small-displacement reference and lacks a nonlinear preloaded tangent and adhesive failure law. Measured guide position and tilt would resolve the uncertainty in the bore motion.

The transmission model places the total route friction at one effective site. It captures material memory and reversal while keeping uniform distal span traction inside the arm. Each whole-rod replay uses the original measured-in-simulation total wrap at the corresponding step. Distributed guide friction, a measured motor, time-resolved sensing and identified material creep remain open. The initial scheduling sweep prescribes the added substep shapes. The two free-rod replays subsequently use the resulting drum commands and solve the equilibrium at every added step. The timed perturbations cover two loaded holds. For each of the twelve winches, compare the [matched command schedule](results/takeup_commands_mu0.15.csv.gz) and [lower-friction estimate schedule](results/takeup_commands_mu0.12.csv.gz) with their respective [matched force history](results/takeup_plant_mu0.15.csv.gz) and [lower-estimate force history](results/takeup_plant_mu0.12.csv.gz). The substep index follows the row order of the corresponding command file. The step and phase identify the next archived target. Fraction zero holds the preceding pose and fraction one reaches the target.

For the U unit, tab rotations and transverse disk motion stay prescribed. Cage stiffness and end restraint are assumed. An axial force balance does not close the other five disk equilibrium components. The M5 pin model uses the existing clamped fixture boundary and frictionless contact. The proof-load multipliers apply to the recovered pin vector, while the head stays at 500 g. Remote shell hotspots and contact-patch stress have different spatial support.

The M5 build-direction virtual gauge follows two points in the homogenized rod map. It ranks large geometric motion in the open web. The local PA12 strain at that location requires a full-mission shell or a physical gauge. Its inverse material endurance requirement is left empty.

At the +175° yaw descent a full Newton trial exceeded the supported bellmouth tangent domain. The equilibrium solver now backtracks inside the same rope model and requires a decreasing residual before accepting a smaller increment. The motion map reports the tested command branches and clamp datum. Reachable endpoints can have an intervening tank collision. The contiguous returnable interval, the smallest gap after allowance and any first failed sample govern interpretation. Actual head/harness contours, actuator ratings and the direction-dependent pose of a manufactured joint still require measurement.

## Reproduction

Launch the scripts with the dependencies used by the [previous round](../extreme_round1_20261119/README.md#verification-and-reproduction) and [supported pin study](../p3_pin_fixture_20261119/README.md). The [validation record](results/validation.json) gives the source revision, input file hashes and actual package versions. Use one BLAS thread. Run in this directory with a fresh output path so archived runs remain intact.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
out=$(mktemp -d)
python m6_full.py --out "$out"
python m6_refinement.py --out "$out"
python m6_support.py --out "$out"
python m6_support.py --out "$out" --area .045 --structure-only
python m6_bores.py --out "$out"
python disturbed_holds.py --out "$out"
python rope_history.py --mode sweep --out "$out"
python rope_history.py --mode coupled --out "$out"
python rope_history.py --mode coupled --feedback --out "$out"
python rope_history.py --mode coupled --compensated --out "$out"
python reversal_takeup.py --out "$out"
python takeup_plant.py --estimate .15 --out "$out"
python takeup_plant.py --estimate .12 --out "$out"
python replay_tangent.py --out "$out"
python u_assembly.py --out "$out"
python m5_contact.py --out "$out"
python m5_contact.py --yield-brackets --out "$out"
python pose_map.py --out "$out"
python pose_boundaries.py --out "$out"
python timed_response.py --out "$out"
python duty.py --out "$out"
python strength.py --out "$out"
python -m unittest -v test_round2
python validate.py --out "$out"
python figures.py --out "$out"
```
