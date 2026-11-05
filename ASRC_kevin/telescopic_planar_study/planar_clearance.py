"""CAD-derived planar clearance screen; all lengths here are millimetres.

Static installation positions are screened separately from a constant-shape
insertion path. Passing a static screen is not a deployment or 3D proof.
"""
from pathlib import Path
import sys, json, csv, math
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'_cad_runtime'))
import shapely as sh
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union

MARGIN=5.
FRONT_RADIUS=16.
REAR_RADIUS=20.  # conservative constant 40 mm envelope for both moving stages
GUIDE_SETBACK=200.

def save_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        keys=list(dict.fromkeys(k for r in rows for k in r))
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def load_geometry():
    cad=json.loads((HERE/'results/cad_sections.json').read_text())
    sections={s['width_mm']:s for s in cad['sections']}
    def polygons(s):return unary_union([Polygon(p['outer'],p['holes']) for p in s['union_polygons']])
    obstacles={k:polygons(s) for k,s in sections.items()}
    center=sections[648.]
    def part(name):return unary_union([Polygon(p['outer'],p['holes']) for a in center['parts'] if a['name']==name for p in a['polygons']])
    xs=np.arange(.5,1600.,1.)
    rays=sh.linestrings(np.stack((np.c_[xs,np.full_like(xs,-100.)],np.c_[xs,np.full_like(xs,600.)]),axis=1))
    roof_bounds=sh.bounds(sh.intersection(part('FT P1'),rays))
    floor_bounds=sh.bounds(sh.intersection(part('FT P2'),rays))
    roof=roof_bounds[:,1];floor=floor_bounds[:,3]
    for a in (roof,floor):
        ok=np.isfinite(a);a[~ok]=np.interp(xs[~ok],xs[ok],a[ok])
    cavity=Polygon(np.vstack((np.c_[xs,floor],np.c_[xs[::-1],roof[::-1]])))
    return cad,obstacles,cavity,xs,floor,roof

def self_screen(p,theta,eps):
    # Original material separation >=64 mm avoids treating adjacent body as contact.
    cell=480./(len(theta)-1)
    arc=np.r_[0.,20.+np.arange(len(theta))*cell]
    n=len(p)-1
    a,b=np.triu_indices(n,k=2)
    keep=arc[b]-arc[a+1]>=64.-1e-8;a,b=a[keep],b[keep]
    seg=sh.linestrings(np.stack((p[:-1],p[1:]),axis=1))
    clear=float(np.min(sh.distance(seg[a],seg[b]))-32.) if len(a) else float('inf')
    simple=bool(LineString(p).is_simple)
    rk=float(np.max(np.abs(np.diff(theta))/(cell*(1+eps)))*16.)
    return simple,clear,rk

