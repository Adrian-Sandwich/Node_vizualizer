# Contrato de grafos — Node Visualizer

Estándar OBLIGATORIO para todo grafo que consuma el visualizador. Un grafo que
no cumpla este contrato se rechaza. Verificación mecánica:

```bash
python3 validate_graph.py <archivo>   # exit 0 = aceptado
```

Dos formatos aceptados:

| Formato | Extensión | Cuándo |
|---|---|---|
| kgraph JSON | `*.kgraph.json` (exacto — el picker filtra por extensión) | < ~250k nodos |
| kbin binario | `*.kbin` | ≥ ~250k nodos, o cuando el JSON pasa de ~200MB |

Umbral duro: el JSON pesa ~1775 bytes/nodo; a ~450MB revienta el `JSON.parse`
del navegador. El kbin pesa ~206 bytes/nodo. Límite absoluto de ambos:
**4,000,000 nodos** (presupuesto fixed-point del Barnes-Hut GPU — el sim lanza
error arriba de eso).

---

## 1. Formato `*.kgraph.json`

### 1.1 Estructura top-level (todas obligatorias)

```json
{
  "format": "kgraph",
  "version": "1.0",
  "meta":   { ... },
  "nodes":  [ ... ],
  "edges":  [ ... ]
}
```

- `format` — string exacto `"kgraph"`. El loader rechaza cualquier otro valor.
- `version` — string `"1.0"`. (No entero `1`: un aprobado viejo lo trae así y
  funciona, pero el estándar es string.)
- Encoding del archivo: **UTF-8**. JSON estricto: sin `NaN`, sin `Infinity`,
  sin comentarios, sin trailing commas.

### 1.2 `nodes[]` — campos por nodo

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `id` | string | **SÍ** | Único en todo el archivo. No vacío. La llave que referencian las aristas. Solo ASCII imprimible (ver §1.6). |
| `label` | string | recomendado | Texto mostrado. Default: el `id`. Cortar a ~40 chars — labels kilométricos ensucian el render. |
| `tag` | string | recomendado | Subtipo fino (panel de detalle). Default `"Unknown"`. |
| `domain` | string | **SÍ**\* | Categoría/cluster. **DEBE ser llave de `meta.domain_colors`** — si no, el nodo cae a gris default. \*Omitirlo = dominio `"default"`, que entonces debe tener color. |
| `vid` | string | opcional | Id "de negocio" original. Default: el `id`. |
| `size` | número | recomendado | Escala visual. Rango sano observado en aprobados: 4–30. Default 10. NO strings. |
| `tooltip` | string | opcional | Texto al pasar el cursor. |
| `props` | objeto | opcional | `{clave: valor}` libre, mostrado en panel de detalle. **Ver restricción crítica §1.5.** |
| `x`, `y`, `z` | número | opcional | Coords 3D horneadas. Regla todo-o-nada: ver §1.4. |

### 1.3 `edges[]` — campos por arista

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `from` | string | **SÍ** | DEBE coincidir EXACTO (case-sensitive) con un `nodes[].id`. |
| `to` | string | **SÍ** | Ídem. |
| `type` | string | recomendado | Etiqueta de la relación. Agrupa/colorea aristas. **Máx 255 tipos distintos** en todo el archivo (u8 en kbin). |
| `label_forward` | string | opcional | Texto de la relación A→B. Fallback de `type`. |
| `label_backward` | string | opcional | Texto B→A. Puede ir vacío. |
| `weight` | número | opcional | Default 1.0. Float. |

**Aristas colgadas (extremo que no existe en `nodes`) = grafo rechazado.**
El visualizador las descarta en silencio (render y física), pero "en silencio"
es exactamente cómo llega basura: si tu generador produce colgadas, tiene un
bug — arréglalo en la fuente, no confíes en el descarte.

Self-loops (`from == to`): permitidos pero inútiles (no aportan al layout ni
al render). El validador los reporta como warning; mejor no emitirlos.

Aristas duplicadas (mismo from/to/type): no rompen pero duplican fuerza de
spring y peso visual. Warning; deduplica en la fuente.

### 1.4 Coordenadas horneadas (`x`/`y`/`z`) — regla todo-o-nada

Dos estados válidos, nada intermedio:

1. **Sin coords** (recomendado por default): NINGÚN nodo trae `x`/`y`/`z`.
   El visualizador calcula el layout radial semántico (hubs al centro,
   dominios en sectores) — casi siempre mejor que coords inventadas.
   **NO inventes coords.** Coords random/grid/ceros = grafo basura clásico.
2. **Bake completo**: TODOS los nodos traen `x`, `y`, `z` finitos (los tres,
   no dos). Origen legítimo: `graph_layout.py --algo radial|drl`, o un layout
   real calculado aguas arriba. Escala convención del repo: normalizado a
   radio ~1400 (`graph_layout.py normalize`). Otras escalas funcionan (la
   cámara se auto-encuadra) pero mantén proporciones sanas: nada de un nodo
   en 1e9.

