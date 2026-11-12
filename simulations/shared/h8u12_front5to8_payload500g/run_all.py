"""Reproduce the H8/U12, rear-only backbone, front5–8 and500g study."""
import argparse,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    root=Path(__file__).resolve().parent
    for stage in [['-B','-m','unittest','-v','test_payload_models.py'],['run_vertical.py','--workers',str(a.workers)],['run_directional.py','--workers',str(a.workers)],['audit_and_render.py','--workers',str(a.workers)]]:
        subprocess.run([sys.executable,*stage],cwd=root,check=True)

if __name__=='__main__':main()
