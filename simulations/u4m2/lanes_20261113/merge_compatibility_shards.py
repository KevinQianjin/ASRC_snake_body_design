"""Merge sharded guide_web_compatibility.py outputs into one coverage summary.

Checks that shards share inputs, cover every record exactly once and completed.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def merge(folder, out):
    shards = sorted(folder.glob('shard_*/summary.json'))
    parts = [json.loads(p.read_text()) for p in shards]
    if not parts:
        raise ValueError('no shards found')
    keys = ('archive_sha256', 'body_sha256', 'guide_sha256', 'sampling', 'land_axial_mm', 'nominal_bond_gap_mm', 'query_margin_mm')
    for p in parts[1:]:
        for k in keys:
            if p[k] != parts[0][k]:
                raise ValueError(f'shard mismatch in {k}')
    counts = sorted(p['shard']['index'] for p in parts)
    if counts != list(range(parts[0]['shard']['count'])) or not all(p['completed'] for p in parts):
        raise ValueError('incomplete shard set')
    rows = [r for p in parts for r in p['rows']]
    labels = [r['state'] for r in rows]
    tags = sorted({r['part'] for r in rows})
    per_state = defaultdict(int)
    for r in rows:
        per_state[r['state']] += 1
    if any(v != len(tags) for v in per_state.values()) or len(per_state) != parts[0]['coverage']['states']:
        raise ValueError('records not covered exactly once per part')
    pen = [r for r in rows if r['minimum_signed_distance_mm'] < 0]
    by_phase = defaultdict(lambda: dict(records=set(), penetrating=set(), min_sd=1e9, max_gamma=0.))
    for r in rows:
        b = by_phase[r['phase']]; b['records'].add(r['state'])
        if r['minimum_signed_distance_mm'] < 0: b['penetrating'].add(r['state'])
        b['min_sd'] = min(b['min_sd'], r['minimum_signed_distance_mm'])
        b['max_gamma'] = max(b['max_gamma'], r['land_implied_shear_strain'])
    worst = min(rows, key=lambda r: r['minimum_signed_distance_mm'])
    result = {k: parts[0][k] for k in ('scope', 'archive', 'archive_sha256', 'coverage', 'body_cad', 'guide_cad', 'body_sha256',
                                      'guide_sha256', 'sampling', 'query_margin_mm', 'land_axial_mm', 'nominal_bond_gap_mm', 'straight',
                                      'payload_g', 'rod_cells_per_module')}
    result.update(
        shards=len(parts), records=len(per_state), unique_geometries=sum(p['unique_geometries'] for p in parts),
        checks=len(rows), penetrating_checks=len(pen), penetrating_records=len({r['state'] for r in pen}),
        minimum_signed_distance_mm=worst['minimum_signed_distance_mm'], worst=worst,
        minimum_reported_value_is_lipschitz_bound=any(r.get('minimum_is_lipschitz_bound') for r in rows if r is worst),
        max_land_axial_relative_displacement_mm=max(r['land_max_axial_relative_displacement_mm'] for r in rows),
        max_land_implied_shear_strain=max(r['land_implied_shear_strain'] for r in rows),
        max_module_curvature_rad_per_mm=max(r['module_max_curvature_rad_per_mm'] for r in rows),
        by_part={t: dict(minimum_signed_distance_mm=min(r['minimum_signed_distance_mm'] for r in rows if r['part'] == t),
                         penetrating_records=sum(r['minimum_signed_distance_mm'] < 0 for r in rows if r['part'] == t),
                         max_land_axial_relative_displacement_mm=max(r['land_max_axial_relative_displacement_mm'] for r in rows if r['part'] == t),
                         max_land_implied_shear_strain=max(r['land_implied_shear_strain'] for r in rows if r['part'] == t)) for t in tags},
        by_phase={k: dict(records=len(v['records']), penetrating_records=len(v['penetrating']),
                          minimum_signed_distance_mm=v['min_sd'], max_land_implied_shear_strain=v['max_gamma'])
                  for k, v in sorted(by_phase.items(), key=lambda kv: str(kv[0]))},
        elapsed_seconds_per_shard=[p['elapsed_seconds'] for p in parts])
    out.write_text(json.dumps(result, indent=1) + '\n')
    (out.parent / (out.stem + '_rows.json')).write_text(json.dumps(sorted(rows, key=lambda r: (int(r['state']) if r['state'].isdigit() else r['state'], r['part'])), indent=0) + '\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    r = merge(a.folder, a.out)
    print(json.dumps({k: r[k] for k in ('records', 'unique_geometries', 'checks', 'penetrating_checks', 'penetrating_records',
                                         'minimum_signed_distance_mm', 'max_land_implied_shear_strain')}, indent=1))
    print(json.dumps(r['by_part'], indent=1)); print(json.dumps(r['by_phase'], indent=1))
