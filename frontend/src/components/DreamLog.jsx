import { useState, useEffect } from 'react';
import { Moon, TrendingUp, AlertTriangle, Clock } from 'lucide-react';
import { C, SectionCard, PageHeader, Badge, EmptyState, LoadingSpinner } from './UIKit';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const EDGE_COLOR  = { HIGH: C.red,    MEDIUM: C.yellow, LOW: C.textFaint };
const ACTION_COLOR = { WATCH_CLOSELY: C.green, MONITOR: C.blue, WAIT: C.textFaint };

export default function DreamLog() {
  const [dreams,  setDreams]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState(null);

  const fetchDreams = async () => {
    try {
      const res  = await fetch(`${API}/api/dreams/latest?limit=20`);
      const json = await res.json();
      setDreams(json.dreams || []);
    } catch(e) { console.error(e); }
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
    } catch(e) { console.error(e); }
    setRunning(false);
  };

  useEffect(() => { fetchDreams(); }, []);

  return (
    <div style={{ padding: '28px 28px', maxWidth: 900, margin: '0 auto' }}>

      <PageHeader
        icon={<Moon size={18} />}
        title="DREAM LOG"
        subtitle="GEMINI BACKGROUND ANALYSIS · RUNS EVERY 4H ON MARKET DAYS"
        right={
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {lastRun && (
              <span style={{ fontSize: 9, color: C.textFaint, fontFamily: 'sans-serif', display: 'flex', alignItems: 'center', gap: 4 }}>
                <Clock size={10} /> {lastRun}
              </span>
            )}
            <button onClick={runCycle} disabled={running} style={{
              background: running ? C.inner : 'rgba(192,132,252,0.12)',
              border: `1px solid ${running ? C.border : C.purple + '55'}`,
              color: running ? C.textFaint : C.purple,
              borderRadius: 6, padding: '8px 20px',
              fontSize: 11, fontWeight: 'bold', fontFamily: 'sans-serif',
              cursor: running ? 'not-allowed' : 'pointer', letterSpacing: 1,
            }}>
              {running ? '⏳ RUNNING...' : '▶ RUN NOW'}
            </button>
          </div>
        }
      />

      {loading && <LoadingSpinner text="Loading dream log..." />}

      {!loading && dreams.length === 0 && (
        <SectionCard title="DREAM LOG" accent={C.purple}>
          <EmptyState
            icon={<Moon size={36} />}
            title="No dreams yet"
            subtitle="Hit Run Now to trigger the first cycle — Gemini will analyse the market and identify the best edge."
          />
        </SectionCard>
      )}

      {!loading && dreams.map((d, i) => {
        const ec  = EDGE_COLOR[d.edge_level]   || C.textFaint;
        const ac  = ACTION_COLOR[d.action]      || C.textFaint;
        const ts  = d.ts ? d.ts.slice(0, 16).replace('T', ' ') + ' UTC' : '';
        return (
          <div key={i} style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderLeft: `3px solid ${ec}`,
            borderRadius: 12,
            padding: '18px 22px',
            marginBottom: 14,
          }}>
            {/* Top row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
              <Badge label={d.edge_level} color={ec} size="lg" />
              {d.top_ticker && (
                <span style={{ fontSize: 15, fontWeight: 'bold', color: C.blue, fontFamily: 'monospace' }}>
                  {d.top_ticker}
                </span>
              )}
              <Badge label={d.action} color={ac} />
              <span style={{ fontSize: 9, color: C.textFaint, fontFamily: 'sans-serif', marginLeft: 'auto' }}>{ts}</span>
            </div>

            {/* Market context */}
            <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
              {d.regime && (
                <span style={{ fontSize: 10, color: C.textDim, fontFamily: 'sans-serif' }}>
                  📊 {d.regime}
                </span>
              )}
              {d.vix > 0 && (
                <span style={{ fontSize: 10, color: C.textDim, fontFamily: 'sans-serif' }}>
                  VIX {d.vix}
                </span>
              )}
              {d.spy_change !== undefined && (
                <span style={{ fontSize: 10, color: d.spy_change >= 0 ? C.green : C.red, fontFamily: 'sans-serif' }}>
                  SPY {d.spy_change >= 0 ? '+' : ''}{d.spy_change}%
                </span>
              )}
            </div>

            {/* Analysis */}
            {d.analysis && (
              <div style={{ fontSize: 12, color: C.text, fontFamily: 'sans-serif', lineHeight: 1.65, marginBottom: 12 }}>
                {d.analysis}
              </div>
            )}

            {/* Risk */}
            {d.key_risk && (
              <div style={{
                background: C.yellow + '0e',
                border: `1px solid ${C.yellow}22`,
                borderRadius: 6, padding: '8px 12px',
                fontSize: 10, color: C.yellow,
                fontFamily: 'sans-serif',
                display: 'flex', alignItems: 'flex-start', gap: 7,
              }}>
                <AlertTriangle size={11} style={{ marginTop: 1, flexShrink: 0 }} />
                {d.key_risk}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
