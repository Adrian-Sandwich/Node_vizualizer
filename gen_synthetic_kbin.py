#!/usr/bin/env python3
"""Genera un .kbin sintético para probar el límite de nodos del sim (paso 4).

Formato KBN1 idéntico al de parquet_to_kbin.py del repo:
  magic 'KBN1' | u32 nodeCount | u32 edgeCount | u32 metaLen | meta JSON
  f32 positions ×3N | u8 domainIdx ×N | u32 idOffsets ×N+1 | u32 idBlobLen
  bytes id blob | u32 edgeSrc ×E | u32 edgeDst ×E | u8 edgeType ×E
  (aristas ordenadas por longitud 3D ascendente)

Uso: python3 gen_synthetic_kbin.py <nodos> <aristas> <salida.kbin>
"""
import json
import struct
import sys

import numpy as np

N = int(sys.argv[1])
E = int(sys.argv[2])
OUT = sys.argv[3]

rng = np.random.default_rng(42)

# Posiciones: esfera uniforme radio 1400 (como el layout del viewer)
r = 1400.0 * np.cbrt(rng.random(N, dtype=np.float64))
costh = rng.uniform(-1, 1, N)
sinth = np.sqrt(1 - costh * costh)
phi = rng.uniform(0, 2 * np.pi, N)
pos = np.empty((N, 3), dtype=np.float32)
pos[:, 0] = r * sinth * np.cos(phi)
pos[:, 1] = r * sinth * np.sin(phi)
pos[:, 2] = r * costh

DOMAINS = ["SynthA", "SynthB", "SynthC", "SynthD"]
dom = rng.integers(0, len(DOMAINS), N, dtype=np.uint8)

# Aristas: mitad cadena local (i, i+delta corto), mitad aleatorias
half = E // 2
src1 = rng.integers(0, N - 8, half, dtype=np.uint32)
dst1 = src1 + rng.integers(1, 8, half).astype(np.uint32)
src2 = rng.integers(0, N, E - half, dtype=np.uint32)
dst2 = rng.integers(0, N, E - half, dtype=np.uint32)
src = np.concatenate([src1, src2])
dst = np.concatenate([dst1, dst2])
keep = src != dst
src, dst = src[keep], dst[keep]

# Orden por longitud 3D ascendente (requisito del formato)
d = pos[src.astype(np.int64)] - pos[dst.astype(np.int64)]
lengths = np.einsum("ij,ij->i", d, d)
order = np.argsort(lengths, kind="stable")
src, dst = src[order], dst[order]
etype = np.zeros(len(src), dtype=np.uint8)

# IDs compactos "s0".."sN-1"
ids = [f"s{i}".encode() for i in range(N)]
offsets = np.zeros(N + 1, dtype=np.uint32)
offsets[1:] = np.cumsum([len(b) for b in ids]).astype(np.uint32)
blob = b"".join(ids)

meta = json.dumps({
    "domains": DOMAINS,
    "domainColors": {d_: c for d_, c in zip(DOMAINS, ["#66d9ff", "#7b8cff", "#b07bff", "#ff7bd5"])},
    "edgeTypes": ["SYNTH"],
    "edgeTypeCounts": {"SYNTH": int(len(src))},
    "source": {"generator": "gen_synthetic_kbin.py", "purpose": "step4 >2M nodes"},
}).encode()

def pad4(b: bytes) -> bytes:
    return b + b"\x00" * (-len(b) % 4)


with open(OUT, "wb") as f:
    f.write(b"KBN1")
    f.write(struct.pack("<III", N, len(src), len(meta)))
    f.write(pad4(meta))
    f.write(pos.astype("<f4").tobytes())
    f.write(pad4(dom.tobytes()))
    f.write(offsets.astype("<u4").tobytes())
    f.write(struct.pack("<I", len(blob)))
    f.write(pad4(blob))
    f.write(src.astype("<u4").tobytes())
    f.write(dst.astype("<u4").tobytes())
    f.write(pad4(etype.tobytes()))

print(f"OK {OUT}: {N} nodos, {len(src)} aristas")
