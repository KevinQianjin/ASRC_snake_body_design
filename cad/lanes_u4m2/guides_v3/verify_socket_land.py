"""Measure actual exported saddle gaps by rays from source-CAD web faces.

This checks the intended flat land and mouth relief in the STL, independently
of the loft's axial sampling. It is not a bond or manufacturing qualification.
"""
import argparse,json
from pathlib import Path
import numpy as np
import trimesh
from shapely.geometry import Polygon

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'guides_v2'


def polygons(mesh,z):
    section=mesh.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
    return [Polygon(p[:,:2]) for p in section.discrete]


def verify(cad,out):
    design=json.loads((cad/'design.json').read_text());rows=[]
    for kind,filename in [('M5','M5_lane_anchorB.stl'),('M6','M6_lane_anchorC.stl')]:
        body=trimesh.load_mesh(SOURCE/filename)
        for station in (-12,12):
            frame=trimesh.load_mesh(cad/f'{kind}_z{station:+d}_guide.stl')
            for z in (-1.6,-.25,-.125,0,.125,.25,1.6):
                sections=polygons(body,station+z)
                for angle in design['web_angles_deg']:
                    a=np.radians(angle);radial=np.array([np.cos(a),np.sin(a)])
                    poly=min(sections,key=lambda p:np.linalg.norm(np.array(p.centroid.coords[0])-radial*19.229))
                    edge=max(np.asarray(poly.exterior.coords)@radial)
                    origin=np.r_[radial*edge,z];direction=np.r_[radial,0.]
                    points,_,_=frame.ray.intersects_location([origin],[direction],multiple_hits=True)
                    if not len(points):raise ValueError('No saddle wall found by inspection ray')
                    measured=float(np.linalg.norm(points-origin,axis=1).min())
                    expected=design['bond_gap_mm']+design['socket_flare_slope']*max(abs(z)-design['socket_land_axial_mm']/2,0)
                    rows.append(dict(part=f'{kind}_z{station:+d}',local_z_mm=z,angle_deg=angle,
                        measured_radial_gap_mm=measured,expected_gap_mm=expected,error_mm=measured-expected))
    result=dict(scope=__doc__,rows=rows,maximum_absolute_error_mm=max(abs(r['error_mm']) for r in rows),
        tolerance_mm=.0002,all_samples_pass=all(abs(r['error_mm'])<.0002 for r in rows))
    out.write_text(json.dumps(result,indent=2)+'\n')
    print('Socket gap rays:',len(rows),'maximum error mm:',result['maximum_absolute_error_mm'],'pass:',result['all_samples_pass'])
    if not result['all_samples_pass']:raise RuntimeError('Exported socket does not have its specified land/relief')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cad',type=Path,default=HERE);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();verify(a.cad,a.out)
