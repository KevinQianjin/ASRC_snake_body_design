"""Export a saved final equilibrium to inspectable centreline coordinates."""
import argparse,csv
from pathlib import Path
import numpy as np
from rope_planar import HERE
from render_rope_results import read_rows,state_for

def main():
    p=argparse.ArgumentParser()
    p.add_argument('combination')
    p.add_argument('target',choices=['head_level','front_semicircle_up','front_semicircle_down'])
    p.add_argument('--output-dir',type=Path,default=HERE/'results')
    a=p.parse_args()
    rows=read_rows(a.output_dir/'all_targets.csv')
    row=next((r for r in rows if r['combination']==a.combination and r['target']==a.target),None)
    if row is None:raise SystemExit('Unknown combination / target')
    rod,data=state_for(row,a.output_dir)
    if data is None:raise SystemExit('No equilibrium was saved for this target; see the failure record.')
    path=a.output_dir/'coordinates';path.mkdir(exist_ok=True)
    filename=path/f'{a.combination}_{a.target}.csv'
    with filename.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['node','reference_s_mm','x_mm','y_mm','z_mm','pitch_deg','is_actual_disk','target_reached'])
        for i,(xy,th) in enumerate(zip(data['points'],data['theta'])):
            w.writerow([i,i*rod.l*1000,xy[0]*1000,xy[1]*1000,0,np.degrees(th),i%rod.sub==0,row['target_reached']])
    print(filename)

if __name__=='__main__':main()
