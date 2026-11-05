"""Extract labelled solid/plane CAD intersections from the tank STEP assembly.

The external support frame is excluded by selecting the named tank subtree.
No manually traced skin/rib boundary is used. Units and output coordinates
are mm: horizontal length=-oldX, vertical height=oldY, width=-oldZ.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/"_cad_runtime"))

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.Bnd import Bnd_Box
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence, TDF_Tool
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from shapely import make_valid
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union


TANK_NAME = "Aircraft fuel tank model - Transparent v9"


def label_name(label):
    attribute = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attribute):
        return attribute.Get().ToExtString()
    return ""


def label_entry(label):
    from OCP.TCollection import TCollection_AsciiString
    entry = TCollection_AsciiString()
    TDF_Tool.Entry_s(label, entry)
    return entry.ToCString()


def referred(tool, label):
    target = TDF_Label()
    if tool.IsReference_s(label) and tool.GetReferredShape_s(label, target):
        return target
    return label


def components(tool, label):
    seq = TDF_LabelSequence()
    tool.GetComponents_s(label, seq, False)
    return [seq.Value(i) for i in range(1, seq.Length()+1)]


def bbox(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)
    return list(box.Get()) if not box.IsVoid() else None


def load_tank(path):
    document = TDocStd_Document(TCollection_ExtendedString("tank-sections"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError("STEP read failed")
    if not reader.Transfer(document):
        raise RuntimeError("STEP/XCAF transfer failed")
    tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    roots = TDF_LabelSequence()
    tool.GetFreeShapes(roots)
    inventory, selected = [], []

    def search(label, depth=0):
        definition = referred(tool, label)
        name = label_name(definition) or label_name(label)
        inventory.append(dict(name=name, depth=depth, entry=label_entry(definition)))
        if name == TANK_NAME:
            selected.append(definition)
            return
        for child in components(tool, definition):
            search(child, depth+1)

    for i in range(1, roots.Length()+1):
        search(roots.Value(i))
    if not selected:
        raise RuntimeError("Named tank subtree not found: "+json.dumps(inventory))
    if len({label_entry(label) for label in selected}) != 1:
        raise RuntimeError("Multiple distinct named tank definitions require explicit selection")
    tank = selected[0]
    parts = []

    def leaves(definition, placement, path_names):
        children = components(tool, definition)
        if children:
            for child in children:
                child_def = referred(tool, child)
                child_name = label_name(child_def) or label_name(child) or label_entry(child_def)
                leaves(child_def, placement.Multiplied(tool.GetLocation_s(child)), path_names+[child_name])
        else:
            shape = tool.GetShape_s(definition).Moved(placement)
            bounds = bbox(shape)
            if bounds is not None:
                parts.append(dict(name=path_names[-1], assembly_path=path_names,
                                  definition_entry=label_entry(definition), shape=shape,
                                  bbox_old_xyz_mm=bounds))

    leaves(tank, TopLoc_Location(), [TANK_NAME])
    if not parts:
        raise RuntimeError("Tank subtree contained no leaf shapes")
    return document, reader, parts, inventory


def wire_points(wire, face, deflection_mm, wire_stats=None):
    explorer = BRepTools_WireExplorer(wire, face)
    points = []
    # Small imported/Boolean vertex gaps are below the requested chordal
    # precision. Record them explicitly; never bridge a larger missing edge.
    join_tolerance = min(.02, deflection_mm/2)
    maximum_join_gap = 0.
    while explorer.More():
        edge = TopoDS.Edge_s(explorer.Current())
        if BRep_Tool.Degenerated_s(edge):
            explorer.Next()
            continue
        curve = BRepAdaptor_Curve(edge)
        discretization = GCPnts_QuasiUniformDeflection(curve, deflection_mm)
        if not discretization.IsDone():
            raise RuntimeError("Curve discretization did not complete")
        sampled = [discretization.Value(i) for i in range(1, discretization.NbPoints()+1)]
        if edge.Orientation() == TopAbs_REVERSED:
            sampled.reverse()
        if points and sampled and math.dist(points[-1], [-sampled[0].X(), sampled[0].Y()]) > 1e-4:
            current_gap = math.dist(points[-1], [-sampled[0].X(), sampled[0].Y()])
            reversed_gap = math.dist(points[-1], [-sampled[-1].X(), sampled[-1].Y()])
            if reversed_gap < current_gap and reversed_gap <= join_tolerance:
                sampled.reverse()
                current_gap = reversed_gap
            if current_gap > join_tolerance:
                raise RuntimeError(f"Ordered wire edge gap {current_gap:.9g} mm; reversed gap {reversed_gap:.9g} mm")
        if points and sampled:
            maximum_join_gap = max(maximum_join_gap, math.dist(points[-1], [-sampled[0].X(), sampled[0].Y()]))
        for point in sampled:
            xy = [-point.X(), point.Y()]
            if not points or math.dist(xy, points[-1]) > 1e-7:
                points.append(xy)
        explorer.Next()
    if len(points) >= 3:
        maximum_join_gap = max(maximum_join_gap, math.dist(points[0], points[-1]))
        if math.dist(points[0], points[-1]) > join_tolerance:
            raise RuntimeError("Ordered wire closure gap exceeds recorded join tolerance")
        if math.dist(points[0], points[-1]) > 1e-7:
            points.append(points[0])
        else:
            points[-1] = points[0]
    if wire_stats is not None:
        wire_stats.append(dict(maximum_join_gap_mm=maximum_join_gap, join_tolerance_mm=join_tolerance))
    return points


def polygon_records(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [dict(outer=[list(x) for x in geometry.exterior.coords],
                     holes=[[list(x) for x in ring.coords] for ring in geometry.interiors],
                     area_mm2=geometry.area)]
    if hasattr(geometry, "geoms"):
        return [record for item in geometry.geoms for record in polygon_records(item)]
    return []


def extract_plane(parts, width_mm, deflection_mm):
    old_z = -width_mm
    # Bounds are derived from the selected tank, never from the external frame.
    xmin = min(p["bbox_old_xyz_mm"][0] for p in parts)-10
    ymin = min(p["bbox_old_xyz_mm"][1] for p in parts)-10
    xmax = max(p["bbox_old_xyz_mm"][3] for p in parts)+10
    ymax = max(p["bbox_old_xyz_mm"][4] for p in parts)+10
    plane = gp_Pln(gp_Pnt(0, 0, old_z), gp_Dir(0, 0, 1))
    face = BRepBuilderAPI_MakeFace(plane, xmin, xmax, ymin, ymax).Face()
    records, geometry_list, failures = [], [], []
    touched = 0
    for index, part in enumerate(parts):
        bounds = part["bbox_old_xyz_mm"]
        if not bounds or old_z < bounds[2]-1e-6 or old_z > bounds[5]+1e-6:
            continue
        touched += 1
        try:
            common = BRepAlgoAPI_Common(part["shape"], face)
            common.Build()
            if not common.IsDone():
                raise RuntimeError("Solid/plane Boolean common failed")
            result = common.Shape()
            valid_brep = BRepCheck_Analyzer(result).IsValid()
            explorer = TopExp_Explorer(result, TopAbs_FACE)
            polygons, face_count, repairs = [], 0, 0
            cad_area, polygon_area, allowed_area_error = 0., 0., 0.
            wire_stats = []
            while explorer.More():
                cut_face = TopoDS.Face_s(explorer.Current())
                outer_wire = BRepTools.OuterWire_s(cut_face)
                outer = wire_points(outer_wire, cut_face, deflection_mm, wire_stats)
                from OCP.TopAbs import TopAbs_WIRE
                wires = TopExp_Explorer(cut_face, TopAbs_WIRE)
                holes = []
                while wires.More():
                    wire = TopoDS.Wire_s(wires.Current())
                    if not wire.IsSame(outer_wire):
                        ring = wire_points(wire, cut_face, deflection_mm, wire_stats)
                        if len(ring) >= 4:
                            holes.append(ring)
                    wires.Next()
                if len(outer) >= 4:
                    polygon = Polygon(outer, holes)
                    properties = GProp_GProps()
                    BRepGProp.SurfaceProperties_s(cut_face, properties)
                    cad_area += properties.Mass()
                    allowed_area_error += polygon.length*deflection_mm+math.pi*deflection_mm**2
                    if not polygon.is_valid:
                        polygon = make_valid(polygon)
                        repairs += 1
                    polygon_area += polygon.area
                    polygons.extend(polygon_records(polygon))
                    geometry_list.append(polygon)
                face_count += 1
                explorer.Next()
            if polygons:
                records.append(dict(part_index=index, name=part["name"],
                                    assembly_path=part["assembly_path"],
                                    section_face_count=face_count,
                                    boolean_result_brep_valid=valid_brep,
                                    repaired_polygon_count=repairs, polygons=polygons,
                                    cad_section_area_mm2=cad_area,
                                    polygon_section_area_mm2=polygon_area,
                                    polygon_cad_area_abs_difference_mm2=abs(cad_area-polygon_area),
                                    polygon_area_error_bound_mm2=allowed_area_error,
                                    maximum_wire_join_gap_mm=max((s["maximum_join_gap_mm"] for s in wire_stats), default=0.),
                                    polygon_area_agrees_with_cad=abs(cad_area-polygon_area)<=allowed_area_error+1e-6))
        except Exception as error:
            failures.append(dict(part_index=index, name=part["name"], error=str(error)))
    union = unary_union(geometry_list) if geometry_list else Polygon()
    if not union.is_valid:
        union = make_valid(union)
    return dict(width_mm=width_mm, old_z_mm=old_z, parts=records,
                union_polygons=polygon_records(union),
                validation=dict(candidate_parts=touched, intersecting_parts=len(records),
                                union_valid=bool(union.is_valid), union_area_mm2=union.area,
                                boolean_or_discretization_failures=failures,
                                all_part_areas_agree_with_cad=all(p["polygon_area_agrees_with_cad"] for p in records),
                                repaired_polygon_count=sum(p["repaired_polygon_count"] for p in records)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=Path, default=HERE/"inputs"/"tank-v2.step")
    parser.add_argument("--output", type=Path, default=HERE/"results"/"cad_sections.json")
    parser.add_argument("--widths", nargs="+", type=float, default=[648, 632, 664, 628, 668])
    parser.add_argument("--deflection", type=float, default=.1)
    args = parser.parse_args()
    if not 0 < args.deflection <= .2:
        raise ValueError("Curve deflection must be positive and no greater than 0.2 mm")
    start = time.time()
    document, reader, parts, inventory = load_tank(args.step)
    bounds = [min(p["bbox_old_xyz_mm"][i] for p in parts) for i in range(3)] + [
        max(p["bbox_old_xyz_mm"][i] for p in parts) for i in range(3, 6)]
    result = dict(source_step=str(args.step.resolve()),
                  source_step_sha256=hashlib.sha256(args.step.read_bytes()).hexdigest(),
                  tank_subtree=TANK_NAME,
                  external_frame_excluded=True, units="mm",
                  coordinate_mapping=dict(length="-oldX", height="oldY", width="-oldZ"),
                  tank_bbox_old_xyz_mm=bounds,
                  tank_bbox_length_height_width_mm=[-bounds[3], bounds[1], -bounds[5], -bounds[0], bounds[4], -bounds[2]],
                  curve_chordal_deflection_mm=args.deflection,
                  maximum_permitted_imported_wire_join_gap_mm=min(.02,args.deflection/2),
                  parts=[{k:v for k,v in p.items() if k != "shape"} for p in parts],
                  known_access_holes=dict(nominal_in_plane_dimensions_mm=[500,200],
                                          geometry="Extracted from CAD, not inserted as manual voids"),
                  sections=[], limitations=[
                      "Only selected width planes are checked; these do not prove 3D collision clearance",
                      "Planar solid intersections preserve CAD voids; the tank exterior bounding box is not filled",
                      "No sweep-envelope, contact, deformation or manufacturing tolerance model",
                      "Finite wire chordal deflection; narrow features remain limited by the source CAD topology",
                  ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for width in args.widths:
        section = extract_plane(parts, width, args.deflection)
        result["sections"].append(section)
        result["elapsed_seconds"] = time.time()-start
        # Save after every plane so the priority center section is usable early.
        temporary = args.output.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        temporary.replace(args.output)
        print(json.dumps(dict(width_mm=width, parts=section["validation"]["intersecting_parts"],
                              area_mm2=section["validation"]["union_area_mm2"],
                              failures=section["validation"]["boolean_or_discretization_failures"],
                              elapsed_seconds=result["elapsed_seconds"])), flush=True)


if __name__ == "__main__":
    main()
