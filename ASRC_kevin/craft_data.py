"""
craft_data.py - numerical data taken from

  P. T. Dewi*, C. Pogue*, C. Shentu, A. Gotelli, J. Burgner-Kahrs,
  "CRAFT: A 3D-printed Modular Design Framework for Task-specific Continuum
  Robots", Research Square preprint rs-8482576/v1, 24 Feb 2026 (CC BY 4.0).

Everything below is transcribed from the preprint text/tables. Items marked
[ASSUMPTION] are NOT in the paper. Items marked [CHECK] were read from the text
extraction of a figure and should be verified against the figure itself.

Units: SI (m, kg, N, rad) unless the name says otherwise (_mm, _g, _min, ...).
"""

# --------------------------------------------------------------------------
# Table 1 (measured mechanical properties) + Fig. 2 (composition) + Table 2
# --------------------------------------------------------------------------
# EI_x / EI_negx / EI_y : flexural rigidity for bending toward X, -X, Y [N m^2]
# EA : axial rigidity [N]       GJ : torsional rigidity [N m / rad]
# In Table 1, values marked with a dagger were derived from structural
# symmetry (flag `EI_derived_from_symmetry`).  The paper gives no "-Y" value;
# this code uses EI(-Y) = EI(Y)  [ASSUMPTION].
# print_time_min, pc_*/pla_* and cost_cad are Table 2 (Ultimaker S5 FDM).
MODULES = {
    "low": dict(
        label="Low stiffness",
        EI_x=0.0024, EI_negx=0.0024, EI_y=0.0024, EA=43.75, GJ=0.059,
        EI_derived_from_symmetry=("negx", "y"),
        components=dict(disks=2, rings=4, octo_flex=4),
        print_time_min=60, pc_g=0.9, pc_m=0.12, pla_g=2.7, pla_m=0.35,
        cost_cad=0.44,
        use="large bending deformation, tight turns"),
    "medium": dict(
        label="Medium stiffness",
        EI_x=0.0046, EI_negx=0.0046, EI_y=0.0046, EA=85.07, GJ=0.14,
        EI_derived_from_symmetry=("negx", "y"),
        components=dict(disks=2, rings=4, octo_flex=8),
        print_time_min=79, pc_g=1.7, pc_m=0.22, pla_g=2.3, pla_m=0.29,
        cost_cad=0.52,
        use="segments that bend and transmit moderate forces"),
    "high": dict(
        label="High stiffness",
        EI_x=0.028, EI_negx=0.028, EI_y=0.028, EA=514.29, GJ=0.38,
        EI_derived_from_symmetry=("negx", "y"),
        components=dict(disks=2, rings=4, octo_flex=4, reinforcement_fillers=4),
        print_time_min=102, pc_g=2.4, pc_m=0.32, pla_g=2.7, pla_m=0.34,
        cost_cad=0.68,
        use="base segments carrying large bending moments / gravity loads"),
    "directional": dict(
        label="Directional stiffness",
        EI_x=0.0037, EI_negx=0.0030, EI_y=0.0035, EA=64.46, GJ=0.080,
        EI_derived_from_symmetry=(),
        components=dict(disks=2, rings=4, octo_flex=6),
        print_time_min=70, pc_g=1.3, pc_m=0.17, pla_g=2.7, pla_m=0.34,
        cost_cad=0.50,
        use="anisotropic bending (asymmetric Octo-Flex placement)"),
    "unidirectional": dict(
        label="Uni-directional stiffness",
        EI_x=0.0057, EI_negx=0.0057, EI_y=0.061, EA=1150.19, GJ=0.11,
        EI_derived_from_symmetry=("negx",),
        components=dict(disks=2, rings=4, octo_flex=4, leaf_springs=2),
        print_time_min=73, pc_g=1.2, pc_m=0.16, pla_g=2.7, pla_m=0.34,
        cost_cad=0.49,
        use="bends in one plane (X), stiff in Y and axially (highest EA)"),
    "extensible": dict(
        label="Extensible",
        EI_x=0.00078, EI_negx=0.00078, EI_y=0.00078, EA=6.80, GJ=0.067,
        EI_derived_from_symmetry=("negx", "y"),
        components=dict(disks=2, rings=6, parallel_springs=4),
        print_time_min=72, pc_g=1.2, pc_m=0.15, pla_g=2.9, pla_m=0.36,
        cost_cad=0.50,
        use="contraction-extension (inchworm crawling)"),
}

