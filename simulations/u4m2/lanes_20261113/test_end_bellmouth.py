"""Tests for the 15 November 2026 evening end-exit bellmouth study."""
import json
import sys
from pathlib import Path
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
CAD = HERE.parents[2] / 'cad' / 'lanes_u4m2'
sys.path.insert(0, str(CAD / 'end_bellmouth_v1'))
import build as bell                     # noqa: E402
from end_bellmouth_study import fillet_path_length   # noqa: E402
from bellmouth_cad_check import build_path, HOLE_R, ROPE_R   # noqa: E402


def test_profile_tangent_to_bore_and_face_radius():
    for wall, th in ((3.9, 29.), (6., 19.), (7., 18.)):
        hb = wall * np.sin(np.radians(th))
        w, _ = bell.profile_radius(np.array([hb, 0.]), wall, th)
        assert abs(w[0] - HOLE_R) < 1e-12
        assert abs(w[1] - (HOLE_R + wall * (1 - np.cos(np.radians(th))))) < 1e-12
        eps = 1e-6; slope = (bell.profile_radius(hb - eps, wall, th)[0] - HOLE_R) / eps
        assert abs(slope) < 1e-3                       # tangent to the bore
        s0 = (bell.profile_radius(eps, wall, th)[0] - bell.profile_radius(0., wall, th)[0]) / eps
        assert abs(-s0 - np.tan(np.radians(th))) < 1e-4    # face angle equals design wrap


def test_cutter_is_volume():
    c = bell.cutter(3.9, 29.)
    assert c.is_volume and c.volume > 0


def test_straight_rope_length_unchanged():
    L, ax, lat = fillet_path_length(0., 6., 7.)
    assert abs(L - 7.) < 1e-12 and abs(ax - 7.) < 1e-12 and lat == 0.


def test_rope_arc_concentric_with_fillet():
    wall, th_d, theta = 3.9, 29., np.radians(25.)
    n = np.array([1., 0., 0.]); lane = (24., 0.)
    P = build_path('distal', lane, n, theta, wall, th_d)
    hb = wall * np.sin(np.radians(th_d))
    centre = np.array([lane[0] + HOLE_R + wall, 0., 41. + hb])
    # every arc sample lies exactly rope radius + wall radius from the fillet centre circle
    d = np.hypot(P[:, 0] - centre[0], P[:, 2] - centre[2])
    on_arc = (P[:, 2] < 41. + hb - 1e-9) & (P[:, 2] > 41. + hb - (wall + ROPE_R) * np.sin(theta) + 1e-9)
    assert on_arc.any()
    assert np.allclose(d[on_arc], wall + ROPE_R, atol=1e-9)


def test_published_bodies_match_check_file():
    chk = json.loads((CAD / 'end_bellmouth_v1' / 'geometry_check.json').read_text())
    assert chk['all_watertight_single_component'] and chk['minimum_bridge_target_met']
    import hashlib
    for name, part in chk['parts'].items():
        assert hashlib.sha256((CAD / 'end_bellmouth_v1' / name).read_bytes()).hexdigest() == part['sha256']
        m = trimesh.load_mesh(CAD / 'end_bellmouth_v1' / name, force='mesh')
        assert m.is_watertight and len(m.split(only_watertight=False)) == 1
