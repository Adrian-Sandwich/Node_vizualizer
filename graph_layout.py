#!/usr/bin/env python3
"""
Bake a 3D layout into a .kgraph.json so the browser can render huge graphs
without running physics (perf mode in app.html activates when nodes carry
precomputed x,y,z).

Algorithms:
  drl    (default) igraph layout_drl 3D — built for large graphs; ~1-4 min
                   for 36k nodes / 365k edges.
  fr     igraph 3D Fruchterman-Reingold (grid-accelerated); slower (~5-15 min)
         but often crisper cluster separation.
  radial degree-based galaxy, no dependencies: hubs at the core, leaves on
         outer orbits, domains in angular sectors, disc-flattened. Best for
         hub-heavy bipartite data (students→courses) where force layouts
         produce hairballs.
  sphere no-dependency fallback: domain-grouped fibonacci-sphere shells.
         Deterministic, O(n), used automatically (with a warning) when
         python-igraph is not installed. app.html has a JS twin of this
         algorithm for graphs loaded without baked coords.

Output: same kgraph JSON with top-level x,y,z on each node (2-decimal
rounding) and meta.layout describing how it was computed.

igraph install (this repo uses a venv because of PEP 668):
  python3 -m venv .venv && .venv/bin/pip install python-igraph
  .venv/bin/python graph_layout.py graphs/foo.kgraph.json
"""

import argparse
import json
import math
import pathlib
import sys
from collections import defaultdict
from datetime import datetime


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fibonacci_sphere(n, radius):
    """n deterministic points spread on a sphere of the given radius."""
    pts = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        y = 1.0 - (2.0 * i + 1.0) / n           # (-1, 1), never exactly polar
        r = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden * i
        pts.append((math.cos(theta) * r * radius, y * radius, math.sin(theta) * r * radius))
    return pts


def layout_sphere(nodes, edges, radius):
    """Dependency-free fallback: cluster centers (one per domain) on a
    fibonacci sphere, members on sub-spheres sized by cbrt(count).
    Mirrored in app.html (computeFallbackLayout) — keep both in sync."""
    groups = defaultdict(list)
    for i, n in enumerate(nodes):
        groups[n.get("domain") or "default"].append(i)

    keys = sorted(groups)  # deterministic order
    centers = fibonacci_sphere(len(keys), radius * 0.55) if len(keys) > 1 else [(0.0, 0.0, 0.0)]
    coords = [None] * len(nodes)
    for gi, key in enumerate(keys):
        members = groups[key]
        cx, cy, cz = centers[gi]
        sub_r = radius * 0.45 * (len(members) / max(len(nodes), 1)) ** (1 / 3) + radius * 0.08
        for mi, (px, py, pz) in zip(members, fibonacci_sphere(len(members), sub_r)):
            coords[mi] = (cx + px, cy + py, cz + pz)
    return coords


def layout_radial(nodes, edges, radius):
    """Degree-based galaxy: hubs at the core, leaves on outer orbits.

    - Radius per node: log-scaled inverse degree (max degree → center).
    - Direction: each domain starts in its own angular sector (fibonacci
      spread), then 3 refinement sweeps pull every node toward the mean
      direction of its neighbors — connected structure becomes visible
      instead of angular noise.
    - Y is flattened to 0.45 for a galactic-disc silhouette.
    Deterministic, dependency-free, O(iters·E).
    """
    n = len(nodes)
    idx = {node["id"]: i for i, node in enumerate(nodes)}

    deg = [0] * n
    pairs = []
    for e in edges:
        a, b = idx.get(e["from"]), idx.get(e["to"])
        if a is None or b is None:
            continue
        deg[a] += 1
        deg[b] += 1
        pairs.append((a, b))

    max_deg = max(deg) or 1
    r_min, r_max = radius * 0.06, radius
    radii = [r_min + (1.0 - math.log1p(d) / math.log1p(max_deg)) * (r_max - r_min)
             for d in deg]

    # initial directions: domain sectors, fibonacci spread inside each sector
    groups = defaultdict(list)
    for i, node in enumerate(nodes):
        groups[node.get("domain") or "default"].append(i)
    keys = sorted(groups)
    sector_centers = fibonacci_sphere(len(keys), 1.0) if len(keys) > 1 else [(0.0, 1.0, 0.0)]
    dirs = [None] * n
    for gi, key in enumerate(keys):
        cx, cy, cz = sector_centers[gi]
        members = groups[key]
        for j, (px, py, pz) in zip(members, fibonacci_sphere(len(members), 1.0)):
            # blend: 70% sector center + 30% spread → tight but non-degenerate
            vx, vy, vz = cx + 0.45 * px, cy + 0.45 * py, cz + 0.45 * pz
            norm = math.sqrt(vx * vx + vy * vy + vz * vz) or 1.0
            dirs[j] = [vx / norm, vy / norm, vz / norm]

    # refinement: pull each node's direction toward its neighbors' mean
    for _ in range(3):
        acc = [[d[0] * 0.5, d[1] * 0.5, d[2] * 0.5] for d in dirs]  # self-weight
        for a, b in pairs:
            da, db = dirs[a], dirs[b]
            acc[a][0] += db[0]; acc[a][1] += db[1]; acc[a][2] += db[2]
            acc[b][0] += da[0]; acc[b][1] += da[1]; acc[b][2] += da[2]
        for i in range(n):
            x, y, z = acc[i]
            norm = math.sqrt(x * x + y * y + z * z)
            if norm > 1e-9:
                dirs[i] = [x / norm, y / norm, z / norm]

    return [(dirs[i][0] * radii[i],
             dirs[i][1] * radii[i] * 0.45,   # flatten → disc
             dirs[i][2] * radii[i]) for i in range(n)]


