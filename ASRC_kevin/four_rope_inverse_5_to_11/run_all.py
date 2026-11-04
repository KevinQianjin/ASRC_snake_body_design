"""Reproduce the approved four-rope study and its inspected deliverables."""
import argparse,subprocess,sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    stages=[['-B','-m','unittest','-v','test_rope_planar.py'],
            ['run_rope_sweep.py','--workers',str(a.workers)],
            ['check_opposing_pairs.py','--workers',str(a.workers)],
            ['rescue_level_continuation.py','--workers',str(a.workers)],
            ['merge_pair_search.py'],['audit_saved_results.py','--workers',str(a.workers)],['render_rope_results.py']]
    for stage in stages:
        print('Running',stage[0],flush=True)
        subprocess.run([sys.executable,*stage],cwd=root,check=True)

if __name__=='__main__':main()
