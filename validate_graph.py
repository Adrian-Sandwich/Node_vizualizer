#!/usr/bin/env python3
"""
Gate de aceptación de grafos — implementa docs/GRAPH_CONTRACT.md.

Uso:
  python3 validate_graph.py grafo.kgraph.json [otro.kbin ...]

Exit codes:
  0 = todos aceptados (puede haber warnings)
  1 = al menos un archivo con errores de contrato
  2 = archivo ilegible / formato irreconocible

Sin dependencias fuera de stdlib.
"""
import json
import math
import struct
import sys

MAX_NODES = 4_000_000       # presupuesto fixed-point del Barnes-Hut GPU
MAX_DOMAINS = 255           # u8 en kbin
MAX_EDGE_TYPES = 255        # u8 en kbin
JSON_NODE_SOFT_CAP = 250_000  # arriba de esto: convertir a kbin
BAKED_COVERAGE = 0.95       # umbral de hasBakedLayout en app.html

# llaves de props que pisan campos estructurales (spread en el loader)
PROPS_RESERVED = {"id", "label", "tag", "domain", "vid", "size", "tooltip",
                  "x", "y", "z"}


class Report:
    def __init__(self, path):
        self.path = path
        self.errors = []
        self.warnings = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def dump(self):
        verdict = "RECHAZADO" if self.errors else "ACEPTADO"
        print(f"\n=== {self.path} → {verdict} "
              f"({len(self.errors)} errores, {len(self.warnings)} warnings)")
        for m in self.errors:
            print(f"  ERROR   {m}")
        for m in self.warnings:
            print(f"  warning {m}")


def is_hex_color(v):
    return (isinstance(v, str) and len(v) == 7 and v[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in v[1:]))


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# ─── kgraph JSON ─────────────────────────────────────────────────────────────