def main():
    out=HERE/'results'
    cad,obs,cavity,xs,floor,roof=load_geometry()
    # These are discrete flank-plane screens, not a continuous 3D swept envelope.
    rear_obs=unary_union([obs[k] for k in (628.,648.,668.)])
    front_obs=unary_union([obs[k] for k in (632.,648.,664.)])
    center_obs=obs[648.]
    ports={'A':np.array([449.,np.interp(449.,xs,floor)]),
           'B':np.array([1147.,np.interp(1147.,xs,floor)])}
    inside=np.arange(0.,1000.01,10.)
    bare=[]
    for port,entry in ports.items():
      for direction in (-1,1):
       for angle in range(5,31):
        v=np.array([direction*math.cos(math.radians(angle)),math.sin(math.radians(angle))])
        guide=entry-GUIDE_SETBACK*v
        sleeve=LineString([guide-300*v,guide])
        sleeve_ok=sleeve.distance(rear_obs)>=30. # 50 mm housing plus 5 mm margin
        roots=entry+inside[:,None]*v
        rear_lines=sh.linestrings(np.stack((np.broadcast_to(guide,roots.shape),roots),axis=1))
        rd=sh.distance(rear_lines,rear_obs)
        rear_ok=(rd>=REAR_RADIUS+MARGIN)&sleeve_ok
        # Root must be above the interpolated skin envelope; aperture is not work space.
        rear_ok &= np.array([cavity.covers(Point(q).buffer(REAR_RADIUS+MARGIN)) for q in roots])
        # A straight 500 mm front is an imposed geometric pose, not an equilibrium.
        ideal_end=roots+500*v
        ideal_lines=sh.linestrings(np.stack((roots,ideal_end),axis=1))
        ideal_ok=(sh.distance(ideal_lines,front_obs)>=FRONT_RADIUS+MARGIN)
        ideal_ok &= np.array([cavity.covers(LineString([a,b]).buffer(FRONT_RADIUS+MARGIN)) for a,b in zip(roots,ideal_end)])
        rr=inside[rear_ok];ii=inside[rear_ok&ideal_ok]
        bare.append(dict(port=port,direction=direction,pitch_deg=angle,
          housing_clear=bool(sleeve_ok),maximum_rear_insertion_mm=float(rr.max()) if len(rr) else None,
          minimum_rear_insertion_mm=float(rr.min()) if len(rr) else None,
          maximum_straight_front_insertion_mm=float(ii.max()) if len(ii) else None,
          minimum_straight_front_insertion_mm=float(ii.min()) if len(ii) else None,
          imposed_straight_front_geometry_only=True))
    save_csv(out/'geometry_axis_windows.csv',bare)
    rows=json.loads((out/'front_equilibria.json').read_text())
    z=np.load(out/'front_states.npz')
    screens=[];examples=[];counts={'placements':0,'rear_clear':0,'static_clear':0,'static_clear_stable':0,'static_clear_stable_low_strain':0,'static_clear_stable_self_clear':0,'all_diagnostic_screens':0}
    for row in rows:
      sid=row['state_id'];p=z[sid+'_points_m']*1000
      theta=z[sid+'_theta_rad'];eps=z[sid+'_strain']
      simple,nonlocal_clear,rk=self_screen(p,theta,eps)
      self_ok=simple and nonlocal_clear>=-1e-6 and rk<1.
      low=not row['axial_strain_exceeds_5_percent'];stable=row['stable_in_plane']
      for port,entry in ports.items():
       for direction in (-1,1):
        a=math.radians(row['pitch_deg']);v=np.array([direction*math.cos(a),math.sin(a)])
        guide=entry-GUIDE_SETBACK*v
        roots=entry+inside[:,None]*v
        local=p*np.array([direction,1.])
        allp=roots[:,None,:]+local[None,:,:]
        curves=sh.linestrings(allp)
        rear_lines=sh.linestrings(np.stack((np.broadcast_to(guide,roots.shape),roots),axis=1))
        rd=sh.distance(rear_lines,rear_obs)
        sleeve_ok=LineString([guide-300*v,guide]).distance(rear_obs)>=30.
        rear_ok=(rd>=REAR_RADIUS+MARGIN)&sleeve_ok
        fd=sh.distance(curves,front_obs)
        inside_ok=np.array([cavity.covers(LineString(q).buffer(FRONT_RADIUS+MARGIN)) for q in allp])
        fit=rear_ok&(fd>=FRONT_RADIUS+MARGIN)&inside_ok
        good=fit&stable&low&self_ok
        counts['placements']+=len(inside);counts['rear_clear']+=int(rear_ok.sum());counts['static_clear']+=int(fit.sum())
        counts['static_clear_stable']+=int(fit.sum())*stable
        counts['static_clear_stable_low_strain']+=int(fit.sum())*(stable and low)
        counts['static_clear_stable_self_clear']+=int(fit.sum())*(stable and self_ok)
        counts['all_diagnostic_screens']+=int(good.sum())
        sfit=inside[fit];sgood=inside[good]
        screens.append(dict(state_id=sid,configuration=row['configuration'],pitch_deg=row['pitch_deg'],port=port,direction=direction,
          total_tension_n=row['total_tension_n'],tensions_n=row['tensions_n'],stable_in_plane=stable,
          max_abs_axial_strain=max(row['max_axial_compression'],row['max_axial_extension']),strain_at_most_5_percent=low,
          centerline_simple=simple,nonlocal_capsule_clearance_mm=nonlocal_clear,radius_times_curvature_max=rk,self_screen_pass=self_ok,
          static_clear_count=int(fit.sum()),minimum_static_insertion_mm=float(sfit.min()) if len(sfit) else None,
          maximum_static_insertion_mm=float(sfit.max()) if len(sfit) else None,
          diagnostic_screened_static_count=int(good.sum()),minimum_screened_insertion_mm=float(sgood.min()) if len(sgood) else None,
          maximum_screened_insertion_mm=float(sgood.max()) if len(sgood) else None))
        if len(sfit):
          i=int(np.flatnonzero(fit)[len(sfit)//2]);ss=float(inside[i])
          # A frozen loaded shape translated through the opening is only one deployment strategy.
          path_s=np.arange(-550.,ss+.1,5.)
          path_p=entry+path_s[:,None]*v
          path_curves=sh.linestrings(path_p[:,None,:]+local[None,:,:])
          path_clear=sh.distance(path_curves,front_obs)>=FRONT_RADIUS+MARGIN
          examples.append(dict(state_id=sid,configuration=row['configuration'],pitch_deg=row['pitch_deg'],port=port,direction=direction,
             insertion_mm=ss,exposed_rear_length_mm=ss+GUIDE_SETBACK,tip_global_mm=allp[i,-1].tolist(),
             tip_x_relative_mm=row['tip_x_mm'],tip_y_relative_mm=row['tip_y_mm'],max_abs_axial_strain=max(row['max_axial_compression'],row['max_axial_extension']),
             stable_in_plane=stable,self_screen_pass=self_ok,strain_at_most_5_percent=low,
             frozen_shape_insertion_clear=bool(path_clear.all()),frozen_path_collision_samples=int((~path_clear).sum()),
             scope='static_planar_diagnostic_not_deployment_or_material_certification'))
    save_csv(out/'front_cad_placements.csv',screens)
    (out/'static_fit_examples.json').write_text(json.dumps(examples,indent=2),encoding='utf-8')
    summary=dict(counts=counts,front_records=len(rows),axis_cases=len(bare),insertion_grid_mm=[0,1000,10],
      guide_setback_mm=GUIDE_SETBACK,front_and_assumed_head_diameter_mm=32,rear_height_mm=40,fixed_housing_height_mm=50,clearance_margin_mm=MARGIN,
      maximum_static_fit_strain_at_most_5_percent=sum(r['strain_at_most_5_percent'] and r['stable_in_plane'] and r['self_screen_pass'] for r in examples),
      frozen_shape_path_pass_examples=sum(r['frozen_shape_insertion_clear'] for r in examples),
      caveats=['5% strain is a diagnostic threshold, not a measured material failure criterion.',
      'Front and head represented by the same 32 mm capsule; actual head geometry not provided.',
      'Five discrete CAD width planes are not a continuous 3D collision check.',
      'Cavity envelope is interpolated across access holes to require the working front to remain inside.',
      '0.5 m front uses 480 mm modules plus a 20 mm massless rigid interface.',
      'No global infeasibility proof; no alternative changing-shape insertion path solved.'])
    (out/'planar_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    np.savez_compressed(out/'cavity_profiles.npz',length_mm=xs,floor_mm=floor,roof_mm=roof)
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
