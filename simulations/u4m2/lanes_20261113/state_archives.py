"""Strict readers for inverse, reference, settled and motion-trace state archives.

Never silently skip an unsupported archive or misalign states with force records.
Units: scaled rod state, tendon tension N, optional rest length m.
"""
import json
import hashlib
from pathlib import Path
import numpy as np

NAMES = [f'a{a}_{ray}' for a in (4, 5, 6) for ray in ('up', 'right', 'down', 'left')]


def load_states(path, ndof=192):
    path = Path(path)
    unsolved_records = 0
    with np.load(path, allow_pickle=False) as data:
        inverse = [k for k in data.files if k.endswith('_z8')]
        if inverse:
            inverse.sort(key=lambda k: (k[0], float(k[1:-3])))
            states = [(k, data[k].copy(), data[k[:-3] + '_T8'].copy(), {}) for k in inverse]
            kind = 'inverse'
        else:
            key = 'closed' if 'closed' in data.files else 'z' if 'z' in data.files else None
            if key is None:
                raise ValueError(f'{path}: unsupported state keys {data.files}')
            Z = np.asarray(data[key])
            if Z.ndim != 2:
                raise ValueError(f'{path}: expected a 2-D state matrix')
            companion = path.with_name(path.name.removesuffix('_states.npz') + '.json')
            rows = json.loads(companion.read_text()) if companion.exists() else None
            if rows is not None:
                total_records = len(rows)
                rows = [r for r in rows if r.get('status', 'solved') == 'solved']
                unsolved_records = total_records - len(rows)
                if len(rows) != len(Z):
                    raise ValueError(f'{path}: {len(Z)} states but {len(rows)} solved records')
            if 'tensions_n' in data.files:
                tensions = np.asarray(data['tensions_n'])
                if len(tensions) != len(Z):
                    raise ValueError(f'{path}: tension count mismatch')
            elif rows is not None:
                tensions = []
                for row in rows:
                    metrics = row.get('closed', row)
                    T = metrics.get('tensions_n')
                    if T is None:
                        T = [metrics[n + '_tension_n'] for n in NAMES]
                    tensions.append(T)
            else:
                raise ValueError(f'{path}: no tension array or companion force records')
            states = [(str(i), z.copy(), np.asarray(T).copy(), {} if rows is None else rows[i])
                      for i, (z, T) in enumerate(zip(Z, tensions))]
            kind = 'closed' if key == 'closed' else 'trace' if '_trace_' in path.name else 'reference'
    if not states:
        raise ValueError(f'{path}: no states')
    checked = []
    for label, z, T, meta in states:
        if z.shape != (ndof,) or T.size != 12 or not np.isfinite(z).all() or not np.isfinite(T).all():
            raise ValueError(f'{path}:{label}: invalid state/tension shape or nonfinite values')
        T = T.reshape(3, 4)
        if (T < 0).any():
            raise ValueError(f'{path}:{label}: negative tendon tension')
        checked.append((label, z, T, meta))
    return checked, {'path': str(path), 'format': kind, 'states': len(checked),
                     'unsolved_records_without_states': unsolved_records,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
