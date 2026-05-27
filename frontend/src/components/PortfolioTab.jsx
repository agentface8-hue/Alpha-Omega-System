import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Zap, RotateCcw, Target, BarChart2, Clock, ChevronDown, ChevronRight, TrendingUp, TrendingDown, AlertTriangle, Shield } from 'lucide-react';
import { C as KC, StatCard as KStatCard } from './UIKit';
import ChartPanel from './ChartPanel';

import { fetchJson, API_BASE } from '../utils/api';
const API = () => API_BASE;
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

// ── Sector map (mirrors backend SECTOR_MAP) ─────────────────────────────────────────────
const SECTOR_MAP_P = {
  AAPL:'Tech', MSFT:'Tech', NVDA:'Tech', AMD:'Tech', GOOGL:'Tech', META:'Tech', AMZN:'Tech',
  TSLA:'Consumer', NFLX:'Consumer', DIS:'Consumer', NKE:'Consumer', SBUX:'Consumer',
  JPM:'Finance', GS:'Finance', BAC:'Finance', V:'Finance', MA:'Finance',
  JNJ:'Health', PFE:'Health', UNH:'Health', ABBV:'Health', LLY:'Health', MRK:'Health',
  XOM:'Energy', CVX:'Energy', COP:'Energy', SLB:'Energy',
  BA:'Industrials', CAT:'Industrials', HON:'Industrials', GE:'Industrials',
  CRWD:'Tech', NET:'Tech', MRVL:'Tech', PANW:'Tech', ZS:'Tech', OKTA:'Tech',
  SHOP:'Tech', SNOW:'Tech', PLTR:'Tech', DDOG:'Tech', GTLB:'Tech',
  COIN:'Finance', SQ:'Finance', PYPL:'Finance',
  BTC:'Crypto', ETH:'Crypto', SOL:'Crypto', XRP:'Crypto', ADA:'Crypto',
};
const getSectorP = ticker => SECTOR_MAP_P[(ticker || '').toUpperCase()] || 'Other';

// ── Extract SL history from portfolio position's trades array ─────────────────
const extractPortfolioSLHistory = pos => {
  const trades  = pos.trades || [];
  const entries = [];
  const origSL  = pos.sl_original || pos.sl;
  const entryTrade = trades.find(t => t.type === 'entry');
  entries.push({ sl: origSL, note: 'Entry SL', ts: entryTrade?.executed_at || pos.entry_date, label: 'Original' });
  if (pos.tp1_hit) {
    const t = trades.find(t => t.type === 'partial_tp1');
    if (t) entries.push({ sl: pos.entry_price, note: 'TP1 hit → SL to breakeven', ts: t.executed_at, label: null });
  }
  if (pos.tp2_hit) {
    const t = trades.find(t => t.type === 'partial_tp2');
    if (t) entries.push({ sl: pos.tp1, note: 'TP2 hit → SL to TP1', ts: t.executed_at, label: null });
  }
  entries.sort((a, b) => (a.ts || '').localeCompare(b.ts || ''));
  let maxSL = -Infinity;
  const asc = entries.filter(e => { if (e.sl >= maxSL) { maxSL = e.sl; return true; } return false; });
  if (asc.length > 1) asc[asc.length - 1].label = 'Current';
  return asc;
};