El detector interno (`hasBakedLayout`) exige ≥95% de nodos con coords finitas
para tratar el archivo como horneado. Entre 1% y 94% = zona basura: ni layout
propio ni bake usable. El validador lo rechaza.

### 1.5 `props` — restricción crítica

El loader hace spread de `props` SOBRE el registro del nodo
(`app.html`, `...n.props` al final del objeto). Consecuencia: una llave de
`props` llamada como campo estructural **PISA ese campo**. `props.id`
sobreescribe el id del nodo → todas sus aristas quedan colgadas. Basura
silenciosa garantizada.

**Llaves PROHIBIDAS dentro de `props`**:
`id`, `label`, `tag`, `domain`, `vid`, `size`, `tooltip`, `x`, `y`, `z`,
y cualquier llave que empiece con `_` (namespace interno del visualizador:
`_tag`, `_domain`, `_vid`, `_tooltip`, `_x`, `_y`, `_z`, `_rawProps`…).

Valores de `props`: strings/números/bools. Objetos anidados se muestran feos
en el panel; aplánalos (`"escuela.nombre": "X"`).

### 1.6 IDs — reglas

- **Únicos** (duplicado = rechazo).
- **No vacíos**, tipo string SIEMPRE (no números: `"7"` sí, `7` no).
- **ASCII imprimible recomendado.** Motivo técnico: si el grafo se convierte a
  kbin, la búsqueda de nodos es binaria con comparación de strings JS
  (UTF-16) contra orden Python (codepoints) — coinciden en ASCII, pueden
  divergir fuera del BMP. Emojis/acentos en `label` y `tooltip`: sin problema.
- **Convención de prefijo `TIPO::resto`** (`EST::S003708`,
  `Person::61723f7d`): opcional pero recomendada. El visualizador la usa como
  fallback de dominio y para acortar el nombre mostrado en kbin.
- **Orden**: si el archivo va a convertirse a kbin, los nodos deben ir
  **ordenados ascendente por `id`** (orden de bytes UTF-8). El parser kbin
  busca por bisección; ids desordenados = búsqueda/panel de detalle rotos EN
  SILENCIO. Para JSON puro es solo warning; para kbin es error duro.
  (Nota: `parquet_to_kbin.py` ordena solo; `kgraph_to_kbin.py` HOY preserva
  el orden del JSON — ordena tu JSON antes de convertir.)

### 1.7 `meta` — campos

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `domain_colors` | `{dominio: "#hex"}` | **SÍ** | Define QUÉ dominios existen, su color, y la leyenda. **El ORDEN de las llaves define el `cluster_id`** de cada dominio — orden estable, no lo barajees entre versiones del mismo grafo. Todo `domain` usado en `nodes` debe estar aquí. Máx **255 dominios** (u8 en kbin). Formato color: `#rrggbb`. |
| `domain_labels` | `{dominio: "texto"}` | recomendado | Nombres bonitos para la leyenda. Default: el nombre del dominio. |
| `node_count` | int | recomendado | DEBE cuadrar con `len(nodes)` si está presente. |
| `edge_count` | int | recomendado | Ídem con `len(edges)`. |
| `edge_type_counts` | `{tipo: int}` | opcional | Readout por tipo de arista. |
| `edge_type_colors` | `{tipo: "#hex"}` | opcional | Colores por tipo de arista. |
| `domain_map` | `{tag: dominio}` | opcional | Mapeo tag→dominio (informativo). |
| `tag_schema` | `[string]` | opcional | Tags existentes. |
| `tag_counts` | `{tag: int}` | opcional | Conteos por tag. |
| `created_at` | string ISO-8601 | recomendado | Timestamp de generación. |
| `title`, `note`, `source` | string | opcional | Contexto humano. `note` es EL lugar para avisos de modelado (ej. "los periodos son islas — el modelo no conecta semestres"). |
| `layout` | string u objeto | opcional | Qué algoritmo horneó las coords. String (`"radial"`, `"drl"`) u objeto `{"algorithm", "radius", "seed", "computed_at"}` como lo escriben `graph_layout.py`/`bake_casper_periodos.py`. Solo si hay coords. |
| `anonymized` | bool | recomendado si aplica | Ver §3. |

### 1.8 Ejemplo mínimo válido

```json
{
  "format": "kgraph",
  "version": "1.0",
  "meta": {
    "created_at": "2026-07-09T12:00:00Z",
    "node_count": 2,
    "edge_count": 1,
    "domain_colors": { "Bug": "#ef476f", "Proyecto": "#66d9ff" },
    "domain_labels": { "Bug": "Bug", "Proyecto": "Proyecto" }
  },
  "nodes": [
    { "id": "BUG-1", "label": "Login rompe", "tag": "Bug", "domain": "Bug",
      "size": 8, "tooltip": "BUG-1 · severidad alta",
      "props": { "estado": "PENDIENTE" } },
    { "id": "PROJ-3", "label": "Portal", "tag": "Proyecto", "domain": "Proyecto",
      "size": 14, "props": {} }
  ],
  "edges": [
    { "from": "BUG-1", "to": "PROJ-3", "type": "PERTENECE_A",
      "label_forward": "pertenece a", "label_backward": "", "weight": 1.0 }
  ]
}
```

