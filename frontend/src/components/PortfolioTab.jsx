import React, { useState, useEffect, useCallback } from 'react';
import { TrendingUp, TrendingDown, RefreshCw, X, Zap, RotateCcw, DollarSign, Target, BarChart2 } from 'lucide-react';

const API = () => import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const fmt  = (n, d=2) => (n == null ? '—' : Number(n).toFixed(d));
const pct  = n => `${n > 0 ? '+' : ''}${fmt(n)}%`;
const usd  = n => `$${fmt(n, 0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`;
const clr  = n => n > 0 ? '#00ff88' : n < 0 ? '#ff4466' : '#94a3b8';
const heatClr = c => c >= 75 ? '#00ff88' : c >= 60 ? '#fbbf24' : '#94a3b8';

const StatCard = ({ label, value, sub, color, small }) => (
  <div style={{ background:'#0d1a2a', border:'1px solid #1a2535', borderRadius:8, padding:'12px 16px', minWidth:100, textAlign:'center' }}>
    <div style={{ fontSize:9, color:'#4a6070', letterSpacing:1, marginBottom:5, fontFamily:'monospace' }}>{label}</div>
    <div style={{ fontSize: small ? 16 : 20, fontWeight:'bold', color: color || '#00d4ff', fontFamily:'monospace' }}>{value}</div>
    {sub && <div style={{ fontSize:9, color:'#4a6070', marginTop:3 }}>{sub}</div>}
  </div>
);

const PositionCard = ({ pos, onClose, onRefresh }) => {
  const pnl    = pos.unrealized_pnl || 0;
  const pnlPct = pos.unrealized_pnl_pct || 0;
  const entry  = pos.entry_price;
  const curr   = pos.current_price || entry;
  const sl     = pos.sl;
  const tp1    = pos.tp1;
  const tp2    = pos.tp2;
  const tp3    = pos.tp3;
  const isPartial = pos.status === 'partial';

  // Progress: how far from entry to TP1
  const range = tp1 - sl;
  const progress = range > 0 ? Math.min(100, Math.max(0, (curr - sl) / range * 100)) : 0;
  const barColor = pnl >= 0 ? '#00ff88' : '#ff4466';

  return (
    <div style={{ background:'#0a1018', border:`1px solid ${pnl >= 0 ? '#1a3525' : '#351a1a'}`, borderRadius:10, padding:14, marginBottom:10 }}>
      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span style={{ fontSize:16, fontWeight:'bold', color:'#e0e0e0', fontFamily:'monospace' }}>{pos.ticker}</span>
          {isPartial && <span style={{ fontSize:9, background:'rgba(251,191,36,0.15)', color:'#fbbf24', borderRadius:4, padding:'2px 6px', border:'1px solid #fbbf24' }}>PARTIAL</span>}
          {pos.tp1_hit && <span style={{ fontSize:9, background:'rgba(0,255,136,0.1)', color:'#00ff88', borderRadius:4, padding:'2px 6px' }}>TP1✓</span>}
          {pos.tp2_hit && <span style={{ fontSize:9, background:'rgba(0,255,136,0.15)', color:'#00ff88', borderRadius:4, padding:'2px 6px' }}>TP2✓</span>}
          {pos.conviction > 0 && <span style={{ fontSize:9, color:heatClr(pos.conviction), fontFamily:'monospace' }}>{pos.conviction}%</span>}
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <span style={{ fontSize:18, fontWeight:'bold', color:clr(pnl), fontFamily:'monospace' }}>
            {pnl >= 0 ? '+' : ''}{fmt(pnl, 0)} <span style={{ fontSize:12 }}>({pct(pnlPct)})</span>
          </span>
          <button onClick={() => onClose(pos.id)} style={{ background:'transparent', border:'1px solid #ff4466', borderRadius:4, padding:'3px 8px', color:'#ff4466', fontSize:10, cursor:'pointer' }}>✕ Close</button>
        </div>
      </div>

      {/* Price progress bar */}
      <div style={{ position:'relative', height:6, background:'#1a2535', borderRadius:3, marginBottom:10, overflow:'hidden' }}>
        <div style={{ position:'absolute', left:0, top:0, height:'100%', width:`${progress}%`, background:barColor, borderRadius:3, transition:'width 0.5s' }} />
      </div>

      {/* Levels grid */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:6, fontSize:10, fontFamily:'monospace' }}>
        {[
          { label:'ENTRY', val:`$${fmt(entry,2)}`, color:'#94a3b8' },
          { label:'PRICE', val:`$${fmt(curr,2)}`, color:clr(pnl) },
          { label:'SL', val:`$${fmt(sl,2)}`, color:'#ff4466' },
          { label:'TP1', val:`$${fmt(tp1,2)}`, color: pos.tp1_hit ? '#00ff88' : '#4a6070' },
          { label:'TP2', val:`$${fmt(tp2,2)}`, color: pos.tp2_hit ? '#00ff88' : '#4a6070' },
          { label:'TP3', val:`$${fmt(tp3,2)}`, color:'#4a6070' },
        ].map(l => (
          <div key={l.label} style={{ textAlign:'center' }}>
            <div style={{ color:'#4a6070', fontSize:8, marginBottom:2 }}>{l.label}</div>
            <div style={{ color:l.color, fontWeight:'bold' }}>{l.val}</div>
          </div>
        ))}
      </div>

      {/* Shares + position size */}
      <div style={{ display:'flex', gap:12, marginTop:8, fontSize:10, color:'#4a6070', fontFamily:'monospace' }}>
        <span>{pos.shares_remaining}/{pos.shares} shares</span>
        <span>Size: ${fmt(pos.position_size, 0)}</span>
        <span>Risk: ${fmt(pos.risk_actual, 0)}</span>
        {pos.mae != null && <span style={{ color:'#ff4466' }}>MAE: {pct(pos.mae / entry * 100)}</span>}
        {pos.mfe != null && <span style={{ color:'#00ff88' }}>MFE: {pct(pos.mfe / entry * 100)}</span>}
      </div>
    </div>
  );
};

