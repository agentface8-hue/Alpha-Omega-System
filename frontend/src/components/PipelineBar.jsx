import { useEffect, useRef, useState } from 'react';
import { Play, RefreshCw } from 'lucide-react';
import { fetchJson } from '../utils/api';

const C = {
  green: '#00ff88',
  border: '#1a2535',
  card: '#0a0f18',
  faint: '#6a8a9a',
};

const AUTO_RUN_KEY = 'ao_pipeline_last_autorun_ms';
const AUTO_RUN_COOLDOWN_MS = 2 * 60 * 60 * 1000; // 2h safety cooldown

export default function PipelineBar({ disabled, onComplete, autoRun = false }) {
  const [running, setRunning] = useState(false);
  const [last, setLast] = useState(null);
  const [err, setErr] = useState(null);
  const autoTriedRef = useRef(false);

  const run = async () => {
    if (running || disabled) return;
    setRunning(true);
    setErr(null);
    try {
      const data = await fetchJson(
        '/api/pipeline/run',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_dream: true, run_autopilot: true, run_learning: true }),
        },
        { timeoutMs: 180000, retries: 1 },
      );
      setLast(data);
      onComplete?.(data);
    } catch (e) {
      setErr(e.message);
    }
    setRunning(false);
  };

  useEffect(() => {
    if (!autoRun || disabled || running || autoTriedRef.current) return;
    autoTriedRef.current = true;
    try {
      const lastMs = Number(localStorage.getItem(AUTO_RUN_KEY) || '0');
      const now = Date.now();
      if (now - lastMs < AUTO_RUN_COOLDOWN_MS) return;
      localStorage.setItem(AUTO_RUN_KEY, String(now));
    } catch {}
    run();
  }, [autoRun, disabled, running]);

  const s = last?.summary;

  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: '12px 16px',
        marginBottom: 10,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <div style={{ flex: 1, minWidth: 200 }}>
        <div style={{ color: C.green, fontSize: 11, fontWeight: 'bold', letterSpacing: 2, fontFamily: 'monospace' }}>
          UNIFIED PIPELINE
        </div>
        <div style={{ color: C.faint, fontSize: 10, marginTop: 4, fontFamily: 'sans-serif' }}>
          Regime → sectors → themes → dream → portfolio check → autopilot → learning → monitor
        </div>
        {s && (
          <div style={{ color: '#8899aa', fontSize: 10, marginTop: 6, fontFamily: 'monospace' }}>
            {s.regime} · themes {(s.active_themes || []).join(', ') || '—'} · dream {s.dream_edge || '—'} {s.dream_ticker || ''} · opened {s.autopilot_opened ?? 0}
          </div>
        )}
        {err && <div style={{ color: '#ff4466', fontSize: 10, marginTop: 6 }}>{err}</div>}
      </div>
      <button
        type="button"
        onClick={run}
        disabled={running || disabled}
        style={{
          background: running ? '#1a2535' : 'rgba(0,255,136,0.12)',
          border: `1px solid ${running ? C.border : C.green + '55'}`,
          color: running ? C.faint : C.green,
          borderRadius: 8,
          padding: '10px 20px',
          fontSize: 11,
          fontWeight: 'bold',
          cursor: running || disabled ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontFamily: 'monospace',
          letterSpacing: 1,
        }}
      >
        {running ? <RefreshCw size={14} /> : <Play size={14} />}
        {running ? 'RUNNING…' : 'RUN FULL PIPELINE'}
      </button>
    </div>
  );
}
