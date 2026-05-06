import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Zap, RotateCcw, Target, BarChart2, Clock, ChevronDown, ChevronRight, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';

const API = () => import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const fmt  = (n, d=2) => (n == null ? '—' : Number(n).toFixed(d));
const pct  = n => `${n > 0 ? '+' : ''}${fmt(n)}%`;
const usd  = n => `$${fmt(n, 0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`;
const clr  = n => n > 0 ? '#00ff88' : n < 0 ? '#ff4466' : '#94a3b8';
const heatClr = c => c >= 75 ? '#00ff88' : c >= 60 ? '#fbbf24' : '#94a3b8';
const MAX_SLOTS_FALLBACK = 10;

const formatDuration = (startIso, endIso = null) => {
  if (!startIso) return '—';
  try {
    const start = new Date(startIso);
    const end   = endIso ? new Date(endIso) : new Date();
    const mins  = Math.floor((end - start) / 60000);
    if (mins < 1)  return '<1m';
    if (mins < 60) return `${mins}m`;
    const hrs    = Math.floor(mins / 60);
    const remMin = mins % 60;
    if (hrs < 24)  return `${hrs}h ${remMin}m`;
    const days   = Math.floor(hrs / 24);
    const remHrs = hrs % 24;
    return `${days}d ${remHrs}h`;
  } catch { return '—'; }
};

const buildCloseReason = (pos) => {
  if (pos.close_reason && pos.close_reason.length > 5) return pos.close_reason;
  const lastTrade = (pos.trades || []).slice(-1)[0] || {};
  const level     = lastTrade.tp_level || '';
  const exitPrice = lastTrade.price;
  const entry     = pos.entry_price;
  const pnl       = pos.realized_pnl || 0;
  const absP      = Math.abs(pnl).toFixed(0);
  const sign      = pnl >= 0 ? '+' : '-';
  if (level === 'SL' || level?.toLowerCase().includes('stop'))
    return `Stop-loss hit @ $${fmt(exitPrice,2)} (entry $${fmt(entry,2)}, loss $${absP})`;
  if (level === 'TP3') return `TP3 hit @ $${fmt(exitPrice,2)} — full target reached (${sign}$${absP})`;
  if (level === 'TP2') return `TP2 hit @ $${fmt(exitPrice,2)} — 2nd target (${sign}$${absP})`;
  if (level === 'TP1') return `TP1 hit @ $${fmt(exitPrice,2)} — 1st target (${sign}$${absP})`;
  if (level === 'MANUAL' || level?.toLowerCase().includes('manual'))
    return `Manual close @ $${fmt(exitPrice,2)} — ${pnl >= 0 ? 'profit' : 'loss'} ${sign}$${absP}`;
  if (level === 'TIMEOUT')
    return `Timeout — closed @ $${fmt(exitPrice,2)} after max hold period (${sign}$${absP})`;
  if (level) return `${level} @ $${fmt(exitPrice,2)} (${sign}$${absP})`;
  return `Closed @ $${fmt(exitPrice,2)} (${sign}$${absP})`;
};

const reasonColor = (pos) => {
  const pnl = pos.realized_pnl || 0;
  const level = ((pos.trades || []).slice(-1)[0] || {}).tp_level || '';
  if (level === 'SL' || level?.toLowerCase().includes('stop')) return '#ff4466';
  if (level?.startsWith('TP')) return '#00ff88';
  return pnl >= 0 ? '#00ff88' : '#ff4466';
};

const StatCard = ({ label, value, sub, color, small }) => (
  <div style={{ background:'#0d1a2a', border:'1px solid #1a2535', borderRadius:8, padding:'12px 16px', minWidth:100, textAlign:'center' }}>
    <div style={{ fontSize:9, color:'#8899aa', letterSpacing:1, marginBottom:5, fontFamily:'monospace' }}>{label}</div>
    <div style={{ fontSize: small ? 16 : 20, fontWeight:'bold', color: color || '#00d4ff', fontFamily:'monospace' }}>{value}</div>
    {sub && <div style={{ fontSize:9, color:'#8899aa', marginTop:3 }}>{sub}</div>}
  </div>
);

