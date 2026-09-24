import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { writeFile, unlink } from 'node:fs/promises';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
import { fileURLToPath } from 'node:url';
import React, { act } from 'react';
import { setTimeout as delay } from 'node:timers/promises';

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost/' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createRoot } = await import('react-dom/client');
const bundle = new URL('./.panels.generated.mjs', import.meta.url);
const components = ['PortfolioTab', 'Analytics', 'DreamLog', 'DeepScan', 'AlphaMegaDashboard', 'SignalTracker', 'BacktestDashboard', 'ScanDashboard', 'PrintingProfits', 'SystemMonitor', 'TopStocks', 'AuditTrail', 'ChartPanel'];
const result = await build({
  stdin: { contents: components.map(name => `export { default as ${name} } from './src/components/${name}.jsx';`).join('\n'), resolveDir: fileURLToPath(new URL('..', import.meta.url)), loader: 'jsx' },
  bundle: true, write: false, format: 'esm', platform: 'node', jsx: 'automatic',
  external: ['react', 'react-dom', 'react/jsx-runtime', 'lucide-react'], define: { 'import.meta.env.VITE_API_URL': '"https://offline.invalid"' },
});
await writeFile(bundle, result.outputFiles[0].text);
const panels = await import(bundle.href);
after(async () => { await unlink(bundle); dom.window.close(); });
const portfolio = { state: { cash: 25000, starting_capital: 25000, max_positions: 8 }, stats: { cash: 25000, equity: 25000 }, open_positions: [], closed_positions: [] };
const response = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

async function mounted(name, fetcher, run, props = {}, fastTimeouts = false) {
  const original = globalThis.fetch;
  const originalTimeout = globalThis.setTimeout;
  const timers = [];
  globalThis.setTimeout = (fn, ms, ...args) => { const timer = originalTimeout(fn, fastTimeouts && ms >= 10000 ? 10 : ms, ...args); timers.push(timer); return timer; };
  globalThis.fetch = fetcher;
  const host = document.getElementById('root');
  const root = createRoot(host);
  try {
    await act(async () => { root.render(React.createElement(panels[name], props)); });
    await run(host);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = original;
    timers.forEach(clearTimeout);
    globalThis.setTimeout = originalTimeout;
  }
}

test('portfolio settles after one initial load and enables the empty slots', async () => {
  let loads = 0;
  await mounted('PortfolioTab', async url => {
    if (url.endsWith('/api/portfolio')) {
      if (++loads > 6) return new Promise(() => {}); // Bound a regression loop.
      return response(portfolio);
    }
    return response({ active: [], closed: [], candidates: [] });
  }, async host => {
    assert.equal(loads, 1, 'data updates must not trigger the initial-load effect');
    assert.ok(!host.textContent.includes('Processing...'));
    assert.equal([...host.querySelectorAll('button')].find(b => b.textContent.includes('AUTO-FILL')).disabled, false);
    assert.equal((host.textContent.match(/empty slot/g) || []).length, 8);
  }, { isOwner: true });
});

test('failed history load displays an error, not an endless spinner or invented count', async () => {
  await mounted('PortfolioTab', async url => {
    if (url.endsWith('/api/trade-history')) return response({ detail: 'unavailable' }, 503);
    if (url.endsWith('/api/portfolio')) return new Promise(() => {});
    return response({ active: [], closed: [], candidates: [] });
  }, async host => {
    const button = [...host.querySelectorAll('button')].find(b => b.textContent.includes('TRADE HISTORY'));
    assert.ok(!button.textContent.includes('85'));
    await act(async () => button.click());
    assert.match(host.textContent, /Unable to load history/i);
    assert.ok(!host.textContent.includes('Loading history...'));
  });
});

test('analytics shows failed requests instead of an empty successful page', async () => {
  await mounted('Analytics', async () => response({}, 503), async host => {
    assert.match(host.textContent, /Unable to load/i);
    assert.ok(!host.textContent.includes('Loading analytics...'));
  });
});

test('dream log distinguishes an API failure from no dreams', async () => {
  await mounted('DreamLog', async () => response({}, 503), async host => {
    assert.match(host.textContent, /Unable to load/i);
    assert.ok(!host.textContent.includes('No dreams yet'));
  });
});

for (const name of ['DeepScan', 'AlphaMegaDashboard']) {
  test(`${name} surfaces HTTP failure and enables retry`, async () => {
    await mounted(name, async () => response({}, 503), async host => {
      assert.ok(!host.textContent.includes('SCANNING...'));
      assert.match(host.textContent, /503|unavailable|failed/i);
    });
  });
}

