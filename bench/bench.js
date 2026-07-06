// bench.js — arnés de benchmark para Node_vizualizer (G10/GB10)
// Uso: node bench.js <url> [--secs N] [--headless] [--press tecla@seg,tecla@seg]
//   BENCH_FLAGS="--enable-features=Vulkan"  (flags extra de chromium)
// Salida stdout: JSON. Progreso: stderr.
const { chromium } = require('playwright');

const argv = process.argv.slice(2);
const url = argv[0];
const secs = (() => { const i = argv.indexOf('--secs'); return i >= 0 ? parseInt(argv[i + 1], 10) : 25; })();
const headless = argv.includes('--headless');
const pressSpec = (() => { const i = argv.indexOf('--press'); return i >= 0 ? argv[i + 1] : ''; })();
const presses = pressSpec ? pressSpec.split(',').map(p => { const [k, t] = p.split('@'); return { key: k, at: parseFloat(t) }; }) : [];
const EXE = process.env.CHROME || '/home/celestial/.cache/ms-playwright/chromium-1223/chrome-linux/chrome';
const extraFlags = (process.env.BENCH_FLAGS || '').split(/\s+/).filter(Boolean);

if (!url) { console.error('uso: node bench.js <url> [--secs N] [--headless] [--press g@30]'); process.exit(1); }
const log = (...a) => console.error('[bench]', ...a);
const withTimeout = (p, ms, tag) => Promise.race([
  p, new Promise(res => setTimeout(() => res({ __timeout: tag, ms }), ms)),
]);

(async () => {
  log('lanzando chromium', headless ? '(headless)' : '(headed)', 'flags extra:', extraFlags.join(' ') || '(ninguno)');
  const browser = await chromium.launch({
    executablePath: EXE,
    headless,
    args: [
      '--no-sandbox',
      '--enable-unsafe-webgpu',
      '--ignore-gpu-blocklist',
      '--no-first-run',
      '--window-size=1920,1080',
      ...extraFlags,
    ],
    env: { ...process.env, DISPLAY: process.env.DISPLAY || ':0' },
  });
  const page = await browser.newPage({ viewport: { width: 1880, height: 980 } });

  const head = [], tail = [], MAXLOG = 150;
  const bhtest = [];
  page.on('console', m => {
    const t = m.text();
    if (t.includes('[bhtest]')) bhtest.push(t);
    if (head.length < MAXLOG) head.push(t);
    else { tail.push(t); if (tail.length > MAXLOG) tail.shift(); }
  });
  page.on('pageerror', e => tail.push('PAGEERROR: ' + e.message));

  const t0 = Date.now();
  log('goto', url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 180000 });
  log('domcontentloaded @', ((Date.now() - t0) / 1000).toFixed(1) + 's');

  const adapter = await withTimeout(page.evaluate(async () => {
    if (!navigator.gpu) return { webgpu: false };
    try {
      const a = await Promise.race([
        navigator.gpu.requestAdapter(),
        new Promise(res => setTimeout(() => res('TIMEOUT_IN_PAGE'), 10000)),
      ]);
      if (a === 'TIMEOUT_IN_PAGE') return { webgpu: true, adapter: 'timeout-10s' };
      if (!a) return { webgpu: true, adapter: null };
      const info = a.info || (a.requestAdapterInfo ? await a.requestAdapterInfo() : {});
      return {
        webgpu: true,
        vendor: info.vendor || '', architecture: info.architecture || '',
        device: info.device || '', description: info.description || '',
        fallback: !!a.isFallbackAdapter,
        maxBufferMB: Math.round((a.limits?.maxBufferSize || 0) / 1048576),
        maxStorageMB: Math.round((a.limits?.maxStorageBufferBindingSize || 0) / 1048576),
      };
    } catch (e) { return { webgpu: true, error: String(e) }; }
  }), 15000, 'adapter-evaluate');
  log('adapter:', JSON.stringify(adapter));

  const webgl = await withTimeout(page.evaluate(() => {
    try {
      const gl = document.createElement('canvas').getContext('webgl2');
      if (!gl) return 'sin webgl2';
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      return String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    } catch (e) { return 'ERR ' + e.message; }
  }), 15000, 'webgl-evaluate');
  log('webgl:', JSON.stringify(webgl));

  // Muestrear #fps-badge cada segundo; teclas programadas con --press
  const samples = [];
  const events = [];
  const pending = [...presses].sort((a, b) => a.at - b.at);
  const tEnd = Date.now() + secs * 1000;
  while (Date.now() < tEnd) {
    const elapsed = (Date.now() - t0) / 1000;
    while (pending.length && elapsed >= pending[0].at) {
      const p = pending.shift();
      await page.keyboard.press(p.key).catch(e => log('press err', e.message));
      events.push({ t: +elapsed.toFixed(1), press: p.key });
      log('press', p.key, '@', elapsed.toFixed(1) + 's');
    }
    const badge = await withTimeout(page.evaluate(() => {
      const el = document.getElementById('fps-badge');
      return el ? el.textContent.trim() : null;
    }), 8000, 'badge').catch(() => 'EVAL_ERR');
    samples.push({ t: +elapsed.toFixed(1), badge: badge && badge.__timeout ? 'TIMEOUT' : badge });
    await new Promise(r => setTimeout(r, 1000));
  }
  log('muestreo terminado,', samples.length, 'muestras');

  const mem = await withTimeout(page.evaluate(() => performance.memory ? {
    usedJSHeapMB: Math.round(performance.memory.usedJSHeapSize / 1048576),
    totalJSHeapMB: Math.round(performance.memory.totalJSHeapSize / 1048576),
  } : null), 8000, 'mem').catch(() => null);

  console.log(JSON.stringify({ url, secs, adapter, webgl, mem, bhtest, events, samples,
    consoleHead: head.slice(0, 60), consoleTail: tail.slice(-60) }, null, 2));
  await browser.close();
  log('fin OK');
})().catch(e => { console.error('BENCH_FATAL:', e.message); process.exit(2); });
