import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Zap, RotateCcw, Target, BarChart2, Clock, ChevronDown, ChevronRight, TrendingUp, TrendingDown, AlertTriangle, Shield } from 'lucide-react';

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
  const [scanCandidates, setScanCandidates] = useState([]);
  const [allActions,     setAllActions]     = useState([]);

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

  useEffect(() => { load(); fetchCandidates([]); fetchActionLog(); }, [load, fetchCandidates, fetchActionLog]);
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
      <style>{`@keyframes p-pulse { 0%,100%{opacity:1} 50%{opacity:0.45} }`}</style>
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

      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap' }}>
        <StatCard label='TOTAL VALUE'  value={usd(s.total_value)}  color='#00d4ff' />
        <StatCard label='CASH'         value={usd(s.cash)}          color='#7ee8ff' sub={`${slots} slot${slots!==1?'s':''} open`} />
        <StatCard label='TOTAL P&L'    value={`${totalPnl>=0?'+':''}${fmt(totalPnl,0)}`} color={clr(totalPnl)} sub={pct(s.total_pnl_pct||0)} />
        <StatCard label='UNREALIZED'   value={`${(s.total_unrealized_pnl||0)>=0?'+':''}${fmt(s.total_unrealized_pnl||0,0)}`} color={clr(s.total_unrealized_pnl||0)} />
        <StatCard label='REALIZED'     value={`${(s.total_realized_pnl||0)>=0?'+':''}${fmt(s.total_realized_pnl||0,0)}`} color={clr(s.total_realized_pnl||0)} />
        <StatCard label='OPEN'         value={s.open_count||0}      sub='positions' color='#fbbf24' />
        <StatCard label='WIN RATE'     value={`${s.win_rate||0}%`}  sub={`${s.total_closed||0} closed`} color={s.win_rate>=60?'#00ff88':s.win_rate>=40?'#fbbf24':'#ff4466'} />
      </div>

      <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10, padding:16, marginBottom:20 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
          <div>
            <div style={{ fontSize:13, fontWeight:'bold', color:'#00d4ff', letterSpacing:1 }}>POSITIONS — {openPositions.length}/{maxPositions} SLOTS USED</div>
            <div style={{ fontSize:10, color:'#2a4a5a', marginTop:2, fontFamily:'sans-serif' }}>Click any position to expand details</div>
          </div>
          <div style={{ display:'flex', gap:8 }}>
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
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:4 }}>
          <div style={{ fontSize:13, fontWeight:'bold', color:'#8899aa', letterSpacing:1 }}>SYSTEM ACTION LOG</div>
          <button onClick={fetchActionLog}
            style={{ background:'transparent', border:'1px solid #1a2535', borderRadius:4, padding:'3px 8px', color:'#8899aa', fontSize:10, cursor:'pointer', display:'flex', alignItems:'center', gap:4 }}>
            <RefreshCw size={10} /> Refresh
          </button>
        </div>
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
      </div>
    </div>
  );
}
