#!/usr/bin/env python3
"""
Prune a large .kgraph.json down to a browser-renderable subgraph.

Strategy (dropout-focused ego network):
  1. Keep every "desercion" (dropout) student node.
  2. Keep "materia" (course/section) nodes taken by >= --min-shared dropouts.
     Sections touched by only one dropout are noise; sections shared by many
     dropouts reveal the courses correlated with dropping out.
  3. Keep "profesor" nodes that teach a kept section.
  4. Optionally keep "continua" (continuing) students who also took a kept
     section (--include-continua) for contrast.
  5. Keep only edges whose both endpoints survived.

Counts at a few thresholds (full graph = 36270 nodes / 365225 edges):
  --min-shared 2  -> ~6700 nodes / ~20000 edges
  --min-shared 3  -> ~4300 nodes / ~13600 edges   (default, smooth)
  --min-shared 5  -> ~2200 nodes / ~5900 edges    (very focused)
"""

import argparse
import json
import pathlib
from collections import defaultdict
from datetime import datetime


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prune(graph, min_shared, include_continua):
    nodes = {n["id"]: n for n in graph["nodes"]}

    def dom(nid):
        n = nodes.get(nid)
        return n.get("domain") if n else None

    dropouts = {i for i, n in nodes.items() if n.get("domain") == "desercion"}

    # Single pass over the (large) edge list: classify each edge once and stash
    # what we need. Professors and continuing students depend on keep_sec, which
    # isn't known until the full CURSO scan finishes, so we collect their
    # (entity, section) pairs here and resolve them afterwards against the small
    # keep_sec set — avoiding 2-3 full passes over 365k+ edges.
    sec_dropouts = defaultdict(set)   # section -> set of dropout students
    prof_pairs = []                   # (professor, section) from IMPARTIDA_POR
    continua_pairs = []               # (continua student, section) from CURSO
    for e in graph["edges"]:
        etype = e.get("type")
        a, b = e["from"], e["to"]
        da, db = dom(a), dom(b)
        if etype == "CURSO":
            sec = b if db == "materia" else (a if da == "materia" else None)
            if sec is None:
                continue
            if da == "desercion" or db == "desercion":
                stu = a if da == "desercion" else b
                sec_dropouts[sec].add(stu)
            elif include_continua and (da == "continua" or db == "continua"):
                stu = a if da == "continua" else b
                continua_pairs.append((stu, sec))
        elif etype == "IMPARTIDA_POR":
            prof = a if da == "profesor" else (b if db == "profesor" else None)
            sec = a if da == "materia" else (b if db == "materia" else None)
            if prof and sec:
                prof_pairs.append((prof, sec))

    keep_sec = {s for s, studs in sec_dropouts.items() if len(studs) >= min_shared}

    keep = set(dropouts) | set(keep_sec)
    keep.update(prof for prof, sec in prof_pairs if sec in keep_sec)
    if include_continua:
        keep.update(stu for stu, sec in continua_pairs if sec in keep_sec)

    new_nodes = [n for n in graph["nodes"] if n["id"] in keep]
    new_edges = [e for e in graph["edges"] if e["from"] in keep and e["to"] in keep]
    return new_nodes, new_edges


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--min-shared", type=int, default=3,
                    help="keep sections taken by >= this many dropouts (default 3)")
    ap.add_argument("--include-continua", action="store_true",
                    help="also keep continuing students who took a kept section")
    args = ap.parse_args()

    g = load(args.input)
    nodes, edges = prune(g, args.min_shared, args.include_continua)

    meta = dict(g.get("meta", {}))
    meta["created_at"] = datetime.now().isoformat() + "Z"
    meta["node_count"] = len(nodes)
    meta["edge_count"] = len(edges)
    meta["pruned_from"] = {
        "source": pathlib.Path(args.input).name,
        "orig_nodes": len(g["nodes"]),
        "orig_edges": len(g["edges"]),
        "min_shared": args.min_shared,
        "include_continua": args.include_continua,
    }

    out = {**g, "meta": meta, "nodes": nodes, "edges": edges}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

    print(f"in : {len(g['nodes'])} nodes / {len(g['edges'])} edges")
    print(f"out: {len(nodes)} nodes / {len(edges)} edges -> {args.output}")


if __name__ == "__main__":
    main()
