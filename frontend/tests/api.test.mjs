import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// Vite replaces import.meta.env; supply just that build-time value for Node.
const source = (await readFile(new URL('../src/utils/api.js', import.meta.url), 'utf8'))
  .replaceAll('import.meta.env.VITE_API_URL', "'https://offline.invalid'");
const { fetchApi, fetchJson } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('a failed POST is never replayed automatically, even with retries configured', async () => {
  let calls = 0;
  const original = globalThis.fetch;
  globalThis.fetch = async () => { calls++; throw new TypeError('connection lost after server accepted request'); };
  try {
    await assert.rejects(fetchApi('/api/portfolio/check', { method: 'POST' }, { retries: 3, backoffMs: 0 }));
    assert.equal(calls, 1);
  } finally { globalThis.fetch = original; }
});

test('read requests retry transient network errors', async () => {
  let calls = 0;
  const original = globalThis.fetch;
  globalThis.fetch = async () => { if (++calls < 3) throw new TypeError('offline'); return { ok: true }; };
  try {
    assert.equal((await fetchApi('/health', {}, { retries: 3, backoffMs: 0 })).ok, true);
    assert.equal(calls, 3);
  } finally { globalThis.fetch = original; }
});

test('an already cancelled request makes no network call', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; return { ok: true }; };
  const controller = new AbortController();
  controller.abort();
  try {
    await assert.rejects(fetchApi('/health', { signal: controller.signal }));
    assert.equal(calls, 0);
  } finally { globalThis.fetch = original; }
});

test('JSON timeout includes the response body after headers arrive', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (_url, options) => ({ ok: true,
    json: () => new Promise((_resolve,reject) => options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true}))
  });
  try {
    await assert.rejects(fetchJson('/slow-body', {}, {timeoutMs:15,retries:1}), /timed out/);
  } finally { globalThis.fetch = original; }
});