def validate_kgraph(path, rep):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        rep.err(f"JSON inválido: {e}")
        return
    if not isinstance(d, dict):
        rep.err("top-level no es objeto")
        return

    # top-level
    if d.get("format") != "kgraph":
        rep.err(f'format debe ser "kgraph" exacto (es {d.get("format")!r}) — el loader lo rechaza')
    if d.get("version") != "1.0":
        rep.warn(f'version debería ser string "1.0" (es {d.get("version")!r})')
    for k in ("meta", "nodes", "edges"):
        if k not in d:
            rep.err(f"falta top-level {k!r}")
    nodes = d.get("nodes") or []
    edges = d.get("edges") or []
    meta = d.get("meta") or {}
    if not isinstance(nodes, list) or not nodes:
        rep.err("nodes vacío o no-lista")
        return

    if len(nodes) > MAX_NODES:
        rep.err(f"{len(nodes):,} nodos > límite duro {MAX_NODES:,} (GPU sim)")
    if len(nodes) > JSON_NODE_SOFT_CAP:
        rep.warn(f"{len(nodes):,} nodos en JSON — convertir a .kbin "
                 f"(JSON.parse revienta ~450MB; kgraph_to_kbin.py)")

    # meta.domain_colors
    dc = meta.get("domain_colors")
    if not isinstance(dc, dict) or not dc:
        rep.err("meta.domain_colors falta o vacío — sin él todo sale gris y no hay leyenda")
        dc = {}
    if len(dc) > MAX_DOMAINS:
        rep.err(f"{len(dc)} dominios > {MAX_DOMAINS} (u8 en kbin)")
    for dom, col in dc.items():
        if not is_hex_color(col):
            rep.err(f"domain_colors[{dom!r}] = {col!r} no es #rrggbb")

    # meta counts cross-check
    for mk, real, what in (("node_count", len(nodes), "nodes"),
                           ("edge_count", len(edges), "edges")):
        mv = meta.get(mk)
        if mv is not None and mv != real:
            rep.err(f"meta.{mk}={mv} no cuadra con len({what})={real}")

    # nodes
    ids = []
    seen = set()
    dup_shown = 0
    coords_full = coords_partial = 0
    domains_used = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            rep.err(f"nodes[{i}] no es objeto")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            rep.err(f"nodes[{i}].id inválido ({nid!r}) — string no vacío obligatorio")
            continue
        if nid in seen:
            if dup_shown < 5:
                rep.err(f"id duplicado: {nid!r}")
            dup_shown += 1
        seen.add(nid)
        ids.append(nid)
        if not nid.isascii() and dup_shown == 0 and coords_partial == 0:
            rep.warn(f"id no-ASCII ({nid!r}) — riesgo de orden divergente si va a kbin")
        dom = n.get("domain", "default")
        domains_used.add(dom)
        sz = n.get("size")
        if sz is not None and not finite(sz):
            rep.err(f"nodes[{i}].size = {sz!r} no numérico/finito")
        props = n.get("props")
        if isinstance(props, dict):
            bad = set(props) & PROPS_RESERVED
            bad |= {k for k in props if isinstance(k, str) and k.startswith("_")}
            if bad:
                rep.err(f"nodes[{i}] ({nid!r}): props con llaves prohibidas {sorted(bad)} "
                        f"— el spread del loader las pisa sobre el nodo")
        has = [k in n for k in ("x", "y", "z")]
        if all(has):
            if all(finite(n[k]) for k in ("x", "y", "z")):
                coords_full += 1
            else:
                rep.err(f"nodes[{i}] ({nid!r}): coords no finitas")
        elif any(has):
            coords_partial += 1
    if dup_shown > 5:
        rep.err(f"... {dup_shown} ids duplicados en total")

    # coords todo-o-nada
    if coords_partial:
        rep.err(f"{coords_partial} nodos con coords INCOMPLETAS (x/y/z parciales) — todo-o-nada")
    if 0 < coords_full < len(nodes):
        frac = coords_full / len(nodes)
        if frac < BAKED_COVERAGE:
            rep.err(f"coords en {coords_full}/{len(nodes)} nodos ({frac:.0%}) — zona basura: "
                    f"ni bake (≥95%) ni layout propio (0%). Quita todas o hornea todas")
        else:
            rep.warn(f"coords en {frac:.0%} de nodos — pasa el umbral 95% pero lo limpio es 100%")

    # dominios sin color
    missing = domains_used - set(dc)
    if missing:
        rep.err(f"dominios usados sin entrada en domain_colors: {sorted(missing)[:10]}"
                f"{' …' if len(missing) > 10 else ''} — esos nodos caen a gris")

    # orden para kbin
    if ids != sorted(ids):
        rep.warn("ids NO ordenados ascendente — OK para JSON, pero conversión a kbin "
                 "rompe la búsqueda binaria (ordena nodes por id antes de convertir)")

    # edges
    idset = seen
    dangling = selfloops = 0
    dup_edges = 0
    edge_seen = set()
    etypes = set()
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            rep.err(f"edges[{i}] no es objeto")
            continue
        a, b = e.get("from"), e.get("to")
        if a not in idset or b not in idset:
            if dangling < 5:
                rep.err(f"arista colgada: {a!r} → {b!r}")
            dangling += 1
            continue
        if a == b:
            selfloops += 1
        t = e.get("type", "")
        etypes.add(t)
        key = (a, b, t)
        if key in edge_seen:
            dup_edges += 1
        edge_seen.add(key)
        w = e.get("weight")
        if w is not None and not finite(w):
            rep.err(f"edges[{i}].weight = {w!r} no numérico/finito")
    if dangling > 5:
        rep.err(f"... {dangling} aristas colgadas en total")
    if len(etypes) > MAX_EDGE_TYPES:
        rep.err(f"{len(etypes)} tipos de arista > {MAX_EDGE_TYPES} (u8 en kbin)")
    if selfloops:
        rep.warn(f"{selfloops} self-loops (no rompen, no aportan)")
    if dup_edges:
        rep.warn(f"{dup_edges} aristas duplicadas (mismo from/to/type) — duplican fuerza de spring")


# ─── kbin ────────────────────────────────────────────────────────────────────

