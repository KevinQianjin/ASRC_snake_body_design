"""Independent numerical and saved-state checks for the spatial delivery."""
import json,hashlib
import numpy as np
from spatial_model import HERE,DB,DATA,SpatialDatabaseRod,RIGIDITY,U,M,dump
from search_steering import OUT

def run():
    checks=[]
    for u,m in [(4,2),(6,3),(8,4)]:
        r=SpatialDatabaseRod(u,m,[u,u+m],sub=2)
        rng=np.random.default_rng(90+u);q=rng.normal(size=(r.m,4))*.16;q[:,3]*=.1
        z=q.ravel()*r.scale;T=np.array([[7.,3.,1.,2.],[4.,2.,3.,.5]])
        E,g=r.evaluate(z,T);v=rng.normal(size=r.ndof);v/=np.linalg.norm(v);h=1e-6
        fd=(r.evaluate(z+h*v,T)[0]-r.evaluate(z-h*v,T)[0])/(2*h)
        assert abs(fd-g@v)<2e-6
        mirror=q.copy();mirror[:,[0,2]]*=-1;Em,gm=r.evaluate(mirror.ravel()*r.scale,T[:,[0,3,2,1]])
        gm=gm.reshape(-1,4);gm[:,[0,2]]*=-1
        assert abs(E-Em)<1e-10;np.testing.assert_allclose(g,gm.ravel(),atol=1e-9)
        qa=np.zeros_like(q);common=.1
        force_by_module=4*common*r.routes.sum(axis=0)
        qa[:,3]=-np.repeat(force_by_module/r.planar.module_EA,r.sub)
        ga=r.evaluate(qa.ravel()*r.scale,np.full((r.k,4),common),gravity=0)[1]
        assert r.residual(ga)<1e-9
        checks.append(dict(configuration=r.label,large_rotation_gradient_error=float(abs(fd-g@v)),mirror_energy_error=float(abs(E-Em)),mirror_gradient_error=float(np.max(np.abs(g-gm.ravel()))),axial_analytic_residual=r.residual(ga)))
    torsion=[]
    for sub in [2,4,8]:
        r=SpatialDatabaseRod(4,2,[6],sub=sub)
        for module,coefficient in [(0,RIGIDITY[U,'GJ','not_specified']),(5,RIGIDITY[M,'GJ','not_specified'])]:
            q=np.zeros((r.m,4));q[module*sub:(module+1)*sub,0]=.2/sub
            E=r.evaluate(q.ravel()*r.scale,gravity=0)[0];expected=.5*coefficient*.2**2
            np.testing.assert_allclose(E,expected,atol=1e-10)
            torsion.append(dict(sub=sub,module=module+1,energy_error=float(abs(E-expected))))
    saved=[]
    for u,m in [(4,2),(6,3),(8,4)]:
        rows=json.loads((OUT/f'U{u}_M{m}_maximums.json').read_text());zfile=np.load(OUT/f'U{u}_M{m}_selected_states.npz')
        for row in rows:
            if not row.get('qualifies'):continue
            r=SpatialDatabaseRod(u,m,row['anchors'],sub=row['cells_per_module']);z=zfile[row['state_id']+'_z'];T=zfile[row['state_id']+'_T']
            metric,_,_=r.metrics(z,T)
            assert metric['equilibrium_residual']<2e-6
            assert metric['geometry_pass']
            assert np.max(T)<=250.0001 and np.min(T)>=-1e-7
            if row['strain_mode']=='low_strain':assert metric['max_abs_axial_strain']<=.0500001
            else:assert metric['max_compression']<=.300001 and metric['max_extension']<=.150001
            for key in ['yaw_deg','vertical_projected_deg','world_elevation_deg','max_abs_axial_strain']:
                np.testing.assert_allclose(metric[key],row[key],atol=1e-7)
            saved.append(dict(configuration=r.label,state_id=row['state_id'],residual=metric['equilibrium_residual']))
    source_hash=hashlib.sha256(DB.read_bytes()).hexdigest()
    assert source_hash==DATA['database_sha256']
    result=dict(passed=True,gradient_and_symmetry_checks=checks,torsion_subdivision_checks=torsion,saved_8cell_records_checked=len(saved),
        maximum_saved_equilibrium_residual=max(r['residual'] for r in saved),source_database_unchanged=True,database_sha256=source_hash,
        scope='Saved 8-cell states are audited; separate 16-cell boundary warnings remain in the report')
    dump(OUT/'audit_validation.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':run()