def layout_igraph(nodes, edges, algo, seed):
    import igraph  # noqa: deferred so --algo sphere works without it

    idx = {n["id"]: i for i, n in enumerate(nodes)}
    pairs = [(idx[e["from"]], idx[e["to"]])
             for e in edges if e["from"] in idx and e["to"] in idx]
    g = igraph.Graph(len(nodes), pairs)
    # DrL misbehaves with multi-edges/self-loops (the casper graph has many
    # parallel CURSO edges) — collapse them; layout only needs topology.
    g.simplify()

    if seed is not None:
        import random
        random.seed(seed)
    if algo == "fr":
        lay = g.layout_fruchterman_reingold_3d(niter=300)
    else:
        lay = g.layout_drl(dim=3)
    return [tuple(c) for c in lay.coords]


def normalize(coords, radius):
    """Center on the centroid, scale so the 95th-percentile radius == radius."""
    n = len(coords)
    cx = sum(c[0] for c in coords) / n
    cy = sum(c[1] for c in coords) / n
    cz = sum(c[2] for c in coords) / n
    centered = [(x - cx, y - cy, z - cz) for x, y, z in coords]
    dists = sorted(math.sqrt(x * x + y * y + z * z) for x, y, z in centered)
    p95 = dists[min(int(n * 0.95), n - 1)] or 1.0
    s = radius / p95
    return [(x * s, y * s, z * s) for x, y, z in centered]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="default: overwrite input")
    ap.add_argument("--algo", choices=["drl", "fr", "radial", "sphere"], default="drl")
    ap.add_argument("--radius", type=float, default=1400.0,
                    help="95th-percentile radius of the final layout (default 1400 ≈ app SCALE*5)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    g = load(args.input)
    nodes, edges = g["nodes"], g["edges"]
    algo = args.algo

    if algo in ("drl", "fr"):
        try:
            import igraph  # noqa
        except ImportError:
            print("WARNING: python-igraph not installed — falling back to --algo radial.\n"
                  "  install: python3 -m venv .venv && .venv/bin/pip install python-igraph",
                  file=sys.stderr)
            algo = "radial"

    print(f"[graph_layout] {len(nodes)} nodes / {len(edges)} edges, algo={algo}",
          file=sys.stderr)
    if algo == "sphere":
        coords = layout_sphere(nodes, edges, args.radius)
    elif algo == "radial":
        coords = layout_radial(nodes, edges, args.radius)
    else:
        coords = layout_igraph(nodes, edges, algo, args.seed)

    coords = normalize(coords, args.radius)
    for n, (x, y, z) in zip(nodes, coords):
        n["x"] = round(x, 2)
        n["y"] = round(y, 2)
        n["z"] = round(z, 2)

    meta = dict(g.get("meta", {}))
    meta["layout"] = {
        "algorithm": algo,
        "radius": args.radius,
        "seed": args.seed,
        "computed_at": datetime.now().isoformat() + "Z",
    }
    out = {**g, "meta": meta, "nodes": nodes}

    out_path = args.output or args.input
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"[graph_layout] wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
