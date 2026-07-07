#!/usr/bin/env python3
"""
Convert a .kgraph.json (text, ~1775 bytes/node) to the binary .kbin format
(~206 bytes/node, ~8.6x smaller, no JSON.parse V8 string wall). Same graph,
same domains/edge-types/colors. Reuses parquet_to_kbin's spiral layout when
the JSON carries no baked x/y/z.

Uso:
  .venv/bin/python kgraph_to_kbin.py graphs/oax_sample_300k.kgraph.json \
      graphs/oax_sample_300k.kbin
"""
import argparse
import json
import struct
import sys
from datetime import datetime

from parquet_to_kbin import MAGIC, PALETTE, spiral_layout


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--algo", choices=["fallback", "radial", "spiral"],
                    default="fallback",
                    help="layout when the JSON carries no coords. 'fallback' "
                         "(default) bakes a cheap spiral placeholder and flags "
                         "the file so the BROWSER runs computeFallbackLayout — "
                         "the exact radial the JSON path uses (semantic hubs). "
                         "'radial'/'spiral' bake that layout in Python instead.")
    args = ap.parse_args()

    import numpy as np
    print("[kg2kbin] leyendo JSON…", file=sys.stderr)
    d = json.load(open(args.input, encoding="utf-8"))
    nodes = d["nodes"]
    edges = d.get("edges", d.get("links", []))
    n = len(nodes)
    node_ids = [nd["id"] for nd in nodes]
    idmap = {nid: i for i, nid in enumerate(node_ids)}

    # domains from the node's domain field (fallback: id prefix)
    def dom_of(nd):
        return nd.get("domain") or nd.get("_domain") or (
            nd["id"].split("::", 1)[0] if "::" in nd["id"] else "default")

    dom_names = sorted({dom_of(nd) for nd in nodes})
    if len(dom_names) > 255:
        raise SystemExit(f"[kg2kbin] {len(dom_names)} dominios > 255 (u8)")
    dom_to_idx = {dn: i for i, dn in enumerate(dom_names)}
    dom_idx = np.array([dom_to_idx[dom_of(nd)] for nd in nodes], dtype=np.uint8)

    # edges → index pairs; drop dangling
    print(f"[kg2kbin] {n:,} nodos, {len(edges):,} aristas — indexando…", file=sys.stderr)
    src_l, dst_l, typ_l = [], [], []
    for e in edges:
        a = idmap.get(e.get("from", e.get("source")))
        b = idmap.get(e.get("to", e.get("target")))
        if a is None or b is None:
            continue
        src_l.append(a); dst_l.append(b); typ_l.append(e.get("type", ""))
    e_src = np.array(src_l, dtype=np.uint32)
    e_dst = np.array(dst_l, dtype=np.uint32)
    types, typ_idx = np.unique(np.array(typ_l), return_inverse=True)
    if len(types) > 255:
        raise SystemExit(f"[kg2kbin] {len(types)} tipos de arista > 255 (u8)")
    typ_idx = typ_idx.astype(np.uint8)
    e = len(e_src)
    type_counts = {t: int(c) for t, c in
                   zip(types.tolist(), np.bincount(typ_idx, minlength=len(types)).tolist())}

    # positions: use baked x/y/z if present, else per --algo
    has_xyz = all(k in nodes[0] for k in ("x", "y", "z"))
    layout_tag = "baked"
    if has_xyz:
        print("[kg2kbin] usando coords horneadas del JSON", file=sys.stderr)
        pos = np.array([[float(nd["x"]), float(nd["y"]), float(nd["z"])]
                        for nd in nodes], dtype=np.float32)
    elif args.algo == "fallback":
        # spiral placeholder only — the browser recomputes radial via
        # computeFallbackLayout (flagged layout:"fallback" in meta). Matches
        # the JSON path exactly; the semantic hub structure the user wants.
        print("[kg2kbin] layout diferido al navegador (computeFallbackLayout)",
              file=sys.stderr)
        deg = (np.bincount(e_src, minlength=n).astype(np.float64)
               + np.bincount(e_dst, minlength=n))
        pos = spiral_layout(np, n, deg, dom_idx.astype(np.int64), len(dom_names))
        layout_tag = "fallback"
    elif args.algo == "radial":
        print("[kg2kbin] sin coords → layout radial (hubs al centro)", file=sys.stderr)
        from graph_layout import layout_radial, normalize
        # layout_radial reads e["from"]/e["to"] + node["id"]/["domain"] — the
        # kgraph edges already carry from/to, feed them straight in
        coords = normalize(layout_radial(nodes, edges, 1400.0), 1400.0)
        pos = np.array(coords, dtype=np.float32)
    else:
        print("[kg2kbin] sin coords → layout espiral", file=sys.stderr)
        deg = (np.bincount(e_src, minlength=n).astype(np.float64)
               + np.bincount(e_dst, minlength=n))
        pos = spiral_layout(np, n, deg, dom_idx.astype(np.int64), len(dom_names))

    # edges sorted by 3D length ascending (short first — drawRange cuts long)
    print("[kg2kbin] ordenando aristas por longitud…", file=sys.stderr)
    diff = pos[e_src].astype(np.float64) - pos[e_dst].astype(np.float64)
    order = np.argsort(np.einsum("ij,ij->i", diff, diff), kind="stable")
    e_src, e_dst, typ_idx = e_src[order], e_dst[order], typ_idx[order]

    # id blob
    encoded = [i.encode("utf-8") for i in node_ids]
    offsets = np.zeros(n + 1, dtype=np.uint32)
    np.cumsum([len(b) for b in encoded], out=offsets[1:])
    blob = b"".join(encoded)

    src_meta = d.get("meta", {})
    colors = src_meta.get("domain_colors") or {}
    meta = {
        "domains": dom_names,
        "domainColors": {dn: colors.get(dn, PALETTE[i % len(PALETTE)])
                         for i, dn in enumerate(dom_names)},
        "edgeTypes": types.tolist(),
        "edgeTypeCounts": type_counts,
        "layout": layout_tag,  # "fallback" → browser runs computeFallbackLayout
        "source": {"from": args.input.split("/")[-1],
                   "createdAt": datetime.now().isoformat() + "Z"},
    }
    meta_b = json.dumps(meta, ensure_ascii=False).encode("utf-8")

    def pad4(b):
        return b + b"\x00" * (-len(b) % 4)

    print("[kg2kbin] escribiendo kbin…", file=sys.stderr)
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
    print(f"[kg2kbin] {n:,} nodos / {e:,} aristas / {len(dom_names)} dominios → "
          f"{args.output} ({mb:.0f}MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
