#!/usr/bin/env python3
"""
Enforcement compartido de docs/GRAPH_CONTRACT.md para todo script que EMITE
un .kgraph.json. Llamar `finalize(obj)` justo antes de json.dump garantiza
que la salida pasa `validate_graph.py`:

  - format/version normalizados ("kgraph" / "1.0")
  - ids de nodo coercidos a string; duplicados = ValueError (falla ruidosa,
    nunca emitir basura)
  - props sin llaves reservadas ni con prefijo "_" (el spread del loader
    las pisaría sobre el nodo)
  - aristas colgadas DESCARTADAS y deduplicadas (from, to, type)
  - todo dominio usado con entrada en meta.domain_colors (backfill de paleta)
  - nodos ORDENADOS ascendente por id — kbinFindIndex bisecta: requisito
    para conversión a .kbin
  - meta.node_count / edge_count recalculados

Uso:
    from kgraph_contract import finalize
    obj = finalize(obj)          # muta y regresa el mismo dict
    json.dump(obj, f, ensure_ascii=False)
"""
import sys

PALETTE = ['#66d9ff', '#7b8cff', '#b07bff', '#ff7bd5', '#ffd166', '#06d6a0',
           '#ef476f', '#a5f3ff', '#f4a261', '#94d2bd', '#e9c46a', '#8ecae6']

# llaves que el loader del visualizador materializa en el registro del nodo;
# props no puede traerlas (mantener en sync con validate_graph.PROPS_RESERVED)
RESERVED_PROPS = {"id", "label", "tag", "domain", "vid", "size", "tooltip",
                  "x", "y", "z"}


def _log(msg):
    print(f"[contract] {msg}", file=sys.stderr)


def finalize(obj, quiet=False):
    """Normaliza `obj` (dict kgraph) al contrato. Muta y regresa el mismo
    dict. ValueError en violaciones no auto-reparables (ids duplicados)."""
    say = (lambda m: None) if quiet else _log

    obj["format"] = "kgraph"
    obj["version"] = "1.0"
    meta = obj.setdefault("meta", {})
    nodes = obj.get("nodes") or []
    edges = obj.get("edges") or []

    # ── nodos: id string, único; props sin llaves reservadas ──
    seen = set()
    for n in nodes:
        nid = n.get("id")
        if not isinstance(nid, str):
            nid = str(nid)
            n["id"] = nid
        if not nid:
            raise ValueError("nodo con id vacío")
        if nid in seen:
            raise ValueError(f"id de nodo duplicado: {nid!r}")
        seen.add(nid)
        props = n.get("props")
        if isinstance(props, dict):
            bad = [k for k in props
                   if k in RESERVED_PROPS or (isinstance(k, str) and k.startswith("_"))]
            for k in bad:
                # renombrar en vez de tirar: el dato sobrevive en el panel
                props[f"prop_{k.lstrip('_')}"] = props.pop(k)
            if bad:
                say(f"props: {len(bad)} llaves reservadas renombradas en {nid!r} ({bad})")

    # ── aristas: endpoints string, sin colgadas, sin duplicadas ──
    kept, dangling, dupes = [], 0, 0
    edge_seen = set()
    for e in edges:
        a, b = e.get("from"), e.get("to")
        if not isinstance(a, str):
            a = str(a); e["from"] = a
        if not isinstance(b, str):
            b = str(b); e["to"] = b
        if a not in seen or b not in seen:
            dangling += 1
            continue
        key = (a, b, e.get("type", ""))
        if key in edge_seen:
            dupes += 1
            continue
        edge_seen.add(key)
        kept.append(e)
    if dangling:
        say(f"aristas colgadas descartadas: {dangling}")
    if dupes:
        say(f"aristas duplicadas descartadas: {dupes}")
    obj["edges"] = kept

    # ── dominios: backfill de color para todo dominio usado ──
    dc = meta.get("domain_colors")
    if not isinstance(dc, dict):
        dc = {}
    used = {n.get("domain", "default") for n in nodes}
    missing = sorted(used - set(dc))
    for i, dom in enumerate(missing):
        dc[dom] = PALETTE[(len(dc) + i) % len(PALETTE)]
    if missing:
        say(f"dominios sin color, paleta asignada: {missing}")
    meta["domain_colors"] = dc
    if len(dc) > 255:
        raise ValueError(f"{len(dc)} dominios > 255 (u8 en kbin)")

    # ── orden por id (requisito de bisección en kbin) + counts ──
    nodes.sort(key=lambda n: n["id"])
    obj["nodes"] = nodes
    meta["node_count"] = len(nodes)
    meta["edge_count"] = len(kept)
    return obj
