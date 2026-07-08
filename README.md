# Graph Visualizer

A 3D force-directed graph that visualizes knowledge graphs and Obsidian notes as an interactive network. Navigate the graph with hand gestures using your webcam — no mouse or controller needed.

Fully standalone — single HTML file, no build step, no npm. Runs entirely in the browser.

## Files

```
Node_visualizer/
  app.html                — the complete app (single file, ~9k lines)
  parquet_to_kbin.py      — edge parquet → binary .kbin (millions scale)
  kgraph_to_kbin.py       — .kgraph.json → .kbin (kills the JSON parse wall)
  parquet_to_kgraph.py    — edge parquet → sampled .kgraph.json
  graph_layout.py         — bake a 3D layout offline (radial / drl / spiral / islands)
  bake_casper_periodos.py — semantic per-period ring layout for Casper graphs
  gen_synthetic_kbin.py   — synthetic .kbin generator (sim stress tests)
  graph_anonymize.py      — strip PII (matrículas / names) across kgraph files
  bench/                  — headless fps + bhtest harness (playwright)
  docs/                   — format notes, physics/layout notes, DGX benchmark
  graphs/                 — data assets (gitignored — see below)
  vendor/                 — MediaPipe, Three.js, fonts (offline)
  README.md · LICENSE
```

> **Data is confidential and NOT versioned.** Everything under `graphs/`
> plus all `*.kgraph.json`, `*.kbin`, and `*.parquet` files are gitignored —
> they hold real student/geographic data. Copy them to a machine by hand
> (rsync/scp), never commit. The only exceptions kept in git are
> `graphs/_test2.kgraph.json` (a 2-node synthetic test fixture) and
> `graphs/INDEX.md`. Before sharing any Casper graph, run
> `graph_anonymize.py` first.

## Quick Start (local machine)

1. Open `app.html` in **Google Chrome** (serve over `localhost`, not raw
   `file://` — or use `launch.command`, which sets the offline flags for you)
2. Two modes:
   - **Notes mode**: Paste a Gemini API key → Select a folder of `.md` files
   - **External graph mode**: Click **LOAD EXTERNAL GRAPH** → pick a
     `.kgraph.json`, `.kbin` (binary, millions scale), or `.html` graph file

## Remote Setup (SSH tunnel)

If the app runs on a remote server (e.g. a GPU machine) and you want to use your **local webcam** for hand tracking, you need an SSH tunnel. The browser requires `localhost` to access the camera (`getUserMedia`).

### Prerequisites on the server

- **Python 3** (pre-installed on most Linux)
- No other dependencies — all libraries (MediaPipe, Three.js, 3d-force-graph, fonts) are
  vendored under `vendor/` and load locally. Graph viewing + hand tracking work fully offline.
  (Notes mode still needs internet: Gemini API for embeddings and `esm.sh` for the UMAP worker.)

### Large graphs — up to millions of nodes

The app renders the full Oaxaca graph (**1.19M nodes / 21.3M edges**) in the
browser. Three scales, three tools:

**1. Millions — binary `.kbin`.** JSON dies at this size (`JSON.parse` needs
the whole file as one string; V8 caps that near 512MB, and objects blow memory
3–5×). The `.kbin` format is typed arrays laid straight over the fetched
ArrayBuffer — no parse, ~206 bytes/node (vs ~1775 for JSON, 8.6× smaller),
node records materialized lazily on interaction, CSR adjacency for 20M-edge
neighbor queries.

```bash
# one-time: python3 -m venv .venv && .venv/bin/pip install duckdb numpy python-igraph
# full graph from an (src,dst,type) edge parquet — no sampling:
.venv/bin/python parquet_to_kbin.py edges.parquet graphs/full.kbin --exclude-types ""
# or convert an existing .kgraph.json (kills the JSON wall):
.venv/bin/python kgraph_to_kbin.py graphs/big.kgraph.json graphs/big.kbin
```

Above 300k nodes the app renders nodes as GPU points (1 vertex each), uploads
a length-sorted edge budget sized to the GPU's `maxBufferSize` (a 4GB-class
card takes all 21.3M edges; a laptop keeps a safe slice), and fades edge
density by zoom. Load a `.kbin` via the file picker or `?graph=graphs/x.kbin`.

**2. Mid-size — bake a layout offline.** For `.kgraph.json` graphs, precompute
3D coords so they load instantly in perf mode (instanced rendering, no live
physics):

