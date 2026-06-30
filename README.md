# Graph Visualizer

A 3D force-directed graph that visualizes knowledge graphs and Obsidian notes as an interactive network. Navigate the graph with hand gestures using your webcam — no mouse or controller needed.

Fully standalone — single HTML file, no build step, no npm. Runs entirely in the browser.

## Files

```
Node_visualizer/
  app.html                              — the complete app
  kg_nebula_bfs_3500_*.html             — sample external graph (3500 nodes)
  notas-cdmx/                           — sample Obsidian notes dataset
  README.md
  LICENSE
```

## Quick Start (local machine)

1. Open `app.html` in **Google Chrome**
2. Two modes:
   - **Notes mode**: Paste a Gemini API key → Select a folder of `.md` files
   - **External graph mode**: Click **LOAD EXTERNAL GRAPH** → Pick an HTML graph file (like `kg_nebula_bfs_3500_*.html`)

## Remote Setup (SSH tunnel)

If the app runs on a remote server (e.g. a GPU machine) and you want to use your **local webcam** for hand tracking, you need an SSH tunnel. The browser requires `localhost` to access the camera (`getUserMedia`).

### Prerequisites on the server

- **Python 3** (pre-installed on most Linux)
- No other dependencies — all libraries (MediaPipe, Three.js, 3d-force-graph, fonts) are
  vendored under `vendor/` and load locally. Graph viewing + hand tracking work fully offline.
  (Notes mode still needs internet: Gemini API for embeddings and `esm.sh` for the UMAP worker.)

### Large graphs

The browser renderer handles roughly <20k edges. For bigger knowledge graphs, prune first:

```bash
python3 graph_prune.py INPUT.kgraph.json OUTPUT.kgraph.json --min-shared 3
```

`--min-shared N` keeps course nodes shared by ≥N dropout students (lower N = bigger graph).
Add `--include-continua` to also keep continuing students for contrast.

### Step 1: Start the server on the remote machine

```bash
ssh user@192.168.168.97

cd /path/to/Node_visualizer

# Serve with no-cache headers (recommended during development)
python3 -c "
from http.server import HTTPServer, SimpleHTTPRequestHandler
class H(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()
HTTPServer(('0.0.0.0', 9090), H).serve_forever()
"

# Or simply:
# python3 -m http.server 9090 --bind 0.0.0.0
```

### Step 2: Create SSH tunnel from your local machine

```bash
ssh -L 9090:localhost:9090 user@192.168.168.97
```

This forwards your local port 9090 to the server's port 9090.

### Step 3: Open in your local browser

```
http://localhost:9090/app.html
```

Your local webcam will work because the browser sees `localhost` (secure context).

> **Note:** Do NOT use the server's IP directly (e.g. `http://192.168.168.97:9090`) — the camera and some browser APIs require HTTPS or localhost.

## Hand Tracking Gestures

| Gesture | Action |
|---|---|
| **Palm** (open hand) | Orbit / rotate the graph |
| **Point** (index finger) | Navigate nodes — move finger to switch between nodes, hold still to select |
| **Peace** ✌️ (index + middle) | Reset camera — zooms to fit the entire graph |
| **Two hands** | Pinch / spread to zoom |

The camera preview (bottom-left) shows the video feed with hand skeleton overlay so you can verify your hands are in frame.

## Features

### Graph Modes

- **Notes pipeline** — reads `.md`/`.txt` files, embeds with Gemini API, clusters by semantic similarity, renders as 3D network with AI-generated labels
- **External graph import** — loads HTML files with embedded graph data (vis.js format), renders nodes as colored spheres by category

### Visualization

- **3D force-directed layout** — nodes positioned by d3-force simulation
- **Colored spheres by cluster** — each category/domain gets a distinct color
- **Interactive detail panel** — select a node to see its properties, mini connection graph, and metadata
- **Hover info box** — shows node name and type while pointing
- **Two color themes** — switch between Warm and Minimal palettes
- **Bloom post-processing** — configurable via the settings panel

### Performance Optimizations

- No CSS2D labels for external graphs (only colored spheres) — handles 3500+ nodes smoothly
- Shared geometry for node meshes
- Label visibility culling for medium graphs (500+ nodes)
- Throttled cluster label updates
- Bloom pass disabled when strength = 0

### Other

- **IndexedDB caching** — analysis results persist across sessions
- **Onboarding tutorial** — guided hand gesture tutorial on first load
- **Keyboard shortcut** — press `H` to recenter the camera
- **Resizable detail panel** — drag the panel edge to resize

## Requirements

- **Google Chrome** (or Chromium-based: Edge, Brave, Arc) — required for File System Access API and WebGL
- **Webcam** — for hand tracking (optional, mouse navigation also works)
- **Gemini API key** — only needed for Notes mode (free at https://aistudio.google.com/apikey)

## How the Notes Pipeline Works

1. **Scanning** — reads all `.md` files from the selected folder
2. **Embedding** — sends note text to Gemini's `gemini-embedding-001` model
3. **Dimensionality reduction** — projects embeddings into 3D via UMAP
4. **Clustering** — groups notes by semantic similarity using k-means
5. **LLM annotation** — Gemini names each cluster and labels edge relationships
6. **Rendering** — displays the network as an interactive 3D force-directed graph

All processing happens client-side. Your notes are sent only to the Gemini API for embedding — nothing is stored on any server.

## Troubleshooting

| Problem | Solution |
|---|---|
| Camera not working | Make sure you're on `localhost`, not the server IP |
| `getUserMedia` error | Use SSH tunnel (see Remote Setup above) |
| WebGL context lost | Close other tabs using WebGL, reload the page |
| Port already in use | Kill existing server: `lsof -ti:9090 \| xargs kill` |
| Stale cache | Add `?v=N` to URL or use the no-cache server script above |
| Hand tracking unreliable at distance | Move closer to camera, ensure good lighting, avoid busy backgrounds |
