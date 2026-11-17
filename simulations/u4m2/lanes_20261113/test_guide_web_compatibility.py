"""Unit checks for the point-sampled guide/body compatibility screen."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import trimesh
from guide_web_compatibility import SignedDistance
from merge_compatibility_shards import merge


class SignedDistanceTest(unittest.TestCase):
    def setUp(self):
        self.box = trimesh.creation.box(extents=(2., 2., 2.))
        self.sdf = SignedDistance([self.box])

    def test_sign_and_value(self):
        d = self.sdf(np.array([[0., 0., 0.], [0., 0., 1.5], [0.9, 0., 0.]]))
        np.testing.assert_allclose(d, [-1., .5, -.1], atol=1e-9)

    def test_minimum_over_components(self):
        other = trimesh.creation.box(extents=(2., 2., 2.)); other.apply_translation([5., 0., 0.])
        sdf = SignedDistance([trimesh.util.concatenate([self.box, other])])
        np.testing.assert_allclose(sdf(np.array([[5., 0., 0.], [2.5, 0., 0.]])), [-1., 1.5], atol=1e-9)

    def test_lipschitz_lower_bound(self):
        rng = np.random.default_rng(3)
        x = rng.uniform(-3, 3, (500, 3)); u = rng.normal(0, .2, (500, 3))
        lower = self.sdf(x) - np.linalg.norm(u, axis=1)
        self.assertTrue(np.all(self.sdf(x + u) >= lower - 1e-9))


class MergeTest(unittest.TestCase):
    def test_rejects_incomplete_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'run'; (folder / 'shard_0').mkdir(parents=True)
            common = dict(archive_sha256='a', body_sha256={}, guide_sha256={}, sampling={}, land_axial_mm=.5,
                          nominal_bond_gap_mm=.15, query_margin_mm=.03, completed=True, shard=dict(index=0, count=2),
                          rows=[], unique_geometries=0)
            (folder / 'shard_0' / 'summary.json').write_text(json.dumps(common))
            with self.assertRaises(ValueError):
                merge(folder, Path(tmp) / 'out.json')


if __name__ == '__main__':
    unittest.main()
