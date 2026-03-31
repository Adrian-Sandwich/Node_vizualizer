#!/usr/bin/env python3
"""
Convert graph HTML files to standard .kgraph.json format.

Supports:
  - matria format (var nodesArr, var edgesArr with metadata)
  - visjs format (nodes = new vis.DataSet([...]), edges = new vis.DataSet([...]))
  - knowledge_graph format (rawVertices, rawEdges with transform step)
  - magi format (procedural/synthetic — not supported)
"""

import re
import json
import sys
import argparse
import pathlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


class KGraphBuilder:
    """Assembles the final .kgraph.json output object."""

    def __init__(self, nodes: List[Dict], edges: List[Dict], meta_source: Dict[str, Any]):
        self.nodes = nodes
        self.edges = edges
        self.meta_source = meta_source

    def build(self) -> Dict[str, Any]:
        """Build the final kgraph object with metadata."""
        source = self.meta_source

        # Handle both UPPERCASE and lowercase keys from different sources
        def get_meta(key_upper: str, key_lower: str):
            return source.get(key_upper) or source.get(key_lower) or {}

        return {
            "format":  "kgraph",
            "version": "1.0",
            "meta": {
                "created_at":        datetime.now().isoformat() + 'Z',
                "node_count":        len(self.nodes),
                "edge_count":        len(self.edges),
                "domain_colors":     get_meta('DOMAIN_COLORS', 'domain_colors'),
                "domain_labels":     get_meta('DOMAIN_LABELS', 'domain_labels'),
                "domain_map":        get_meta('DOMAIN_MAP', 'domain_map'),
                "tag_schema":        get_meta('TAG_SCHEMA', 'tag_schema'),
                "tag_counts":        get_meta('TAG_COUNTS', 'tag_counts'),
                "edge_type_counts":  get_meta('EDGE_TYPE_COUNTS', 'edge_type_counts'),
                "edge_type_colors":  get_meta('EDGE_TYPE_COLORS', 'edge_type_colors'),
            },
            "nodes": self.nodes,
            "edges": self.edges,
        }


# ============================================================================
# JSON Extraction Helpers
# ============================================================================

def _extract_json_value(text: str, start: int) -> str:
    """Extract a balanced JSON value (array or object) starting at position start.

    Uses bracket/brace depth tracking to find the end of the JSON value.
    Handles string escaping to avoid counting brackets inside strings.
    """
    i = start
    # Skip leading whitespace
    while i < len(text) and text[i] in ' \t\n\r':
        i += 1
    if i >= len(text):
        return ''

    opener = text[i]
    closer = {'{': '}', '[': ']'}.get(opener)

    if closer is None:
        # Primitive (string, number, boolean, null) — read to semicolon or comma
        end = text.find(';', i)
        if end == -1:
            end = text.find(',', i)
        return text[i:end] if end > i else text[i:]

    # Track bracket/brace depth
    depth = 1
    in_str = False
    escape = False
    j = i + 1

    while j < len(text):
        c = text[j]

        if escape:
            escape = False
        elif c == '\\' and in_str:
            escape = True
        elif c == '"' and not escape:
            in_str = not in_str
        elif not in_str:
            if c in '{[':
                depth += 1
            elif c in '}]':
                depth -= 1
                if depth == 0:
                    return text[i:j+1]
        j += 1

    return text[i:]


def _extract_js_var(html_text: str, varname: str) -> Any:
    """Extract a JavaScript variable value as a Python object.

    Looks for patterns like: var VARNAME = <json_value>;
    Returns parsed JSON, or empty list/dict if not found.
    """
    pattern = rf'(var\s+)?{re.escape(varname)}\s*=\s*'
    m = re.search(pattern, html_text)
    if not m:
        return [] if 'Arr' in varname or varname.startswith('raw') else {}

    start = m.end()
    value_str = _extract_json_value(html_text, start)

    try:
        return json.loads(value_str)
    except json.JSONDecodeError as e:
        print(f"WARNING: Failed to parse {varname}: {e}", file=sys.stderr)
        return [] if varname.endswith('Arr') else {}


def _extract_vis_dataset(html_text: str, varname: str) -> List[Dict]:
    """Extract a vis.DataSet([...]) array by parsing bracket-balanced JSON.

    Looks for: varname = new vis.DataSet([...])
    Returns the parsed array, or empty list if not found.
    """
    # Match either "var varname = new vis.DataSet(" or "varname = new vis.DataSet("
    patterns = [
        rf'var\s+{re.escape(varname)}\s*=\s*new\s+vis\.DataSet\s*\(',
        rf'{re.escape(varname)}\s*=\s*new\s+vis\.DataSet\s*\(',
    ]

    for pattern in patterns:
        m = re.search(pattern, html_text)
        if m:
            start = m.end()
            # Skip to the opening bracket/brace that starts the data
            while start < len(html_text) and html_text[start] in ' \t\n\r':
                start += 1
            if start < len(html_text) and html_text[start] in '[{':
                value_str = _extract_json_value(html_text, start)
                try:
                    return json.loads(value_str)
                except json.JSONDecodeError as e:
                    print(f"WARNING: Failed to parse {varname}: {e}", file=sys.stderr)
                    return []

    return []


