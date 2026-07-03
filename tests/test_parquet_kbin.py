"""Tests for the .kbin binary format (pure struct — no duckdb needed).
Run: python3 -m unittest discover tests

Requires numpy only for the spiral_layout test; skips gracefully without it.
"""
import io
import json
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


def write_mini_kbin(buf, nodes, edges, domains, edge_types):
    """Reference writer for a tiny graph, mirroring parquet_to_kbin layout."""
    n, e = len(nodes), len(edges)
    meta = {"domains": domains, "domainColors": {},
            "edgeTypes": edge_types, "edgeTypeCounts": {}, "source": {}}
    meta_b = json.dumps(meta).encode("utf-8")
    pad4 = lambda b: b + b"\x00" * (-len(b) % 4)
    buf.write(b"KBN1")
    buf.write(struct.pack("<III", n, e, len(meta_b)))
    buf.write(pad4(meta_b))
    for nd in nodes:
        buf.write(struct.pack("<fff", *nd["pos"]))
    buf.write(pad4(b"".join(struct.pack("<B", nd["dom"]) for nd in nodes)))
    blob = b""
    offsets = [0]
    for nd in nodes:
        blob += nd["id"].encode("utf-8")
        offsets.append(len(blob))
    buf.write(struct.pack(f"<{n+1}I", *offsets))
    buf.write(struct.pack("<I", len(blob)))
    buf.write(pad4(blob))
    for s, _, _ in edges:
        buf.write(struct.pack("<I", s))
    for _, d, _ in edges:
        buf.write(struct.pack("<I", d))
    buf.write(pad4(b"".join(struct.pack("<B", t) for _, _, t in edges)))


def read_kbin(data):
    """Reference reader replicating the browser's parsing logic."""
    assert data[:4] == b"KBN1"
    n, e, meta_len = struct.unpack_from("<III", data, 4)
    pad4 = lambda x: (x + 3) & ~3
    off = 16
    meta = json.loads(data[off:off + meta_len])
    off += pad4(meta_len)
    pos = struct.unpack_from(f"<{3*n}f", data, off); off += 12 * n
    dom = struct.unpack_from(f"<{n}B", data, off); off += pad4(n)
    id_off = struct.unpack_from(f"<{n+1}I", data, off); off += 4 * (n + 1)
    (blob_len,) = struct.unpack_from("<I", data, off); off += 4
    blob = data[off:off + blob_len]; off += pad4(blob_len)
    src = struct.unpack_from(f"<{e}I", data, off); off += 4 * e
    dst = struct.unpack_from(f"<{e}I", data, off); off += 4 * e
    typ = struct.unpack_from(f"<{e}B", data, off); off += pad4(e)
    assert off == len(data), f"trailing bytes: {len(data) - off}"
    ids = [blob[id_off[i]:id_off[i + 1]].decode("utf-8") for i in range(n)]
    return {"meta": meta, "pos": pos, "dom": dom, "ids": ids,
            "src": src, "dst": dst, "typ": typ}


class TestKbinRoundtrip(unittest.TestCase):
    def test_roundtrip(self):
        nodes = [
            {"id": "Person::abc", "dom": 1, "pos": (1.5, -2.0, 3.25)},
            {"id": "Tesela::t1", "dom": 0, "pos": (0.0, 0.5, -1.0)},
            {"id": "Person::ñandú", "dom": 1, "pos": (9.0, 9.0, 9.0)},  # UTF-8 multibyte
        ]
        edges = [(0, 1, 0), (2, 1, 1)]
        buf = io.BytesIO()
        write_mini_kbin(buf, nodes, edges, ["Tesela", "Person"], ["IN_TESELA", "LIVES_IN"])
        out = read_kbin(buf.getvalue())
        self.assertEqual(out["ids"], ["Person::abc", "Tesela::t1", "Person::ñandú"])
        self.assertEqual(out["dom"], (1, 0, 1))
        self.assertEqual(out["src"], (0, 2))
        self.assertEqual(out["dst"], (1, 1))
        self.assertEqual(out["typ"], (0, 1))
        self.assertAlmostEqual(out["pos"][0], 1.5)
        self.assertAlmostEqual(out["pos"][5], -1.0)
        self.assertEqual(out["meta"]["domains"], ["Tesela", "Person"])


@unittest.skipIf(np is None, "numpy not installed")
class TestSpiralLayout(unittest.TestCase):
    def test_shapes_and_determinism(self):
        from parquet_to_kbin import spiral_layout
        n = 500
        rng = np.random.default_rng(7)
        deg = rng.integers(1, 40, n).astype(np.float64)
        dom = rng.integers(0, 3, n).astype(np.int64)
        a = spiral_layout(np, n, deg, dom, 3)
        b = spiral_layout(np, n, deg, dom, 3)
        self.assertEqual(a.shape, (n, 3))
        self.assertTrue(np.isfinite(a).all())
        self.assertTrue((a == b).all())  # deterministic

    def test_hubs_near_center(self):
        from parquet_to_kbin import spiral_layout
        n = 400
        deg = np.ones(n, dtype=np.float64)
        deg[:5] = 500.0  # hubs
        dom = np.zeros(n, dtype=np.int64)
        pos = spiral_layout(np, n, deg, dom, 1)
        r = np.linalg.norm(pos, axis=1)
        self.assertLess(r[:5].mean(), r[5:].mean() * 0.5)


if __name__ == "__main__":
    unittest.main()
