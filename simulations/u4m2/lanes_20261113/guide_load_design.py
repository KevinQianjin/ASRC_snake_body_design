"""Turn exported guide loads into traceable preliminary design-load requirements.

No material allowables are assumed. This is not a stress FEA or a strength pass.
The arm calculation idealises each radial arm as a rectangular cantilever rooted
at r=7.8 mm and ignores hole stress concentrations and frame/web load sharing.
"""
import argparse,csv,gzip,itertools,json
from pathlib import Path
import numpy as np


def screen(folder,out,factor=3.):
    summary=json.loads((folder/'summary.json').read_text())
    root=7.8;width=4.;thickness=3.2
    peaks={}
    def record(key,value,location):
        if value>peaks.get(key,{}).get('value',-1):peaks[key]=dict(value=float(value),location=location)
    with gzip.open(folder/'hole_loads.csv.gz','rt') as f:
        reader=csv.DictReader(f)
        key=lambda r:(r['archive'],r['state'],r['module'])
        for module_loc,module_rows in itertools.groupby(reader,key=key):
            stations={}
            for row in module_rows:stations.setdefault(row['station_z_mm'],[]).append(row)
            for station,rows in stations.items():
                loc=module_loc+(station,)
                station_total=sum(float(r['force_n']) for r in rows)
                record('station_sum_hole_force_n',station_total,loc)
                for ray in ['up','right','down','left']:
                    forces=[r for r in rows if r['ray']==ray]
                    Fr=Mt=Mo=0.
                    for row in forces:
                        F=np.array([float(row[n]) for n in ['fx_n','fy_n','fz_n']])
                        er=np.array({'up':[0,1,0],'right':[0,0,1],'down':[0,-1,0],'left':[0,0,-1]}[ray])
                        et=np.cross([1,0,0],er);r=24 if row['set']=='B' else summary['radii_mm'][2]
                        Fr+=F@er;Mt+=(F@et)*(r-root);Mo+=F[0]*(r-root)
                        record('hole_projected_bearing_mpa',np.linalg.norm(F)/(2.*thickness),loc+(row['set'],ray))
                    sigma=abs(Fr)/(width*thickness)+6*abs(Mt)/(thickness*width**2)+6*abs(Mo)/(width*thickness**2)
                    record('arm_nominal_normal_stress_mpa',sigma,loc+(ray,))
    result=dict(scope=__doc__,factor=factor,assumed_arm_root_radius_mm=root,assumed_arm_width_mm=width,assumed_thickness_mm=thickness,
        operating_maxima=peaks,scaled_design_requirements=dict(
            single_hole_force_n=factor*summary['maximum_hole_force_n'],
            station_net_force_n=factor*summary['maximum_station_force_n'],
            station_net_moment_nmm=factor*summary['maximum_station_moment_nmm'],
            station_sum_absolute_hole_forces_n=factor*peaks['station_sum_hole_force_n']['value'],
            nominal_arm_normal_stress_mpa=factor*peaks['arm_nominal_normal_stress_mpa']['value'],
            nominal_hole_bearing_mpa=factor*peaks['hole_projected_bearing_mpa']['value']),
        acceptance='Not assessed: printed strength, stress concentrations, anisotropy, fatigue, friction, bond/wire capacity and mount load sharing are unvalidated. Moment and force maxima may occur in different states; use the per-state loads for combined-load tests.')
    out.write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(screen(a.folder,a.out),indent=2))