const ClosedRow = ({ pos }) => {
  const pnl = pos.realized_pnl || 0;
  const pnlPct = pos.entry_price > 0 ? (pnl / pos.position_size * 100) : 0;
  const lastTrade = (pos.trades || []).slice(-1)[0] || {};
  return (
    <tr style={{ borderBottom:'1px solid #0d1a2a' }}>
      <td style={{ padding:'5px 6px', color:'#e0e0e0', fontWeight:'bold', fontFamily:'monospace' }}>{pos.ticker}</td>
      <td style={{ padding:'5px 6px', textAlign:'right', color:'#4a6070', fontSize:10 }}>{(pos.entry_date||'').slice(0,10)}</td>
      <td style={{ padding:'5px 6px', textAlign:'right', color:'#94a3b8' }}>${fmt(pos.entry_price,2)}</td>
      <td style={{ padding:'5px 6px', textAlign:'right', color:'#94a3b8' }}>${fmt(lastTrade.price,2)}</td>
      <td style={{ padding:'5px 6px', textAlign:'right', color:clr(pnl), fontWeight:'bold' }}>{pnl>=0?'+':''}{fmt(pnl,0)}</td>
      <td style={{ padding:'5px 6px', textAlign:'right', color:clr(pnlPct) }}>{pct(pnlPct)}</td>
      <td style={{ padding:'5px 6px', textAlign:'right', color: lastTrade.tp_level?.includes('TP')? '#00ff88': lastTrade.tp_level==='SL'?'#ff4466':'#94a3b8', fontSize:10 }}>
        {lastTrade.tp_level || '—'}
      </td>
    </tr>
  );
};