```bash
.venv/bin/python graph_layout.py IN.kgraph.json -o OUT.kgraph.json --algo radial
```

`--algo`: `radial` (hubs at core, domains in sectors — reveals semantic
structure; mirrors the in-browser `computeFallbackLayout`), `drl`/`fr`
(igraph force-directed, organic), `spiral`, `sphere`. Disconnected graphs are
laid out per-component and placed on a ring automatically. Perf mode activates
above 8k nodes / 60k edges (`?perf=1|0` overrides).

**3. Physics on open.** Any graph settles into an organic sphere via a WebGPU
grid Barnes-Hut charge (O(N), a 64³→128³ FMM-lite pyramid) that scales to 1M+
nodes. `?sim=0` opts out (opens straight into the baked/fallback layout).
Caveat: graphs with mega-hubs (e.g. Oaxaca's ~110 municipios, each with 100k+
edges) don't form a clean ball — the monopole approximation diverges on
degree-1000+ hubs; the radial layout (`O` key) reads better there.

**Anonymization:** `graph_anonymize.py` replaces student matrículas and
professor names with sequential aliases across a set of kgraph files (shared
mapping). Always run it before sharing any Casper graph.

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
| **Palm** (open hand) | Orbit / rotate — around the selected node when there is one |
| **Point** (index finger) | An on-graph cursor follows your fingertip; hover a node and dwell ~0.5s to select |
| **Pinch** 🤏 (index + thumb) | Instant select of the hovered node |
| **Two hands** | Move apart / together to zoom |
| **Peace** ✌️ (index + middle) | Hold to reset the camera to the full graph |
| **Fist** ✊ (hold ~1.5s) | Pause / resume hand tracking (rest your hand) |

Hand tracking runs on MediaPipe Tasks HandLandmarker (GPU delegate) with a
One Euro landmark filter, rotation-invariant gesture classification, and
adaptive exposure compensation for bright backgrounds. `?legacy=1` forces the
older Pose→crop pipeline; `?crop=0` disables the local-contrast enhancement.

## Keyboard

| Key | Action |
|---|---|
| **G** | Galaxy view: space theme + cycles spiral ↔ sphere (settled physics, cached) |
| **O** | Jump to the file's baked / fallback (radial) layout — the semantic view |
| **B** | Background toggle: white (file's own palette) ↔ deep space |
| **E** | Edge density 100% → 60% → 30% (short edges kept first — cluster view) |
| **+ / −** | Node size — density lever that works at any zoom |
| **H** | Recenter camera |
| **ESC** | Close the detail panel / deselect |

Perf mode also shows **DENSIDAD** and **GRAVEDAD** sliders (bottom center):
node size over the auto-density fit, and the relax centering strength (which
re-settles the sphere live on release).

The camera preview (bottom-left) shows the video feed with hand skeleton overlay so you can verify your hands are in frame.

**URL params:** `?graph=<url>` auto-loads a graph (`.kgraph.json`, `.html`, or
`.kbin`) over HTTP; `?ob=0` skips the gesture onboarding; `?galaxy=1` opens the
galaxy view; `?sim=0` skips the physics-on-open; `?bh=1|0` forces the grid
Barnes-Hut charge on/off; `?maxedges=<n>` overrides the GPU edge budget;
`?bhtest=1` runs the numeric A/B of grid vs exact charge (not with `sim=0`);
`?perf=1|0` forces perf mode; `?points=1|0` forces points vs instanced meshes;
`?debug=1` enables console logging + gesture HUD; `?legacy=1` / `?crop=0`
control the hand-tracking pipeline.

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

- **Binary `.kbin` loader** — typed-array views over the raw ArrayBuffer, no
  JSON.parse; lazy node records; CSR adjacency. Renders 1.19M nodes / 21.3M edges.
- **Points mode** above 300k nodes — 1 vertex/node (63× fewer verts than
  instanced spheres), single draw call, position updates are one buffer flush.
- **GPU edge budget** sized to the adapter's `maxBufferSize`, edges length-sorted
  so the cut drops the longest hairball edges first; density fades by zoom.
- **WebGPU grid Barnes-Hut** charge (O(N)) for the live relax at millions scale.
- Shared geometry, label culling, throttled cluster labels, bloom off at 0.

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
