import React, { useEffect, useState } from 'react';
import { fetchJson } from '../utils/api';

function fmtTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}

function colorFor(status) {
  if ((status || '').includes('closed')) return '#fbbf24';
  if ((status || '').includes('open')) return '#00ff88';
  if ((status || '').includes('veto')) return '#ff4466';
  return '#00d4ff';
}

export default function AuditTrail({ compact = false, limit = 12 }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const data = await fetchJson(`/api/audit/recent?limit=${limit}`, {}, { timeoutMs: 12000, retries: 1 });
      setRecords(data.records || []);
    } catch (e) {
      setError(e.message || 'audit unavailable');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [limit]);

  return (
    <div style={{
      background: '#0a0f18',
      border: '1px solid #1a2535',
      borderRadius: 10,
      overflow: 'hidden',
      marginTop: compact ? 10 : 0,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 12px', borderBottom: '1px solid #1a2535',
      }}>
        <div style={{ color: '#c084fc', fontFamily: 'monospace', fontSize: 10, letterSpacing: 2 }}>
          DECISION REPLAY AUDIT
        </div>
        <button onClick={load} disabled={loading} style={{
          background: 'transparent', border: '1px solid #1a2535', borderRadius: 4,
          color: '#8899aa', padding: '3px 8px', fontSize: 9, fontFamily: 'monospace',
          cursor: 'pointer',
        }}>
          {loading ? 'LOADING' : 'REFRESH'}
        </button>
      </div>
      <div style={{ maxHeight: compact ? 220 : 360, overflow: 'auto', padding: 10 }}>
        {error && <div style={{ color: '#ff4466', fontSize: 11, fontFamily: 'monospace' }}>{error}</div>}
        {!error && records.length === 0 && (
          <div style={{ color: '#4a6a8a', fontSize: 11, fontFamily: 'monospace' }}>
            {loading ? 'Loading audit trail...' : 'No audit records yet.'}
          </div>
        )}
        {records.map((r) => (
          <div key={r.id} style={{
            border: '1px solid #1a2535',
            borderLeft: `3px solid ${colorFor(r.status)}`,
            borderRadius: 8,
            padding: '8px 10px',
            marginBottom: 8,
            background: '#050810',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 4 }}>
              <span style={{ color: '#e5e7eb', fontFamily: 'monospace', fontWeight: 'bold', fontSize: 12 }}>
                {r.symbol || 'SYSTEM'} · {r.action || r.event_type}
              </span>
              <span style={{ color: '#4a6a8a', fontFamily: 'monospace', fontSize: 10 }}>{fmtTime(r.ts)}</span>
            </div>
            <div style={{ color: colorFor(r.status), fontFamily: 'monospace', fontSize: 10, marginBottom: 4 }}>
              {r.event_type} · {r.status || 'recorded'}{r.confidence != null ? ` · ${Math.round(r.confidence * 100)}%` : ''}
            </div>
            <div style={{ color: '#b8c7d9', fontSize: 11, lineHeight: 1.35 }}>
              {(r.verdict || r.metadata?.reason || 'Decision captured for replay.').slice(0, 220)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
