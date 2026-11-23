"""Print the governing-step bond table (results/bond_cases.json) as Markdown."""
import json
import sys
from pathlib import Path

rows = json.loads((Path(__file__).parent / "results/bond_cases.json").read_text())["rows"]
steps = sys.argv[1:] or ["1709", "1710", "1885"]
print("| mismatch | nh | crown mm | G MPa | station | peak axial shear | mean axial shear | peak normal | witness motion mm | closure mm | guide−web rotation ° | max land force N |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for x in rows:
    if str(x["step"]) not in steps:
        continue
    p, m = x["peak_abs_traction_MPa"], x["area_mean_abs_traction_MPa"]
    print(f"| {x['mismatch']} | {x['nh']} | {x['crown_mm']} | {x['G_MPa']:.0f} | {x['station_mm']:+d} | "
          f"{p['axial_shear']:.2f} | {m['axial_shear']:.2f} | {p['normal']:.2f} | "
          f"{x['witness_relative_motion_mm']:.5f} | {x['witness_normal_closure_mm']:.5f} | "
          f"{x['guide_minus_web_rotation_deg']:.4f} | {max(x['land_force_N_by_rib_deg_x10'].values()):.2f} |")
