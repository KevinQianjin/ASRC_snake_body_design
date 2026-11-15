"""Consolidate matching contact checkpoints without losing failed/incomplete runs.

The first checkpoint defines required coverage. Duplicate cached rows are only
accepted when their measurements are exactly identical. Source files are kept.
"""
import argparse
import hashlib
import json
from pathlib import Path


def merge(inputs, out):
    data = [json.loads(p.read_text()) for p in inputs]
    result = dict(data[0])
    fields = ('archive_sha256', 'guide_design', 'cad_sha256', 'guide_cad_sha256',
              'requested_axial_resolutions_mm', 'selected_parts',
              'rod_cells_per_module', 'payload_g', 'boolean_transfer_precision',
              'body_scope')
    expected = [(h, state, part)
                for h in result['requested_axial_resolutions_mm']
                for state in result['selected_states']
                for part in result['selected_parts']]
    if len(expected) != len(set(expected)):
        raise ValueError('Primary checkpoint has duplicate requested coverage')
    rows = {}
    duplicates = 0
    for checkpoint in data:
        if any(checkpoint[k] != result[k] for k in fields):
            raise ValueError('Checkpoint inputs or numerical methods differ')
        for row in checkpoint['rows']:
            key = (row['resolution_mm'], row['state'], row['part'])
            if key not in expected:
                raise ValueError('Checkpoint contains unrequested coverage')
            normalized = {k:v for k,v in row.items() if k != 'reused_geometry_from_state'}
            if key in rows:
                previous = {k:v for k,v in rows[key].items() if k != 'reused_geometry_from_state'}
                if previous != normalized:
                    raise ValueError('Duplicate checkpoint measurements disagree')
                duplicates += 1
            else:
                rows[key] = row
    if set(rows) != set(expected):
        raise ValueError('Combined checkpoints do not cover all requested checks')
    result['rows'] = [rows[key] for key in expected]
    result['completed'] = True
    result['all_selected_poses_clear'] = all(r['pass_interference'] for r in result['rows'])
    result.pop('stop_reason', None)
    result.pop('exit_code', None)
    result['elapsed_seconds'] = sum(d['elapsed_seconds'] for d in data)
    result['checkpoint_recovery'] = dict(
        note='Complete coverage reconstructed from preserved checkpoints; elapsed_seconds sums recorded segment compute times, not total wall time.',
        identical_cached_duplicate_rows_omitted=duplicates,
        segments=[dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                       completed=d['completed'], rows=len(d['rows']),
                       stop_reason=d.get('stop_reason')) for p,d in zip(inputs,data)])
    out.mkdir(parents=True, exist_ok=True)
    (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = merge(args.inputs, args.out)
    print(f"Validated {len(result['rows'])} unique part checks")
