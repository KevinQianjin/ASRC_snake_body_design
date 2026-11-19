"""Independently audit the saved continuation steps and recover both shell faces."""

import argparse
import json
from pathlib import Path


from continuation import Checkpoints
from shell import Mesh, Model, shell_elements
from study import save, surface_extremes


def audit(raw, cache, model):
    data = json.loads(raw.read_text())
    if not data["completed"]:
        raise ValueError(f"Incomplete case {raw.name}")
    states = Checkpoints(model, data["case"], None, cache)
    fractions = sorted(states.seeds)
    accepted = {round(s["fraction"], 9) for s in data["steps"] if s["accepted"]}
    if set(fractions) != accepted | {0.0}:
        raise ValueError(f"Scratch steps differ from the accepted continuation in {raw.name}")
    samples = {r["fraction"]: r for r in data["samples"]}
    worst = 1.0
    for fraction in fractions:
        q, _ = states.load(fraction)
        x = model.mapping(q)[0]
        ratio = model.mesh.minimum_orientation(x)
        if ratio <= 0.0:
            raise ValueError(f"Folded triangle in {raw.name} at fraction {fraction}, ratio {ratio}")
        worst = min(worst, ratio)
        if fraction in samples:
            row = samples[fraction]
            if abs(ratio - row["minimum_oriented_area_ratio"]) > 1.0e-6:
                raise ValueError("Scratch geometry disagrees with the published sample")
            mesh = model.mesh
            _, _, _, strains = shell_elements(x, mesh.tri, mesh.coeff, mesh.material, False)
            faces = surface_extremes(mesh, strains)
            peak = max(abs(faces[s]["strain"]) for s in ("principal_tensile", "principal_compressive"))
            if abs(peak - row["max_abs_surface_strain"]) > 1.0e-6:
                raise ValueError("Scratch strain disagrees with the saved sample")
            row["surface_extremes"] = faces
    data["accepted_state_orientation_audit"] = dict(states=len(fractions), minimum_ratio=worst)
    save(raw, data)
    print(raw.name, len(fractions), f"{worst:.7f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--cases", nargs="+", help="Optional file stems, such as point_146")
    args = parser.parse_args()
    raws = (
        sorted(args.results.glob("*.json"))
        if args.cases is None
        else [args.results / (case + ".json") for case in args.cases]
    )
    if not raws:
        parser.error("No case files found")
    model = mesh = None
    for raw in raws:
        metadata = json.loads(raw.read_text())
        if (
            mesh is None
            or mesh.info["max_triangle_area_mm2"] != metadata["mesh"]["max_triangle_area_mm2"]
        ):
            mesh = Mesh(metadata["mesh"]["max_triangle_area_mm2"])
            model = None
        if model is None or model.variant != metadata["variant"]:
            model = Model(mesh, metadata["variant"])
        audit(raw, args.cache, model)


if __name__ == "__main__":
    main()
