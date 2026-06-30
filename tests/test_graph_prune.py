"""Tests for graph_prune.prune — run: python3 -m unittest discover tests"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_prune import prune


def make_graph():
    """Synthetic dropout graph:
      S1 taken by D1,D2,D3 (3 dropouts); S2 by D1,D2 (2); S3 by D1 (1).
      C1 (continua) took S1. Profs: S1->P1, S2->P2, S3->P2.
    """
    nodes = [
        {"id": "D1", "domain": "desercion"},
        {"id": "D2", "domain": "desercion"},
        {"id": "D3", "domain": "desercion"},
        {"id": "C1", "domain": "continua"},
        {"id": "S1", "domain": "materia"},
        {"id": "S2", "domain": "materia"},
        {"id": "S3", "domain": "materia"},
        {"id": "P1", "domain": "profesor"},
        {"id": "P2", "domain": "profesor"},
    ]
    edges = [
        {"from": "D1", "to": "S1", "type": "CURSO"},
        {"from": "D2", "to": "S1", "type": "CURSO"},
        {"from": "D3", "to": "S1", "type": "CURSO"},
        {"from": "D1", "to": "S2", "type": "CURSO"},
        {"from": "D2", "to": "S2", "type": "CURSO"},
        {"from": "D1", "to": "S3", "type": "CURSO"},
        {"from": "C1", "to": "S1", "type": "CURSO"},
        {"from": "S1", "to": "P1", "type": "IMPARTIDA_POR"},
        {"from": "S2", "to": "P2", "type": "IMPARTIDA_POR"},
        {"from": "S3", "to": "P2", "type": "IMPARTIDA_POR"},
    ]
    return {"nodes": nodes, "edges": edges}


def ids(nodes):
    return set(n["id"] for n in nodes)


def edge_keys(edges):
    return set((e["from"], e["to"], e["type"]) for e in edges)


class TestPrune(unittest.TestCase):
    def test_min_shared_3(self):
        n, e = prune(make_graph(), min_shared=3, include_continua=False)
        self.assertEqual(ids(n), {"D1", "D2", "D3", "S1", "P1"})
        self.assertEqual(edge_keys(e), {
            ("D1", "S1", "CURSO"), ("D2", "S1", "CURSO"),
            ("D3", "S1", "CURSO"), ("S1", "P1", "IMPARTIDA_POR"),
        })

    def test_min_shared_2(self):
        n, e = prune(make_graph(), min_shared=2, include_continua=False)
        self.assertEqual(ids(n), {"D1", "D2", "D3", "S1", "S2", "P1", "P2"})
        self.assertEqual(len(e), 7)

    def test_include_continua(self):
        n, e = prune(make_graph(), min_shared=2, include_continua=True)
        self.assertIn("C1", ids(n))
        self.assertIn(("C1", "S1", "CURSO"), edge_keys(e))

    def test_continua_excluded_by_default(self):
        n, _ = prune(make_graph(), min_shared=2, include_continua=False)
        self.assertNotIn("C1", ids(n))

    def test_edges_only_between_kept_nodes(self):
        n, e = prune(make_graph(), min_shared=3, include_continua=False)
        kept = ids(n)
        for edge in e:
            self.assertIn(edge["from"], kept)
            self.assertIn(edge["to"], kept)


if __name__ == "__main__":
    unittest.main()
