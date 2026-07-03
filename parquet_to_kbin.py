#!/usr/bin/env python3
"""
Export a (src, dst, type) edge parquet to the viewer's binary .kbin format —
no JSON, no per-node objects in the browser, no V8 string limit. Handles the
FULL graph (tested: 1.19M nodes / 21.3M edges → ~250MB).

.kbin layout (little-endian):
  magic  'KBN1'
  u32    nodeCount
  u32    edgeCount
  u32    metaLen
  bytes  meta JSON  {domains:[...], domainColors:{...}, edgeTypes:[...],
                     edgeTypeCounts:{...}, source:{...}}
  f32    positions  ×3N   (spiral-galaxy layout baked here, numpy O(N+E))
  u8     domainIdx  ×N    (index into meta.domains)
  u32    idOffsets  ×N+1  (into the UTF-8 id blob)
  u32    idBlobLen
  bytes  id blob UTF-8    (decoded lazily in the browser for tooltips/panel)
  u32    edgeSrc    ×E    (node indices; edges sorted by 3D length ascending
  u32    edgeDst    ×E     so drawRange density cuts drop long edges first)
  u8     edgeType   ×E    (index into meta.edgeTypes)

Example:
  .venv/bin/python parquet_to_kbin.py ~/Desktop/oax_sample_edges.parquet \
      graphs/oax_full.kbin
"""

import argparse
import json
import math
import struct
import sys
from datetime import datetime

MAGIC = b"KBN1"
# pairwise-proximity spam that buries semantic structure (same default as
# parquet_to_kgraph.py)
DEFAULT_EXCLUDE = "NEARBY,ON_BLOCK_FRONT,ON_ROAD"

PALETTE = ['#66d9ff', '#7b8cff', '#b07bff', '#ff7bd5', '#ffd166', '#06d6a0',
           '#ef476f', '#a5f3ff', '#f4a261', '#94d2bd', '#e9c46a', '#8ecae6',
           '#c77dff', '#80ffdb', '#ffadad', '#bdb2ff']


