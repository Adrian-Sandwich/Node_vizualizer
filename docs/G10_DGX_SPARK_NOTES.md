# Notas: escala de millones en DGX Spark (GB10) — 2026-07-06

Corrida de `feature/millions-scale` sobre una **DGX Spark** (GPU NVIDIA **GB10**,
aarch64, 128 GB unificados) para probar los límites reales del visualizador,
migrando desde el MacBook original. Resumen de qué funcionó, qué no, y qué
reintentar cuando haya hardware de gráficos convencional.

> **PII**: los grafos `graphs/casper_real_*.kgraph.json` contienen matrículas.
> NUNCA se versionan (están en `.git/info/exclude`). Los `.kbin` grandes
> (`oax_full`, `oax_all`, sintéticos) también quedan fuera de git — se copian a mano.

## La caja (lo importante de la arquitectura)

La DGX Spark viene **compute-only de fábrica**: trae todo el stack CUDA pero
NO el userspace gráfico de NVIDIA (sin `libGLX/EGL_nvidia`, sin ICD de Vulkan).
El escritorio arranca sobre un **framebuffer simple** por software.

- El WebGPU/WebGL del navegador en Linux corre sobre el userspace de NVIDIA
  (EGL/Vulkan), así que **sin instalarlo no hay GPU en el navegador**.
- Instalar `libnvidia-gl-580` a secas **rompe el stack**: mete userspace
  580.159 contra un módulo de kernel 580.126 en memoria (mismatch → `nvidia-smi`
  muere). El único combo consistente para el kernel `6.17.0-1008-nvidia` fue
  **580.142** del PPA `canonical-nvidia/nvidia-desktop-edge` (módulos
  precompilados + userspace parejos). Requiere reboot.
- Con el driver + `nvidia_drm modeset=1`, la salida **HDMI pasa a la GB10**
  (`card1-HDMI-A-1`). A partir de ahí **la GPU sí pinta en el monitor**.
- Cuidado con GDM/GNOME: si glvnd ofrece el EGL de NVIDIA primero, la sesión
  de escritorio rebota al greeter. Fix: forzar Mesa para el escritorio en
  `/etc/environment` (`__EGL_VENDOR_LIBRARY_FILENAMES=.../50_mesa.json`,
  `__GLX_VENDOR_LIBRARY_NAME=mesa`) y revertir a NVIDIA **solo** para el
  visualizador (ver `bench/README.md`).

**Conclusión de arquitectura**: la Spark *puede* con esto, pero el camino de
gráficos es frágil (driver del PPA, override de EGL por proceso). En una caja
con tarjeta de gráficos convencional (salida de display nativa NVIDIA) todo
esto debería ser directo. Reintentar ahí.

## Resultados del benchmark (GPU real, GB10)

fps = mediana/mín del badge; render headless con `--disable-frame-rate-limit`.

| Prueba | Resultado |
|---|---|
| bhtest sanity (`_test2`, ?bhtest=1) | cos **1.0000**, relErr 0.000 ✓ |
| `oax_full` (1.16M nodos / 9.6M aristas) | carga ~4.6 s · esfera 178/124 · espiral 288/114 · heap 441 MB |
| `oax_all` (1.19M / 21.3M) | carga ~4.8 s · esfera 558/206 · espiral 232/108 · heap 657 MB · **cero crashes** (moría en Mac) |
| `MAX_GPU_EDGES` 8M / 12M / **22M** (oax_all) | 539/147 · 563/141 · **532/151 esf, 753/75 esp — cero errores GPU** |
| Sintético **3M nodos** (`gen_synthetic_kbin.py`) | sim ~80 fps sostenidos, heap 695 MB, sin overflow |
| Ventana interactiva headed (`oax_full`, sim=0) | **renderiza en el monitor** a 31-50 fps, renderer "NVIDIA GB10/PCIe" |

### Hallazgos
- **`MAX_GPU_EDGES` (app.html) escala hasta 22M sin recorte** en la GB10: el
  buffer de aristas (~0.5 GB) cabe de sobra en el `maxBufferSize` de 4 GB del
  adapter. Se puede subir la constante a las 21.3M reales.
- **Límite del sim: nodos**, no aristas. El presupuesto de punto fijo i32 del
  binning (assert de 2M en app.html) aguanta subirse; con `BH_FP_SCALE` 2048→1024
  la precisión del bhtest quedó **idéntica** y 3M nodos corren bien.
- **Divergencia del grid FMM-lite en layouts reales** ⚠️: en `oax_full` el
  bhtest da cos_p05 −0.92, cosW_p50 −0.15, ratio_p50 0.038, relErr_p95 3.69 —
  el Barnes-Hut de grid se aparta fuerte del exacto O(N²) sobre el layout real
  (el sanity de 2 nodos es perfecto). Independiente de la escala fixed-point.
  **Verificar si en Metal/Mac pasa igual**; sospechoso: los mega-hubs
  (Municipality/Locality con grado >1000).
- El bhtest a 3M nodos **no completa**: el kernel exacto O(N²) (9e12 pares en
  un dispatch) excede el watchdog de la GPU → device lost. Para validar >~1.5M
  habría que trocear (chunk) el kernel de referencia.

## Cómo correrlo (en esta caja, post-fix de driver)

```bash
# server
cd Node_vizualizer && python3 -m http.server 8777 --bind 127.0.0.1

# ventana interactiva por GPU (ver bench/README.md para los flags exactos)
#   sim=0 abre al instante; sim=1 corre el relax físico (~1 min p/ 1M nodos,
#   esconde aristas y deja "LIVE GPU SIM…" — parece colgado pero no lo está)

# benchmark headless / screenshots
node bench/bench.js "http://localhost:8777/app.html?graph=graphs/oax_full.kbin" --secs 30 --headless
node bench/shot.js oax_full graphs_shot --settle 20
```

Query params útiles: `?bh=1|0` (Barnes-Hut on/off), `?sim=0` (salta el relax),
`?perf=1`, `?bhtest=1` (A/B numérico grid vs exacto; NO corre con `sim=0`).
