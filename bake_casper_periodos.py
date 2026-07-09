#!/usr/bin/env python3
"""Bake semántico para grafos Casper multi-periodo: un cluster de fuerza
(drl) por periodo, periodos en anillo cronológico, profesores y nodos sin
periodo al centroide de sus vecinos (flotan entre periodos).

El layout genérico embarra los periodos encimados (los profesores puentean
todo en un solo componente, así que el modo islas de graph_layout no aplica).

Uso:
  .venv/bin/python bake_casper_periodos.py graphs/casper_real_completo.kgraph.json
  # escribe <input>_layout.kgraph.json junto al original
"""
import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime

from graph_layout import layout_igraph, normalize
from kgraph_contract import finalize

R = 1400.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="default: <input sin .kgraph.json>_layout.kgraph.json")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    dst = args.output or re.sub(r"\.kgraph\.json$", "", args.input) + "_layout.kgraph.json"

    d = json.load(open(args.input))
    nodes, edges = d["nodes"], d["edges"]
    n = len(nodes)
    idx = {nd["id"]: i for i, nd in enumerate(nodes)}

    # EST::S03728_202360 (sufijo) | SEC::202360_92800 (prefijo tras ::)
    period_of = [None] * n
    for i, nd in enumerate(nodes):
        m = re.search(r"_(20\d{4})$", nd["id"]) or re.search(r"::(20\d{4})_", nd["id"])
        if m:
            period_of[i] = m.group(1)

    # solo periodos principales (>=3% de nodos); intersemestrales chicos van
    # al paso de centroide junto con los profesores
    pc = Counter(p for p in period_of if p)
    periods = sorted(p for p, c in pc.items() if c >= n * 0.03)
    for i in range(n):
        if period_of[i] not in periods:
            period_of[i] = None
    print(f"periodos: {periods}", file=sys.stderr)

    coords = [None] * n
    ring_r = R * 1.05
    island_r = R * 0.42
    for k, p in enumerate(periods):
        ang = 2 * math.pi * k / len(periods)
        cx, cz = ring_r * math.cos(ang), ring_r * math.sin(ang)
        members = [i for i in range(n) if period_of[i] == p]
        mset = {nodes[i]["id"] for i in members}
        sub_nodes = [nodes[i] for i in members]
        sub_edges = [e for e in edges if e["from"] in mset and e["to"] in mset]
        # drl (fuerza real) por periodo: bola orgánica; radial daba abanicos
        sub = normalize(layout_igraph(sub_nodes, sub_edges, "drl", args.seed), island_r)
        for i, (x, y, z) in zip(members, sub):
            coords[i] = (cx + x, y, cz + z)
        print(f"  {p}: {len(members)} nodos, {len(sub_edges)} aristas internas",
              file=sys.stderr)

    # profesores / sin periodo: centroide de vecinos, elevados entre anillos
    adj = {}
    for e in edges:
        a, b = idx.get(e["from"]), idx.get(e["to"])
        if a is None or b is None:
            continue
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    rest = [i for i in range(n) if coords[i] is None]
    for i in rest:
        nbrs = [j for j in adj.get(i, []) if coords[j] is not None]
        if nbrs:
            x = sum(coords[j][0] for j in nbrs) / len(nbrs)
            z = sum(coords[j][2] for j in nbrs) / len(nbrs)
            coords[i] = (x, island_r * 0.75, z)
        else:
            coords[i] = (0.0, R * 1.8, 0.0)
    print(f"  sin periodo (profes/sueltos): {len(rest)}", file=sys.stderr)

    coords = normalize(coords, R)
    for nd, (x, y, z) in zip(nodes, coords):
        nd["x"] = round(x, 2)
        nd["y"] = round(y, 2)
        nd["z"] = round(z, 2)
    meta = dict(d.get("meta", {}))
    meta["layout"] = {"algorithm": "drl-periodos-anillo", "radius": R,
                      "seed": args.seed,
                      "computed_at": datetime.now().isoformat() + "Z"}
    out = finalize({**d, "meta": meta, "nodes": nodes})
    json.dump(out, open(dst, "w"), ensure_ascii=False)
    print(f"wrote {dst}", file=sys.stderr)


if __name__ == "__main__":
    main()
