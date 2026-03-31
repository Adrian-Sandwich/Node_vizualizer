# KGraph Format — Standard Graph Exchange

## What is it?

A standard `.kgraph.json` format for storing knowledge graphs independently of HTML wrapping. This allows you to:
- Convert any vis.js or matria HTML export to a portable JSON format
- Load graph files directly into app.html without parsing HTML
- Preserve metadata (domain colors, tag schemas, edge type counts) along with the graph

## Quick Start

### Option 1: Load a Pre-Converted Graph (Easiest) ⚡

1. Open `app.html` in a browser
2. Click "LOAD EXTERNAL GRAPH"
3. Select a `.kgraph.json` file from the `graphs/` folder
4. The graph loads immediately with all metadata intact

**Available graphs in `graphs/` folder:**
- `grafo_muestra_1k.kgraph.json` — 471 nodes, 1,099 edges
- `kg_nebula_bfs_3500_20260113_022814.kgraph.json` — 2,792 nodes, 4,414 edges
- `jerarquia_interactiva.kgraph.json` — 326 nodes, 358 edges
- `knowledge_graph.kgraph.json` — 831 nodes, 1,175 edges

### Option 2: Convert Your Own HTML Graph

```bash
python3 graph_converter.py input_file.html
python3 graph_converter.py input_file.html --pretty    # pretty-print JSON
python3 graph_converter.py input_file.html --force-format kg  # override detection
```

Then load the resulting `.kgraph.json` in app.html via "LOAD EXTERNAL GRAPH".

## Format Specification

### Top-level structure
```json
{
  "format": "kgraph",
  "version": "1.0",
  "meta": { ... },
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

### Node object
```json
{
  "id": "unique_id",
  "label": "display_name",
  "tag": "Person",              // vertex type/tag
  "domain": "demographic",       // domain grouping
  "vid": "original_vertex_id",
  "size": 10,                    // optional size hint
  "tooltip": "<b>HTML</b>...",   // optional tooltip
  "props": {                     // arbitrary properties
    "email": "...",
    "geom": "POINT(...)"
  }
}
```

### Edge object
```json
{
  "from": "node_id_1",
  "to": "node_id_2",
  "type": "HAS_OCCUPATION",          // edge type
  "label_forward": "HAS_OCCUPATION",
  "label_backward": "",              // optional reverse label
  "weight": 1.0                      // optional weight
}
```

### Metadata object
```json
{
  "created_at": "2026-03-31T12:34:56Z",
  "node_count": 1000,
  "edge_count": 5000,
  "domain_colors": {
    "demographic": "#FFA726",
    "commerce": "#EF5350"
  },
  "domain_labels": {
    "demographic": "Demografico",
    "commerce": "Comercio"
  },
  "tag_counts": {
    "Person": 800,
    "Commerce": 200
  },
  "edge_type_counts": {
    "HAS_OCCUPATION": 1200,
    "IN_POSTALCODE": 800
  }
}
```

## Supported HTML Formats

| Format | Detection | Example Files |
|---|---|---|
| **matria** | `var nodesArr` | grafo_muestra_1k.html |
| **visjs** | `new vis.DataSet(` | kg_nebula_bfs_3500.html, jerarquia_interactiva.html |
| **knowledge_graph** | `rawVertices`, `rawEdges` | knowledge_graph.html |
| **magi** | procedural (unsupported) | magi_graph_explorer.html |

## File Size

- **grafo_muestra_1k.html** (471 nodes, 1,099 edges) → 445 KB
- **kg_nebula_bfs_3500.html** (2,792 nodes, 4,414 edges) → 2.2 MB
- **jerarquia_interactiva.html** (326 nodes, 358 edges) → ~100 KB
- **knowledge_graph.html** (831 nodes, 1,175 edges) → ~270 KB

## Implementation Details

### Python Converter (graph_converter.py)

- Uses bracket-depth counting to extract JSON from HTML without executing JavaScript
- Handles escaped quotes and nested structures
- Automatically detects format; supports `--force-format` override
- Palettes edge types and node groups with consistent colors

### app.html Updates

- Line 1005: Updated file input to accept `.html` and `.json`
- Lines 1515–1544: New `parseKGraphFormat()` function
- Lines 1597–1610: JSON detection and routing in `loadExternalGraph()`
- No changes to `mapExternalToInternal()` — the new format maps directly to the existing internal schema

## Testing

All four HTML formats have been successfully converted:

```bash
✓ grafo_muestra_1k.html → 471 nodes, 1099 edges
✓ kg_nebula_bfs_3500.html → 2792 nodes, 4414 edges
✓ jerarquia_interactiva.html → 326 nodes, 358 edges
✓ knowledge_graph.html → 831 nodes, 1175 edges
```

Load any of the generated `.kgraph.json` files in app.html to verify the round-trip is working.