---

## 2. Formato `*.kbin`

Binario little-endian. Generar SIEMPRE con los converters del repo
(`kgraph_to_kbin.py` desde un kgraph válido, `parquet_to_kbin.py` desde
parquet) — no escribas el binario a mano salvo que implementes el layout
byte a byte:

```
offset  tipo        contenido
0       char[4]     magic "KBN1"
4       u32         N (node count)
8       u32         E (edge count)
12      u32         metaLen (bytes del JSON de meta, sin padding)
16      bytes       meta JSON UTF-8, padded a múltiplo de 4 con \x00
...     f32 × 3N    posiciones x,y,z por nodo (SIEMPRE presentes)
...     u8 × N      domainIdx por nodo (índice en meta.domains), padded a 4
...     u32 × (N+1) idOffsets (offsets acumulados al blob de ids; [0]=0)
...     u32         blobLen
...     bytes       id blob UTF-8 concatenado, padded a 4
...     u32 × E     edgeSrc (índice de nodo)
...     u32 × E     edgeDst
...     u8 × E      edgeTypeIdx (índice en meta.edgeTypes), padded a 4
EOF     — el parser exige que el archivo termine EXACTO aquí: bytes de sobra
          o faltantes = rechazo.
```

`meta` JSON (llaves camelCase, distinto del kgraph):

| Llave | Tipo | Requerido | Regla |
|---|---|---|---|
| `domains` | `[string]` | **SÍ** | Nombres de dominio; `domainIdx` indexa aquí. Máx 255. |
| `domainColors` | `{dominio: "#hex"}` | **SÍ** | Color por dominio. |
| `edgeTypes` | `[string]` | **SÍ** | `edgeTypeIdx` indexa aquí. Máx 255. |
| `edgeTypeCounts` | `{tipo: int}` | recomendado | |
| `layout` | string | **SÍ** | `"baked"` (coords reales), `"fallback"` (placeholder espiral — el navegador recalcula el radial al cargar), `"radial"`, `"spiral"`. |
| `source` | `{from, createdAt}` | recomendado | Procedencia. |

Invariantes duros (el validador los verifica):

- **Ids ordenados ascendente** (orden bytes UTF-8) — la búsqueda es binaria.
- Todo `domainIdx[i] < len(domains)`; todo `edgeSrc/edgeDst < N`.
- Posiciones finitas (sin NaN/Inf). El kbin no tiene estado "sin coords":
  si no hay layout real, se hornea placeholder y se marca `layout:"fallback"`.
- **Aristas ordenadas por longitud 3D ascendente** — la densidad de aristas
  (tecla E, calidad adaptiva) corta por `drawRange`: cortas primero = look de
  clusters. Desordenadas no rompen, pero el corte de densidad queda aleatorio
  (warning).
- N ≤ 4,000,000.

Nota de render: por encima del presupuesto de la GPU (5M–24M según
`maxBufferSize`), las aristas excedentes no se suben — otra razón para
ordenarlas por longitud (se pierden las largas, no las estructurales).

---

## 3. Datos sensibles (PII)

Grafos con matrículas, nombres, emails, direcciones: pasar por
`graph_anonymize.py` ANTES de compartir/subir. Marcar `meta.anonymized: true`.
Los archivos de `graphs/` están gitignoreados — se copian a mano, NUNCA se
commitean.

---

## 4. Nombre, ubicación, entrega

- Extensión exacta `.kgraph.json` o `.kbin`. (`.graph.json`, `.json` a secas:
  el picker NO los acepta.)
- Nombre: `snake_case`, descriptivo, con sufijo de layout si aplica:
  `casper_real_completo_layout.kgraph.json`.
- Destino: `graphs/` del repo. Aprobados: `graphs/aproved/`.
- Carga: botón **LOAD EXTERNAL GRAPH**, o URL `?graph=graphs/foo.kgraph.json`.

---

## 5. Checklist de aceptación (gate)

Un grafo se ACEPTA solo si:

1. `python3 validate_graph.py archivo` → exit 0.
2. Cero errores. Warnings revisados y justificados (ej. self-loops que el
   modelo realmente contiene).
3. Carga visual de humo: abrir en el visualizador, verificar que la leyenda
   muestra los dominios esperados, que el panel de detalle abre un nodo
   arbitrario, y que O (bake) / G (galaxy) no dejan pantalla vacía.

Reglas que más basura han dejado pasar (aprender de la historia):

- Aristas apuntando a ids que no existen (typos, prefijos inconsistentes
  `EST::x` vs `est::x`).
- `props` con llave `id`/`size` pisando campos estructurales.
- Coords horneadas parciales o inventadas (random/ceros).
- Dominios usados sin entrada en `domain_colors` → nodos grises.
- Ids numéricos (`7` en vez de `"7"`) → llaves que no cruzan.
- kbin generado de JSON con ids desordenados → búsqueda rota silenciosa.
