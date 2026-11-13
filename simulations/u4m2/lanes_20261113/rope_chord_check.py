"""How far each rope chord leaves its lane inside a module (ropes are guided only at the end disks).
Usage: python rope_chord_check.py STATES.npz [...]; prints max bend angle per module and the largest
radial-outward, radial-inward and tangential offset (mm) of the straight rope from its lane position."""
import os; os.environ['OPENBLAS_NUM_THREADS']='1'
import sys, json
import numpy as np, lanes
lanes.install()
import backbone
r=backbone.spatial_rod(4,2,[4,5,6],20,8,'niti18_E40')
names=['U1','U2','U3','U4','M5','M6']
out={n:dict(bend=0,rad_out=0,rad_in=0,tang=0) for n in names}
def scan(f):
    d=np.load(f)
    for k in [k for k in d if k.endswith('_z8')]:
        
        _,_,det=r.evaluate(d[k],d[k.replace('_z8','_T8')],detail=True); p,F=det['points'],det['frames']
        for j in range(6):
            i0,i1=j*8,j*8+8; o=out[names[j]]
            o['bend']=max(o['bend'],float(np.degrees(np.arccos(np.clip((np.trace(F[i0].T@F[i1])-1)/2,-1,1)))))
            for s in range(3):
                if r.routes[s,j]==0: continue
                for rope in range(4):
                    off=r.offsets3[s,rope]; a=p[i0]+F[i0]@off; b=p[i1]+F[i1]@off
                    rad=off/np.linalg.norm(off); tan=np.cross([1,0,0],rad)
                    for i in range(i0+1,i1):
                        n=F[i][:,0]; t=np.dot(p[i]-a,n)/np.dot(b-a,n); q=a+t*(b-a)
                        loc=F[i].T@(q-p[i]) - off
                        o['rad_out']=max(o['rad_out'],1000*np.dot(loc,rad)); o['rad_in']=max(o['rad_in'],-1000*np.dot(loc,rad)); o['tang']=max(o['tang'],1000*abs(np.dot(loc,tan)))
    return d

for f in sys.argv[1:]: scan(f)
for n,o in out.items(): print(n,{k:round(v,2) for k,v in o.items()})
json.dump(out, open(sys.argv[-1].replace('.npz', '_rope_chords.json'), 'w'), indent=1)