# Friendly aliases accepted by the model code.
ALIASES = {
    "uni": "unidirectional", "uni_directional": "unidirectional",
    "uni-directional": "unidirectional", "dir": "directional",
    "ext": "extensible", "lo": "low", "med": "medium", "hi": "high",
}

# The paper's text quotes the low-stiffness EI as 0.024 N m^2 in Sec. 2.1,
# but Table 1 says 0.0024 (and "medium ~ 2x low" only holds for 0.0024).
# This code follows Table 1.
TEXT_TABLE_DISCREPANCY = {"low_EI_text": 0.024, "low_EI_table": 0.0024}

# --------------------------------------------------------------------------
# Geometry (Fig. 2 and Sec. 4.3)
# --------------------------------------------------------------------------
MODULE_DIAMETER_MM = 32.0            # wing-probe and pipe-crawler modules
HAND_MODULE_DIAMETER_MM = 22.0       # soft-hand fingers
FDM_MAX_DIAMETER_MM = 40.0           # largest FDM scale shown (Fig. 9)
SLA_MIN_DIAMETER_MM = 10.0           # smallest SLA scale shown (Fig. 9)
FLEXURE_LENGTH_MM = 45.0             # l = 45 mm for all compliant components
DISK_HEIGHT_MM = 1.5                 # h = 1.5 mm (disk), ring h = 1.5 mm
# Total module length is NOT stated in the text.
MODULE_LENGTH_M = (FLEXURE_LENGTH_MM + 2 * DISK_HEIGHT_MM) / 1000.0
#   = 48 mm  [ASSUMPTION: 45 mm flexure + two 1.5 mm end disks]

# Component cross-sections (t = thickness, w = width), read from Fig. 2 [CHECK]
COMPONENTS = {
    "octo_flex": dict(t_mm=0.8, w_mm=1.5, l_mm=45.0, material="PC"),
    "reinforcement_filler": dict(t_mm=0.75, w_mm=1.5, l_mm=45.0, material="PC"),
    "leaf_spring": dict(t_mm=0.5, w_mm=3.0, l_mm=45.0, material="PC"),
    "parallel_spring": dict(t_mm=0.5, w_mm=1.5, l_mm=45.0, material="PC"),
    "disk": dict(h_mm=1.5, outer_diameter_mm=32.0, material="PLA"),
    "ring": dict(h_mm=1.5, material="PLA"),
}
# Other dimensions printed in Fig. 2 whose assignment is unclear in the text
# extraction [CHECK against the figure]: slot for Octo-Flex 8.5 mm, 13 mm,
# 21.3 mm, 10 mm.
FIG2_UNASSIGNED_MM = (8.5, 13.0, 21.3, 10.0)

# --------------------------------------------------------------------------
# Fabrication (Sec. 4.3)
# --------------------------------------------------------------------------
FABRICATION = dict(
    fdm_printer="Ultimaker S5", print_core_mm=0.25, layer_height_fdm_mm=0.1,
    infill_percent=100, orientation="flat on build plate",
    disks_rings_material="PLA",
    flexures_springs_fillers_material="PC (polycarbonate)",
    glue="cyanoacrylate, cure >= 3 h",
    joining="split-shank rivets through end-disk holes",
    sla_printer="Formlabs", layer_height_sla_mm=0.025,
    sla_note="small modules printed monolithic, non-brittle resin",
    pla_cost_cad_per_90m=84.0, pc_cost_cad_per_90m=117.0,
    print_time_range_h=(1.0, 2.0),
)

# --------------------------------------------------------------------------
# Mechanical characterisation protocol (Sec. 4.4) - useful to copy for your own
# measurements (EI = P L^3/(3 d), EA = P L/d, GJ = T/theta)
# --------------------------------------------------------------------------
CHARACTERISATION = dict(
    bending_masses_g=(10, 200), axial_masses_g=(10, 250),
    fig3_lateral_tip_forces_N=(0.1, 2.0), fig4_axial_loads_N=(0.1, 2.5),
    fig4_torsion_loads_Nm=(0.002, 0.05),
    measurement="camera + manual tracing in Fusion 360",
    repeats="one test per module type, new prototype for each test",
)

