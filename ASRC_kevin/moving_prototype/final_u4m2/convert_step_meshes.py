"""Convert the uploaded U/M STEP assemblies to OpenSCAD-readable STL.

Requires cadquery-ocp (OpenCascade Python bindings). The STEP files are not
modified. The uploaded files declare millimetre units.
"""

import argparse
from pathlib import Path

from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.StlAPI import StlAPI_Writer


def convert(source: Path, destination: Path, linear_mm: float, angular_rad: float) -> None:
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(source))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Could not read STEP file: {source} (status {status})")
    roots = reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise RuntimeError(f"STEP file contains no transferable shape: {source}")

    mesher = BRepMesh_IncrementalMesh(shape, linear_mm, False, angular_rad, True)
    mesher.Perform()
    if not mesher.IsDone():
        raise RuntimeError(f"Meshing failed for {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    if not writer.Write(shape, str(destination)):
        raise RuntimeError(f"STL export failed for {source}")
    print(f"{source.name}: roots={roots}, STL={destination} ({destination.stat().st_size:,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cad-dir", type=Path, required=True,
        help="Folder containing UniDirectional_96.step and Medium_Stiffness_96.step",
    )
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--linear-mm", type=float, default=0.12,
                        help="Maximum linear mesh deflection in mm (default: 0.12)")
    parser.add_argument("--angular-rad", type=float, default=0.25,
                        help="Maximum angular mesh deflection in radians (default: 0.25)")
    args = parser.parse_args()
    if args.linear_mm <= 0 or args.angular_rad <= 0:
        parser.error("mesh deflections must be positive")

    for stem in ("UniDirectional_96", "Medium_Stiffness_96"):
        convert(args.cad_dir / f"{stem}.step",
                args.output_dir / f"{stem}.stl",
                args.linear_mm, args.angular_rad)


if __name__ == "__main__":
    main()
