import React, { useState, useCallback, useEffect } from 'react';

const API = () => window.__AO_API__ || import.meta.env.VITE_API_URL || 'https://289c4c10-4400-4814-b389-cf8b47133fc3.clouding.host';

const SIGNAL_LABELS = {
  sma_flat:      { label: 'SMA 150 flat',     desc: '12+ months horizontal' },
  compressed:    { label: 'Price compressed',  desc: 'ATR < 4% of price' },
  vol_dry:       { label: 'Volume drought',    desc: 'Below prior-year avg' },
  curling:       { label: 'SMA curling up',    desc: 'Slope turned positive' },
  vol_explosion: { label: 'Volume explosion',  desc: '1.8x base avg' },
};

const STAGE_COLORS = {
  sleeping:  { bg: 'rgba(56,138,221,0.12)', border: '#378ADD', label: '😴 Sleeping', sub: 'Watch — not yet' },
  early:     { bg: 'rgba(29,158,117,0.15)', border: '#1D9E75', label: '🌱 Early entry', sub: 'Enter now' },
  confirmed: { bg: 'rgba(239,159,39,0.15)', border: '#EF9F27', label: '🚀 Moving',     sub: 'Move started' },
};

export default function DeepScan() {
  const [data,     setData]     = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [filter,   setFilter]   = useState('all');

  const load = useCallback(async (refresh = false) => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API()}/api/scan/sleeping-giants${refresh ? '?refresh=true' : ''}`);
      if (!r.ok) throw new Error(await r.text());
      setData(await r.json());
    } catch (e) { setError(e.message); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const results = (data?.results || []).filter(r =>
    filter === 'all' || r.stage === filter
  );

  const counts = {
    all:       data?.results?.length || 0,
    early:     (data?.results || []).filter(r => r.stage === 'early').length,
    sleeping:  (data?.results || []).filter(r => r.stage === 'sleeping').length,
    confirmed: (data?.results || []).filter(r => r.stage === 'confirmed').length,
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'monospace', color: '#e0e0e0', maxWidth: 960, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 'bold', letterSpacing: 1.5, color: '#e0e0e0' }}>
            SLEEPING GIANTS
          </div>
          <div style={{ fontSize: 11, color: '#4a5568', marginTop: 4, fontFamily: 'sans-serif' }}>
            Long-base breakout scanner · weekly · cached 7 days
          </div>
        </div>
        <button onClick={() => load(true)} disabled={loading}
          style={{ background: loading ? '#1a2535' : '#1D9E75', border: 'none', borderRadius: 6,
                   color: '#fff', padding: '8px 16px', cursor: 'pointer', fontSize: 12, fontFamily: 'monospace' }}>
          {loading ? '⏳ SCANNING...' : '⚡ REFRESH SCAN'}
        </button>
      </div>

      {/* Stats row */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 20 }}>
          {[
            { key: 'all',       label: 'Total found',    color: '#e0e0e0' },
            { key: 'early',     label: '🌱 Early entry', color: '#1D9E75' },
            { key: 'sleeping',  label: '😴 Sleeping',    color: '#378ADD' },
            { key: 'confirmed', label: '🚀 Moving',      color: '#EF9F27' },
          ].map(s => (
            <div key={s.key}
              onClick={() => setFilter(s.key)}
              style={{ background: filter === s.key ? 'rgba(255,255,255,0.05)' : '#0a0f18',
                       border: `1px solid ${filter === s.key ? s.color : '#1a2535'}`,
                       borderRadius: 8, padding: '12px', cursor: 'pointer', textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: s.color }}>{counts[s.key]}</div>
              <div style={{ fontSize: 10, color: '#4a5568', marginTop: 4, fontFamily: 'sans-serif' }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Cache info */}
      {data?.from_cache && (
        <div style={{ fontSize: 10, color: '#4a5568', marginBottom: 16, fontFamily: 'sans-serif' }}>
          ⚡ Cached results · last scanned {data.cached_at?.slice(0,10)} · {data.results?.length} stocks checked
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ background: 'rgba(255,68,102,0.08)', border: '1px solid #ff446633',
                      borderRadius: 8, padding: '10px 16px', marginBottom: 16, color: '#ff8899', fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Empty */}
      {!loading && !error && data && results.length === 0 && (
        <div style={{ textAlign: 'center', color: '#4a5568', padding: 60, fontFamily: 'sans-serif' }}>
          No stocks found for this filter. Try "All" or run a fresh scan.
        </div>
      )}

      {/* Loading */}
      {loading && !data && (
        <div style={{ textAlign: 'center', color: '#4a5568', padding: 60, fontFamily: 'sans-serif' }}>
          Scanning {100}+ stocks across 3 years of weekly data...
          <br/><span style={{ fontSize: 11, marginTop: 8, display: 'block' }}>This takes 2-3 minutes on first run</span>
        </div>
      )}

      {/* Results */}
      <div style={{ display: 'grid', gap: 12 }}>
        {results.map(r => {
          const stg = STAGE_COLORS[r.stage] || STAGE_COLORS.sleeping;
          const sigKeys = Object.keys(SIGNAL_LABELS);
          return (
            <div key={r.ticker}
              style={{ background: stg.bg, border: `1px solid ${stg.border}`,
                       borderRadius: 10, padding: '14px 18px' }}>

              {/* Top row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 18, fontWeight: 'bold', color: '#e0e0e0' }}>{r.ticker}</span>
                  <span style={{ fontSize: 11, color: stg.border, fontFamily: 'sans-serif',
                                 background: `${stg.border}22`, borderRadius: 4, padding: '2px 8px' }}>
                    {stg.label}
                  </span>
                  <span style={{ fontSize: 11, color: '#4a5568', fontFamily: 'sans-serif' }}>
                    {stg.sub}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: '#e0e0e0' }}>${r.price?.toFixed(2)}</span>
                  <span style={{ fontSize: 12, color: '#4a5568', fontFamily: 'sans-serif' }}>
                    SMA150 ${r.sma150?.toFixed(2)}
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 'bold', color: stg.border }}>
                    {r.score}/5
                  </span>
                </div>
              </div>

              {/* Signal pills */}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {sigKeys.map(k => {
                  const hit = r.signals?.[k];
                  return (
                    <div key={k}
                      style={{ background: hit ? `${stg.border}22` : 'rgba(255,255,255,0.03)',
                               border: `1px solid ${hit ? stg.border : '#1a2535'}`,
                               borderRadius: 6, padding: '4px 10px',
                               opacity: hit ? 1 : 0.4 }}>
                      <div style={{ fontSize: 10, fontWeight: 'bold', color: hit ? stg.border : '#4a5568',
                                    fontFamily: 'sans-serif' }}>
                        {hit ? '✓' : '·'} {SIGNAL_LABELS[k].label}
                      </div>
                      <div style={{ fontSize: 9, color: '#4a5568', fontFamily: 'sans-serif' }}>
                        {SIGNAL_LABELS[k].desc}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      {data && !loading && (
        <div style={{ marginTop: 24, fontSize: 10, color: '#4a5568', fontFamily: 'sans-serif', textAlign: 'center' }}>
          Score 3/5 = watch · 4/5 = early entry · 5/5 = move started
          <br/>Best entry: signals 1-3 present, 4 just triggered (SMA curling)
        </div>
      )}
    </div>
  );
}