for (const name of ['Analytics', 'DreamLog', 'DeepScan', 'AlphaMegaDashboard']) {
  test(`${name} leaves loading state when a request hangs`, async () => {
    await mounted(name, (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
    }), async host => {
      await act(async () => { await delay(35); });
      assert.match(host.textContent, /timed out|unavailable|Unable to load/i);
      assert.ok(!host.textContent.includes('SCANNING...'));
    }, {}, true);
  });
}

for (const name of ['SignalTracker', 'BacktestDashboard', 'ScanDashboard', 'PrintingProfits', 'SystemMonitor', 'TopStocks', 'AuditTrail', 'ChartPanel']) {
  test(`${name} mounts with offline responses without crashing`, async () => {
    await mounted(name, async () => response({}, 503), async host => {
      assert.ok(host.textContent.trim().length > 0);
    });
  });
}

test('Futures reports failed data loading instead of spinning forever', async () => {
  await mounted('PrintingProfits', async () => response({}, 503), async host => {
    await act(async () => [...host.querySelectorAll('button')].find(b => b.textContent.includes('FUTURES')).click());
    assert.match(host.textContent, /Unable to load futures/i);
  });
});

test('Signal Tracker reports a failed initial request', async () => {
  await mounted('SignalTracker', async () => response({}, 503), async host => {
    assert.match(host.textContent, /Unable to load signals/i);
  });
});

test('streamed scanner displays provider errors instead of swallowing them', async () => {
  await mounted('ScanDashboard', async url => url.endsWith('/api/scan/stream')
    ? new Response('data: {"type":"error","error":"provider unavailable"}\n\n', { headers: { 'Content-Type': 'text/event-stream' } })
    : response({ watchlists: {} }), async host => {
      await act(async () => [...host.querySelectorAll('button')].find(b => b.textContent === 'RUN SCAN').click());
      assert.match(host.textContent, /provider unavailable/);
    });
});


test('full portfolio renders all positions and disables auto-fill', async () => {
  const full = {...portfolio, open_positions: Array.from({length:8}, (_,i)=>({
    id:`p${i}`,ticker:`TEST${i}`,entry_price:100,current_price:101,sl:95,tp1:110,tp2:120,tp3:130,
    shares:10,shares_remaining:10,entry_date:'2026-09-20',status:'open'
  }))};
  await mounted('PortfolioTab', async url => response(url.endsWith('/api/portfolio') ? full : {active:[],closed:[],candidates:[]}), async host => {
    assert.match(host.textContent,/8\/8 SLOTS USED/);
    assert.ok(!host.textContent.includes('empty slot'));
    assert.equal([...host.querySelectorAll('button')].find(b=>b.textContent.includes('PORTFOLIO FULL')).disabled,true);
    assert.ok(host.textContent.includes('TEST7'));
  }, {isOwner:true});
});

test('failed portfolio load keeps slot actions disabled and marks balances unverified', async () => {
  await mounted('PortfolioTab',async()=>response({},503),async host=>{
    assert.match(host.textContent,/unverified/);
    assert.equal([...host.querySelectorAll('button')].find(b=>b.textContent.includes('AUTO-FILL')).disabled,true);
    assert.ok(!host.textContent.includes('empty slot'));
  },{isOwner:true});
});

test('scanner reports an interrupted stream without a complete result', async () => {
  await mounted('ScanDashboard', async url => url.endsWith('/api/scan/stream')
    ? new Response('data: {"type":"progress","progress":"halfway"}\n\n') : response({watchlists:{}}),async host=>{
    await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent==='RUN SCAN').click());
    assert.match(host.textContent,/ended before completion/);
  });
});

test('System Monitor distinguishes failed requests from healthy refresh', async () => {
  await mounted('SystemMonitor',async()=>response({},503),async host=>{
    assert.match(host.textContent,/Unable to load system data/);
    assert.ok(!host.textContent.includes('Refresh OK'));
  });
});

test('unavailable history displays provenance without invented performance', async()=>{
  await mounted('PortfolioTab',async url=>response(url.endsWith('/api/trade-history')
    ? {trades:[],stats:null,history_available:false,message:'Older remote history is unavailable'}
    : url.endsWith('/api/portfolio') ? portfolio : {active:[],closed:[],candidates:[]}),async host=>{
      await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent.includes('TRADE HISTORY')).click());
      assert.match(host.textContent,/Older remote history is unavailable/);
      assert.ok(!host.textContent.includes('PROFIT FACTOR'));
      assert.ok(!host.textContent.includes('TRADE HISTORY (0)'));
    });
});
