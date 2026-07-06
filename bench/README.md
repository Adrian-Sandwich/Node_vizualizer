# bench/ — arnés de benchmark GPU del visualizador

Herramientas usadas para medir el visualizador con millones de nodos en la
DGX Spark (GB10). Ver `../docs/G10_DGX_SPARK_NOTES.md` para resultados y contexto.

Requiere Node + `playwright` (npm) y un binario de Chromium. Apunta el binario
con la env `CHROME` (por defecto usa el de la caché de Playwright).

```bash
npm i playwright                       # el paquete; reusa el chromium en caché
export CHROME=/ruta/al/chromium/chrome # opcional si no está en la ruta default
```

## Servir el visualizador
```bash
cd .. && python3 -m http.server 8777 --bind 127.0.0.1
```

## Flags de GPU (Linux + NVIDIA)
El WebGL/WebGPU headed usa la GPU con:
```
--no-sandbox --use-gl=angle --use-angle=gl-egl --enable-unsafe-webgpu --ignore-gpu-blocklist
```
En la Spark, además exportar el EGL de NVIDIA (porque el escritorio fuerza Mesa):
```bash
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
```
`--no-sandbox` es obligatorio con el Chromium de Playwright en Ubuntu 24.04
(no trae perfil AppArmor → si no, hace FATAL "No usable sandbox").

## bench.js — fps + bhtest
```bash
node bench.js "http://localhost:8777/app.html?graph=graphs/oax_full.kbin" --secs 30 --headless
node bench.js "http://localhost:8777/app.html?graph=graphs/oax_all.kbin"  --secs 150 --headless --press g@75
```
Lee `#fps-badge` cada 1s, captura `[bhtest]`, imprime JSON. `--press g@75`
presiona teclas en segundos dados (G = esfera↔espiral). `BENCH_FLAGS` añade
flags extra de chromium. Lección: envolver los `page.evaluate` en timeout —
`requestAdapter()` se cuelga si se fuerza Vulkan sin ICD.

## shot.js — screenshots (esfera + espiral)
```bash
node shot.js oax_full mi_shot --settle 20
```
Renderiza headless en la GPU y guarda `mi_shot_esfera.png` / `mi_shot_espiral.png`.
Le da click a SKIP para saltar el onboarding.

## gen_synthetic_kbin.py — grafos de prueba
```bash
python3 ../gen_synthetic_kbin.py 3000000 6000000 ../graphs/synth_3M.kbin
```
Genera un `.kbin` (formato KBN1) del tamaño que pidas para estresar el sim.