def spiral_layout(np, n, deg, dom_idx, n_domains, radius=1400.0):
    """Vectorized twin of graph_layout.layout_spiral (numpy, O(N))."""
    ARMS = 4
    SWIRL = 2.4 * math.pi
    rng = np.random.default_rng(1234567)  # deterministic

    log_max = math.log1p(float(deg.max() if n else 1) or 1.0)
    t_log = 1.0 - np.log1p(deg) / log_max
    rank = np.empty(n, dtype=np.float64)
    rank[np.argsort(-deg, kind="stable")] = (np.arange(n) + 0.5) / n
    t = 0.6 * t_log + 0.4 * rank
    r_norm = np.clip(t ** 1.25 + rng.normal(0, 0.05, n), 0.02, 1.0)
    rr = radius * (0.05 + 0.95 * r_norm)

    # arm per node: small domains sprinkle across all arms
    counts = np.bincount(dom_idx, minlength=n_domains)
    arm_share = max(n / ARMS, 1)
    spread = np.where(counts < arm_share * 0.6, ARMS,
                      np.clip(np.ceil(counts / arm_share), 1, ARMS)).astype(np.int64)
    base = np.arange(n_domains, dtype=np.int64) % ARMS
    arm = (base[dom_idx] + (rng.random(n) * spread[dom_idx]).astype(np.int64)) % ARMS

    theta = (arm * (2 * math.pi / ARMS)
             + (rr / radius) * SWIRL
             + rng.normal(0, 1, n) * (0.18 + 0.5 * (1 - rr / radius)))
    thick = radius * (0.15 * (1 - rr / radius) ** 1.6 + 0.02)
    pos = np.empty((n, 3), dtype=np.float32)
    pos[:, 0] = rr * np.cos(theta)
    pos[:, 1] = rng.normal(0, 1, n) * thick
    pos[:, 2] = rr * np.sin(theta)
    return pos


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parquet")
    ap.add_argument("output")
    ap.add_argument("--exclude-types", default=DEFAULT_EXCLUDE)
    ap.add_argument("--max-edges", type=int, default=0,
                    help="0 = keep ALL remaining edges (default)")
    args = ap.parse_args()

    import duckdb
    import numpy as np
    con = duckdb.connect()
    P = args.parquet
    excl = [t.strip() for t in args.exclude_types.split(",") if t.strip()]
    excl_sql = ",".join(f"'{t}'" for t in excl) or "''"

    print("[kbin] leyendo aristas…", file=sys.stderr)
    cols = con.execute(f"""
        SELECT src, dst, type FROM '{P}' WHERE type NOT IN ({excl_sql})
    """).fetchnumpy()
    src, dst, typ = cols["src"], cols["dst"], cols["type"]
    e = len(src)
    print(f"[kbin] {e:,} aristas tras filtro", file=sys.stderr)

    print("[kbin] indexando nodos…", file=sys.stderr)
    all_ids = np.concatenate([src, dst])
    node_ids, inverse = np.unique(all_ids, return_inverse=True)
    n = len(node_ids)
    e_src = inverse[:e].astype(np.uint32)
    e_dst = inverse[e:].astype(np.uint32)
    del all_ids, inverse

    # domains from id prefix
    prefixes = np.array([i.split("::", 1)[0] for i in node_ids])
    domains, dom_idx = np.unique(prefixes, return_inverse=True)
    if len(domains) > 255:
        raise SystemExit(f"[kbin] {len(domains)} dominios > 255 (u8)")
    dom_idx = dom_idx.astype(np.uint8)
    del prefixes

    # edge types
    types, typ_idx = np.unique(typ, return_inverse=True)
    if len(types) > 255:
        raise SystemExit(f"[kbin] {len(types)} tipos de arista > 255 (u8)")
    typ_idx = typ_idx.astype(np.uint8)
    type_counts = {t: int(c) for t, c in
                   zip(types.tolist(), np.bincount(typ_idx).tolist())}
    del typ

    print("[kbin] grados + layout espiral…", file=sys.stderr)
    deg = (np.bincount(e_src, minlength=n).astype(np.float64)
           + np.bincount(e_dst, minlength=n))
    pos = spiral_layout(np, n, deg, dom_idx.astype(np.int64), len(domains))

    print("[kbin] ordenando aristas por longitud…", file=sys.stderr)
    d = pos[e_src].astype(np.float64) - pos[e_dst].astype(np.float64)
    length2 = np.einsum("ij,ij->i", d, d)
    del d
    order = np.argsort(length2, kind="stable")
    del length2
    e_src, e_dst, typ_idx = e_src[order], e_dst[order], typ_idx[order]
    del order
    if args.max_edges and e > args.max_edges:
        e_src, e_dst, typ_idx = (e_src[:args.max_edges], e_dst[:args.max_edges],
                                 typ_idx[:args.max_edges])
        print(f"[kbin] cap: {e:,} → {args.max_edges:,}", file=sys.stderr)
        e = args.max_edges

    print("[kbin] blob de ids…", file=sys.stderr)
    encoded = [i.encode("utf-8") for i in node_ids.tolist()]
    offsets = np.zeros(n + 1, dtype=np.uint32)
    np.cumsum([len(b) for b in encoded], out=offsets[1:])
    blob = b"".join(encoded)
    del encoded

    meta = {
        "domains": domains.tolist(),
        "domainColors": {d: PALETTE[i % len(PALETTE)] for i, d in enumerate(domains.tolist())},
        "edgeTypes": types.tolist(),
        "edgeTypeCounts": type_counts,
        "source": {"parquet": P.split("/")[-1], "excludedTypes": excl,
                   "createdAt": datetime.now().isoformat() + "Z"},
    }
    meta_b = json.dumps(meta, ensure_ascii=False).encode("utf-8")

    def pad4(b):
        return b + b"\x00" * (-len(b) % 4)

    print("[kbin] escribiendo…", file=sys.stderr)
    # every variable-length / u8 section is padded to 4 bytes so the browser
    # can create aligned Float32Array/Uint32Array views directly on the buffer
    with open(args.output, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<III", n, e, len(meta_b)))
        f.write(pad4(meta_b))
        f.write(pos.astype("<f4").tobytes(order="C"))
        f.write(pad4(dom_idx.tobytes()))
        f.write(offsets.astype("<u4").tobytes())
        f.write(struct.pack("<I", len(blob)))
        f.write(pad4(blob))
        f.write(e_src.astype("<u4").tobytes())
        f.write(e_dst.astype("<u4").tobytes())
        f.write(pad4(typ_idx.tobytes()))

    import os
    mb = os.path.getsize(args.output) / 1e6
    print(f"[kbin] {n:,} nodos / {e:,} aristas / {len(domains)} dominios → "
          f"{args.output} ({mb:.0f}MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