# ============================================================================
# Format Detection
# ============================================================================

def detect_format(html_text: str) -> str:
    """Detect the graph format based on keywords in the HTML."""
    if 'var nodesArr' in html_text:
        return 'matria'
    if 'rawVertices' in html_text or 'rawEdges' in html_text:
        return 'kg'
    if 'new vis.DataSet(' in html_text:
        return 'visjs'
    return 'unknown'


# ============================================================================
# Node/Edge Mapping Helpers
# ============================================================================

def _map_matria_node(n: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a matria-format node to kgraph format."""
    # Exclude vis.js rendering fields
    skip = {'id', 'label', 'shape', 'group', 'color', 'size', 'font',
            'borderWidth', '_tag', '_domain', '_vid', '_tooltip'}
    props = {k: v for k, v in n.items()
             if k not in skip and not isinstance(v, dict) and v is not None}

    return {
        'id':      n['id'],
        'label':   n.get('label', n['id']),
        'tag':     n.get('_tag') or n.get('group', 'Unknown'),
        'domain':  n.get('_domain') or n.get('group', 'default'),
        'vid':     n.get('_vid', n['id']),
        'size':    n.get('size', 10),
        'tooltip': n.get('_tooltip', ''),
        'props':   props,
    }


def _map_matria_edge(e: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a matria-format edge to kgraph format."""
    return {
        'from':           e['from'],
        'to':             e['to'],
        'type':           e.get('_edgeType', 'UNKNOWN'),
        'label_forward':  e.get('_edgeType', 'UNKNOWN'),
        'label_backward': '',
        'weight':         1.0,
    }


def _infer_group_from_color(node: Dict[str, Any]) -> Optional[str]:
    """Try to infer the node group from its color field."""
    color = node.get('color')
    if isinstance(color, dict):
        color = color.get('background')
    # Return the color hex as a pseudo-group for now; we'll build the palette
    if isinstance(color, str) and color.startswith('#'):
        return color
    return None


def _count_by_key(items: List[Dict], key: str) -> Dict[str, int]:
    """Count occurrences of each value for a given key."""
    counts = {}
    for item in items:
        val = item.get(key)
        if val:
            counts[val] = counts.get(val, 0) + 1
    return counts


# ============================================================================
# Format Converters
# ============================================================================

def convert_matria(html_text: str) -> Dict[str, Any]:
    """Convert matria format (var nodesArr, var edgesArr, etc.)."""
    # Extract all metadata variables
    extracted = {}
    for var in ['nodesArr', 'edgesArr', 'DOMAIN_COLORS', 'DOMAIN_LABELS',
                'DOMAIN_MAP', 'TAG_SCHEMA', 'TAG_COUNTS', 'EDGE_TYPE_COUNTS',
                'EDGE_TYPE_COLORS']:
        extracted[var] = _extract_js_var(html_text, var)

    nodes_raw = extracted.get('nodesArr', [])
    edges_raw = extracted.get('edgesArr', [])

    nodes = [_map_matria_node(n) for n in nodes_raw]
    edges = [_map_matria_edge(e) for e in edges_raw]

    return KGraphBuilder(nodes, edges, extracted).build()


def convert_visjs(html_text: str) -> Dict[str, Any]:
    """Convert visjs format (new vis.DataSet for nodes and edges)."""
    nodes_raw = _extract_vis_dataset(html_text, 'nodes')
    edges_raw = _extract_vis_dataset(html_text, 'edges')

    # Build domain colors from node groups or colors
    domain_colors = {}
    PALETTE = ['#42A5F5', '#66BB6A', '#FFA726', '#EF5350', '#AB47BC',
               '#26C6DA', '#9CCC65', '#78909C', '#EC407A', '#8D6E63']
    ci = 0

    for n in nodes_raw:
        grp = n.get('group')
        if not grp:
            grp = _infer_group_from_color(n)
        if not grp:
            grp = 'Unknown'
        n['_resolved_group'] = grp

        if grp not in domain_colors:
            raw_color = n.get('color')
            if isinstance(raw_color, str) and raw_color.startswith('#'):
                domain_colors[grp] = raw_color
            elif isinstance(raw_color, dict):
                domain_colors[grp] = raw_color.get('background', PALETTE[ci % len(PALETTE)])
            else:
                domain_colors[grp] = PALETTE[ci % len(PALETTE)]
            ci += 1

    nodes = [{
        'id':      n['id'],
        'label':   n.get('label', str(n['id'])),
        'tag':     n['_resolved_group'],
        'domain':  n['_resolved_group'],
        'vid':     n['id'],
        'size':    n.get('size', 10),
        'tooltip': n.get('title', ''),
        'props':   {},
    } for n in nodes_raw]

    edge_type_counts = {}
    edges = []
    for e in edges_raw:
        etype = e.get('title') or 'UNKNOWN'  # visjs uses 'title' for edge type
        edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1
        edges.append({
            'from':           e['from'],
            'to':             e['to'],
            'type':           etype,
            'label_forward':  etype,
            'label_backward': '',
            'weight':         float(e.get('width', 1)),
        })

    meta_extras = {
        'domain_colors':     domain_colors,
        'domain_labels':     {g: g for g in domain_colors},
        'edge_type_counts':  edge_type_counts,
        'tag_counts':        _count_by_key(nodes, 'tag'),
    }

    return KGraphBuilder(nodes, edges, meta_extras).build()


def convert_knowledge_graph(html_text: str) -> Dict[str, Any]:
    """Convert knowledge_graph format (rawVertices + rawEdges)."""
    vertices_raw = _extract_js_var(html_text, 'rawVertices')
    edges_raw = _extract_js_var(html_text, 'rawEdges')

    if not vertices_raw:
        vertices_raw = []
    if not edges_raw:
        edges_raw = []

    # Build domain colors from unique tags
    domain_colors = {}
    PALETTE = ['#42A5F5', '#66BB6A', '#FFA726', '#EF5350', '#AB47BC',
               '#26C6DA', '#9CCC65', '#78909C', '#EC407A', '#8D6E63']
    ci = 0
    for v in vertices_raw:
        tag = v.get('tag', 'Unknown')
        if tag not in domain_colors:
            domain_colors[tag] = PALETTE[ci % len(PALETTE)]
            ci += 1

    nodes = [{
        'id':      v['vid'],
        'label':   v.get('props', {}).get('name', v['vid']),
        'tag':     v.get('tag', 'Unknown'),
        'domain':  v.get('tag', 'Unknown'),
        'vid':     v['vid'],
        'size':    10,
        'tooltip': '',
        'props':   {k: str(val) for k, val in (v.get('props') or {}).items()
                    if val is not None},
    } for v in vertices_raw]

    edge_type_counts = {}
    edges = []
    for e in edges_raw:
        etype = e.get('type', 'UNKNOWN')
        edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1
        edges.append({
            'from':           e['src'],
            'to':             e['dst'],
            'type':           etype,
            'label_forward':  etype,
            'label_backward': '',
            'weight':         1.0,
        })

    meta_extras = {
        'domain_colors':    domain_colors,
        'domain_labels':    {g: g for g in domain_colors},
        'edge_type_counts': edge_type_counts,
        'tag_counts':       _count_by_key(nodes, 'tag'),
    }

    return KGraphBuilder(nodes, edges, meta_extras).build()


def convert_magi(html_text: str) -> Dict[str, Any]:
    """Magi format is procedurally generated — not supported."""
    raise NotImplementedError(
        "magi_graph_explorer.html generates synthetic data at runtime. "
        "There is no static data to extract. "
        "To convert it, please use the app to generate and export the graph."
    )


# ============================================================================
# Main Converter Dispatcher
# ============================================================================

def convert_file(input_path: pathlib.Path, force_format: Optional[str] = None) -> Dict[str, Any]:
    """Load an HTML graph file and convert it to kgraph format."""
    html_text = input_path.read_text(encoding='utf-8')

    fmt = force_format or detect_format(html_text)
    print(f'[graph_converter] Format detected: {fmt}', file=sys.stderr)

    converters = {
        'matria': convert_matria,
        'visjs':  convert_visjs,
        'kg':     convert_knowledge_graph,
        'magi':   convert_magi,
    }

    if fmt not in converters:
        raise ValueError(
            f'Unknown format "{fmt}". Available: {", ".join(converters.keys())}. '
            f'Use --force-format to override.'
        )

    return converters[fmt](html_text)


# ============================================================================
# CLI
# ============================================================================

def main():
    """Command-line interface for graph conversion."""
    parser = argparse.ArgumentParser(
        description='Convert HTML graph files to .kgraph.json format.'
    )
    parser.add_argument('input', help='Input HTML graph file')
    parser.add_argument('output', nargs='?',
                        help='Output .kgraph.json file (default: replace .html with .kgraph.json)')
    parser.add_argument('--pretty', action='store_true',
                        help='Pretty-print JSON output (indent=2)')
    parser.add_argument('--force-format', choices=['matria', 'visjs', 'kg', 'magi'],
                        help='Override automatic format detection')

    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f'ERROR: Input file not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    output_path = pathlib.Path(args.output) if args.output else \
                  input_path.with_suffix('.kgraph.json')

    try:
        result = convert_file(input_path, args.force_format)

        indent = 2 if args.pretty else None
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=indent),
            encoding='utf-8'
        )

        meta = result['meta']
        print(f'[graph_converter] ✓ Converted {meta["node_count"]} nodes, '
              f'{meta["edge_count"]} edges → {output_path}', file=sys.stderr)

    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
