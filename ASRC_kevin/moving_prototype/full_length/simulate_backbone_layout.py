"""First-pass beam screening for U4+M2 backbone layout.

This is an Euler-Bernoulli, elastic screening calculation, not FEA. It compares
the per-module rod span with bending a continuous rod across the 12 mm joint.
It does not model anchor contact, NiTi superelasticity, print failure, or the
actual flexible-body STEP geometry.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
OUT = HERE / "backbone_layout_screening"
OUT.mkdir(exist_ok=True)

DIAMETER_MM = 1.8
MODULE_ROD_SPAN_MM = 84.0
JOINT_GAP_MM = 12.0
JOINT_ANGLES_DEG = (5, 10, 15, 25)
# NiTi modulus is deliberately swept because grade, phase, and loading state
# are not specified. These are assumed elastic moduli, not certified values.
MODULI_GPA = (30, 40, 50, 70)

I_MM4 = math.pi * DIAMETER_MM**4 / 64.0
AREA_MM2 = math.pi * DIAMETER_MM**2 / 4.0


def beam_screen(E_GPa: float, span_mm: float, angle_deg: float) -> dict[str, float]:
    E_N_mm2 = E_GPa * 1000.0
    angle_rad = math.radians(angle_deg)
    EI_N_mm2 = E_N_mm2 * I_MM4
    moment_N_mm = EI_N_mm2 * angle_rad / span_mm
    surface_stress_MPa = E_N_mm2 * (DIAMETER_MM / 2) * angle_rad / span_mm
    # Pin-ended Euler load. This flags compressive instability scale only.
    euler_load_N = math.pi**2 * EI_N_mm2 / span_mm**2
    return {
        "E_GPa": E_GPa,
        "span_mm": span_mm,
        "angle_deg": angle_deg,
        "moment_N_mm": moment_N_mm,
        "surface_stress_MPa": surface_stress_MPa,
        "euler_buckling_load_N": euler_load_N,
    }


rows: list[dict[str, float | str]] = []
for E in MODULI_GPA:
    for angle in JOINT_ANGLES_DEG:
        for name, span in (
            ("rod bends over one M module", MODULE_ROD_SPAN_MM),
            ("continuous rod bends across joint gap", JOINT_GAP_MM),
        ):
            rows.append({"layout_case": name, **beam_screen(E, span, angle)})

csv_path = OUT / "layout_screening.csv"
with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

# Plot angle-driven surface stress over uncertainty in assumed elastic modulus.
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)
colors = {30: "#3b82f6", 40: "#10b981", 50: "#f59e0b", 70: "#ef4444"}
for E in MODULI_GPA:
    module_stress = [beam_screen(E, MODULE_ROD_SPAN_MM, a)["surface_stress_MPa"] for a in JOINT_ANGLES_DEG]
    gap_stress = [beam_screen(E, JOINT_GAP_MM, a)["surface_stress_MPa"] for a in JOINT_ANGLES_DEG]
    axes[0].plot(JOINT_ANGLES_DEG, module_stress, "o-", color=colors[E], label=f"{E} GPa")
    axes[1].plot(JOINT_ANGLES_DEG, gap_stress, "o-", color=colors[E], label=f"{E} GPa")
axes[0].set_title("Rod bends over 84 mm module span")
axes[1].set_title("Continuous rod bends over 12 mm joint gap")
for ax in axes:
    ax.set_xlabel("Imposed angle change (degrees)")
    ax.set_ylabel("Estimated elastic surface stress (MPa)")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Assumed E")
fig.suptitle("1.8 mm rod layout screening — elastic beam estimate")
plot_path = OUT / "layout_stress_comparison.png"
fig.savefig(plot_path, dpi=180)
fig.savefig(OUT / "layout_stress_comparison.svg")
plt.close(fig)

# Summarize the geometric ratio, which is independent of modulus and angle.
ratio = MODULE_ROD_SPAN_MM / JOINT_GAP_MM
mid = beam_screen(40, MODULE_ROD_SPAN_MM, 25)
gap = beam_screen(40, JOINT_GAP_MM, 25)
summary = OUT / "README.md"
summary.write_text(
    "# Backbone layout screening\n\n"
    "This is a simple elastic Euler-Bernoulli beam estimate, not finite-element analysis. "
    "It compares bending a 1.8 mm rod over the 84 mm M-module body with forcing the same "
    "angle change across the 12 mm articulated gap. The assumed NiTi modulus is swept "
    "from 30 to 70 GPa because the actual grade/phase data are not yet supplied.\n\n"
    f"At 40 GPa and 25 degrees, estimated moment/stress are "
    f"{mid['moment_N_mm']:.1f} N mm / {mid['surface_stress_MPa']:.0f} MPa over one module, "
    f"versus {gap['moment_N_mm']:.1f} N mm / {gap['surface_stress_MPa']:.0f} MPa across the gap. "
    f"The simple curvature estimate is {ratio:.1f} times higher for the short gap.\n\n"
    "This supports keeping the two M-module rods separate across their hinge. It does not "
    "select an end-anchor design: no anchor geometry, contact, friction, pullout, PA12 "
    "failure, NiTi superelastic response, or measured service force is included. Euler "
    "buckling loads in the CSV are ideal pin-ended estimates and should be treated only "
    "as a warning scale. Print a fit/retention coupon and test it with a force gauge before "
    "any payload or high-tension test.\n\n"
    "Files: `layout_screening.csv` contains the calculation table; `layout_stress_comparison.png` "
    "plots estimated bending stress. Run with `python simulate_backbone_layout.py`.\n",
    encoding="utf-8",
)
print(f"CSV: {csv_path}")
print(f"Plot: {plot_path}")
print(f"Summary: {summary}")
print(f"40 GPa, 25 deg module: M={mid['moment_N_mm']:.1f} N mm, stress={mid['surface_stress_MPa']:.1f} MPa, Pcr={mid['euler_buckling_load_N']:.1f} N")
print(f"40 GPa, 25 deg gap: M={gap['moment_N_mm']:.1f} N mm, stress={gap['surface_stress_MPa']:.1f} MPa, Pcr={gap['euler_buckling_load_N']:.1f} N")