// ── SL History panel ──────────────────────────────────────────────────────────────
const PortfolioSLHistoryPanel = ({ pos, onClose }) => {
  const history = extractPortfolioSLHistory(pos);
  if (history.length === 0) return null;
  const fmtT = ts => {
    if (!ts) return '';
    try { return new Date(ts).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' }); }
    catch { return ts.slice(11,16) || ''; }
  };
  return (
    <div style={{ background:'#07101d', borderTop:'1px solid #1a2535', padding:'10px 14px' }}
      onClick={e => e.stopPropagation()}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
        <span style={{ fontSize:9, fontWeight:'bold', color:'#c084fc', letterSpacing:1, fontFamily:'monospace' }}>SL HISTORY</span>
        <button onClick={onClose} style={{ background:'transparent', border:'none', color:'#8899aa', cursor:'pointer', fontSize:14, lineHeight:1 }}>×</button>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
        {history.map((h, i) => {
          const isLast   = i === history.length - 1;
          const rowLabel = h.label || `+${formatDuration(pos.entry_date, h.ts)}`;
          return (
            <div key={i} style={{ display:'grid', gridTemplateColumns:'70px 80px 1fr 60px', gap:8, alignItems:'center', opacity: isLast ? 1 : 0.65 }}>
              <span style={{ fontSize:9, color: isLast ? '#c084fc' : '#2a4a5a', fontFamily:'monospace', fontWeight: isLast ? 'bold' : 'normal' }}>{rowLabel}</span>
              <span style={{ fontSize:12, fontWeight:'bold', color:'#ff4466', fontFamily:'monospace' }}>${h.sl.toFixed(2)}</span>
              <span style={{ fontSize:9, color:'#8899aa', fontFamily:'sans-serif' }}>{h.note}</span>
              <span style={{ fontSize:8, color:'#2a4a5a', fontFamily:'monospace', textAlign:'right' }}>{fmtT(h.ts)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ── Trade State Badge (Phase 1 — observe only) ───────────────────────────────
const P_STATE_CFG = {
  RUNNING:    { color:'#00ff88', bg:'rgba(0,255,136,0.12)',  label:'RUNNING',  pulse:true  },
  DEVELOPING: { color:'#00d4ff', bg:'rgba(0,212,255,0.12)',  label:'DEVELOP',  pulse:false },
  PROTECTING: { color:'#fbbf24', bg:'rgba(251,191,36,0.12)', label:'PROTECT',  pulse:false },
  EXIT:       { color:'#ff4466', bg:'rgba(255,68,102,0.12)', label:'EXIT',     pulse:true  },
};
const PTradeStateBadge = ({ state }) => {
  if (!state) return null;
  const cfg = P_STATE_CFG[state] || { color:'#8899aa', bg:'rgba(136,153,170,0.1)', label:state, pulse:false };
  return (
    <span style={{
      fontSize:8, fontWeight:'bold', fontFamily:'sans-serif',
      padding:'1px 5px', borderRadius:3,
      background:cfg.bg, color:cfg.color,
      border:`1px solid ${cfg.color}44`,
      animation: cfg.pulse ? 'p-pulse 1.5s ease-in-out infinite' : 'none',
      display:'inline-block', verticalAlign:'middle',
    }}>
      {cfg.label}
    </span>
  );
};
const PScoreTrendArrow = ({ score, prev }) => {
  if (score == null || prev == null) return null;
  const diff = score - prev;
  if (diff > 0.5)  return <span style={{ color:'#00ff88', fontSize:11 }}>&#8593;</span>;
  if (diff < -0.5) return <span style={{ color:'#ff4466', fontSize:11 }}>&#8595;</span>;
  return <span style={{ color:'#8899aa', fontSize:11 }}>&#8594;</span>;
};

const StatCard = ({ label, value, sub, color, small }) => (
  <div style={{ background:'#0d1a2a', border:'1px solid #1a2535', borderRadius:8, padding:'12px 16px', minWidth:100, textAlign:'center' }}>
    <div style={{ fontSize:9, color:'#8899aa', letterSpacing:1, marginBottom:5, fontFamily:'monospace' }}>{label}</div>
    <div style={{ fontSize: small ? 16 : 20, fontWeight:'bold', color: color || '#00d4ff', fontFamily:'monospace' }}>{value}</div>
    {sub && <div style={{ fontSize:9, color:'#8899aa', marginTop:3 }}>{sub}</div>}
  </div>
);

// ── Price level graph (SVG ruler: SL → Entry → curr → TP1 → TP2 → TP3) ─────
const PriceLevelGraph = ({ entry, sl, curr, tp1, tp2, tp3, pnl }) => {
  const W = 560, H = 88, PAD = 32;
  const allP = [sl, entry, curr, tp1, tp2, tp3].filter(v => v > 0 && isFinite(v));
  if (allP.length < 3) return null;
  const minP = Math.min(...allP) * 0.997;
  const maxP = Math.max(...allP) * 1.003;
  const span = maxP - minP || 1;
  const toX  = p => PAD + ((p - minP) / span) * (W - 2 * PAD);

  const MID = 44;
  const G = '#00ff88', R = '#ff4466', GRAY = '#94a3b8';
  const pColor = pnl >= 0 ? G : R;

  // Sort levels by price so alternating above/below avoids label collision
  const rawLevels = [
    { price: sl,    label: 'SL',    color: R,        priceStr: `$${sl.toFixed(2)}` },
    { price: entry, label: 'Entry', color: GRAY,     priceStr: `$${entry.toFixed(2)}` },
    { price: tp1,   label: 'TP1',   color: '#7cb8ff', priceStr: `$${tp1.toFixed(2)}` },
    { price: tp2,   label: 'TP2',   color: '#4aef9f', priceStr: `$${tp2.toFixed(2)}` },
    { price: tp3,   label: 'TP3',   color: G,        priceStr: `$${tp3.toFixed(2)}` },
  ].filter(l => l.price > 0).sort((a, b) => a.price - b.price);

  // Alternate above/below by sorted index so close labels don't clash
  const levels = rawLevels.map((l, i) => ({ ...l, side: i % 2 === 0 ? 'above' : 'below' }));

  const sx = toX(sl), ex = toX(entry), mx = toX(Math.max(tp1, tp2, tp3));
  const cx = toX(curr);

  return (
    <div style={{ width:'100%', background:'#060c16', borderRadius:7, padding:'8px 6px 4px', marginBottom:12, border:'1px solid #1a2535' }}>
      <div style={{ fontSize:8, color:'#8899aa', letterSpacing:1, fontFamily:'monospace', marginBottom:2, marginLeft:6 }}>PRICE LEVELS</div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width:'100%', height:H, display:'block', overflow:'visible' }} preserveAspectRatio="xMidYMid meet">
        {/* Zone fills */}
        <rect x={sx} y={MID-2} width={Math.max(0, ex - sx)} height={4} fill={R} opacity={0.25} rx={2}/>
        <rect x={ex} y={MID-2} width={Math.max(0, mx - ex)} height={4} fill={G} opacity={0.18} rx={2}/>
        {/* Baseline */}
        <line x1={PAD - 6} y1={MID} x2={W - PAD + 6} y2={MID} stroke="#1a2535" strokeWidth={1.5}/>

        {/* Level ticks + labels */}
        {levels.map(({ price, label, color, priceStr, side }) => {
          const lx = toX(price);
          const above = side === 'above';
          return (
            <g key={label}>
              <line x1={lx} y1={MID - 9} x2={lx} y2={MID + 9} stroke={color} strokeWidth={1.5}/>
              <text x={lx} y={above ? MID - 13 : MID + 20} textAnchor="middle" fill={color} fontSize={8} fontFamily="monospace" fontWeight="bold">{label}</text>
              <text x={lx} y={above ? MID - 22 : MID + 30} textAnchor="middle" fill={color} fontSize={7} fontFamily="monospace">{priceStr}</text>
            </g>
          );
        })}

        {/* Current price — downward triangle pointer */}
        <polygon points={`${cx-6},${MID-14} ${cx+6},${MID-14} ${cx},${MID-4}`} fill={pColor} opacity={0.95}/>
        <line x1={cx} y1={MID-4} x2={cx} y2={MID+4} stroke={pColor} strokeWidth={2}/>
        <text x={cx} y={MID-18} textAnchor="middle" fill={pColor} fontSize={8.5} fontFamily="monospace" fontWeight="bold">${curr.toFixed(2)}</text>
      </svg>
    </div>
  );
};

// ── Open position card ───────────────────────────────────────────────────────
const PositionCard = ({ pos, onClose, onRefresh, bench = [], onOpenBench }) => {
  const [expanded, setExpanded] = useState(false);
  const [slHistoryOpen, setSlHistoryOpen] = useState(false);
  const [slOverrideOpen, setSlOverrideOpen]     = useState(false);
  const [slOverrideVal,  setSlOverrideVal]       = useState('');
  const [slOverrideErr,  setSlOverrideErr]       = useState(null);
  const [slOverrideBusy, setSlOverrideBusy]      = useState(false);
  const submitOverrideSL = async () => {
    const val = parseFloat(slOverrideVal);
    if (!val || val <= 0 || val >= (pos.entry_price || 9999)) { setSlOverrideErr('Enter a valid SL below entry price'); return; }
    setSlOverrideBusy(true); setSlOverrideErr(null);
    try {
      const r = await fetch(`${API()}/api/signals/override-sl/${pos.id}?new_sl=${val}`, { method:'POST' });
      const d = await r.json();
      if (d.error) { setSlOverrideErr(d.error); }
      else { setSlOverrideOpen(false); setSlOverrideVal(''); if (onRefresh) onRefresh(); }
    } catch (e) { setSlOverrideErr(e.message); }
    setSlOverrideBusy(false);
  };
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
  const distToSL  = ((curr - sl) / curr * 100).toFixed(2);
  const distToTP1 = ((tp1 - curr) / curr * 100).toFixed(2);
  const distToTP2 = ((tp2 - curr) / curr * 100).toFixed(2);
  const distToTP3 = ((tp3 - curr) / curr * 100).toFixed(2);
  const rr        = range > 0 ? ((tp1 - entry) / (entry - sl)).toFixed(2) : '—';
  const maePct = entry > 0 ? (pos.mae / entry * 100).toFixed(2) : 0;
  const mfePct = entry > 0 ? (pos.mfe / entry * 100).toFixed(2) : 0;
  const atRisk  = curr <= sl * 1.02;
  const nearTP1 = curr >= tp1 * 0.98;

  return (
    <div style={{
      background: expanded ? '#0c1420' : '#0a1018',
      border: `1px solid ${expanded ? '#c084fc44' : pnl >= 0 ? '#1a3525' : '#351a1a'}`,
      borderRadius: 10, marginBottom: 10, overflow: 'hidden', transition: 'border-color 0.2s',
    }}>
      <div onClick={() => setExpanded(e => !e)} style={{ padding: 14, cursor: 'pointer' }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            {expanded ? <ChevronDown size={13} color='#c084fc' /> : <ChevronRight size={13} color='#8899aa' />}
            <span style={{ fontSize:16, fontWeight:'bold', color:'#e0e0e0', fontFamily:'monospace' }}>{pos.ticker}</span>
            {/* Current price + delay indicator */}
            <span style={{ fontSize:13, fontWeight:'bold', color:clr(pnl), fontFamily:'monospace' }}>${fmt(curr, 2)}</span>
            <span title="~15min delayed (yfinance — no Alpaca key)" style={{ fontSize:8, fontWeight:'bold', color:'#fbbf24', background:'rgba(251,191,36,0.12)', border:'1px solid rgba(251,191,36,0.3)', borderRadius:3, padding:'1px 5px', fontFamily:'sans-serif', cursor:'default', letterSpacing:0.5 }}>D</span>
            {pos.atr_at_entry > 0 && <span title="14-day Average True Range at position entry" style={{ fontSize:9, color:'#00d4ff', fontFamily:'monospace', background:'rgba(0,212,255,0.08)', borderRadius:3, padding:'1px 6px', border:'1px solid rgba(0,212,255,0.2)' }}>ATR ${fmt(pos.atr_at_entry, 2)}</span>}
            {isPartial && <span style={{ fontSize:9, background:'rgba(251,191,36,0.15)', color:'#fbbf24', borderRadius:4, padding:'2px 6px', border:'1px solid #fbbf24' }}>PARTIAL</span>}
            {pos.tp1_hit && <span style={{ fontSize:9, background:'rgba(0,255,136,0.1)', color:'#00ff88', borderRadius:4, padding:'2px 6px' }}>TP1✓</span>}
            {pos.tp2_hit && <span style={{ fontSize:9, background:'rgba(0,255,136,0.15)', color:'#00ff88', borderRadius:4, padding:'2px 6px' }}>TP2✓</span>}
            {pos.conviction > 0 && <span style={{ fontSize:9, color:heatClr(pos.conviction), fontFamily:'monospace' }}>{pos.conviction}%</span>}
            {pos.live_score != null && (
              <>
                <span style={{ fontSize:9, color:'#8899aa', fontFamily:'monospace' }}>&#8635;{pos.live_score}%</span>
                <PScoreTrendArrow score={pos.live_score} prev={pos.live_score_prev} />
                <PTradeStateBadge state={pos.trade_state} />
              </>
            )}
            {pos.dynamic_tp_active && pos.trade_state === 'RUNNING' && (
              <span style={{ fontSize:8, fontWeight:'bold', color:'#00ff88', background:'rgba(0,255,136,0.1)', border:'1px solid #00ff8833', borderRadius:3, padding:'1px 5px', fontFamily:'sans-serif' }}>Dynamic TP</span>
            )}
            {pos.partial_exit_suggested && (
              <span style={{ fontSize:8, fontWeight:'bold', color:'#f97316', background:'rgba(249,115,22,0.1)', border:'1px solid #f9731633', borderRadius:3, padding:'1px 5px', fontFamily:'sans-serif' }}>&#9888; Partial exit</span>
            )}
            {pos.dynamic_tp_active && pos.trade_state === 'RUNNING' && (
              <span style={{ fontSize:8, fontWeight:'bold', color:'#00ff88', background:'rgba(0,255,136,0.1)', border:'1px solid #00ff8833', borderRadius:3, padding:'1px 5px', fontFamily:'sans-serif' }}>Dynamic TP</span>
            )}
            {pos.partial_exit_suggested && (
              <span style={{ fontSize:8, fontWeight:'bold', color:'#f97316', background:'rgba(249,115,22,0.1)', border:'1px solid #f9731633', borderRadius:3, padding:'1px 5px', fontFamily:'sans-serif' }}>&#9888; Partial exit</span>
            )}
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
            <button onClick={e => { e.stopPropagation(); setSlOverrideOpen(o => !o); setSlOverrideErr(null); }}
              title='Override stop-loss'
              style={{ background:'transparent', border:`1px solid ${slOverrideOpen ? '#c084fc' : '#2a4a5a'}`, borderRadius:4, padding:'3px 7px', color: slOverrideOpen ? '#c084fc' : '#2a4a5a', fontSize:10, cursor:'pointer', display:'flex', alignItems:'center', gap:3 }}>
              <Shield size={10} /> SL
            </button>
            <button onClick={e => { e.stopPropagation(); onClose(pos.id); }}
              style={{ background:'transparent', border:'1px solid #ff4466', borderRadius:4, padding:'3px 8px', color:'#ff4466', fontSize:10, cursor:'pointer' }}
            >✕ Close</button>
          </div>
        </div>
        <div style={{ position:'relative', height:6, background:'#1a2535', borderRadius:3, marginBottom:10, overflow:'hidden' }}>
          <div style={{ position:'absolute', left:0, top:0, height:'100%', width:`${progress}%`, background:barColor, borderRadius:3, transition:'width 0.5s' }} />
        </div>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:6, fontSize:10, fontFamily:'monospace' }}>
          {[
            { label:'ENTRY', val:`$${fmt(entry,2)}`, color:'#94a3b8' },
            { label:'PRICE', val:`$${fmt(curr,2)}`, color:clr(pnl) },
            { label:'SL', val:`$${fmt(sl,2)}`, color:'#ff4466', clickable:true },
            { label:'TP1', val:`$${fmt(tp1,2)}`, color: pos.tp1_hit ? '#00ff88' : '#8899aa' },
            { label:'TP2', val:`$${fmt(tp2,2)}`, color: pos.tp2_hit ? '#00ff88' : '#8899aa' },
            { label:'TP3', val:`$${fmt(tp3,2)}`, color:'#8899aa' },
          ].map(l => (
            <div key={l.label} style={{ textAlign:'center' }}
              onClick={l.clickable ? e => { e.stopPropagation(); setSlHistoryOpen(o => !o); } : undefined}
            >
              <div style={{ color:'#8899aa', fontSize:8, marginBottom:2 }}>{l.label}</div>
              <div style={{ color:l.color, fontWeight:'bold',
                textDecoration: l.clickable ? 'underline dotted' : 'none',
                cursor: l.clickable ? 'pointer' : 'default',
              }}>{l.val}</div>
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

      {slHistoryOpen && <PortfolioSLHistoryPanel pos={pos} onClose={() => setSlHistoryOpen(false)} />}

      {slOverrideOpen && (
        <div style={{ background:'#07101d', borderTop:'1px solid #c084fc44', padding:'10px 14px' }}
          onClick={e => e.stopPropagation()}>
          <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap' }}>
            <Shield size={12} color='#c084fc' />
            <span style={{ fontSize:9, fontWeight:'bold', color:'#c084fc', fontFamily:'monospace', letterSpacing:1 }}>OVERRIDE STOP-LOSS</span>
            <span style={{ fontSize:9, color:'#8899aa', fontFamily:'monospace' }}>current: ${fmt(sl,2)}</span>
            <input type='number' step='0.01' value={slOverrideVal}
              onChange={e => setSlOverrideVal(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submitOverrideSL()}
              placeholder={fmt(sl,2)}
              style={{ width:90, background:'#0d1a2a', border:'1px solid #c084fc', borderRadius:4, padding:'4px 8px', color:'#e0e0e0', fontSize:12, fontFamily:'monospace', textAlign:'center' }}
              autoFocus />
            <button onClick={submitOverrideSL} disabled={slOverrideBusy}
              style={{ background:'linear-gradient(135deg,#c084fc,#7c3aed)', border:'none', borderRadius:4, padding:'4px 12px', color:'#fff', fontSize:10, fontWeight:'bold', cursor:'pointer' }}>
              {slOverrideBusy ? '…' : 'SET'}
            </button>
            <button onClick={() => { setSlOverrideOpen(false); setSlOverrideErr(null); }}
              style={{ background:'transparent', border:'none', color:'#8899aa', cursor:'pointer', fontSize:14, lineHeight:1 }}>×</button>
          </div>
          {slOverrideErr && <div style={{ fontSize:10, color:'#ff4466', marginTop:6, fontFamily:'sans-serif' }}>{slOverrideErr}</div>}
        </div>
      )}

      {pos.trade_state === 'EXIT' && pos.live_score != null && (
        <div style={{ borderTop:'1px solid #ff446633', padding:'7px 14px', background:'rgba(255,68,102,0.07)', display:'flex', alignItems:'center', gap:8 }}>
          <AlertTriangle size={13} color='#ff4466' style={{ flexShrink:0, animation:'p-pulse 1.5s ease-in-out infinite' }} />
          <span style={{ fontSize:10, color:'#ff4466', fontFamily:'sans-serif', fontWeight:'bold' }}>
            &#9888; Score below threshold — consider closing this position
          </span>
          <span style={{ fontSize:9, color:'#8899aa', fontFamily:'sans-serif', marginLeft:'auto' }}>
            Live score: {pos.live_score}%
          </span>
        </div>
      )}

      {bench.length > 0 && (
        <React.Fragment>
          <div style={{ borderTop:'1px solid #0d1a2a', background:'#070c14', padding:'8px 14px', display:'flex', alignItems:'center', gap:8, flexWrap:'wrap' }}>
            <span style={{ fontSize:8, color:'#2a4a5a', letterSpacing:1, fontFamily:'monospace', fontWeight:'bold', whiteSpace:'nowrap' }}>BENCH</span>
            {bench.map(c => (
              <div key={c.ticker} style={{ display:'flex', alignItems:'center', gap:6, background:'#0d1a2a', border:'1px solid #1a2535', borderRadius:6, padding:'4px 10px' }}>
                <span style={{ fontSize:11, fontWeight:'bold', color:'#e0e0e0', fontFamily:'monospace' }}>{c.ticker}</span>
                <span style={{ fontSize:9, color: c.conviction_pct >= 75 ? '#00ff88' : '#fbbf24', fontFamily:'monospace' }}>{c.conviction_pct}%</span>
                {c.sector && <span style={{ fontSize:8, color:'#2a4a5a', fontFamily:'sans-serif' }}>{c.sector}</span>}
                <button onClick={e => { e.stopPropagation(); onOpenBench && onOpenBench(c); }}
                  style={{ background:'linear-gradient(135deg,#00ff88,#00bb66)', border:'none', borderRadius:4, padding:'2px 8px', color:'#000', fontSize:9, fontWeight:'bold', cursor:'pointer' }}>
                  OPEN
                </button>
              </div>
            ))}
          </div>
        </React.Fragment>
      )}

      {expanded && (
        <div style={{ borderTop:'1px solid #1a2535', padding:'14px', background:'#080c14' }}>
          <PriceLevelGraph entry={entry} sl={sl} curr={curr} tp1={tp1} tp2={tp2} tp3={tp3} pnl={pnl} />

          {/* ── Stock Chart with Entry/SL/TP markers ── */}
          <ChartPanel
            symbol={pos.ticker}
            tradeParams={{
              entry:      entry,
              entry_low:  entry * 0.999,
              entry_high: entry * 1.001,
              sl:         sl,
              tp1:        tp1,
              tp2:        tp2,
              tp3:        tp3,
            }}
          />

          <div style={{ background:'#0d1520', border:'1px solid #1a2535', borderRadius:8, padding:'12px 14px', marginBottom:14 }}>
            <div style={{ fontSize:8, color:'#c084fc', letterSpacing:1, marginBottom:10, fontFamily:'monospace', fontWeight:'bold' }}>ENTRY REASON</div>
            {pos.pillar_scores && Object.keys(pos.pillar_scores).length > 0 && (
              <div style={{ marginBottom:12 }}>
                <div style={{ fontSize:8, color:'#8899aa', marginBottom:6, fontFamily:'monospace', letterSpacing:1 }}>CONVICTION PILLARS</div>
                <div style={{ display:'flex', gap:12, flexWrap:'wrap' }}>
                  {[
                    { key:'p1', label:'P1 Trend' },
                    { key:'p2', label:'P2 Volume' },
                    { key:'p3', label:'P3 S/R' },
                    { key:'p4', label:'P4 Multi-TF' },
                    { key:'p5', label:'P5 R/R' },
                  ].map(({ key, label }) => {
                    const score = pos.pillar_scores[key];
                    const pColor = score == null ? '#2a4a5a' : score >= 70 ? '#00ff88' : score >= 50 ? '#fbbf24' : '#ff4466';
                    return (
                      <div key={key} style={{ textAlign:'center', minWidth:62 }}>
                        <div style={{ fontSize:8, color:'#8899aa', marginBottom:4, fontFamily:'monospace' }}>{label}</div>
                        <div style={{ background:'#0a1018', borderRadius:3, height:5, width:62, overflow:'hidden', marginBottom:3 }}>
                          <div style={{ height:'100%', width:`${score || 0}%`, background:pColor, borderRadius:3, transition:'width 0.4s' }} />
                        </div>
                        <div style={{ fontSize:9, color:pColor, fontFamily:'monospace', fontWeight:'bold' }}>{score != null ? `${score}%` : '—'}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            <div style={{ display:'flex', gap:14, flexWrap:'wrap', fontSize:11, fontFamily:'monospace', color:'#94a3b8' }}>
              {pos.conviction > 0 && <span>Conviction: <b style={{color:heatClr(pos.conviction)}}>{pos.conviction}%</b></span>}
              {pos.tas && pos.tas !== '—' && pos.tas !== '' && <span>TAS: <b style={{color:'#00d4ff'}}>{pos.tas}</b></span>}
              {pos.entry_market_context?.vix > 0 && (
                <span>VIX: <b style={{color: pos.entry_market_context.vix > 25 ? '#ff4466' : pos.entry_market_context.vix > 20 ? '#fbbf24' : '#00ff88'}}>{pos.entry_market_context.vix}</b></span>
              )}
              {pos.entry_market_context?.spy_change_pct != null && (
                <span>SPY: <b style={{color: pos.entry_market_context.spy_change_pct >= 0 ? '#00ff88' : '#ff4466'}}>{pos.entry_market_context.spy_change_pct >= 0 ? '+' : ''}{pos.entry_market_context.spy_change_pct}%</b></span>
              )}
              {pos.atr_at_entry > 0 && <span>ATR: <b style={{color:'#e0e0e0'}}>${fmt(pos.atr_at_entry, 2)}</b></span>}
              {pos.regime && <span>Regime: <b style={{color:'#00d4ff'}}>{pos.regime}</b></span>}
              {pos.sector && <span>Sector: <b style={{color:'#8899aa'}}>{pos.sector}</b></span>}
              {pos.signal_id && <span style={{color:'#2a4a5a'}}>ID: {pos.signal_id.slice(0,8)}</span>}
              {(!pos.pillar_scores || Object.keys(pos.pillar_scores).length === 0) && !pos.tas && (!pos.entry_market_context || !pos.entry_market_context.vix) && (
                <span style={{color:'#2a4a5a', fontStyle:'italic'}}>Legacy position — detailed entry context not stored. Conviction: {pos.conviction}%</span>
              )}
            </div>
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:14 }}>
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
            <div style={{ background:'#0d1520', border:'1px solid #1a2535', borderRadius:8, padding:'12px 14px' }}>
              <div style={{ fontSize:8, color:'#c084fc', letterSpacing:1, marginBottom:10, fontFamily:'monospace', fontWeight:'bold' }}>TRADE LOG</div>
              {(pos.trades || []).length === 0 && <div style={{ fontSize:10, color:'#2a4a5a' }}>No trades recorded</div>}
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

// ── Closed trade row ───────────────────────────────────────────────────────────────
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
      <tr onClick={() => setExpanded(e => !e)}
        style={{ borderBottom: expanded ? 'none' : '1px solid #0d1a2a', cursor:'pointer', background: expanded ? '#0d1520' : 'transparent' }}
      >
        <td style={{ padding:'8px 6px', color:'#e0e0e0', fontWeight:'bold', fontFamily:'monospace' }}>
          <span style={{ display:'inline-flex', alignItems:'center', gap:4 }}>
            {expanded ? <ChevronDown size={10} color='#8899aa' /> : <ChevronRight size={10} color='#8899aa' />}
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
            <Clock size={9} color='#2a4a5a' /> {duration}
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
            {/* Price chart thumbnail — only shown if chart_url exists */}
            {pos.chart_url && (
              <div style={{ marginTop:12 }}>
                <div style={{ fontSize:8, color:'#00d4ff', letterSpacing:1, marginBottom:6, fontFamily:'monospace' }}>📈 TRADE CHART</div>
                <img
                  src={pos.chart_url}
                  alt={`${pos.ticker} trade chart`}
                  onClick={() => window.open(pos.chart_url, '_blank')}
                  style={{ width:'100%', maxWidth:640, borderRadius:4, cursor:'pointer', border:'1px solid #1a2535', display:'block' }}
                  title="Click to open full size"
                />
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
};

// ── Period P&L Bar ────────────────────────────────────────────────────────────
const PeriodPnLBar = ({ closedPositions, startingCash }) => {
  const periods = [
    { label: '1D',  days: 1 },
    { label: '1W',  days: 7 },
    { label: '1M',  days: 30 },
    { label: '3M',  days: 90 },
    { label: '6M',  days: 180 },
    { label: '1Y',  days: 365 },
  ];

  const getPeriod = (days) => {
    const cutoff = new Date(Date.now() - days * 86400000).toISOString();
    const trades = (closedPositions || []).filter(p => (p.closed_at || '') >= cutoff);
    const pnl    = trades.reduce((sum, p) => sum + (p.realized_pnl || 0), 0);
    const wins   = trades.filter(p => (p.realized_pnl || 0) > 0).length;
    return { pnl, count: trades.length, wins };
  };

  return (
    <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10,
      padding:'12px 16px', marginBottom:20, display:'flex', gap:0, flexWrap:'wrap' }}>
      <div style={{ fontSize:8, color:'#8899aa', letterSpacing:1.5, fontFamily:'monospace',
        fontWeight:'bold', width:'100%', marginBottom:10 }}>PROFIT BY PERIOD</div>
      {periods.map(({ label, days }) => {
        const { pnl, count, wins } = getPeriod(days);
        const pct = startingCash > 0 ? (pnl / startingCash * 100) : 0;
        const wr  = count > 0 ? Math.round(wins / count * 100) : null;
        const c   = pnl > 0 ? '#00ff88' : pnl < 0 ? '#ff4466' : '#8899aa';
        return (
          <div key={label} style={{ flex:1, minWidth:80, textAlign:'center',
            borderRight:'1px solid #1a2535', padding:'4px 8px', lastChild:{ borderRight:'none' } }}>
            <div style={{ fontSize:9, color:'#8899aa', fontFamily:'monospace', marginBottom:4 }}>{label}</div>
            <div style={{ fontSize:14, fontWeight:'bold', color:c, fontFamily:'monospace' }}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(0)}
            </div>
            <div style={{ fontSize:9, color:c, fontFamily:'monospace' }}>
              {pct >= 0 ? '+' : ''}{pct.toFixed(1)}%
            </div>
            <div style={{ fontSize:8, color:'#2a4a5a', marginTop:3, fontFamily:'sans-serif' }}>
              {count} trade{count !== 1 ? 's' : ''}{wr !== null ? ` · ${wr}% WR` : ''}
            </div>
          </div>
        );
      })}
    </div>
  );
};


export default function PortfolioTab({ compact = false, isOwner = false, backendReady = true }) {
  const [data, setData]             = useState(null);
  const [loading, setLoading]       = useState(false);
  const [checking, setChecking]     = useState(false);
  const [openTicker, setOpenTicker] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [countdown, setCountdown]   = useState(30);
  const [error, setError]           = useState(null);
  const [sessionWarn, setSessionWarn] = useState(null);
  const [scanCandidates, setScanCandidates] = useState([]);
  const [allActions,     setAllActions]     = useState([]);
  const [tradeHistory,   setTradeHistory]   = useState(null);   // { trades, stats }
  const [historyTab,     setHistoryTab]     = useState('log');  // 'log' | 'history'

  const load = useCallback(async (silent = false) => {
    if (!backendReady) return;
    if (!silent) setLoading(true);
    try {
      const json = await fetchJson('/api/portfolio', {}, { timeoutMs: 50000, retries: 3 });
      setData(json);
      setError(null);
    } catch (e) { setError(e.message || 'Failed to load portfolio'); }
    setLoading(false);
  }, [backendReady]);

  const fetchActionLog = useCallback(async () => {
    try {
      const r = await fetch(`${API()}/api/signals`);
      if (!r.ok) return;
      const d = await r.json();
      const sigs = [...(d.active || []), ...(d.closed || [])];
      const actions = sigs.flatMap(s =>
        (s.action_log || []).map(a => ({ ...a, ticker: s.ticker || a.ticker || '?' }))
      );
      actions.sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));
      setAllActions(actions.slice(0, 50));
    } catch { /* silent */ }
  }, []);

  const fetchTradeHistory = useCallback(async () => {
    try {
      const r = await fetch(`${API()}/api/trade-history`);
      if (!r.ok) return;
      setTradeHistory(await r.json());
    } catch { /* silent */ }
  }, []);

  const fetchCandidates = useCallback(async (excludeTickers = []) => {
    try {
      const exc = excludeTickers.filter(Boolean).join(',');
      const url = exc
        ? `${API()}/api/scan/candidates?exclude=${encodeURIComponent(exc)}`
        : `${API()}/api/scan/candidates`;
      const r = await fetch(url);
      if (!r.ok) return;
      const d = await r.json();
      setScanCandidates(d.candidates || []);
    } catch (e) { /* silent — bench is non-critical */ }
  }, []);

  const getBenchForPos = (pos) => {
    const activeTickers = (data?.open_positions || []).map(p => p.ticker.toUpperCase());
    const pool = scanCandidates.filter(c => !activeTickers.includes(c.ticker.toUpperCase()));
    const sector = getSectorP(pos.ticker);
    const sameS  = pool.filter(c => getSectorP(c.ticker) === sector);
    const others = pool.filter(c => getSectorP(c.ticker) !== sector);
    return [...sameS, ...others].slice(0, 2);
  };

  const openBenchAsPosition = async (candidate) => {
    setLoading(true);
    try {
      const r = await fetch(`${API()}/api/portfolio/open`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: candidate.ticker, entry_price: candidate.entry_price,
          sl: candidate.sl, tp1: candidate.tp1, tp2: candidate.tp2, tp3: candidate.tp3,
          conviction: candidate.conviction_pct, asset_type: 'stock',
          pillar_scores: candidate.pillar_scores || {},
          tas: candidate.tas || '',
          entry_market_context: candidate.entry_market_context || {},
        }),
      });
      const result = await r.json();
      if (result.error) setError(result.error);
      else { await load(); }
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  const checkPrices = async () => {
    setChecking(true);
    try {
      const r = await fetch(`${API()}/api/portfolio/check`, { method:'POST' });
      if (!r.ok) throw new Error(await r.text());
      const result = await r.json();
      setData(result.portfolio);
      setCountdown(30);
      const tickers = (result.portfolio?.open_positions || []).map(p => p.ticker.toUpperCase());
      fetchCandidates(tickers);
      fetchActionLog();
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
          conviction: best.conviction_pct, asset_type: 'stock',
          pillar_scores: best.pillar_scores || {},
          tas: best.tas || '',
          entry_market_context: best.entry_market_context || {},
        }),
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
      // session_note = soft warning (premarket/afterhours), not an error
      if (result.session_note) setSessionWarn(result.session_note);
      if (result.opened?.length > 0) setError(null);
      else if (!result.session_note) setError(result.message || 'No qualifying signals found (need conviction >= 72%)');
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
    try {
      const r = await fetch(`${API()}/api/portfolio/reset`, { method:'POST' });
      const result = await r.json();
      // Reset endpoint now returns fresh portfolio — use it directly, no second roundtrip
      if (result.state) setData(result);
      else await load();
      setError(null); setSessionWarn(null);
    } catch (e) { setError(e.message); }
  };

  useEffect(() => {
    if (!backendReady) return;
    load();
    fetchCandidates([]);
    fetchActionLog();
  }, [load, fetchCandidates, fetchActionLog, backendReady]);
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
    <div style={{ padding: compact ? '10px 12px' : '28px 24px', fontFamily:"'Inter',sans-serif", color:'#e0e0e0', maxWidth:1200, margin:'0 auto' }}>
      <style>{`@keyframes p-pulse { 0%,100%{opacity:1} 50%{opacity:0.45} }`}</style>

      {/* ── Header — hidden in compact/grid mode ── */}
      {!compact && (
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:24 }}>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ background:'linear-gradient(135deg,#00d4ff22,#0088cc22)', border:'1px solid #00d4ff33', borderRadius:10, padding:10, display:'flex' }}>
            <BarChart2 size={20} color='#00d4ff' />
          </div>
          <div>
            <div style={{ fontSize:16, fontWeight:'bold', color:'#e0e0e0', letterSpacing:1.5, fontFamily:'monospace' }}>ACTIVE PORTFOLIO</div>
            <div style={{ fontSize:10, color:KC.textFaint, fontFamily:'sans-serif', marginTop:3 }}>
              Paper trading · $25K · Max {maxPositions} positions · ${Math.round(data?.state?.max_position_size ?? 3340).toLocaleString()}/trade · $500 risk
            </div>
          </div>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <button onClick={() => { setAutoRefresh(a => !a); setCountdown(30); }}
            style={{ background: autoRefresh ? 'rgba(0,212,255,0.12)' : 'transparent', border:`1px solid ${autoRefresh?'#00d4ff':'#1a2535'}`, borderRadius:6, padding:'7px 14px', color: autoRefresh?'#00d4ff':'#8899aa', fontSize:11, cursor:'pointer', fontFamily:'monospace' }}>
            {autoRefresh ? `AUTO ${countdown}s` : 'AUTO OFF'}
          </button>
          <button onClick={checkPrices} disabled={checking}
            style={{ background:'linear-gradient(135deg,#00d4ff,#0066aa)', border:'none', borderRadius:6, padding:'7px 16px', color:'#fff', fontSize:12, fontWeight:'bold', cursor:'pointer', display:'flex', alignItems:'center', gap:6 }}>
            <RefreshCw size={13} /> {checking?'CHECKING...':'CHECK PRICES'}
          </button>
          <button onClick={reset} title="Reset portfolio" style={{ background:'transparent', border:'1px solid #ff446633', borderRadius:6, padding:'7px 10px', color:'#ff4466', fontSize:11, cursor:'pointer' }}>
            <RotateCcw size={12} />
          </button>
        </div>
      </div>
      )} {/* end !compact header */}

      {error && (
        <div style={{ background:'rgba(255,68,102,0.08)', border:'1px solid #ff446633', borderRadius:8, padding:'10px 16px', marginBottom:16, color:'#ff8899', fontSize:12, display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          {error} <span style={{ cursor:'pointer', color:KC.red, fontSize:16 }} onClick={() => setError(null)}>✕</span>
        </div>
      )}

      {sessionWarn && (
        <div style={{ background:'rgba(251,191,36,0.08)', border:'1px solid rgba(251,191,36,0.3)', borderRadius:8, padding:'10px 16px', marginBottom:16, color:'#fbbf24', fontSize:12, display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          ⚠ {sessionWarn} <span style={{ cursor:'pointer', color:'#fbbf24', fontSize:16 }} onClick={() => setSessionWarn(null)}>✕</span>
        </div>
      )}

      {/* ── Stats row ── */}
      <div style={{ display:'flex', gap: compact ? 6 : 10, marginBottom: compact ? 10 : 24, flexWrap:'wrap' }}>
        <KStatCard label='TOTAL VALUE'   value={usd(s.total_value)}  color='#00d4ff' accent='#00d4ff' compact={compact} />
        <KStatCard label='CASH'          value={usd(s.cash)}          color='#7ee8ff' sub={`${slots} slot${slots!==1?'s':''} open`} compact={compact} />
        <KStatCard label='TOTAL P&L'     value={`${totalPnl>=0?'+':''}${fmt(totalPnl,0)}`} color={clr(totalPnl)} sub={pct(s.total_pnl_pct||0)} accent={clr(totalPnl)} compact={compact} />
        <KStatCard label='UNREALIZED'    value={`${(s.total_unrealized_pnl||0)>=0?'+':''}${fmt(s.total_unrealized_pnl||0,0)}`} color={clr(s.total_unrealized_pnl||0)} compact={compact} />
        <KStatCard label='REALIZED'      value={`${(s.total_realized_pnl||0)>=0?'+':''}${fmt(s.total_realized_pnl||0,0)}`} color={clr(s.total_realized_pnl||0)} compact={compact} />
        <KStatCard label='OPEN'          value={s.open_count||0}      sub='positions' color='#fbbf24' compact={compact} />
        <KStatCard label='WIN RATE'      value={(s.total_closed||0)===0?'—':`${s.win_rate||0}%`}  sub={`${s.total_closed||0} closed`} color={(s.total_closed||0)===0?KC.textFaint:(s.win_rate>=60?KC.green:s.win_rate>=40?KC.yellow:KC.red)} compact={compact} />
      </div>

      {/* ── Period P&L breakdown ── */}
      {!compact && <PeriodPnLBar closedPositions={closedPositions} startingCash={data?.state?.starting_capital || 25000} />}

      <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10, padding:16, marginBottom:20 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
          <div>
            <div style={{ fontSize:13, fontWeight:'bold', color:'#00d4ff', letterSpacing:1 }}>POSITIONS — {openPositions.length}/{maxPositions} SLOTS USED</div>
            <div style={{ fontSize:10, color:'#2a4a5a', marginTop:2, fontFamily:'sans-serif' }}>Click any position to expand details</div>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            {isOwner && <>
            <input value={openTicker} onChange={e => setOpenTicker(e.target.value.toUpperCase())}
              onKeyDown={e => e.key==='Enter' && openFromScan()}
              placeholder='TICKER' maxLength={6}
              style={{ width:90, background:'#0d1a2a', border:'1px solid #1a2535', borderRadius:6, padding:'6px 10px', color:'#e0e0e0', fontSize:13, fontFamily:'monospace', letterSpacing:2, textAlign:'center' }} />
            <button onClick={openFromScan} disabled={loading || !openTicker.trim()}
              style={{ background:'linear-gradient(135deg,#00ff88,#00bb66)', border:'none', borderRadius:6, padding:'6px 14px', color:'#000', fontSize:12, fontWeight:'bold', cursor:'pointer', display:'flex', alignItems:'center', gap:5 }}>
              <Target size={13} /> OPEN
            </button>
            <button onClick={autopilot} disabled={loading || slots===0}
              style={{ background: slots===0?'#1a2535':'linear-gradient(135deg,#7c3aed,#a855f7)', border: slots===0?'1px solid #2a3545':'none', borderRadius:6, padding:'6px 14px', color: slots===0?'#4a5568':'#fff', fontSize:12, fontWeight:'bold', cursor: slots===0?'not-allowed':'pointer', display:'flex', alignItems:'center', gap:5 }}>
              <Zap size={13} /> {slots===0 ? 'PORTFOLIO FULL' : `AUTO-FILL ${slots} SLOTS`}
            </button>
            </>}
            {!isOwner && (
              <div style={{ fontSize:10, color:'#4a6a8a', fontFamily:'sans-serif',
                display:'flex', alignItems:'center', gap:4 }}>
                👁 View only
              </div>
            )}
          </div>
        </div>
        {loading && <div style={{ padding:10, color:'#fbbf24', fontSize:11, fontFamily:'monospace' }}>⧑ Processing...</div>}
        {openPositions.length === 0 && !loading && (
          <div style={{ textAlign:'center', padding:'30px 20px', color:'#8899aa', fontSize:12 }}>
            No open positions. Enter a ticker or click AUTO-FILL to start.
          </div>
        )}
        {openPositions.map(pos => (
          <PositionCard key={pos.id} pos={pos} onClose={closePos} onRefresh={() => { load(true); fetchActionLog(); }}
            bench={getBenchForPos(pos)} onOpenBench={openBenchAsPosition} />
        ))}
        {Array.from({ length: slots }).map((_, i) => (
          <div key={i} style={{ border:'1px dashed #1a2535', borderRadius:10, padding:14, marginBottom:10, textAlign:'center', color:'#1a2535', fontSize:12 }}>
            — empty slot {openPositions.length + i + 1} —
          </div>
        ))}
      </div>

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

      <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10, padding:16, marginTop:20 }}>
        {/* Tab header */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
          <div style={{ display:'flex', gap:4 }}>
            {[['log','SYSTEM ACTION LOG'],['history','TRADE HISTORY (85)']].map(([key,label]) => (
              <button key={key} onClick={() => { setHistoryTab(key); if(key==='history' && !tradeHistory) fetchTradeHistory(); }}
                style={{ background: historyTab===key ? '#1a2535' : 'transparent',
                         border:`1px solid ${historyTab===key ? '#2a4a6a' : '#1a2535'}`,
                         borderRadius:4, padding:'4px 10px', color: historyTab===key ? '#00d4ff' : '#4a6a8a',
                         fontSize:10, fontWeight:'bold', letterSpacing:0.8, cursor:'pointer' }}>
                {label}
              </button>
            ))}
          </div>
          {historyTab === 'log' && (
            <button onClick={fetchActionLog}
              style={{ background:'transparent', border:'1px solid #1a2535', borderRadius:4, padding:'3px 8px', color:'#8899aa', fontSize:10, cursor:'pointer', display:'flex', alignItems:'center', gap:4 }}>
              <RefreshCw size={10} /> Refresh
            </button>
          )}
          {historyTab === 'history' && (
            <button onClick={fetchTradeHistory}
              style={{ background:'transparent', border:'1px solid #1a2535', borderRadius:4, padding:'3px 8px', color:'#8899aa', fontSize:10, cursor:'pointer', display:'flex', alignItems:'center', gap:4 }}>
              <RefreshCw size={10} /> Refresh
            </button>
          )}
        </div>

        {/* ACTION LOG tab */}
        {historyTab === 'log' && (<>
          <div style={{ fontSize:10, color:'#2a4a5a', marginBottom:12, fontFamily:'sans-serif' }}>Last 50 actions across all signals</div>
          {allActions.length === 0 ? (
            <div style={{ textAlign:'center', padding:'20px', color:'#2a4a5a', fontSize:12, fontFamily:'monospace' }}>No actions recorded yet.</div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
              {allActions.map((a, i) => {
                const act = a.action || '';
                const col = act.includes('TP') || act === 'TSL_MOVE' || act === 'TRAILING_SL' || act === 'TSL_ACTIVATED'
                  ? '#00ff88'
                  : act.includes('SL_HIT') || act === 'CLOSED' || act === 'STOPPED' || act === 'MOMENTUM_FADE' || act === 'TIMEOUT' || a.category === 'bad'
                  ? '#ff4466'
                  : act === 'OPENED' || act === 'STATE_CHANGE'
                  ? '#00d4ff'
                  : '#8899aa';
                return (
                  <div key={i} style={{ display:'grid', gridTemplateColumns:'130px 65px 140px 1fr', gap:8, alignItems:'center', fontSize:10, fontFamily:'monospace', borderBottom:'1px solid #060d14', paddingBottom:4, paddingTop:2 }}>
                    <span style={{ color:'#2a4a5a' }}>{(a.ts || '').slice(0,19).replace('T',' ')}</span>
                    <span style={{ color:'#e0e0e0', fontWeight:'bold' }}>{a.ticker}</span>
                    <span style={{ color:col, fontWeight:'bold' }}>{act}</span>
                    <span style={{ color:'#8899aa', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{a.detail || ''}</span>
                  </div>
                );
              })}
            </div>
          )}
        </>)}

        {/* TRADE HISTORY tab */}
        {historyTab === 'history' && (<>
          {!tradeHistory ? (
            <div style={{ textAlign:'center', padding:'20px', color:'#2a4a5a', fontSize:12 }}>Loading history...</div>
          ) : (<>
            {/* Summary stats bar */}
            <div style={{ display:'flex', gap:12, flexWrap:'wrap', marginBottom:14 }}>
              {[
                ['TOTAL',          tradeHistory.stats?.total ?? '—'],
                ['WIN RATE',       `${tradeHistory.stats?.win_rate ?? 0}%`],
                ['AVG P&L',        `${tradeHistory.stats?.avg_pnl > 0 ? '+' : ''}${tradeHistory.stats?.avg_pnl ?? 0}%`],
                ['PROFIT FACTOR',  tradeHistory.stats?.profit_factor ?? '—'],
                ['AVG MFE',        `+${tradeHistory.stats?.avg_mfe ?? 0}%`],
                ['AVG MAE',        `${tradeHistory.stats?.avg_mae ?? 0}%`],
              ].map(([lbl, val]) => (
                <div key={lbl} style={{ background:'#060d14', border:'1px solid #1a2535', borderRadius:6, padding:'6px 12px', minWidth:70 }}>
                  <div style={{ fontSize:9, color:'#4a6a8a', letterSpacing:1 }}>{lbl}</div>
                  <div style={{ fontSize:13, fontWeight:'bold', color: lbl==='WIN RATE' ? (parseFloat(val)>=50?'#00ff88':'#ff4466') : lbl==='AVG P&L' ? (parseFloat(val)>=0?'#00ff88':'#ff4466') : '#e0e0e0' }}>{val}</div>
                </div>
              ))}
            </div>
            {/* Table */}
            <div style={{ overflowX:'auto' }}>
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:10, fontFamily:'monospace' }}>
                <thead>
                  <tr style={{ borderBottom:'1px solid #1a2535', color:'#4a6a8a', fontSize:9, letterSpacing:0.8 }}>
                    {['DATE','TICKER','REGIME','CONV','TAS','VOL','EXIT','P&L%','MFE','MAE'].map(h => (
                      <th key={h} style={{ padding:'4px 6px', textAlign:'left', whiteSpace:'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(tradeHistory.trades || []).map((t, i) => {
                    const pnl = parseFloat(t.pnl_pct ?? 0);
                    const pnlColor = pnl > 0 ? '#00ff88' : pnl < 0 ? '#ff4466' : '#94a3b8';
                    const exitColor = t.exit_reason?.includes('TP') ? '#00ff88' : t.exit_reason?.includes('SL') ? '#ff4466' : '#8899aa';
                    return (
                      <tr key={i} style={{ borderBottom:'1px solid #060d14' }}>
                        <td style={{ padding:'4px 6px', color:'#4a6a8a' }}>{(t.date_closed || '').slice(0,10)}</td>
                        <td style={{ padding:'4px 6px', color:'#e0e0e0', fontWeight:'bold' }}>{t.ticker}</td>
                        <td style={{ padding:'4px 6px', color:'#8899aa', fontSize:9 }}>{t.regime || '—'}</td>
                        <td style={{ padding:'4px 6px', color: parseFloat(t.conviction||0)>=72 ? '#00d4ff' : '#8899aa' }}>{t.conviction ? `${Math.round(t.conviction)}%` : '—'}</td>
                        <td style={{ padding:'4px 6px', color: t.tas_num>=3 ? '#00d4ff' : '#4a6a8a' }}>{t.tas_num != null ? `${t.tas_num}/4` : '—'}</td>
                        <td style={{ padding:'4px 6px', color: parseFloat(t.vol_ratio||0)>=1.0 ? '#00ff88' : '#ff4466' }}>{t.vol_ratio ? `${parseFloat(t.vol_ratio).toFixed(2)}x` : '—'}</td>
                        <td style={{ padding:'4px 6px', color: exitColor }}>{t.exit_reason || '—'}</td>
                        <td style={{ padding:'4px 6px', color: pnlColor, fontWeight:'bold' }}>{pnl > 0 ? '+' : ''}{pnl.toFixed(2)}%</td>
                        <td style={{ padding:'4px 6px', color:'#00ff88' }}>{t.mfe_pct != null ? `+${parseFloat(t.mfe_pct).toFixed(2)}%` : '—'}</td>
                        <td style={{ padding:'4px 6px', color:'#ff4466' }}>{t.mae_pct != null ? `${parseFloat(t.mae_pct).toFixed(2)}%` : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>)}
        </>)}
      </div>
    </div>
  );
}
