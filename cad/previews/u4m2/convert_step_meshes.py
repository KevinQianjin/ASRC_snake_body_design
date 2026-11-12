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
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer


def read_shape(source: Path):
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(source))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Could not read STEP file: {source} (status {status})")
    roots = reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise RuntimeError(f"STEP file contains no transferable shape: {source}")
    return roots, shape


def mesh_shape(shape, linear_mm: float, angular_rad: float) -> None:
    mesher = BRepMesh_IncrementalMesh(shape, linear_mm, False, angular_rad, True)
    mesher.Perform()
    if not mesher.IsDone():
        raise RuntimeError("STEP geometry meshing failed")


def write_stl(shape, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    if not writer.Write(shape, str(destination)):
        raise RuntimeError(f"STL export failed for {destination}")
    print(f"STL={destination} ({destination.stat().st_size:,} bytes)")


def export_unidirectional(source: Path, output_dir: Path,
                          linear_mm: float, angular_rad: float) -> None:
    roots, shape = read_shape(source)
    mesh_shape(shape, linear_mm, angular_rad)
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    solids = []
    while explorer.More():
        solids.append(explorer.Current())
        explorer.Next()
    if len(solids) != 5:
        raise RuntimeError(f"Expected 5 U-module solids, found {len(solids)}")
    print(f"{source.name}: roots={roots}, solids={len(solids)}")
    for index, solid in enumerate(solids, start=1):
        write_stl(solid, output_dir / f"UniDirectional_96_part_0{index}.stl")


def export_medium(source: Path, destination: Path,
                  linear_mm: float, angular_rad: float) -> None:
    roots, shape = read_shape(source)
    mesh_shape(shape, linear_mm, angular_rad)
    print(f"{source.name}: roots={roots}, medium module assembly")
    write_stl(shape, destination)


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

    export_unidirectional(args.cad_dir / "UniDirectional_96.step",
                          args.output_dir, args.linear_mm, args.angular_rad)
    export_medium(args.cad_dir / "Medium_Stiffness_96.step",
                  args.output_dir / "Medium_Stiffness_96.stl",
                  args.linear_mm, args.angular_rad)


if __name__ == "__main__":
    main()
