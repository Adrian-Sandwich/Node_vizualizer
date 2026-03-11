# Topologies of Ideas

A 3D force-directed graph that visualizes your Obsidian notes as an interactive network of ideas. Notes are embedded using the Gemini API, clustered by semantic similarity, and rendered as a navigable 3D space.

Fully standalone — single HTML file, no build step, no server. Runs entirely in the browser.

## Files

```
topologies-of-ideas-v1/
  app.html   — the complete app (open in any browser)
  README.md
  LICENSE
```

## Quick Start

1. Open `app.html` in a modern browser
2. Paste your Gemini API key (get one free at https://aistudio.google.com/apikey)
3. Click **SELECT NOTES FOLDER** and pick your Obsidian vault (or any folder of `.md` files)
4. Wait for the pipeline to embed, cluster, and render your notes

On return visits, click **RESUME PREVIOUS SESSION** to instantly restore your last analysis from the browser cache.

## Features

- **3D force-directed graph** — notes as labeled nodes, semantic connections as edges
- **AI-powered clustering** — automatic grouping via UMAP dimensionality reduction + k-means, with Gemini-generated cluster names
- **Three topology views** — switch between Centralized, Decentralized, and Distributed network layouts
- **Interactive exploration** — click nodes to open a side panel with note preview and connections
- **Edge hover** — hover links to see AI-generated relationship labels between notes
- **Color themes** — switch between Warm and Grey palettes
- **IndexedDB caching** — analysis results persist across sessions so you don't re-run the pipeline every visit
- **Keyboard shortcuts** — press `H` to recenter the camera

## Hand Tracking Navigation

The app includes a hands-free navigation mode powered by MediaPipe Hands — no controller needed, just your webcam.

| Gesture | Action |
|---|---|
| **Palm** (open hand) | Orbit / rotate the graph |
| **Point** (index finger extended) | Hover over nodes; aim at a node and hold to select |
| **Two hands** (both open) | Pinch / spread to zoom |
| **Fist** | Reset camera to default position |

When you first raise your index finger, the nearest node to the screen center is automatically highlighted so navigation starts immediately without having to aim precisely.

Hand tracking activates automatically once the graph is loaded and your webcam is available.

## Example Notes

The `notas-cdmx/` folder contains a sample dataset about the socioeconomic distribution of Mexico City — a good way to see the graph in action without needing your own notes.

## Requirements

- **Google Chrome** (or Chromium-based browsers like Edge) — required for the File System Access API that reads your notes folder. Firefox and Safari do not support this API.
- A Gemini API key (free tier works fine)
- A folder of Markdown notes (`.md` files)

## How It Works

1. **Scanning** — reads all `.md` files from the selected folder
2. **Embedding** — sends note text to Gemini's `gemini-embedding-001` model
3. **Dimensionality reduction** — projects high-dimensional embeddings into 3D via UMAP
4. **Clustering** — groups notes by semantic similarity using k-means
5. **LLM annotation** — Gemini names each cluster and labels edge relationships
6. **Rendering** — displays the network as an interactive 3D force-directed graph

All processing happens client-side. Your notes are sent only to the Gemini API for embedding and annotation — nothing is stored on any server.

## Browser Support

Requires WebGL and the File System Access API. Use Google Chrome or a Chromium-based browser (Edge, Brave, Arc, etc.).
