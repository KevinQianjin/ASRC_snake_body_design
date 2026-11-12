"""Run summarize_length_cycle.py on a cycle results folder produced with --source/--startup/--out.

The original summary script hard-codes the 1 N, 10 mm-payout command set. This
wrapper points it at another folder and replaces the startup-specific sentences
in the generated REPORT.md with the command set actually used.
"""
import argparse, json
from pathlib import Path
import length_cycle, summarize_length_cycle as S

ap = argparse.ArgumentParser()
ap.add_argument('folder'); ap.add_argument('--source', required=True); ap.add_argument('--startup', required=True)
ap.add_argument('--pretension', type=float, required=True)
a = ap.parse_args()
out, src, up = Path(a.folder).resolve(), Path(a.source).resolve(), Path(a.startup).resolve()
for mod in (length_cycle, S):
    mod.OUT = out; mod.SOURCE = src
length_cycle.STARTUP = up
S.main()
rep = out / 'REPORT.md'; t = rep.read_text()
P = f'{a.pretension:g}'
subs = {
    '# U4+M2 Multi-Rope Length-Controlled Round-Trip Study':
        f'# U4+M2 Length-Controlled Round Trip: {P} N pretension and stable startup',
    'Rest-length commands for 12 ropes are derived from the existing E40, 20-degree, anchor [4,5,6] reference states at eight cells per module.':
        f'Rest-length commands for 12 ropes are derived from E40, 20-degree, anchor [4,5,6] reference states with a **{P} N minimum on every rope** '
        f'(`{src.name}`) and a **stable startup** (`{up.name}`), at eight cells per module. Model parameters: `model_data/MODEL_DATA.md`.',
    'Paying out the upper ropes by 10 mm is a specified initial condition for this study; failure here does not imply that every straightening procedure fails.':
        f'The startup raises the head from natural sag (all ropes at {P} N) to 20 degrees through held-elevation states.',
    '- Next step: add pretension margin and stability constraints, redesign startup and rope-length commands, then repeat the sensitivity cases. These corrections have not been implemented in this study.':
        f'- This run implements the pretension margin ({P} N floor in the reference poses) and the redesigned startup. Remaining failures in the sensitivity cases are open-loop calibration effects (posture tracking, or rope tension with a longer free rope).',
    '- Initial condition: clamp at s=-750 mm outside the tank; the three upper ropes are paid out 10 mm from baseline. The initial payout transient is not simulated. Straightening reels in from the resulting stationary state, which may be unstable.':
        f'- Initial condition: clamp at s=-750 mm outside the tank, front in natural sag with every rope at {P} N. Startup follows the held-elevation states of `startup_sweep.py` (head raised in 2.5 degree steps to 20 degrees, all ropes >= {P} N, each state stable at 8 cells).',
    "'python length_cycle.py'": "",
}
for old, new in subs.items():
    t = t.replace(old, new)
t = t.replace('python length_cycle.py\npython summarize_length_cycle.py',
              f'python length_cycle.py --source results/{src.name} --startup results/{up.name} --out {out.name}\n'
              f'python summarize_cycle_run.py {out.name} --source results/{src.name} --startup results/{up.name} --pretension {P}')
rep.write_text(t)
print('wrote', rep)
