// Captura pantallazos de página completa a un viewport exacto, vía CDP.
//
// `chrome --window-size` no baja del ancho mínimo de ventana del sistema
// (~500 px en Windows), así que no sirve para comprobar el diseño móvil.
// Emulation.setDeviceMetricsOverride sí fija el viewport real.
//
// Uso:  node herramientas/capturar.mjs <url> <salida.png> <ancho> [alto] [movil] [claro|oscuro]
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { dirname } from 'node:path';
import { tmpdir } from 'node:os';

const [url, salida, anchoTxt, altoTxt = '900', movilTxt = '', temaTxt = ''] =
  process.argv.slice(2);
if (!url || !salida || !anchoTxt) {
  console.error('uso: node herramientas/capturar.mjs <url> <salida.png> <ancho> [alto] [movil]');
  process.exit(1);
}
const ancho = Number(anchoTxt);
const alto = Number(altoTxt);
const movil = movilTxt === 'movil';
const tema = temaTxt === 'claro' ? 'light' : temaTxt === 'oscuro' ? 'dark' : '';

const CHROME = process.env.CHROME_BIN ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const puerto = 9222 + Math.floor(Math.random() * 400);
const perfil = `${tmpdir()}\\cap-${puerto}`;

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--hide-scrollbars', `--remote-debugging-port=${puerto}`, `--user-data-dir=${perfil}`,
  // Sin esto, Windows impone un ancho mínimo de ventana (~454 px) que el
  // override de métricas no puede bajar, y el móvil no se puede comprobar.
  `--window-size=${ancho},${alto}`,
  'about:blank',
], { stdio: 'ignore' });

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

async function objetivo() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${puerto}/json/list`);
      const pestanas = (await r.json()).filter((t) => t.type === 'page');
      if (pestanas.length) return pestanas[0].webSocketDebuggerUrl;
    } catch { /* Chrome aún no levanta */ }
    await esperar(250);
  }
  throw new Error('Chrome no expuso el puerto de depuración');
}

function conectar(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let id = 0;
    const pendientes = new Map();
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pendientes.has(msg.id)) {
        const { ok, fail } = pendientes.get(msg.id);
        pendientes.delete(msg.id);
        msg.error ? fail(new Error(msg.error.message)) : ok(msg.result);
      }
    });
    ws.addEventListener('error', reject);
    ws.addEventListener('open', () => resolve({
      enviar: (method, params = {}) => new Promise((ok, fail) => {
        const n = ++id;
        pendientes.set(n, { ok, fail });
        ws.send(JSON.stringify({ id: n, method, params }));
      }),
      cerrar: () => ws.close(),
    }));
  });
}

try {
  const cdp = await conectar(await objetivo());
  await cdp.enviar('Page.enable');
  if (tema) {
    await cdp.enviar('Emulation.setEmulatedMedia', {
      features: [{ name: 'prefers-color-scheme', value: tema }],
    });
  }
  await cdp.enviar('Emulation.setDeviceMetricsOverride', {
    width: ancho, height: alto, deviceScaleFactor: 1, mobile: movil,
  });
  await cdp.enviar('Page.navigate', { url });
  await esperar(1400);

  const medir = async () => {
    const { result } = await cdp.enviar('Runtime.evaluate', {
      expression: 'JSON.stringify({w:document.documentElement.scrollWidth,' +
        'h:document.documentElement.scrollHeight,vw:window.innerWidth})',
      returnByValue: true,
    });
    return JSON.parse(result.value);
  };

  // Una captura solo vale si el viewport es el que se pidió. La emulación a
  // veces no prende a la primera, así que se comprueba y se reintenta antes de
  // escribir el archivo: una captura inválida cuesta la ronda entera.
  let m = await medir();
  for (let i = 0; i < 3 && m.vw !== ancho; i++) {
    await cdp.enviar('Emulation.setDeviceMetricsOverride', {
      width: ancho, height: alto, deviceScaleFactor: 1, mobile: movil,
    });
    await esperar(700);
    m = await medir();
  }
  if (m.vw !== ancho) {
    throw new Error(`viewport ${m.vw}px, se pidieron ${ancho}px: captura no válida`);
  }

  const { data } = await cdp.enviar('Page.captureScreenshot', {
    format: 'png', captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: m.w, height: m.h, scale: 1 },
  });
  mkdirSync(dirname(salida), { recursive: true });
  writeFileSync(salida, Buffer.from(data, 'base64'));
  console.log(`${salida}  viewport ${m.vw}px  ${tema || 'auto'}  documento ${m.w}x${m.h}` +
    (m.w > m.vw ? '  ¡DESBORDA A LO ANCHO!' : ''));
  cdp.cerrar();
} finally {
  chrome.kill();
  try { rmSync(perfil, { recursive: true, force: true }); } catch { /* ya no está */ }
}