export default function PortfolioTab() {
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [checking, setChecking] = useState(false);
  const [openTicker, setOpenTicker] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [countdown, setCountdown]    = useState(30);
  const [error, setError]       = useState(null);
  const [activeTab, setActiveTab] = useState('open');

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
      // First get scan data for the ticker
      const scanRes = await fetch(`${API()}/api/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: [openTicker.trim().toUpperCase()], watchlist: null }),
      });
      const scanData = await scanRes.json();
      const best = (scanData.results || [])[0];
      if (!best || best.hard_fail) {
        setError(`${openTicker}: No valid signal (hard fail or no data)`);
        setLoading(false);
        return;
      }
      const r = await fetch(`${API()}/api/portfolio/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: best.ticker,
          entry_price: best.entry_high || best.last_close,
          sl: best.sl, tp1: best.tp1, tp2: best.tp2, tp3: best.tp3,
          conviction: best.conviction_pct, asset_type: 'stock',
        }),
      });
      const result = await r.json();
      if (result.error) { setError(result.error); }
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
      else setError('No qualifying signals found (need conviction >= 65%)');
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

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { checkPrices(); return 30; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [autoRefresh]);

  const s     = data?.stats || {};
  const state = data?.state || {};
  const openPositions  = data?.open_positions  || [];
  const closedPositions = (data?.closed_positions || []).slice().reverse();
  const slots = Math.max(0, 5 - openPositions.length);
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
            <div style={{ fontSize:11, color:'#4a6070' }}>Paper trading · $25K starting capital · Max 5 positions · $500 risk/trade</div>
          </div>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <button onClick={() => { setAutoRefresh(a => !a); setCountdown(30); }}
            style={{ background: autoRefresh ? 'rgba(0,212,255,0.15)' : 'transparent', border:`1px solid ${autoRefresh?'#00d4ff':'#1a2535'}`, borderRadius:6, padding:'6px 12px', color: autoRefresh?'#00d4ff':'#4a6070', fontSize:11, cursor:'pointer' }}>
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

      {error && <div style={{ background:'rgba(255,68,102,0.1)', border:'1px solid #ff4466', borderRadius:8, padding:10, marginBottom:14, color:'#ff4466', fontSize:12 }}>{error} <span style={{ cursor:'pointer', float:'right' }} onClick={() => setError(null)}>✕</span></div>}

      {/* Stats row */}
      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap' }}>
        <StatCard label="TOTAL VALUE"  value={usd(s.total_value)}  color='#00d4ff' />
        <StatCard label="CASH"         value={usd(s.cash)}          color='#7ee8ff' sub={`${slots} slot${slots!==1?'s':''} open`} />
        <StatCard label="TOTAL P&L"    value={`${totalPnl>=0?'+':''}${fmt(totalPnl,0)}`} color={clr(totalPnl)} sub={pct(s.total_pnl_pct||0)} />
        <StatCard label="UNREALIZED"   value={`${(s.total_unrealized_pnl||0)>=0?'+':''}${fmt(s.total_unrealized_pnl||0,0)}`} color={clr(s.total_unrealized_pnl||0)} />
        <StatCard label="REALIZED"     value={`${(s.total_realized_pnl||0)>=0?'+':''}${fmt(s.total_realized_pnl||0,0)}`} color={clr(s.total_realized_pnl||0)} />
        <StatCard label="OPEN"         value={s.open_count||0}      sub="positions" color='#fbbf24' />
        <StatCard label="WIN RATE"     value={`${s.win_rate||0}%`}  sub={`${s.total_closed||0} closed`} color={s.win_rate>=60?'#00ff88':s.win_rate>=40?'#fbbf24':'#ff4466'} />
      </div>

      {/* Position slots + open controls */}
      <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10, padding:16, marginBottom:20 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
          <div style={{ fontSize:13, fontWeight:'bold', color:'#00d4ff', letterSpacing:1 }}>
            POSITIONS — {openPositions.length}/5 SLOTS USED
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
              style={{ background: slots===0?'#1a2535':'linear-gradient(135deg,#7c3aed,#a855f7)', border:'none', borderRadius:6, padding:'6px 14px', color:'#fff', fontSize:12, fontWeight:'bold', cursor: slots===0?'not-allowed':'pointer', display:'flex', alignItems:'center', gap:5 }}>
              <Zap size={13} /> AUTO-FILL {slots} SLOTS
            </button>
          </div>
        </div>

        {loading && <div style={{ padding:10, color:'#fbbf24', fontSize:11, fontFamily:'monospace' }}>⏳ Processing...</div>}

        {openPositions.length === 0 && !loading && (
          <div style={{ textAlign:'center', padding:'30px 20px', color:'#4a6070', fontSize:12 }}>
            No open positions. Enter a ticker or click AUTO-FILL to start.
          </div>
        )}

        {openPositions.map(pos => (
          <PositionCard key={pos.id} pos={pos} onClose={closePos} />
        ))}

        {/* Empty slots */}
        {Array.from({ length: slots }).map((_, i) => (
          <div key={i} style={{ border:'1px dashed #1a2535', borderRadius:10, padding:14, marginBottom:10, textAlign:'center', color:'#1a2535', fontSize:12 }}>
            — empty slot {openPositions.length + i + 1} —
          </div>
        ))}
      </div>

      {/* Closed positions table */}
      {closedPositions.length > 0 && (
        <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10, padding:16 }}>
          <div style={{ fontSize:13, fontWeight:'bold', color:'#94a3b8', marginBottom:12, letterSpacing:1 }}>
            TRADE LOG — {closedPositions.length} CLOSED
          </div>
          <div style={{ overflowX:'auto' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11, fontFamily:'monospace' }}>
              <thead>
                <tr style={{ borderBottom:'1px solid #1a2535' }}>
                  {['Ticker','Date','Entry','Exit','P&L $','P&L %','Result'].map(h => (
                    <th key={h} style={{ padding:'6px 6px', textAlign:'right', color:'#4a6070', fontSize:9, fontWeight:'normal', letterSpacing:1 }}>{h}</th>
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
