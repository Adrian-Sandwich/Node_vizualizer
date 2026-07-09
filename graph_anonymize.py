#!/usr/bin/env python3
"""
Anonymize personal data in casper .kgraph.json files for public hosting.

- Student nodes (EST::<matrícula>) → EST::S<seq>  (sequential, irreversible)
- Professor nodes (PROF::<name>)   → PROF::P<seq> (name fully removed)
- Labels and tooltips are regenerated from the anonymous IDs.
- Course/section nodes (SEC::/MAT:: etc.) are left untouched — not personal.

All input files share ONE mapping (the union of ids is collected first and
numbered in sorted order), so the same student maps to the same alias across
the full graph and its pruned/derived versions.

Usage:
  python3 graph_anonymize.py graphs/casper_*.kgraph.json
(rewrites files in place)
"""

import argparse
import json
import re
import sys

from kgraph_contract import finalize


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_mapping(paths):
    students, profs = set(), set()
    for p in paths:
        g = load(p)
        for n in g["nodes"]:
            nid = n.get("id", "")
            if nid.startswith("EST::"):
                students.add(nid)
            elif nid.startswith("PROF::"):
                profs.add(nid)
    mapping = {}
    for i, nid in enumerate(sorted(students), 1):
        mapping[nid] = f"EST::S{i:06d}"
    for i, nid in enumerate(sorted(profs), 1):
        mapping[nid] = f"PROF::P{i:04d}"
    return mapping


def anon_node(n, mapping):
    old = n.get("id", "")
    new = mapping.get(old)
    if not new:
        return  # not a personal node
    short = new.split("::", 1)[1]
    n["id"] = new
    n["vid"] = new
    n["label"] = short
    tip = n.get("tooltip", "")
    if old.startswith("EST::"):
        # "Matrícula 00479456 — continúa" → keep only the outcome part
        suffix = tip.split("—", 1)[1].strip() if "—" in tip else ""
        n["tooltip"] = f"Estudiante {short}" + (f" — {suffix}" if suffix else "")
    else:
        n["tooltip"] = f"Profesor {short}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()

    mapping = build_mapping(args.files)
    print(f"[anon] {len(mapping)} personal ids in shared mapping", file=sys.stderr)

    for p in args.files:
        g = load(p)
        for n in g["nodes"]:
            anon_node(n, mapping)
        for e in g["edges"]:
            e["from"] = mapping.get(e["from"], e["from"])
            e["to"] = mapping.get(e["to"], e["to"])
        meta = g.get("meta", {})
        meta["anonymized"] = True
        g["meta"] = meta
        g = finalize(g)  # re-ordena por los ids nuevos + contrato
        with open(p, "w", encoding="utf-8") as f:
            json.dump(g, f, ensure_ascii=False)
        print(f"[anon] wrote {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
