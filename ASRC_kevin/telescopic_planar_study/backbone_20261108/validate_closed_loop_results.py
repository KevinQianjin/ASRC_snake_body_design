"""Check exported feedback data against command bounds and equilibrium contracts."""
import csv,hashlib,json,subprocess
import numpy as np
from closed_loop_cycle import OUT,HERE,CASES,adapt_scale,correction

def main():
    checked=[]
    references=np.load(OUT/'nominal_gains.npz')
    for case in CASES:
        rows=json.loads((OUT/f'{case}.json').read_text());trace=json.loads((OUT/f'{case}_feedback.json').read_text())
        summary=json.loads((OUT/f'{case}_summary.json').read_text());data=np.load(OUT/f'{case}_states.npz')
        assert summary['completed']
        assert len(rows)==1069==len(data['closed'])==len(data['open'])==len(data['rest'])
        assert len(list(csv.DictReader((OUT/f'{case}.csv').open())))==len(rows)
        for mode in ['open','closed']:
            assert sum(not q[mode]['checks_pass'] for q in rows)==summary[mode]['failed_samples']
            for q in rows:
                m=q[mode]
                assert m['residual']<2e-6
                assert all(np.isfinite(v) for v in m.values() if isinstance(v,(float,int)))
        assert all(np.all(np.isfinite(data[k])) for k in ['closed','open','points','open_points','rest'])
        assert np.all(data['rest']>0)
        expected=references['R']+CASES[case][3]-1+np.asarray([q['offset_mm'] for q in rows]).reshape(-1,3,4)/1000
        np.testing.assert_allclose(data['rest'],expected,rtol=0,atol=1e-12)
        assert max(np.max(np.abs(q['offset_mm'])) for q in rows)<=5.000001
        scale=1.;previous=None;last_index=None
        for q in trace:
            if q['index']!=last_index:previous=None
            norm=max(abs(q['yaw_error_deg']),abs(q['elevation_error_deg']))
            scale=adapt_scale(previous,norm,scale)
            assert abs(scale-q['next_correction_scale'])<1e-12
            previous=norm;last_index=q['index']
        for a,b in zip(trace,trace[1:]):
            if a['index']==b['index']:
                actual=np.array(b['offset_mm'])-a['offset_mm']
                assert np.max(abs(actual))<=.250001
                expected,_=correction(references['B'][a['index']],np.array([a['yaw_error_deg'],a['elevation_error_deg']]),np.array(a['tensions_n']),np.array(a['offset_mm']))
                np.testing.assert_allclose(actual,expected*a['next_correction_scale'],rtol=0,atol=2e-6)
        assert all(q['residual']<2e-6 for q in trace)
        assert all(np.all(np.isfinite(q['tensions_n'])) for q in trace)
        assert sum(not q['checks_pass'] for q in trace)==summary['feedback_trace']['failed_samples']
        checked.append(dict(case=case,samples=len(rows),trace_samples=len(trace),passed=True,
                            total_qp_failures=sum(q['qp_failures'] for q in rows),
                            maximum_feedback_iterations=max(q['iterations'] for q in rows),
                            samples_above_controller_angle_target=sum(max(abs(q['closed']['yaw_error_deg']),abs(q['closed']['elevation_error_deg']))>.2 for q in rows),
                            max_settled_node_step_mm=float(np.linalg.norm(np.diff(data['points'],axis=0),axis=2).max())))
    result=dict(result='pass',checks=checked,git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip(),
                code_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['closed_loop_cycle.py','render_closed_loop.py','test_closed_loop.py','validate_closed_loop_results.py']},
                note='Data consistency and numerical contracts only; not a physical or continuous-motion validation.')
    (OUT/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
