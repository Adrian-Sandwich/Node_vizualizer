# Graph Library

Pre-converted `.kgraph.json` files ready to load in app.html.

## Available Graphs

### grafo_muestra_1k.kgraph.json
- **Format**: MatrIA (Mexican sociodemographic knowledge graph)
- **Nodes**: 471
- **Edges**: 1,099
- **Domains**: demographic, commerce, spatial, electoral, environment
- **Source**: grafo_muestra_1k.html

### kg_nebula_bfs_3500_20260113_022814.kgraph.json
- **Format**: NebulaGraph (vis.js export)
- **Nodes**: 2,792
- **Edges**: 4,414
- **Types**: Person, CommerceDenue, Commerce, ElectoralSection, Occupation, etc.
- **Source**: kg_nebula_bfs_3500_20260113_022814.html

### grafo_muestra_matria.kgraph.json
- **Format**: MatrIA (Mexican sociodemographic knowledge graph)
- **Nodes**: 9,181
- **Edges**: 25,453
- **Domains**: spatial, environment, demographic, electoral, commerce, metrics, apps, personality, worship, health, poverty, crime
- **Source**: grafo_muestra_matria.html

### jerarquia_interactiva.kgraph.json
- **Format**: Hierarchy/Taxonomy
- **Nodes**: 326
- **Edges**: 358
- **Structure**: Parent-child relationships, no explicit domains
- **Source**: jerarquia_interactiva (2).html

### knowledge_graph.kgraph.json
- **Format**: Knowledge Graph (Education/Learning system)
- **Nodes**: 831
- **Edges**: 1,175
- **Types**: profesor, estudiante, curso, tema, assignment
- **Source**: knowledge_graph.html

## How to Load

1. Open `app.html` in a web browser
2. Click "LOAD EXTERNAL GRAPH"
3. Select any `.kgraph.json` file from this folder
4. The graph renders with all metadata (colors, types, properties) intact

## Convert Your Own

To convert an HTML graph file to `.kgraph.json`:

```bash
python3 ../graph_converter.py your_graph.html
```

The converter supports:
- **matria** format (`var nodesArr`)
- **visjs** format (`new vis.DataSet()`)
- **knowledge_graph** format (`rawVertices`/`rawEdges`)

Then move the generated `.kgraph.json` to this folder.
