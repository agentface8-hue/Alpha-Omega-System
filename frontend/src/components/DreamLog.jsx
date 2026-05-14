import { useState, useEffect } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const EDGE_COLOR = { HIGH: '#ff4466', MEDIUM: '#fbbf24', LOW: '#4a6a8a' };
const ACTION_COLOR = { WATCH_CLOSELY: '#00ff88', MONITOR: '#00d4ff', WAIT: '#4a6a8a' };

export default function DreamLog() {
  const [dreams, setDreams]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [running, setRunning]   = useState(false);
  const [lastRun, setLastRun]   = useState(null);

  const fetchDreams = async () => {
    try {
      const res  = await fetch(`${API}/api/dreams/latest?limit=20`);
      const json = await res.json();
      setDreams(json.dreams || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const runCycle = async () => {
    setRunning(true);
    try {
      await fetch(`${API}/api/dreams/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true }),
      });
      setLastRun(new Date().toLocaleTimeString());
      setTimeout(fetchDreams, 3000);
    } catch (e) { console.error(e); }
    setRunning(false);
  };

  useEffect(() => { fetchDreams(); }, []);

  const card = { background: '#0a0f18', border: '1px solid #1a2535', borderRadius: 12, padding: '20px 24px', marginBottom: 16 };

  return (
    <div style={{ padding: '24px 28px', maxWidth: 900, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 22 }}>💭</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: '#c084fc', fontFamily: 'monospace', letterSpacing: 2 }}>DREAM LOG</span>
          </div>
          <div style={{ fontSize: 10, color: '#4a6a8a', fontFamily: 'sans-serif', letterSpacing: 1 }}>
            GEMINI BACKGROUND MARKET ANALYSIS · RUNS EVERY 4H ON MARKET DAYS
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {lastRun && <span style={{ fontSize: 9, color: '#4a6a8a', fontFamily: 'sans-serif' }}>Last run: {lastRun}</span>}
          <button
            onClick={runCycle}
            disabled={running}
            style={{ background: running ? '#1a2535' : 'rgba(192,132,252,0.15)', border: '1px solid #c084fc55', color: running ? '#4a6a8a' : '#c084fc', borderRadius: 6, padding: '8px 18px', fontSize: 11, fontWeight: 'bold', fontFamily: 'sans-serif', cursor: running ? 'not-allowed' : 'pointer', letterSpacing: 1 }}>
            {running ? '⏳ RUNNING...' : '▶ RUN NOW'}
          </button>
        </div>
      </div>

      {/* Dream cards */}
      {loading ? (
        <div style={{ color: '#4a6a8a', fontFamily: 'sans-serif', fontSize: 12, textAlign: 'center', padding: 40 }}>Loading dream log...</div>
      ) : dreams.length === 0 ? (
        <div style={{ ...card, textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>💭</div>
          <div style={{ color: '#4a6a8a', fontFamily: 'sans-serif', fontSize: 12 }}>No dreams yet. Hit Run Now to trigger the first cycle.</div>
        </div>
      ) : (
        dreams.map((d, i) => {
          const ec = EDGE_COLOR[d.edge_level] || '#4a6a8a';
          const ac = ACTION_COLOR[d.action]   || '#4a6a8a';
          const ts = d.ts ? d.ts.slice(0, 16).replace('T', ' ') + ' UTC' : '';
          return (
            <div key={i} style={{ ...card, borderLeft: `3px solid ${ec}` }}>
              {/* Top row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <span style={{ fontSize: 10, fontWeight: 'bold', color: ec, background: ec + '22', padding: '2px 8px', borderRadius: 4, fontFamily: 'sans-serif', letterSpacing: 1 }}>
                  {d.edge_level}
                </span>
                {d.top_ticker && (
                  <span style={{ fontSize: 14, fontWeight: 'bold', color: '#00d4ff', fontFamily: 'monospace' }}>
                    {d.top_ticker}
                  </span>
                )}
                <span style={{ fontSize: 9, fontWeight: 'bold', color: ac, background: ac + '18', padding: '2px 8px', borderRadius: 4, fontFamily: 'sans-serif' }}>
                  {d.action}
                </span>
                <span style={{ fontSize: 9, color: '#2a4a5a', fontFamily: 'sans-serif', marginLeft: 'auto' }}>{ts}</span>
              </div>

              {/* Context row */}
              <div style={{ display: 'flex', gap: 16, marginBottom: 10 }}>
                {d.regime && <span style={{ fontSize: 9, color: '#8899aa', fontFamily: 'sans-serif' }}>📊 {d.regime}</span>}
                {d.vix > 0 && <span style={{ fontSize: 9, color: '#8899aa', fontFamily: 'sans-serif' }}>VIX {d.vix}</span>}
                {d.spy_change !== undefined && <span style={{ fontSize: 9, color: d.spy_change >= 0 ? '#00ff88' : '#ff4466', fontFamily: 'sans-serif' }}>SPY {d.spy_change >= 0 ? '+' : ''}{d.spy_change}%</span>}
              </div>

              {/* Analysis */}
              {d.analysis && (
                <div style={{ fontSize: 11, color: '#c9d8e8', fontFamily: 'sans-serif', lineHeight: 1.6, marginBottom: 10 }}>
                  {d.analysis}
                </div>
              )}

              {/* Risk */}
              {d.key_risk && (
                <div style={{ fontSize: 10, color: '#fbbf24', fontFamily: 'sans-serif', background: '#fbbf2410', border: '1px solid #fbbf2420', borderRadius: 4, padding: '6px 10px' }}>
                  ⚠️ {d.key_risk}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
