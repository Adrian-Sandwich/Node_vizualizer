"""Tests for graph_layout (sphere algorithm only — no igraph dependency).
Run: python3 -m unittest discover tests
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_layout import fibonacci_sphere, layout_sphere, normalize


def nodes_for(domains):
    return [{"id": f"N{i}", "domain": d} for i, d in enumerate(domains)]


class TestFibonacciSphere(unittest.TestCase):
    def test_count_and_radius(self):
        pts = fibonacci_sphere(100, 10.0)
        self.assertEqual(len(pts), 100)
        for x, y, z in pts:
            self.assertAlmostEqual(math.sqrt(x * x + y * y + z * z), 10.0, places=6)

    def test_deterministic(self):
        self.assertEqual(fibonacci_sphere(50, 5.0), fibonacci_sphere(50, 5.0))


class TestLayoutSphere(unittest.TestCase):
    def test_all_nodes_get_coords(self):
        nodes = nodes_for(["a"] * 10 + ["b"] * 5 + [None] * 3)
        coords = layout_sphere(nodes, [], 1400.0)
        self.assertEqual(len(coords), len(nodes))
        self.assertTrue(all(c is not None for c in coords))

    def test_domains_separated(self):
        # centroid of each domain group should differ
        nodes = nodes_for(["a"] * 20 + ["b"] * 20)
        coords = layout_sphere(nodes, [], 1400.0)
        ca = [sum(coords[i][k] for i in range(20)) / 20 for k in range(3)]
        cb = [sum(coords[i][k] for i in range(20, 40)) / 20 for k in range(3)]
        d = math.dist(ca, cb)
        self.assertGreater(d, 100.0)

    def test_deterministic(self):
        nodes = nodes_for(["a", "b", "a", "c", "b"])
        self.assertEqual(layout_sphere(nodes, [], 1400.0),
                         layout_sphere(nodes_for(["a", "b", "a", "c", "b"]), [], 1400.0))


class TestNormalize(unittest.TestCase):
    def test_centered_and_scaled(self):
        coords = [(i + 5.0, 2.0 * i, -i) for i in range(100)]
        out = normalize(coords, 1400.0)
        n = len(out)
        for k in range(3):
            self.assertAlmostEqual(sum(c[k] for c in out) / n, 0.0, places=6)
        dists = sorted(math.sqrt(x * x + y * y + z * z) for x, y, z in out)
        self.assertAlmostEqual(dists[min(int(n * 0.95), n - 1)], 1400.0, places=4)


if __name__ == "__main__":
    unittest.main()
