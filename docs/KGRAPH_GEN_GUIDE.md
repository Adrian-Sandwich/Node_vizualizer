# Guía: generar un grafo compatible (`.kgraph.json`)

Para que otro agente/Claude produzca un archivo que el visualizador cargue sin
tocar código. Formato de texto `.kgraph.json` (para millones de nodos ver el
final: convertir a `.kbin`).

## Esquema

```json
{
  "format": "kgraph",
  "version": "1.0",
  "meta": {
    "domain_colors": { "Bug": "#ef476f", "Proyecto": "#66d9ff", "Persona": "#06d6a0" },
    "domain_labels": { "Bug": "Bug", "Proyecto": "Proyecto", "Persona": "Persona" },
    "edge_type_counts": { "PERTENECE_A": 120, "ASIGNADO_A": 80 }
  },
  "nodes": [
    { "id": "BUG-1", "label": "Login rompe", "tag": "Bug", "domain": "Bug",
      "size": 8, "tooltip": "BUG-1 · severidad alta", "props": { "estado": "PENDIENTE" } }
  ],
  "edges": [
    { "from": "BUG-1", "to": "PROJ-3", "type": "PERTENECE_A", "weight": 1.0 }
  ]
}
```

## Reglas (obligatorio)

- **`nodes[].id`** — string único. Es la llave; las aristas lo referencian.
- **`edges[].from` / `edges[].to`** — deben coincidir EXACTO con un `id` de nodo.
  Aristas con extremos inexistentes se descartan en silencio.
- **`nodes[].domain`** — categoría del nodo. **Todo `domain` usado DEBE existir
  en `meta.domain_colors`**; si no, el nodo cae a un color default. El orden de
  `domain_colors` define el índice de color (cluster_id) de cada dominio.
- **`meta.domain_colors`** — mapa `{ dominio: "#hex" }`. Define qué dominios
  existen y su color. Es lo que llena la leyenda. Sin esto, todo sale gris.

## Campos opcionales (mejoran, no rompen)

- `nodes[].label` — texto mostrado (default: el `id`).
- `nodes[].tag` — subtipo fino (aparece en el panel de detalle).
- `nodes[].tooltip` — texto al pasar el cursor.
- `nodes[].size` — número, escala visual del nodo (default 10).
- `nodes[].props` — objeto libre `{clave: valor}`; se muestra en el panel de detalle.
- `nodes[].x`,`.y`,`.z` — coords 3D horneadas. **Omítelas** y deja que el
  visualizador calcule el layout (radial semántico) — es mejor que inventarlas.
- `edges[].type` — etiqueta de la relación (agrupa/colorea aristas).
- `edges[].weight` — número (default 1.0).
- `meta.domain_labels` — nombres bonitos por dominio para la leyenda.
- `meta.edge_type_counts` — conteos por tipo de arista (readout).

## Reglas de tamaño

- **< ~250k nodos**: `.kgraph.json` está bien.
- **> ~250k nodos**: el JSON pesa ~1775 bytes/nodo y a ~450MB revienta el
  `JSON.parse` del navegador. Generar el JSON y luego convertir:
  `python3 kgraph_to_kbin.py grafo.kgraph.json grafo.kbin` (~206 bytes/nodo).

## Validar antes de mandar

```bash
python3 - grafo.kgraph.json <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
ids = {n["id"] for n in d["nodes"]}
doms = set(d["meta"]["domain_colors"])
bad_dom = {n["domain"] for n in d["nodes"]} - doms
dangling = sum(1 for e in d["edges"] if e["from"] not in ids or e["to"] not in ids)
print(f"{len(d['nodes'])} nodos, {len(d['edges'])} aristas")
print("dominios sin color:", bad_dom or "OK")
print("aristas colgadas:", dangling)
PY
```

Cero aristas colgadas y cero dominios sin color = listo.

## Nombre y ubicación

- El archivo **debe terminar en `.kgraph.json`** (el picker filtra por extensión;
  `.graph.json` NO se acepta).
- Va en el directorio `graphs/` del repo.
- Está gitignoreado (datos confidenciales) — se copia a mano, nunca se commitea.
- PII (matrículas, nombres): pásalo por `graph_anonymize.py` antes de compartir.

## Mandar por rsync

Destino en la máquina de trabajo (repo del visualizador):

```
<host>:/ruta/al/repo/Node_vizualizer/graphs/
```

Ejemplo (desde donde esté el archivo generado):

```bash
rsync -avP grafo.kgraph.json \
  celestial@192.168.168.63:/home/celestial/src/Node_vizualizer/graphs/
```

En el visualizador: **LOAD EXTERNAL GRAPH** → elegir el archivo, o
`?graph=graphs/grafo.kgraph.json` en la URL.
