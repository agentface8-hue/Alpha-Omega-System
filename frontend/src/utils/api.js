/** Shared API client — retries + timeout for Render cold starts. */
export const API_BASE =
  import.meta.env.VITE_API_URL || 'http://46.183.113.197';

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * fetch with timeout and retries. Throws on final failure.
 */
export async function fetchApi(path, options = {}, cfg = {}) {
  const {
    timeoutMs = 45000,
    retries = 3,
    backoffMs = 2500,
  } = cfg;
  const url = `${API_BASE}${path}`;
  let lastErr;
  for (let attempt = 0; attempt < retries; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...options, signal: ctrl.signal });
      clearTimeout(timer);
      return res;
    } catch (e) {
      clearTimeout(timer);
      lastErr = e;
      const msg = e?.name === 'AbortError' ? 'Request timed out — backend may be waking up' : (e?.message || String(e));
      lastErr = new Error(msg);
      if (attempt < retries - 1) await sleep(backoffMs * (attempt + 1));
    }
  }
  throw lastErr;
}

export async function fetchJson(path, options = {}, cfg = {}) {
  const res = await fetchApi(path, options, cfg);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

/** Poll /health until Render is awake (max ~2 min). */
export async function warmupBackend(onStatus) {
  for (let i = 0; i < 10; i++) {
    try {
      const data = await fetchJson('/health', {}, { timeoutMs: 25000, retries: 1 });
      if (data?.status === 'online') return true;
    } catch {
      onStatus?.(i >= 2 ? 'slow' : 'connecting');
    }
    await sleep(6000);
  }
  return false;
}
