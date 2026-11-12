"""Linear planar screening of a fixed-axis, telescopic rear support.

The fixed 50 x 50 x 2 mm sleeve is behind the front guide plane and is NOT
part of the exposed cantilever. The exposed support is either 40/30 mm
square tubes, each occupying half the exposed length, or one 30 mm tube.
An interface force AND the front assembly's gravity moment are applied.
This is a nominal beam screen, not validation of telescopic joints.

Run: python rear_beam.py [--output-dir PATH] [--self-test-only]
All generated labels and metadata are English.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

GRAVITY = 9.81
YOUNG_PA = 69e9
DENSITY_KG_M3 = 2700.0
REFERENCE_YIELD_PA = 240e6
HEAD_MASS_KG = 0.5
FRONT_MASS_KG = 0.05
FRONT_LENGTH_M = 0.5
FRONT_SHAPES = ("horizontal", "aligned", "folded")
LAYOUTS = ("stepped_40_30", "single_30")


@dataclass(frozen=True)
class Section:
    name: str
    outer_m: float
    wall_m: float
    young_pa: float = YOUNG_PA
    density_kg_m3: float = DENSITY_KG_M3
    reference_yield_pa: float = REFERENCE_YIELD_PA

    @property
    def area_m2(self):
        return self.outer_m**2 - (self.outer_m - 2*self.wall_m)**2

    @property
    def inertia_m4(self):
        return (self.outer_m**4 - (self.outer_m-2*self.wall_m)**4)/12

    @property
    def ei_nm2(self):
        return self.young_pa*self.inertia_m4

    @property
    def ea_n(self):
        return self.young_pa*self.area_m2

    @property
    def linear_mass_kg_m(self):
        return self.density_kg_m3*self.area_m2


SECTIONS = {size: Section(f"Al square tube {size}x{size}x2 mm", size/1000, .002)
            for size in (50, 40, 30)}


def segments_for(layout, length_m):
    if length_m <= 0:
        raise ValueError("Exposed length must be positive")
    if layout == "stepped_40_30":
        return [(0., length_m/2, SECTIONS[40]),
                (length_m/2, length_m, SECTIONS[30])]
    if layout == "single_30":
        return [(0., length_m, SECTIONS[30])]
    raise ValueError(f"Unknown layout: {layout}")


def integrate_gauss(function, lower, upper):
    # Three-point Gauss integration is exact for this polynomial beam problem.
    midpoint, half = (upper+lower)/2, (upper-lower)/2
    q = math.sqrt(3/5)
    return half*sum(weight*function(midpoint+half*node)
                    for node, weight in ((-q, 5/9), (0., 8/9), (q, 5/9)))


def integrate_simpson(function, lower, upper, intervals=200):
    if intervals % 2:
        raise ValueError("Simpson interval count must be even")
    step = (upper-lower)/intervals
    return step/3*(function(lower)+function(upper)+sum(
        (4 if i % 2 else 2)*function(lower+i*step)
        for i in range(1, intervals)))


def front_loads(shape, angle_rad, head_mass_kg=HEAD_MASS_KG,
                front_mass_kg=FRONT_MASS_KG):
    if min(head_mass_kg, front_mass_kg) < 0:
        raise ValueError("Masses cannot be negative")
    if shape == "horizontal":
        head_lever, front_lever = FRONT_LENGTH_M, FRONT_LENGTH_M/2
    elif shape == "aligned":
        head_lever = FRONT_LENGTH_M*math.cos(angle_rad)
        front_lever = FRONT_LENGTH_M/2*math.cos(angle_rad)
    elif shape == "folded":
        # Assumed projected COM locations; no claim of front equilibrium.
        head_lever, front_lever = .25, .125
    else:
        raise ValueError(f"Unknown front shape: {shape}")
    force = (head_mass_kg+front_mass_kg)*GRAVITY
    moment = GRAVITY*(head_mass_kg*head_lever+front_mass_kg*front_lever)
    return force, moment, head_lever, front_lever


def solve_beam(segments, angle_rad, tip_force_down_n, tip_moment_clockwise_nm,
               *, self_weight=True, numerical_check=False):
    """Small-deflection Euler-Bernoulli beam plus linear axial shortening.

    Local axis points outward/upward at angle_rad from horizontal. Positive
    reported bending moment is clockwise; rotation_rad is signed CCW.
    Tube loads are distributed along nominal straight reference geometry.
    """
    length = segments[-1][1]
    ca, sa = math.cos(angle_rad), math.sin(angle_rad)

    def downstream_weight_and_first_moment(x):
        weight, first = 0., 0.
        if self_weight:
            for lo, hi, section in segments:
                start = max(lo, x)
                if hi > start:
                    density = section.linear_mass_kg_m*GRAVITY
                    weight += density*(hi-start)
                    first += density*((hi-x)**2-(start-x)**2)/2
        return weight, first

    def moment(x):
        return (tip_moment_clockwise_nm + tip_force_down_n*ca*(length-x)
                + ca*downstream_weight_and_first_moment(x)[1])

    def axial_compression(x):
        return sa*(tip_force_down_n+downstream_weight_and_first_moment(x)[0])

    def integrate_response(integrator):
        rotation, normal_down, axial_shortening = 0., 0., 0.
        for lo, hi, section in segments:
            rotation += integrator(lambda x: moment(x)/section.ei_nm2, lo, hi)
            normal_down += integrator(
                lambda x: (length-x)*moment(x)/section.ei_nm2, lo, hi)
            axial_shortening += integrator(
                lambda x: axial_compression(x)/section.ea_n, lo, hi)
        return rotation, normal_down, axial_shortening

    rotation, normal_down, axial_shortening = integrate_response(integrate_gauss)
    total_weight = downstream_weight_and_first_moment(0.)[0]
    max_stress, critical_x, critical_section = -1., None, None
    # Moment and compression decrease on each constant-section interval.
    # Both sides of section changes must be considered through each lo cut.
    for lo, hi, section in segments:
        stress = (abs(axial_compression(lo))/section.area_m2
                  + abs(moment(lo))*section.outer_m/2/section.inertia_m4)
        if stress > max_stress:
            max_stress, critical_x, critical_section = stress, lo, section.name
    result = dict(
        exposed_length_m=length,
        interface_force_down_n=tip_force_down_n,
        interface_moment_clockwise_nm=tip_moment_clockwise_nm,
        exposed_rear_mass_kg=sum((hi-lo)*sec.linear_mass_kg_m
                                  for lo, hi, sec in segments),
        root_gravity_moment_nm=moment(0.),
        root_vertical_shear_n=tip_force_down_n+total_weight,
        root_transverse_shear_n=(tip_force_down_n+total_weight)*ca,
        local_normal_deflection_down_mm=normal_down*1000,
        local_axial_shortening_mm=axial_shortening*1000,
        interface_vertical_deflection_down_mm=(normal_down*ca+axial_shortening*sa)*1000,
        interface_horizontal_displacement_mm=(normal_down*sa-axial_shortening*ca)*1000,
        interface_rotation_ccw_rad=-rotation,
        interface_rotation_ccw_deg=-math.degrees(rotation),
        maximum_nominal_normal_stress_mpa=max_stress/1e6,
        critical_cut_from_front_guide_m=critical_x,
        critical_section=critical_section,
        nominal_yield_screen_ratio=max_stress/REFERENCE_YIELD_PA,
        nominal_yield_factor=REFERENCE_YIELD_PA/max_stress if max_stress else None,
        passes_nominal_section_yield_screen=max_stress <= REFERENCE_YIELD_PA,
        joint_strength_verified=False,
        joint_flexibility_included=False,
        scope="Linear beam screening; no overall design approval",
    )
    if numerical_check:
        numerical = integrate_response(integrate_simpson)
        numerical_root_moment = tip_moment_clockwise_nm+tip_force_down_n*ca*length
        if self_weight:
            numerical_root_moment += sum(integrate_simpson(
                lambda x: sec.linear_mass_kg_m*GRAVITY*ca*x, lo, hi)
                for lo, hi, sec in segments)
        result.update(
            root_gravity_moment_numerical_nm=numerical_root_moment,
            root_moment_integration_abs_difference_nm=abs(numerical_root_moment-moment(0.)),
            integration_rotation_abs_difference_rad=abs(numerical[0]-rotation),
            integration_normal_deflection_abs_difference_mm=abs(numerical[1]-normal_down)*1000,
            integration_axial_shortening_abs_difference_mm=abs(numerical[2]-axial_shortening)*1000,
        )
    return result


def calculate_case(layout, length_m, angle_deg, front_shape="horizontal",
                   *, head_mass_kg=HEAD_MASS_KG, front_mass_kg=FRONT_MASS_KG):
    angle = math.radians(angle_deg)
    force, moment, head_lever, front_lever = front_loads(
        front_shape, angle, head_mass_kg, front_mass_kg)
    row = solve_beam(segments_for(layout, length_m), angle, force, moment,
                     numerical_check=True)
    row.update(layout=layout, rear_axis_angle_from_horizontal_deg=angle_deg,
               front_shape=front_shape, head_mass_kg=head_mass_kg,
               front_assembly_mass_kg=front_mass_kg,
               head_horizontal_lever_from_interface_m=head_lever,
               front_com_horizontal_lever_from_interface_m=front_lever,
               front_nominal_length_m=FRONT_LENGTH_M,
               guide_couple_force_at_150mm_spacing_n=row["root_gravity_moment_nm"]/.15,
               guide_couple_force_at_200mm_spacing_n=row["root_gravity_moment_nm"]/.20)
    # These are ideal guide reactions normal to the rear axis. M/s alone
    # is the equal/opposite moment-couple component, not a complete bearing load.
    for spacing_mm in (150, 200):
        couple = row["root_gravity_moment_nm"]/(spacing_mm/1000)
        row[f"front_guide_normal_reaction_at_{spacing_mm}mm_spacing_n"] = (
            row["root_transverse_shear_n"]+couple)
        row[f"rear_guide_normal_reaction_at_{spacing_mm}mm_spacing_n"] = -couple
    return row


def independent_checks():
    checks = []

    def close(name, actual, expected, rtol=1e-10, atol=1e-12):
        passed = abs(actual-expected) <= atol+rtol*abs(expected)
        checks.append(dict(name=name, actual=actual, expected=expected, passed=passed))
        if not passed:
            raise AssertionError(f"{name}: {actual} != {expected}")

    section, length, force, moment = SECTIONS[30], .8, 5.7, 2.3
    segments = [(0., length, section)]
    r = solve_beam(segments, 0., force, moment, self_weight=False)
    close("Uniform beam: tip force plus applied end moment, deflection",
          r["interface_vertical_deflection_down_mm"]/1000,
          force*length**3/(3*section.ei_nm2)+moment*length**2/(2*section.ei_nm2))
    close("Uniform beam: tip force plus applied end moment, rotation",
          -r["interface_rotation_ccw_rad"],
          force*length**2/(2*section.ei_nm2)+moment*length/section.ei_nm2)
    close("Uniform beam: root moment includes end moment",
          r["root_gravity_moment_nm"], force*length+moment)
    r = solve_beam(segments, 0., 0., 0., self_weight=True)
    q = section.linear_mass_kg_m*GRAVITY
    close("Uniform self-weight: deflection", r["interface_vertical_deflection_down_mm"]/1000,
          q*length**4/(8*section.ei_nm2))
    close("Uniform self-weight: rotation", -r["interface_rotation_ccw_rad"],
          q*length**3/(6*section.ei_nm2))
    close("Uniform self-weight: root moment", r["root_gravity_moment_nm"], q*length**2/2)
    r = solve_beam(segments, math.pi/2, force, 0., self_weight=False)
    close("Vertical beam: axial shortening", r["interface_vertical_deflection_down_mm"]/1000,
          force*length/section.ea_n)
    close("Vertical beam: negligible bending", r["root_gravity_moment_nm"], 0.)
    # Independent discrete mass integration checks force and root moment.
    segments = segments_for("stepped_40_30", .9)
    angle = math.radians(17)
    test = solve_beam(segments, angle, force, moment, numerical_check=True)
    discrete_weight, discrete_moment = 0., 0.
    for lo, hi, sec in segments:
        dx = (hi-lo)/1000
        for i in range(1000):
            x = lo+(i+.5)*dx
            dw = sec.linear_mass_kg_m*GRAVITY*dx
            discrete_weight += dw
            discrete_moment += dw*x*math.cos(angle)
    close("Stepped beam: independently summed weight",
          test["root_vertical_shear_n"], force+discrete_weight)
    close("Stepped beam: independently summed root moment",
          test["root_gravity_moment_nm"],
          moment+force*.9*math.cos(angle)+discrete_moment)
    close("Stepped beam: Gauss versus Simpson deflection",
          test["integration_normal_deflection_abs_difference_mm"], 0., atol=1e-10)
    # A zero-length first segment is avoided; splitting an identical beam
    # must not change its response or mass.
    full = solve_beam([(0., .8, section)], .2, force, moment)
    split = solve_beam([(0., .4, section), (.4, .8, section)], .2, force, moment)
    close("Section subdivision invariance", full["interface_vertical_deflection_down_mm"],
          split["interface_vertical_deflection_down_mm"])
    return checks


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent/"results")
    parser.add_argument("--self-test-only", action="store_true")
    args = parser.parse_args()
    checks = independent_checks()
    if args.self_test_only:
        print(json.dumps(dict(checks_passed=len(checks), checks=checks), indent=2))
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [calculate_case(layout, round(.2+.1*i, 2), angle, shape)
            for layout in LAYOUTS for i in range(9)
            for angle in (5, 10, 15, 20, 25) for shape in FRONT_SHAPES]
    write_csv(args.output_dir/"rear_beam.csv", rows)
    section_rows = [dict(name=sec.name, role="Fixed sleeve behind guide plane" if size==50 else "Exposed beam candidate",
                         outer_mm=sec.outer_m*1000, wall_mm=sec.wall_m*1000,
                         area_mm2=sec.area_m2*1e6, inertia_mm4=sec.inertia_m4*1e12,
                         ei_nm2=sec.ei_nm2, linear_mass_kg_m=sec.linear_mass_kg_m)
                    for size, sec in SECTIONS.items()]
    write_csv(args.output_dir/"rear_beam_sections.csv", section_rows)
    summary = dict(
        cases=len(rows), independent_checks_passed=len(checks),
        material_assumptions=dict(material="Aluminium; alloy and temper not selected",
                                  young_pa=YOUNG_PA, density_kg_m3=DENSITY_KG_M3,
                                  reference_yield_pa=REFERENCE_YIELD_PA,
                                  yield_value_is_design_assumption_not_measured=True),
        front_assumptions=dict(head_mass_kg=HEAD_MASS_KG,
                               front_assembly_mass_kg=FRONT_MASS_KG,
                               front_mass_includes_interface_and_wiring_allowance=True,
                               front_nominal_length_m=FRONT_LENGTH_M,
                               shapes="Horizontal, rear-axis aligned, and assumed folded projected COM cases; not solved front equilibria"),
        rear_assumptions=dict(exposed_lengths_m=[round(.2+.1*i, 2) for i in range(9)],
                              angles_from_horizontal_deg=[5,10,15,20,25],
                              stepped_layout="First half 40x40x2 mm; second half 30x30x2 mm",
                              fixed_sleeve="50x50x2 mm, behind front guide; excluded from exposed beam",
                              guide_spacing_m=[.15,.20],
                              guide_couple_definition="M/s is a couple component; ideal normal support reactions also include transverse force"),
        limitations=[
            "Ideal continuous cantilever; zero joint compliance, clearance and slip",
            "No verification of guide contact pressure, local tube wall deformation, fasteners, base anchorage or joint strength",
            "No Euler or local buckling, torsion, stress concentrations, friction, fatigue or dynamic loads",
            "No drive, tendon or external cable forces beyond the assumed 0.05 kg front mass allowance",
            "Rear self-weight uses only the exposed beam; overlap and other moving hardware masses are not included",
            "No tank geometry, insertion swept-volume or allowable extension assessment",
            "Nominal section yield screening is not overall admissibility or hardware approval",
            "Front shapes prescribe horizontal COM levers; they do not validate a loaded U/M front assembly",
        ],
        maximum_nominal_normal_stress_mpa=max(r["maximum_nominal_normal_stress_mpa"] for r in rows),
        maximum_interface_vertical_deflection_down_mm=max(r["interface_vertical_deflection_down_mm"] for r in rows),
        max_integration_deflection_difference_mm=max(r["integration_normal_deflection_abs_difference_mm"] for r in rows),
        representative_cases=[r for r in rows if r["exposed_length_m"]==1. and
                              r["rear_axis_angle_from_horizontal_deg"]==15 and
                              r["front_shape"]=="horizontal"],
        checks=checks,
    )
    (args.output_dir/"rear_beam_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in (
        "cases", "independent_checks_passed", "maximum_nominal_normal_stress_mpa",
        "maximum_interface_vertical_deflection_down_mm", "max_integration_deflection_difference_mm")}, indent=2))


if __name__ == "__main__":
    main()