def validate_kbin(path, rep):
    with open(path, "rb") as f:
        buf = f.read()
    if len(buf) < 16 or buf[:4] != b"KBN1":
        rep.err(f"magic inválido ({buf[:4]!r}) — no es kbin")
        return
    n, e, meta_len = struct.unpack_from("<III", buf, 4)
    pad4 = lambda x: (x + 3) & ~3
    off = 16
    try:
        meta = json.loads(buf[off:off + meta_len].decode("utf-8"))
    except Exception as ex:
        rep.err(f"meta JSON ilegible: {ex}")
        return
    off += pad4(meta_len)

    if n > MAX_NODES:
        rep.err(f"{n:,} nodos > límite duro {MAX_NODES:,} (GPU sim lanza error)")

    # layout de secciones — el parser del navegador exige tamaño EXACTO
    try:
        pos = struct.unpack_from(f"<{n * 3}f", buf, off); off += n * 12
        off += pad4(n)  # domainIdx (validado abajo)
        dom_off = off - pad4(n)
        id_offsets = struct.unpack_from(f"<{n + 1}I", buf, off); off += (n + 1) * 4
        (blob_len,) = struct.unpack_from("<I", buf, off); off += 4
        blob = buf[off:off + blob_len]; off += pad4(blob_len)
        src = struct.unpack_from(f"<{e}I", buf, off); off += e * 4
        dst = struct.unpack_from(f"<{e}I", buf, off); off += e * 4
        type_off = off; off += pad4(e)
    except struct.error:
        rep.err("archivo truncado — secciones no caben en el tamaño declarado")
        return
    if off != len(buf):
        rep.err(f"{len(buf) - off} bytes de sobra al final — el parser del navegador rechaza")

    # meta obligatoria
    domains = meta.get("domains")
    if not isinstance(domains, list) or not domains:
        rep.err("meta.domains falta o vacío")
        domains = []
    if len(domains) > MAX_DOMAINS:
        rep.err(f"{len(domains)} dominios > {MAX_DOMAINS}")
    dcol = meta.get("domainColors")
    if not isinstance(dcol, dict):
        rep.err("meta.domainColors falta")
    else:
        for dom in domains:
            if not is_hex_color(dcol.get(dom, "")):
                rep.err(f"domainColors[{dom!r}] falta o no es #rrggbb")
    etypes = meta.get("edgeTypes")
    if not isinstance(etypes, list):
        rep.err("meta.edgeTypes falta")
        etypes = []
    if len(etypes) > MAX_EDGE_TYPES:
        rep.err(f"{len(etypes)} tipos de arista > {MAX_EDGE_TYPES}")
    if meta.get("layout") not in ("baked", "fallback", "radial", "spiral"):
        rep.warn(f"meta.layout = {meta.get('layout')!r} fuera de valores conocidos")

    # posiciones finitas
    bad_pos = sum(1 for v in pos if not math.isfinite(v))
    if bad_pos:
        rep.err(f"{bad_pos} coordenadas no finitas (NaN/Inf)")

    # domainIdx en rango
    dom_idx = buf[dom_off:dom_off + n]
    if domains:
        over = sum(1 for v in dom_idx if v >= len(domains))
        if over:
            rep.err(f"{over} domainIdx fuera de rango (≥ {len(domains)})")

    # ids: offsets monótonos, UTF-8, ORDENADOS (búsqueda binaria)
    if id_offsets[0] != 0 or id_offsets[-1] != blob_len:
        rep.err("idOffsets no cuadran con blobLen")
    ids_sorted = True
    prev = None
    try:
        for i in range(n):
            s = blob[id_offsets[i]:id_offsets[i + 1]].decode("utf-8")
            if prev is not None and s < prev:
                ids_sorted = False
                break
            prev = s
    except UnicodeDecodeError:
        rep.err("id blob con UTF-8 inválido")
    if not ids_sorted:
        rep.err("ids NO ordenados ascendente — kbinFindIndex (búsqueda binaria) queda roto: "
                "panel de detalle/búsqueda fallan silencioso")

    # edges en rango
    over_e = sum(1 for i in range(e) if src[i] >= n or dst[i] >= n)
    if over_e:
        rep.err(f"{over_e} aristas con índice de nodo fuera de rango")
    tidx = buf[type_off:type_off + e]
    if etypes:
        over_t = sum(1 for v in tidx if v >= len(etypes))
        if over_t:
            rep.err(f"{over_t} edgeTypeIdx fuera de rango")

    # aristas por longitud ascendente (muestra: primeras vs últimas 1000)
    def elen2(i):
        a, b = src[i], dst[i]
        return sum((pos[a * 3 + k] - pos[b * 3 + k]) ** 2 for k in range(3))
    if e > 2000:
        head = sorted(elen2(i) for i in range(1000))
        tail = sorted(elen2(i) for i in range(e - 1000, e))
        if head[500] > tail[500]:  # medianas invertidas = claramente desordenado
            rep.warn("aristas NO ordenadas por longitud — el corte de densidad (tecla E, "
                     "calidad adaptiva) elimina aristas al azar en vez de las largas")


# ─── main ────────────────────────────────────────────────────────────────────

def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    any_err = False
    for path in argv[1:]:
        rep = Report(path)
        try:
            if path.endswith(".kbin"):
                validate_kbin(path, rep)
            elif path.endswith(".kgraph.json"):
                validate_kgraph(path, rep)
            else:
                rep.err("extensión desconocida — debe ser .kgraph.json o .kbin "
                        "(el picker del visualizador filtra por extensión)")
        except OSError as ex:
            print(f"{path}: ilegible: {ex}", file=sys.stderr)
            return 2
        rep.dump()
        any_err |= bool(rep.errors)
    return 1 if any_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
