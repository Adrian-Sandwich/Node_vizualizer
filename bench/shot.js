// shot.js — renderiza un grafo en la GB10 (headless, GPU real) y guarda PNGs.
// Uso: node shot.js <graph> <out-prefix> [--settle N]
const { chromium } = require('playwright');
const a = process.argv.slice(2);
const graph = a[0], out = a[1];
const settle = (() => { const i = a.indexOf('--settle'); return i >= 0 ? +a[i + 1] : 20; })();
const EXE = process.env.CHROME || '/home/celestial/.cache/ms-playwright/chromium-1223/chrome-linux/chrome';
const log = (...x) => console.error('[shot]', ...x);

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE, headless: true,
    args: ['--no-sandbox', '--enable-unsafe-webgpu', '--ignore-gpu-blocklist',
           '--use-gl=angle', '--use-angle=gl-egl', '--window-size=1920,1080'],
    env: { ...process.env, DISPLAY: process.env.DISPLAY || ':0',
           __EGL_VENDOR_LIBRARY_FILENAMES: '/usr/share/glvnd/egl_vendor.d/10_nvidia.json' },
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('console', m => { if (/GRAPH ONLINE|webgl|error creating/i.test(m.text())) log('page:', m.text().slice(0, 80)); });

  log('cargando', graph);
  await page.goto(`http://localhost:8777/app.html?graph=graphs/${graph}`, { waitUntil: 'domcontentloaded', timeout: 180000 });
  const wgl = await page.evaluate(() => { try { const g = document.createElement('canvas').getContext('webgl2'); const e = g.getExtension('WEBGL_debug_renderer_info'); return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'webgl2 ok'; } catch (x) { return 'ERR ' + x.message; } });
  log('renderer:', wgl);

  await page.waitForTimeout(3000);
  // cerrar el onboarding (botón SKIP) para ver el grafo real
  try { await page.click('text=SKIP', { timeout: 4000 }); log('SKIP clickeado'); }
  catch { try { await page.keyboard.press('Escape'); } catch {} log('SKIP no hallado, seguí'); }

  await page.waitForTimeout(settle * 1000);           // deja asentar la física (esfera)
  await page.screenshot({ path: `${out}_esfera.png` });
  log('shot esfera →', `${out}_esfera.png`);

  await page.keyboard.press('g');                       // espiral
  await page.waitForTimeout(6000);
  await page.screenshot({ path: `${out}_espiral.png` });
  log('shot espiral →', `${out}_espiral.png`);

  await browser.close();
  log('fin');
})().catch(e => { console.error('SHOT_FATAL:', e.message); process.exit(2); });