# --------------------------------------------------------------------------
# Fatigue test (Sec. 4.5, Fig. 10)
# --------------------------------------------------------------------------
FATIGUE = dict(
    module="low", material="PC", cycles=10_000, frequency_Hz=0.2,
    tendon_displacement_mm=(0.0, 10.0), sinusoid_amplitude_mm=5.0,
    machine="Instron ElectroPuls E1000 (displacement control)",
    max_tendon_force_N=3.14, bend_angle_deg=64.4,
    result=("stable at first, then gradual drop in peak force; four cracks "
            "in the flexures after 10 000 cycles"),
    crack_locations=4,
    reference_ABS_spiral_joint_crack_cycles=3800,   # Safai [28], comparable scale
    note="nylon specimens in that reference lasted substantially longer",
    limitation="only the low-stiffness module was tested",
)

# --------------------------------------------------------------------------
# Applications (Sec. 2.2-2.4, 4.6)
# --------------------------------------------------------------------------
WING_ROBOT = dict(
    mockup="Cessna 172, NACA 2412, 1:3 scale", span_mm=1571,
    access_port_diameter_mm=40, module_diameter_mm=32,
    actuation="8 x Dynamixel XC430-T240BB-T, custom 3D-printed frame",
    control="PlayStation DualSense teleoperation (Python)",
    sensing="camera at tip",
    original=dict(base="high", middle="medium", distal="low"),
    reconfigured=dict(base="high", middle="unidirectional",
                      distal="directional"),
    # modules per segment are NOT given in the text
    sag_combined_mm_original=55.0, sag_combined_mm_reconfigured=33.0,
    sag_reduction_percent=41.0,
    sag_conditions="zero tendon tension, self-weight only",
    reach="original: up to panel 3; reconfigured: reliably reaches panel 4",
    unchanged="base segment, actuation unit, tendon routing, control interface",
    payload="tip camera only (mass not stated)",
)

PIPE_ROBOT = dict(
    module_diameter_mm=32, pipe_inner_diameter_mm=50, pipe_length_mm=826,
    path="straight sections, 90 deg bend, 30 deg incline",
    actuation="3 x Dynamixel XL430-W250-T",
    tendons="front 1, middle 2, rear 2; spring steel wire 0.38 mm",
    bowden_tube_mm=dict(outer=3.2, inner=2.5, length=914.4),
    modules="extensible + stiffer modules, passive steering",
    speed_mm_per_s=dict(straight=1.2, bend_90=1.0, incline_30=0.53),
)

HAND_ROBOT = dict(
    module="unidirectional", module_diameter_mm=22, finger_length_mm=83,
    fingers=5, finger_mount_angle_deg=22.5,
    actuation="XL430-W250-T per bending finger, rigid linkage for centre finger",
    arm="Franka Panda", trials=13, eggs_cracked=12, complete_separation=11,
    success_rate_percent=84.6, failure_cause="egg misalignment, force variability",
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def canonical(name):
    n = name.strip().lower().replace(" ", "_")
    n = ALIASES.get(n, n)
    if n not in MODULES:
        raise KeyError(f"unknown module '{name}'. Known: {list(MODULES)}")
    return n


def module_mass_kg(key, extras_g=0.0):
    """Printed-material mass from Table 2 (PC + PLA filament weight).
    Excludes rivets, glue and tendons; add them with extras_g."""
    m = MODULES[canonical(key)]
    return (m["pc_g"] + m["pla_g"] + extras_g) / 1000.0


def print_tables():
    keys = list(MODULES)
    print("Table 1 - measured mechanical properties")
    print(f"{'':32s}" + "".join(f"{k:>15s}" for k in keys))
    rows = [("EI toward X  [N m^2]", "EI_x"), ("EI toward -X [N m^2]", "EI_negx"),
            ("EI toward Y  [N m^2]", "EI_y"), ("EA [N]", "EA"),
            ("GJ [N m/rad]", "GJ")]
    for lab, f in rows:
        print(f"{lab:32s}" + "".join(f"{MODULES[k][f]:15.5g}" for k in keys))
    print("\nTable 2 - fabrication (FDM)")
    print(f"{'print time [min]':32s}" + "".join(
        f"{MODULES[k]['print_time_min']:15d}" for k in keys))
    print(f"{'PC [g]':32s}" + "".join(f"{MODULES[k]['pc_g']:15.1f}" for k in keys))
    print(f"{'PLA [g]':32s}" + "".join(f"{MODULES[k]['pla_g']:15.1f}" for k in keys))
    print(f"{'cost [CAD]':32s}" + "".join(
        f"{MODULES[k]['cost_cad']:15.2f}" for k in keys))
    print(f"{'mass PC+PLA [g]':32s}" + "".join(
        f"{module_mass_kg(k)*1000:15.1f}" for k in keys))


if __name__ == "__main__":
    print_tables()