// ── Open position card — clickable, expands full detail panel ──────────────
const PositionCard = ({ pos, onClose }) => {
  const [expanded, setExpanded] = useState(false);
  const pnl       = pos.unrealized_pnl || 0;
  const pnlPct    = pos.unrealized_pnl_pct || 0;
  const entry     = pos.entry_price;
  const curr      = pos.current_price || entry;
  const sl        = pos.sl;
  const tp1       = pos.tp1;
  const tp2       = pos.tp2;
  const tp3       = pos.tp3;
  const isPartial = pos.status === 'partial';
  const duration  = formatDuration(pos.entry_date);
  const range     = tp1 - sl;
  const progress  = range > 0 ? Math.min(100, Math.max(0, (curr - sl) / range * 100)) : 0;
  const barColor  = pnl >= 0 ? '#00ff88' : '#ff4466';

  // Distances to targets
  const distToSL  = ((curr - sl) / curr * 100).toFixed(2);
  const distToTP1 = ((tp1 - curr) / curr * 100).toFixed(2);
  const distToTP2 = ((tp2 - curr) / curr * 100).toFixed(2);
  const distToTP3 = ((tp3 - curr) / curr * 100).toFixed(2);
  const rr        = range > 0 ? ((tp1 - entry) / (entry - sl)).toFixed(2) : '—';

  // MAE/MFE as %
  const maePct = entry > 0 ? (pos.mae / entry * 100).toFixed(2) : 0;
  const mfePct = entry > 0 ? (pos.mfe / entry * 100).toFixed(2) : 0;

  // Risk status
  const atRisk = curr <= sl * 1.02;  // within 2% of SL
  const nearTP1 = curr >= tp1 * 0.98;

  return (
    <div style={{
      background: expanded ? '#0c1420' : '#0a1018',
      border: `1px solid ${expanded ? '#c084fc44' : pnl >= 0 ? '#1a3525' : '#351a1a'}`,
      borderRadius: 10, marginBottom: 10, overflow: 'hidden',
      transition: 'border-color 0.2s',
    }}>
      {/* ── Main row — always visible ── */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{ padding: 14, cursor: 'pointer' }}
      >
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            {expanded
              ? <ChevronDown size={13} color="#c084fc" />
              : <ChevronRight size={13} color="#8899aa" />
            }
            <span style={{ fontSize:16, fontWeight:'bold', color:'#e0e0e0', fontFamily:'monospace' }}>{pos.ticker}</span>
            {isPartial && <span style={{ fontSize:9, background:'rgba(251,191,36,0.15)', color:'#fbbf24', borderRadius:4, padding:'2px 6px', border:'1px solid #fbbf24' }}>PARTIAL</span>}
            {pos.tp1_hit && <span style={{ fontSize:9, background:'rgba(0,255,136,0.1)', color:'#00ff88', borderRadius:4, padding:'2px 6px' }}>TP1✓</span>}
            {pos.tp2_hit && <span style={{ fontSize:9, background:'rgba(0,255,136,0.15)', color:'#00ff88', borderRadius:4, padding:'2px 6px' }}>TP2✓</span>}
            {pos.conviction > 0 && <span style={{ fontSize:9, color:heatClr(pos.conviction), fontFamily:'monospace' }}>{pos.conviction}%</span>}
            <span style={{ fontSize:9, color:'#00d4ff', display:'flex', alignItems:'center', gap:3, background:'rgba(0,212,255,0.08)', borderRadius:4, padding:'2px 6px' }}>
              <Clock size={9} /> {duration}
            </span>
            {atRisk && <span style={{ fontSize:9, background:'rgba(255,68,102,0.15)', color:'#ff4466', borderRadius:4, padding:'2px 6px' }}>⚠ NEAR SL</span>}
            {nearTP1 && !pos.tp1_hit && <span style={{ fontSize:9, background:'rgba(0,255,136,0.15)', color:'#00ff88', borderRadius:4, padding:'2px 6px' }}>→ TP1</span>}
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:6 }}>
            <span style={{ fontSize:18, fontWeight:'bold', color:clr(pnl), fontFamily:'monospace' }}>
              {pnl >= 0 ? '+' : ''}{fmt(pnl, 0)} <span style={{ fontSize:12 }}>({pct(pnlPct)})</span>
            </span>
            <button
              onClick={e => { e.stopPropagation(); onClose(pos.id); }}
              style={{ background:'transparent', border:'1px solid #ff4466', borderRadius:4, padding:'3px 8px', color:'#ff4466', fontSize:10, cursor:'pointer' }}
            >✕ Close</button>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ position:'relative', height:6, background:'#1a2535', borderRadius:3, marginBottom:10, overflow:'hidden' }}>
          <div style={{ position:'absolute', left:0, top:0, height:'100%', width:`${progress}%`, background:barColor, borderRadius:3, transition:'width 0.5s' }} />
        </div>

        {/* Level grid */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:6, fontSize:10, fontFamily:'monospace' }}>
          {[
            { label:'ENTRY', val:`$${fmt(entry,2)}`, color:'#94a3b8' },
            { label:'PRICE', val:`$${fmt(curr,2)}`, color:clr(pnl) },
            { label:'SL', val:`$${fmt(sl,2)}`, color:'#ff4466' },
            { label:'TP1', val:`$${fmt(tp1,2)}`, color: pos.tp1_hit ? '#00ff88' : '#8899aa' },
            { label:'TP2', val:`$${fmt(tp2,2)}`, color: pos.tp2_hit ? '#00ff88' : '#8899aa' },
            { label:'TP3', val:`$${fmt(tp3,2)}`, color:'#8899aa' },
          ].map(l => (
            <div key={l.label} style={{ textAlign:'center' }}>
              <div style={{ color:'#8899aa', fontSize:8, marginBottom:2 }}>{l.label}</div>
              <div style={{ color:l.color, fontWeight:'bold' }}>{l.val}</div>
            </div>
          ))}
        </div>

        <div style={{ display:'flex', gap:12, marginTop:8, fontSize:10, color:'#8899aa', fontFamily:'monospace' }}>
          <span>{pos.shares_remaining}/{pos.shares} shares</span>
          <span>Size: ${fmt(pos.position_size, 0)}</span>
          <span>Risk: ${fmt(pos.risk_actual, 0)}</span>
          {pos.mae != null && <span style={{ color:'#ff4466' }}>MAE: {pct(pos.mae / entry * 100)}</span>}
          {pos.mfe != null && <span style={{ color:'#00ff88' }}>MFE: {pct(pos.mfe / entry * 100)}</span>}
        </div>
      </div>

      {/* ── Expanded detail panel ── */}
      {expanded && (
        <div style={{ borderTop:'1px solid #1a2535', padding:'14px', background:'#080c14' }}>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:14 }}>

            {/* Panel 1 — Target distances */}
            <div style={{ background:'#0d1520', border:'1px solid #1a2535', borderRadius:8, padding:'12px 14px' }}>
              <div style={{ fontSize:8, color:'#c084fc', letterSpacing:1, marginBottom:10, fontFamily:'monospace', fontWeight:'bold' }}>TARGET DISTANCES</div>
              <div style={{ fontSize:11, fontFamily:'monospace', lineHeight:2 }}>
                <div style={{ display:'flex', justifyContent:'space-between' }}>
                  <span style={{ color:'#ff4466' }}>SL</span>
                  <span style={{ color:'#ff4466' }}>${fmt(sl,2)}</span>
                  <span style={{ color: parseFloat(distToSL) < 2 ? '#ff4466' : '#8899aa' }}>{distToSL}% away</span>
                </div>
                <div style={{ display:'flex', justifyContent:'space-between' }}>
                  <span style={{ color: pos.tp1_hit ? '#00ff88' : '#fbbf24' }}>TP1 {pos.tp1_hit ? '✓' : ''}</span>
                  <span style={{ color:'#e0e0e0' }}>${fmt(tp1,2)}</span>
                  <span style={{ color:'#8899aa' }}>{pos.tp1_hit ? 'hit' : `+${distToTP1}%`}</span>
                </div>
                <div style={{ display:'flex', justifyContent:'space-between' }}>
                  <span style={{ color: pos.tp2_hit ? '#00ff88' : '#94a3b8' }}>TP2 {pos.tp2_hit ? '✓' : ''}</span>
                  <span style={{ color:'#e0e0e0' }}>${fmt(tp2,2)}</span>
                  <span style={{ color:'#8899aa' }}>{pos.tp2_hit ? 'hit' : `+${distToTP2}%`}</span>
                </div>
                <div style={{ display:'flex', justifyContent:'space-between' }}>
                  <span style={{ color:'#94a3b8' }}>TP3</span>
                  <span style={{ color:'#e0e0e0' }}>${fmt(tp3,2)}</span>
                  <span style={{ color:'#8899aa' }}>+{distToTP3}%</span>
                </div>
                <div style={{ borderTop:'1px solid #1a2535', marginTop:6, paddingTop:6, display:'flex', justifyContent:'space-between' }}>
                  <span style={{ color:'#8899aa' }}>R:R</span>
                  <span style={{ color: parseFloat(rr) >= 2 ? '#00ff88' : '#fbbf24', fontWeight:'bold' }}>{rr}:1</span>
                </div>
              </div>
            </div>

            {/* Panel 2 — Position stats */}
            <div style={{ background:'#0d1520', border:'1px solid #1a2535', borderRadius:8, padding:'12px 14px' }}>
              <div style={{ fontSize:8, color:'#c084fc', letterSpacing:1, marginBottom:10, fontFamily:'monospace', fontWeight:'bold' }}>POSITION STATS</div>
              <div style={{ fontSize:11, fontFamily:'monospace', lineHeight:2, color:'#94a3b8' }}>
                <div>Unrealized P&L: <b style={{color:clr(pnl)}}>{pnl>=0?'+':''}{fmt(pnl,0)} ({pct(pnlPct)})</b></div>
                <div>Realized P&L: <b style={{color:clr(pos.realized_pnl||0)}}>{(pos.realized_pnl||0)>=0?'+':''}{fmt(pos.realized_pnl||0,0)}</b></div>
                <div>Shares held: <b style={{color:'#e0e0e0'}}>{pos.shares_remaining} / {pos.shares}</b></div>
                <div>Position size: <b style={{color:'#e0e0e0'}}>${fmt(pos.position_size,0)}</b></div>
                <div>Risk amount: <b style={{color:'#ff4466'}}>${fmt(pos.risk_actual,0)}</b></div>
                <div>Time open: <b style={{color:'#00d4ff'}}>{duration}</b></div>
                <div>MAE: <b style={{color:'#ff4466'}}>{maePct}%</b> · MFE: <b style={{color:'#00ff88'}}>+{mfePct}%</b></div>
              </div>
            </div>

            {/* Panel 3 — Trade log */}
            <div style={{ background:'#0d1520', border:'1px solid #1a2535', borderRadius:8, padding:'12px 14px' }}>
              <div style={{ fontSize:8, color:'#c084fc', letterSpacing:1, marginBottom:10, fontFamily:'monospace', fontWeight:'bold' }}>TRADE LOG</div>
              {(pos.trades || []).length === 0 && (
                <div style={{ fontSize:10, color:'#2a4a5a' }}>No trades recorded</div>
              )}
              {(pos.trades || []).map((t, i) => (
                <div key={i} style={{ fontSize:10, fontFamily:'monospace', lineHeight:1.8, borderBottom:'1px solid #0d1520', paddingBottom:4, marginBottom:4 }}>
                  <div style={{ display:'flex', justifyContent:'space-between' }}>
                    <span style={{ color: t.type==='entry'?'#00d4ff': t.pnl>=0?'#00ff88':'#ff4466', fontWeight:'bold' }}>
                      {t.type?.replace(/_/g,' ').toUpperCase()}
                    </span>
                    {t.pnl != null && t.type !== 'entry' && (
                      <span style={{ color: t.pnl>=0?'#00ff88':'#ff4466' }}>{t.pnl>=0?'+':''}{fmt(t.pnl,0)}</span>
                    )}
                  </div>
                  <div style={{ color:'#8899aa' }}>
                    @ ${fmt(t.price,2)} · {t.shares} shares
                    {t.executed_at && <span style={{ color:'#2a4a5a' }}> · {t.executed_at.slice(11,16)}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Closed trade row — clickable, expands full detail panel ───────────────
const ClosedRow = ({ pos }) => {
  const [expanded, setExpanded] = useState(false);
  const pnl       = pos.realized_pnl || 0;
  const pnlPct    = pos.position_size > 0 ? (pnl / pos.position_size * 100) : 0;
  const lastTrade = (pos.trades || []).slice(-1)[0] || {};
  const duration  = formatDuration(pos.entry_date, pos.closed_at);
  const fullReason = buildCloseReason(pos);
  const rColor    = reasonColor(pos);
  const isWin     = pnl >= 0;

  return (
    <>
      <tr
        onClick={() => setExpanded(e => !e)}
        style={{ borderBottom: expanded ? 'none' : '1px solid #0d1a2a', cursor:'pointer', background: expanded ? '#0d1520' : 'transparent' }}
      >
        <td style={{ padding:'8px 6px', color:'#e0e0e0', fontWeight:'bold', fontFamily:'monospace' }}>
          <span style={{ display:'inline-flex', alignItems:'center', gap:4 }}>
            {expanded ? <ChevronDown size={10} color="#8899aa" /> : <ChevronRight size={10} color="#8899aa" />}
            {pos.ticker}
          </span>
        </td>
        <td style={{ padding:'8px 6px', textAlign:'right', color:'#8899aa', fontSize:10 }}>{(pos.entry_date||'').slice(0,10)}</td>
        <td style={{ padding:'8px 6px', textAlign:'right', color:'#94a3b8' }}>${fmt(pos.entry_price,2)}</td>
        <td style={{ padding:'8px 6px', textAlign:'right', color:'#94a3b8' }}>${fmt(lastTrade.price,2)}</td>
        <td style={{ padding:'8px 6px', textAlign:'right', color:clr(pnl), fontWeight:'bold' }}>{pnl>=0?'+':''}{fmt(pnl,0)}</td>
        <td style={{ padding:'8px 6px', textAlign:'right', color:clr(pnlPct) }}>{pct(pnlPct)}</td>
        <td style={{ padding:'8px 6px', textAlign:'right', color:'#8899aa', fontSize:10 }}>
          <span style={{ display:'inline-flex', alignItems:'center', gap:3 }}>
            <Clock size={9} color="#2a4a5a" /> {duration}
          </span>
        </td>
        <td style={{ padding:'8px 6px', textAlign:'left', fontSize:10 }}>
          <span style={{ color:rColor, background:`${rColor}15`, border:`1px solid ${rColor}33`, borderRadius:4, padding:'2px 7px', fontWeight:'bold', whiteSpace:'nowrap' }}>
            {lastTrade.tp_level || (isWin ? 'WIN' : 'LOSS')}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr style={{ borderBottom:'1px solid #0d1a2a', background:'#080c14' }}>
          <td colSpan={8} style={{ padding:'10px 14px' }}>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:16 }}>
              <div style={{ background:`${rColor}0d`, border:`1px solid ${rColor}33`, borderRadius:8, padding:'10px 14px' }}>
                <div style={{ fontSize:8, color:'#8899aa', letterSpacing:1, marginBottom:5, fontFamily:'monospace' }}>CLOSE REASON</div>
                <div style={{ fontSize:12, color:rColor, fontWeight:'bold', lineHeight:1.5 }}>{fullReason}</div>
              </div>
              <div style={{ background:'#0d1520', border:'1px solid #1a2535', borderRadius:8, padding:'10px 14px' }}>
                <div style={{ fontSize:8, color:'#8899aa', letterSpacing:1, marginBottom:8, fontFamily:'monospace' }}>TRADE STATS</div>
                <div style={{ fontSize:11, color:'#94a3b8', fontFamily:'monospace', lineHeight:1.8 }}>
                  <div>Entry: <b style={{color:'#e0e0e0'}}>${fmt(pos.entry_price,2)}</b> → Exit: <b style={{color:rColor}}>${fmt(lastTrade.price,2)}</b></div>
                  <div>Shares: <b style={{color:'#e0e0e0'}}>{pos.shares}</b> · Size: <b style={{color:'#e0e0e0'}}>${fmt(pos.position_size,0)}</b></div>
                  <div>Risk: <b style={{color:'#ff4466'}}>${fmt(pos.risk_actual,0)}</b> · Held: <b style={{color:'#00d4ff'}}>{duration}</b></div>
                  {pos.tp1_hit && <div style={{color:'#00ff88'}}>✓ TP1 hit</div>}
                  {pos.tp2_hit && <div style={{color:'#00ff88'}}>✓ TP2 hit</div>}
                  {pos.tp3_hit && <div style={{color:'#00ff88'}}>✓ TP3 hit</div>}
                </div>
              </div>
              <div style={{ background:'#0d1520', border:'1px solid #1a2535', borderRadius:8, padding:'10px 14px' }}>
                <div style={{ fontSize:8, color:'#8899aa', letterSpacing:1, marginBottom:8, fontFamily:'monospace' }}>TRADE LOG</div>
                {(pos.trades || []).map((t, i) => (
                  <div key={i} style={{ fontSize:10, color:'#8899aa', fontFamily:'monospace', lineHeight:1.7 }}>
                    <span style={{ color: t.type==='entry'?'#00d4ff': t.pnl>=0?'#00ff88':'#ff4466' }}>
                      {t.type?.replace(/_/g,' ').toUpperCase()}
                    </span>
                    {' '}@ ${fmt(t.price,2)} · {t.shares}sh
                    {t.pnl != null && t.type !== 'entry' && (
                      <span style={{ color: t.pnl>=0?'#00ff88':'#ff4466' }}> {t.pnl>=0?'+':''}{fmt(t.pnl,0)}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

export default function PortfolioTab() {
  const [data, setData]             = useState(null);
  const [loading, setLoading]       = useState(false);
  const [checking, setChecking]     = useState(false);
  const [openTicker, setOpenTicker] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [countdown, setCountdown]   = useState(30);
  const [error, setError]           = useState(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const r = await fetch(`${API()}/api/portfolio`);
      if (!r.ok) throw new Error(await r.text());
      setData(await r.json());
      setError(null);
    } catch (e) { setError(e.message); }
    setLoading(false);
  }, []);

  const checkPrices = async () => {
    setChecking(true);
    try {
      const r = await fetch(`${API()}/api/portfolio/check`, { method:'POST' });
      if (!r.ok) throw new Error(await r.text());
      const result = await r.json();
      setData(result.portfolio);
      setCountdown(30);
    } catch (e) { setError(e.message); }
    setChecking(false);
  };

  const openFromScan = async () => {
    if (!openTicker.trim()) return;
    setLoading(true);
    try {
      const scanRes = await fetch(`${API()}/api/scan`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: [openTicker.trim().toUpperCase()], watchlist: null }),
      });
      const scanData = await scanRes.json();
      const best = (scanData.results || [])[0];
      if (!best || best.hard_fail) { setError(`${openTicker}: No valid signal`); setLoading(false); return; }
      const r = await fetch(`${API()}/api/portfolio/open`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: best.ticker, entry_price: best.entry_high || best.last_close,
          sl: best.sl, tp1: best.tp1, tp2: best.tp2, tp3: best.tp3,
          conviction: best.conviction_pct, asset_type: 'stock' }),
      });
      const result = await r.json();
      if (result.error) setError(result.error);
      else { setOpenTicker(''); await load(); }
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  const autopilot = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API()}/api/portfolio/autopilot`, { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
      const result = await r.json();
      await load();
      if (result.opened?.length > 0) setError(null);
      else setError(result.message || 'No qualifying signals found (need conviction >= 55%)');
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  const closePos = async (id) => {
    try {
      await fetch(`${API()}/api/portfolio/close/${id}`, { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
      await load(true);
    } catch (e) { setError(e.message); }
  };

  const reset = async () => {
    if (!window.confirm('Reset portfolio to $25,000? All positions will be cleared.')) return;
    await fetch(`${API()}/api/portfolio/reset`, { method:'POST' });
    await load();
  };

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => setCountdown(c => { if (c <= 1) { checkPrices(); return 30; } return c - 1; }), 1000);
    return () => clearInterval(timer);
  }, [autoRefresh]);

  const s               = data?.stats || {};
  const openPositions   = data?.open_positions  || [];
  const closedPositions = (data?.closed_positions || []).slice().reverse();
  const maxPositions    = data?.state?.max_positions ?? MAX_SLOTS_FALLBACK;
  const slots           = Math.max(0, maxPositions - openPositions.length);
  const totalPnl = s.total_pnl || 0;

  return (
    <div style={{ padding:20, fontFamily:"'Inter',sans-serif", color:'#e0e0e0', maxWidth:1200, margin:'0 auto' }}>

      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ background:'linear-gradient(135deg,#00d4ff,#0088cc)', borderRadius:10, padding:10, display:'flex' }}>
            <BarChart2 size={22} color='#fff' />
          </div>
          <div>
            <div style={{ fontSize:18, fontWeight:'bold', color:'#fff', letterSpacing:1 }}>ACTIVE PORTFOLIO</div>
            <div style={{ fontSize:11, color:'#8899aa' }}>Paper trading · $25K starting capital · Max {maxPositions} positions · $5,000/trade · $500 risk/trade</div>
          </div>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <button onClick={() => { setAutoRefresh(a => !a); setCountdown(30); }}
            style={{ background: autoRefresh ? 'rgba(0,212,255,0.15)' : 'transparent', border:`1px solid ${autoRefresh?'#00d4ff':'#1a2535'}`, borderRadius:6, padding:'6px 12px', color: autoRefresh?'#00d4ff':'#8899aa', fontSize:11, cursor:'pointer' }}>
            {autoRefresh ? `AUTO ${countdown}s` : 'AUTO OFF'}
          </button>
          <button onClick={checkPrices} disabled={checking}
            style={{ background:'linear-gradient(135deg,#00d4ff,#0066aa)', border:'none', borderRadius:6, padding:'6px 14px', color:'#fff', fontSize:12, fontWeight:'bold', cursor:'pointer', display:'flex', alignItems:'center', gap:5 }}>
            <RefreshCw size={13} className={checking?'spin':''} /> {checking?'CHECKING...':'CHECK PRICES'}
          </button>
          <button onClick={reset} style={{ background:'transparent', border:'1px solid #ff4466', borderRadius:6, padding:'6px 10px', color:'#ff4466', fontSize:11, cursor:'pointer' }}>
            <RotateCcw size={12} />
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background:'rgba(255,68,102,0.1)', border:'1px solid #ff4466', borderRadius:8, padding:10, marginBottom:14, color:'#ff4466', fontSize:12 }}>
          {error} <span style={{ cursor:'pointer', float:'right' }} onClick={() => setError(null)}>✕</span>
        </div>
      )}

      {/* Stats */}
      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap' }}>
        <StatCard label="TOTAL VALUE"  value={usd(s.total_value)}  color='#00d4ff' />
        <StatCard label="CASH"         value={usd(s.cash)}          color='#7ee8ff' sub={`${slots} slot${slots!==1?'s':''} open`} />
        <StatCard label="TOTAL P&L"    value={`${totalPnl>=0?'+':''}${fmt(totalPnl,0)}`} color={clr(totalPnl)} sub={pct(s.total_pnl_pct||0)} />
        <StatCard label="UNREALIZED"   value={`${(s.total_unrealized_pnl||0)>=0?'+':''}${fmt(s.total_unrealized_pnl||0,0)}`} color={clr(s.total_unrealized_pnl||0)} />
        <StatCard label="REALIZED"     value={`${(s.total_realized_pnl||0)>=0?'+':''}${fmt(s.total_realized_pnl||0,0)}`} color={clr(s.total_realized_pnl||0)} />
        <StatCard label="OPEN"         value={s.open_count||0}      sub="positions" color='#fbbf24' />
        <StatCard label="WIN RATE"     value={`${s.win_rate||0}%`}  sub={`${s.total_closed||0} closed`} color={s.win_rate>=60?'#00ff88':s.win_rate>=40?'#fbbf24':'#ff4466'} />
      </div>

      {/* Positions */}
      <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10, padding:16, marginBottom:20 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
          <div>
            <div style={{ fontSize:13, fontWeight:'bold', color:'#00d4ff', letterSpacing:1 }}>
              POSITIONS — {openPositions.length}/{maxPositions} SLOTS USED
            </div>
            <div style={{ fontSize:10, color:'#2a4a5a', marginTop:2, fontFamily:'sans-serif' }}>Click any position to expand details</div>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            <input value={openTicker} onChange={e => setOpenTicker(e.target.value.toUpperCase())}
              onKeyDown={e => e.key==='Enter' && openFromScan()}
              placeholder="TICKER" maxLength={6}
              style={{ width:90, background:'#0d1a2a', border:'1px solid #1a2535', borderRadius:6, padding:'6px 10px', color:'#e0e0e0', fontSize:13, fontFamily:'monospace', letterSpacing:2, textAlign:'center' }} />
            <button onClick={openFromScan} disabled={loading || !openTicker.trim()}
              style={{ background:'linear-gradient(135deg,#00ff88,#00bb66)', border:'none', borderRadius:6, padding:'6px 14px', color:'#000', fontSize:12, fontWeight:'bold', cursor:'pointer', display:'flex', alignItems:'center', gap:5 }}>
              <Target size={13} /> OPEN
            </button>
            <button onClick={autopilot} disabled={loading || slots===0}
              style={{ background: slots===0?'#1a2535':'linear-gradient(135deg,#7c3aed,#a855f7)', border: slots===0?'1px solid #2a3545':'none', borderRadius:6, padding:'6px 14px', color: slots===0?'#4a5568':'#fff', fontSize:12, fontWeight:'bold', cursor: slots===0?'not-allowed':'pointer', display:'flex', alignItems:'center', gap:5 }}>
              <Zap size={13} /> {slots===0 ? 'PORTFOLIO FULL' : `AUTO-FILL ${slots} SLOTS`}
            </button>
          </div>
        </div>

        {loading && <div style={{ padding:10, color:'#fbbf24', fontSize:11, fontFamily:'monospace' }}>⏳ Processing...</div>}
        {openPositions.length === 0 && !loading && (
          <div style={{ textAlign:'center', padding:'30px 20px', color:'#8899aa', fontSize:12 }}>
            No open positions. Enter a ticker or click AUTO-FILL to start.
          </div>
        )}
        {openPositions.map(pos => <PositionCard key={pos.id} pos={pos} onClose={closePos} />)}
        {Array.from({ length: slots }).map((_, i) => (
          <div key={i} style={{ border:'1px dashed #1a2535', borderRadius:10, padding:14, marginBottom:10, textAlign:'center', color:'#1a2535', fontSize:12 }}>
            — empty slot {openPositions.length + i + 1} —
          </div>
        ))}
      </div>

      {/* Trade log */}
      {closedPositions.length > 0 && (
        <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10, padding:16 }}>
          <div style={{ fontSize:13, fontWeight:'bold', color:'#94a3b8', marginBottom:4, letterSpacing:1 }}>
            TRADE LOG — {closedPositions.length} CLOSED
          </div>
          <div style={{ fontSize:10, color:'#2a4a5a', marginBottom:12, fontFamily:'sans-serif' }}>Click any row to expand full details</div>
          <div style={{ overflowX:'auto' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11, fontFamily:'monospace' }}>
              <thead>
                <tr style={{ borderBottom:'1px solid #1a2535' }}>
                  {['Ticker','Date','Entry','Exit','P&L $','P&L %','Duration','Result'].map(h => (
                    <th key={h} style={{ padding:'6px 6px', textAlign: h==='Result' ? 'left' : 'right', color:'#8899aa', fontSize:9, fontWeight:'normal', letterSpacing:1 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {closedPositions.map(pos => <ClosedRow key={pos.id} pos={pos} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
