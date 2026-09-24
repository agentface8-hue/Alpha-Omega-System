/** Shared API client — retries + timeout for Render cold starts. */
function resolveApiBase() {
  const raw = import.meta.env.VITE_API_URL || 'https://alpha-omega-system.onrender.com';
  // Dead Clouding hostname still set in some Vercel envs — never use it.
  if (String(raw).includes('clouding.host')) {
    return 'https://alpha-omega-system.onrender.com';
  }
  return raw;
}
export const API_BASE = resolveApiBase();

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Retry reads only: a timed-out mutation may already have completed on the server.
 */
async function request(path, options, cfg, consume) {
  const {
    timeoutMs = 45000,
    retries = 3,
    backoffMs = 2500,
  } = cfg;
  const url = `${API_BASE}${path}`;
  const method = String(options.method || 'GET').toUpperCase();
  const attempts = ['GET', 'HEAD'].includes(method) ? Math.max(1, retries) : 1;
  const callerSignal = options.signal;
  let lastErr;
  for (let attempt = 0; attempt < attempts; attempt++) {
    callerSignal?.throwIfAborted();
    const ctrl = new AbortController();
    const cancel = () => ctrl.abort(callerSignal.reason);
    callerSignal?.addEventListener('abort', cancel, { once: true });
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    let headersReceived = false;
    try {
      const res = await fetch(url, { ...options, signal: ctrl.signal });
      headersReceived = true;
      return await consume(res);
    } catch (e) {
      callerSignal?.throwIfAborted();
      lastErr = e;
      const msg = e?.name === 'AbortError' ? 'Request timed out — backend may be waking up' : (e?.message || String(e));
      lastErr = new Error(msg);
      if (headersReceived) throw lastErr;
    } finally {
      clearTimeout(timer);
      callerSignal?.removeEventListener('abort', cancel);
    }
    if (attempt < attempts - 1) await sleep(backoffMs * (attempt + 1));
  }
  throw lastErr;
}

export function fetchApi(path, options = {}, cfg = {}) {
  return request(path, options, cfg, res => res);
}

export function fetchJson(path, options = {}, cfg = {}) {
  return request(path, options, cfg, async res => {
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}${text ? `: ${text.slice(0, 300)}` : ''}`);
    }
    return res.json();
  });
}

/** Poll /health until backend responds (max ~2 min). Accepts degraded (JSON fallback). */
export async function warmupBackend(onStatus) {
  for (let i = 0; i < 10; i++) {
    try {
      const data = await fetchJson('/health', {}, { timeoutMs: 25000, retries: 1 });
      if (data?.status === 'online' || data?.status === 'degraded') return true;
    } catch {
      onStatus?.(i >= 2 ? 'slow' : 'connecting');
    }
    await sleep(6000);
  }
  return false;
}
