"""Merge independent search branches into a derived final result set."""
import argparse,csv,json
from pathlib import Path
import numpy as np
from rope_planar import HERE
from run_rope_sweep import BASE_FIELDS,write_json,jsonable
from rescue_level_continuation import load_group

def prefer(new,old):
    if new['target_reached'] and not old['target_reached']:return True
    if old['target_reached'] and not new['target_reached']:return False
    if new['target_reached']:
        n=bool(new['stable_in_plane'] and new['passes_self_envelope_screen'])
        o=bool(old['stable_in_plane'] and old['passes_self_envelope_screen'])
        if n!=o:return n
        return new['target_total_tension_n']<old['target_total_tension_n']-1e-7
    if new['target']!='head_level':
        if old['semicircle_max_error_mm'] is None:return True
        return new['semicircle_max_error_mm']<old['semicircle_max_error_mm']-1e-5
    return False

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=HERE/'results');a=p.parse_args();out=a.output_dir
    assert (out/'group_summary.json').exists() and (out/'opposing_pair_summary.json').exists()
    derived=out/'final_groups';derived.mkdir(exist_ok=True)
    allrows=[];adopted=[];fields=BASE_FIELDS+['top_bottom_pair_common_n','source_stage']
    for source in sorted((out/'groups').glob('*.json')):
        meta=json.loads(source.read_text());front,rear=meta['summary']['front'],meta['summary']['rear'];stem=source.stem
        rows,states,tensions=load_group(out,front,rear)
        for r in rows:r['top_bottom_pair_common_n']=0.;r['source_stage']='primary_or_neighbour_continuation'
        trialfile=out/'opposing_pair_trials'/(stem+'.json')
        trial=json.loads(trialfile.read_text());updates=trial['updates']
        if updates:
            z=np.load(trialfile.with_name(stem+'_updates.npz'))
            for j,update in enumerate(updates):
                i=update['primary_row_index'];assert update['combination']==rows[i]['combination'] and update['target']==rows[i]['target']
                if prefer(update,rows[i]):
                    r={k:v for k,v in update.items() if k!='primary_row_index'};r['source_stage']='opposing_pair_supplement'
                    rows[i]=r;states[i]=z['state'][j];tensions[i]=z['tensions'][j]
                    adopted.append(dict(group=stem,index=i,combination=r['combination'],target=r['target']))
        with (derived/(stem+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for r in rows:w.writerow({k:json.dumps(v,default=jsonable) if isinstance(v,list) else v for k,v in r.items()})
        np.savez_compressed(derived/(stem+'_states.npz'),state=states,tensions=tensions)
        allrows.extend(rows)
    assert len(allrows)==30510
    with (out/'all_targets.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in allrows:w.writerow({k:json.dumps(v,default=jsonable) if isinstance(v,list) else v for k,v in r.items()})
    write_json(out/'final_merge_audit.json',dict(rows=len(allrows),unique_configurations=len({r['combination'] for r in allrows}),
                   adopted_opposing_pair_updates=len(adopted),adopted=adopted))
    print(json.dumps(dict(rows=len(allrows),adopted=len(adopted))),flush=True)

if __name__=='__main__':main()
