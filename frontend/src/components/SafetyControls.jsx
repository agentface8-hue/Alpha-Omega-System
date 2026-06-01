import React, { useEffect, useState } from 'react';
import { fetchJson } from '../utils/api';

export default function SafetyControls() {
  const [state, setState] = useState(null);
  const [msg, setMsg] = useState('');

  async function load() {
    try {
      const data = await fetchJson('/api/safety/status', {}, { timeoutMs: 10000, retries: 1 });
      setState(data);
    } catch (e) {
      setMsg(e.message || 'safety unavailable');
    }
  }

  async function post(path, body) {
    setMsg('');
    try {
      const data = await fetchJson(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      }, { timeoutMs: 10000, retries: 1 });
      setState(data.state || data);
      setMsg('updated');
    } catch (e) {
      setMsg(e.message || 'request failed');
    }
  }

  useEffect(() => {
    load();
  }, []);

  const halted = state?.global_halt;
  const haltedSymbols = Object.keys(state?.halted_symbols || {});

  return (
    <div style={{ background: '#0a0f18', border: '1px solid #1a2535', borderRadius: 10, padding: 12, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ color: halted ? '#ff4466' : '#00ff88', fontFamily: 'monospace', fontSize: 11, letterSpacing: 2 }}>
          TRADING SAFETY · {halted ? 'HALTED' : 'ACTIVE'}
        </div>
        <button onClick={load} style={{ fontSize: 11, cursor: 'pointer' }}>Refresh</button>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
        <button onClick={() => post('/api/safety/halt-all', { reason: 'UI halt all' })}
          style={{ background: '#3a0712', color: '#ff4466', border: '1px solid #ff446655', borderRadius: 6, padding: '6px 10px', cursor: 'pointer' }}>
          HALT ALL
        </button>
        <button onClick={() => post('/api/safety/resume')}
          style={{ background: '#062815', color: '#00ff88', border: '1px solid #00ff8855', borderRadius: 6, padding: '6px 10px', cursor: 'pointer' }}>
          RESUME
        </button>
      </div>
      <div style={{ color: '#8899aa', fontSize: 12, lineHeight: 1.45 }}>
        {state ? `Max daily loss $${state.max_daily_realized_loss} · max open risk $${state.max_open_risk} · live confirmed ${state.live_mode_confirmed ? 'yes' : 'no'}` : 'loading...'}
      </div>
      <div style={{ color: '#4a6a8a', fontSize: 11, marginTop: 6 }}>
        Halted symbols: {haltedSymbols.length ? haltedSymbols.join(', ') : 'none'}
      </div>
      {msg && <div style={{ color: '#fbbf24', fontSize: 11, marginTop: 6 }}>{msg}</div>}
    </div>
  );
}
