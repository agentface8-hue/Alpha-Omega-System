import React, { useEffect, useState } from 'react';
import { fetchJson } from '../utils/api';

function scoreColor(score) {
  if (score >= 85) return '#00ff88';
  if (score >= 65) return '#fbbf24';
  return '#8899aa';
}

export default function AiRadar() {
  const [briefs, setBriefs] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    try {
      const data = await fetchJson('/api/radar/latest?limit=3', {}, { timeoutMs: 12000, retries: 1 });
      setBriefs(data.briefs || []);
    } catch (e) {
      setError(e.message || 'AI Radar unavailable');
    }
  }

  async function runNow() {
    setRunning(true);
    setError('');
    try {
      const data = await fetchJson('/api/radar/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true }),
      }, { timeoutMs: 45000, retries: 1 });
      setBriefs([data, ...briefs].slice(0, 3));
    } catch (e) {
      setError(e.message || 'Radar run failed');
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const latest = briefs[0];
  const findings = latest?.top_findings || [];

  return (
    <div style={{ background: '#0a0f18', border: '1px solid #1a2535', borderRadius: 10, overflow: 'hidden', marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 12px', borderBottom: '1px solid #1a2535' }}>
        <div>
          <div style={{ color: '#00d4ff', fontFamily: 'monospace', fontSize: 11, letterSpacing: 2 }}>AI RADAR</div>
          <div style={{ color: '#4a6a8a', fontSize: 11, marginTop: 2 }}>Observer-only scout for new AI/platform upgrades</div>
        </div>
        <button onClick={runNow} disabled={running} style={{
          background: running ? '#1a2535' : '#062815',
          color: running ? '#8899aa' : '#00ff88',
          border: '1px solid #00ff8844',
          borderRadius: 6,
          padding: '5px 10px',
          fontSize: 11,
          cursor: running ? 'wait' : 'pointer',
        }}>
          {running ? 'SCANNING...' : 'RUN RADAR'}
        </button>
      </div>
      <div style={{ padding: 12 }}>
        {error && <div style={{ color: '#ff4466', fontSize: 11, marginBottom: 8 }}>{error}</div>}
        <div style={{ color: '#b8c7d9', fontSize: 12, marginBottom: 10 }}>
          {latest?.summary || 'No radar brief yet. Run Radar to scan public AI/tooling sources.'}
        </div>
        {findings.slice(0, 5).map((f) => (
          <div key={`${f.source}-${f.title}`} style={{ borderTop: '1px solid #1a2535', padding: '8px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
              <a href={f.url} target="_blank" rel="noreferrer" style={{ color: '#e5e7eb', fontSize: 12, textDecoration: 'none', fontWeight: 600 }}>
                {f.title}
              </a>
              <span style={{ color: scoreColor(f.relevance_score), fontFamily: 'monospace', fontSize: 11 }}>
                {f.relevance_score}/100
              </span>
            </div>
            <div style={{ color: '#4a6a8a', fontSize: 10, marginTop: 2 }}>
              {f.source} · {f.recommended_action?.toUpperCase()} · {f.status}
            </div>
            {f.summary && <div style={{ color: '#9fb3c8', fontSize: 11, marginTop: 3, lineHeight: 1.35 }}>{f.summary}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
