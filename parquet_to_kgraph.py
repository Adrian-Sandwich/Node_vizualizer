#!/usr/bin/env python3
"""
Convert a (src, dst, type) edge parquet into a viewer-sized .kgraph.json.

Strategy: sample N seed nodes of a chosen domain (default Person), keep the
selected edge types incident to them, pull in the touched entities, then keep
entity↔entity edges among included nodes. Domains come from the id prefix
("Person::x" → Person) and get automatic colors.

Example (Oaxaca sample, 1.19M nodes / 21.3M edges → ~viewer scale):
  .venv/bin/python parquet_to_kgraph.py ~/Desktop/oax_sample_edges.parquet \
      graphs/oax_sample.kgraph.json --persons 20000

Requires duckdb (pip install duckdb).
"""

import argparse
import json
import sys
from datetime import datetime

from kgraph_contract import finalize

# pairwise-proximity spam that buries the semantic structure at scale
DEFAULT_EXCLUDE = "NEARBY,ON_BLOCK_FRONT,ON_ROAD"

PALETTE = ['#66d9ff', '#7b8cff', '#b07bff', '#ff7bd5', '#ffd166', '#06d6a0',
           '#ef476f', '#a5f3ff', '#f4a261', '#94d2bd', '#e9c46a', '#8ecae6']


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parquet")
    ap.add_argument("output")
    ap.add_argument("--persons", type=int, default=20000,
                    help="seed sample size (default 20000)")
    ap.add_argument("--seed-domain", default="Person",
                    help="id prefix to sample (default Person)")
    ap.add_argument("--exclude-types", default=DEFAULT_EXCLUDE,
                    help=f"comma list of edge types to drop (default {DEFAULT_EXCLUDE})")
    ap.add_argument("--max-edges", type=int, default=400000,
                    help="hard cap on output edges (default 400k)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    import duckdb
    con = duckdb.connect()
    P = args.parquet
    excl = [t.strip() for t in args.exclude_types.split(",") if t.strip()]
    excl_sql = ",".join(f"'{t}'" for t in excl) or "''"

    con.execute(f"""
      CREATE TEMP TABLE sem AS
      SELECT src, dst, type FROM '{P}' WHERE type NOT IN ({excl_sql})
    """)
    con.execute(f"""
      CREATE TEMP TABLE seeds AS
      SELECT id FROM (
        SELECT DISTINCT src AS id FROM sem WHERE src LIKE '{args.seed_domain}::%'
        UNION
        SELECT DISTINCT dst FROM sem WHERE dst LIKE '{args.seed_domain}::%'
      ) USING SAMPLE reservoir({args.persons} ROWS) REPEATABLE ({args.seed})
    """)
    # edges incident to the seeds
    con.execute("""
      CREATE TEMP TABLE picked AS
      SELECT e.* FROM sem e
      JOIN seeds s ON e.src = s.id OR e.dst = s.id
    """)
    # nodes = seeds + touched entities; then add entity↔entity edges among them
    con.execute("""
      CREATE TEMP TABLE node_ids AS
      SELECT DISTINCT id FROM (
        SELECT src AS id FROM picked UNION SELECT dst FROM picked
      )
    """)
    con.execute(f"""
      INSERT INTO picked
      SELECT e.* FROM sem e
      JOIN node_ids a ON e.src = a.id
      JOIN node_ids b ON e.dst = b.id
      WHERE e.src NOT LIKE '{args.seed_domain}::%'
        AND e.dst NOT LIKE '{args.seed_domain}::%'
    """)
    con.execute("CREATE TEMP TABLE final_edges AS SELECT DISTINCT src, dst, type FROM picked")

    n_edges = con.execute("SELECT count(*) FROM final_edges").fetchone()[0]
    if n_edges > args.max_edges:
        con.execute(f"""
          CREATE TEMP TABLE capped AS
          SELECT * FROM final_edges USING SAMPLE reservoir({args.max_edges} ROWS) REPEATABLE ({args.seed})
        """)
        con.execute("DROP TABLE final_edges")
        con.execute("ALTER TABLE capped RENAME TO final_edges")
        print(f"[parquet2kg] cap: {n_edges:,} → {args.max_edges:,} aristas (sample)", file=sys.stderr)

    edges = [{"from": s, "to": d, "type": t, "label_forward": t.lower().replace("_", " "),
              "label_backward": "", "weight": 1.0}
             for s, d, t in con.execute("SELECT src, dst, type FROM final_edges").fetchall()]

    ids = sorted({e["from"] for e in edges} | {e["to"] for e in edges})
    # ids sin prefijo "Tipo::" no truenan: dominio "default", label = id
    pre = lambda i: i.split("::", 1)[0] if "::" in i else "default"
    post = lambda i: i.split("::", 1)[1] if "::" in i else i
    doms = sorted({pre(i) for i in ids})
    dom_color = {d: PALETTE[i % len(PALETTE)] for i, d in enumerate(doms)}
    nodes = [{"id": i, "label": post(i)[:18],
              "tag": pre(i), "domain": pre(i),
              "vid": i, "size": 7, "tooltip": i, "props": {}} for i in ids]

    from collections import Counter
    etc = Counter(e["type"] for e in edges)
    out = {
        "format": "kgraph", "version": "1.0",
        "meta": {
            "created_at": datetime.now().isoformat() + "Z",
            "node_count": len(nodes), "edge_count": len(edges),
            "domain_colors": dom_color,
            "domain_labels": {d: d for d in doms},
            "domain_map": None, "tag_schema": None,
            "tag_counts": dict(Counter(n["tag"] for n in nodes)),
            "edge_type_counts": dict(etc),
            "source": {"parquet": P.split("/")[-1], "persons": args.persons,
                       "excluded_types": excl, "seed": args.seed},
        },
        "nodes": nodes, "edges": edges,
    }
    out = finalize(out)  # contrato: ids/props/colgadas/orden/counts
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"[parquet2kg] {len(out['nodes']):,} nodos / {len(out['edges']):,} aristas → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
