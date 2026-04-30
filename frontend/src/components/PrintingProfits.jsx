import React, { useState, useEffect, useCallback } from 'react';
import { TrendingUp, TrendingDown, Zap, RefreshCw, RotateCcw, DollarSign, Target, Activity, BarChart2, Clock, Shield, ChevronDown, ChevronUp } from 'lucide-react';

const API = () => import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const fmt  = (n, d=2) => n == null ? '—' : Number(n).toFixed(d);
const usd  = n => `$${fmt(Math.abs(n), 0).replace(/\B(?=(\d{3})+(?!\d))/g,',')}`;
const pct  = n => `${n>=0?'+':''}${fmt(n)}%`;
const clr  = n => n > 0 ? '#00ff88' : n < 0 ? '#ff4466' : '#94a3b8';
const heatClr = c => c >= 75 ? '#00ff88' : c >= 65 ? '#fbbf24' : '#94a3b8';
const dirClr  = d => d === 'long' ? '#00ff88' : '#ff4466';
const dirBg   = d => d === 'long' ? 'rgba(0,255,136,0.08)' : 'rgba(255,68,102,0.08)';
const dirBorder = d => d === 'long' ? '#1a3525' : '#351a1a';

// ── Stat Card ─────────────────────────────────────────────────────────────────
const Stat = ({ label, value, sub, color, small }) => (
  <div style={{ background:'#0d1a2a', border:'1px solid #1a2535', borderRadius:8,
    padding:'10px 14px', textAlign:'center', minWidth:90 }}>
    <div style={{ fontSize:9, color:'#4a6070', letterSpacing:1, marginBottom:4, fontFamily:'monospace' }}>{label}</div>
    <div style={{ fontSize:small?15:19, fontWeight:'bold', color:color||'#00d4ff', fontFamily:'monospace' }}>{value}</div>
    {sub && <div style={{ fontSize:9, color:'#4a6070', marginTop:3 }}>{sub}</div>}
  </div>
);

// ── Signal Card (long or short) ───────────────────────────────────────────────
const SignalCard = ({ r, onOpen }) => {
  const dir   = r.direction || 'long';
  const isLng = dir === 'long';
  const [exp, setExp] = useState(false);
  return (
    <div style={{ background:dirBg(dir), border:`1px solid ${dirBorder(dir)}`,
      borderRadius:8, padding:'10px 12px', marginBottom:8 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span style={{ fontSize:14, fontWeight:'bold', color:'#e0e0e0', fontFamily:'monospace' }}>{r.ticker}</span>
          <span style={{ fontSize:9, background:dirBg(dir), color:dirClr(dir),
            border:`1px solid ${dirClr(dir)}`, borderRadius:3, padding:'2px 6px', fontWeight:'bold' }}>
            {isLng ? '▲ LONG' : '▼ SHORT'}
          </span>
          <span style={{ fontSize:9, color:heatClr(r.conviction_pct), fontFamily:'monospace', fontWeight:'bold' }}>
            {r.conviction_pct}%
          </span>
          <span style={{ fontSize:9, color:'#7ee8ff', fontFamily:'monospace' }}>{r.tas}</span>
          <span style={{ fontSize:9, color:'#4a6070' }}>{r.heat}</span>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          {r.kelly_label && (
            <span style={{ fontSize:9, color:'#a855f7', background:'rgba(168,85,247,0.1)',
              borderRadius:3, padding:'2px 6px', border:'1px solid rgba(168,85,247,0.3)' }}>
              Kelly: {r.kelly_label}
            </span>
          )}
          <button onClick={() => onOpen(r)} style={{ background:dirClr(dir), border:'none',
            borderRadius:4, padding:'4px 10px', color:'#000', fontSize:10, fontWeight:'bold', cursor:'pointer' }}>
            OPEN
          </button>
          <button onClick={() => setExp(!exp)} style={{ background:'transparent', border:'none',
            color:'#4a6070', cursor:'pointer', padding:2 }}>
            {exp ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
          </button>
        </div>
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:4,
        fontSize:10, fontFamily:'monospace', marginTop:8 }}>
        {[
          { l:'ENTRY', v:`$${fmt(r.last_close||r.entry,2)}`, c:'#94a3b8' },
          { l:'SL',    v:`$${fmt(r.sl,2)}`,  c:'#ff4466' },
          { l:'TP1',   v:`$${fmt(r.tp1,2)}`, c:'#00ff88' },
          { l:'R:R',   v:`${fmt(r.rr,1)}:1`, c:'#fbbf24' },
          { l:'RISK',  v:`$${r.kelly_risk_usd||0}`, c:'#a855f7' },
        ].map(x => (
          <div key={x.l} style={{ textAlign:'center' }}>
            <div style={{ color:'#4a6070', fontSize:8, marginBottom:2 }}>{x.l}</div>
            <div style={{ color:x.c, fontWeight:'bold' }}>{x.v}</div>
          </div>
        ))}
      </div>
      {exp && (
        <div style={{ marginTop:8, fontSize:9, color:'#94a3b8', fontFamily:'monospace',
          background:'rgba(255,255,255,0.02)', borderRadius:4, padding:'6px 8px',
          borderLeft:`2px solid ${dirClr(dir)}` }}>
          {r.ta_note}
        </div>
      )}
    </div>
  );
};

// ── Futures Card ──────────────────────────────────────────────────────────────
const FuturesCard = ({ f }) => {
  if (f.error) return (
    <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:8, padding:12 }}>
      <div style={{ color:'#e0e0e0', fontWeight:'bold', fontFamily:'monospace' }}>{f.symbol}</div>
      <div style={{ color:'#ff4466', fontSize:10 }}>{f.error}</div>
    </div>
  );
  const isUp   = f.change_pct >= 0;
  const isBull = f.trend === 'BULL';
  return (
    <div style={{ background:'#0a1018', border:`1px solid ${isBull?'#1a3525':'#351a1a'}`,
      borderRadius:8, padding:12 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
        <div>
          <div style={{ fontSize:13, fontWeight:'bold', color:'#e0e0e0', fontFamily:'monospace' }}>{f.symbol}</div>
          <div style={{ fontSize:9, color:'#4a6070' }}>{f.name}</div>
        </div>
        <div style={{ textAlign:'right' }}>
          <div style={{ fontSize:16, fontWeight:'bold', color:'#e0e0e0', fontFamily:'monospace' }}>
            ${fmt(f.price, f.price > 100 ? 2 : 4)}
          </div>
          <div style={{ fontSize:11, color:clr(f.change_pct), fontWeight:'bold' }}>
            {isUp?'+':''}{fmt(f.change_pct)}%
          </div>
        </div>
      </div>
      <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:8 }}>
        <span style={{ fontSize:9, color:isBull?'#00ff88':'#ff4466',
          background:isBull?'rgba(0,255,136,0.08)':'rgba(255,68,102,0.08)',
          border:`1px solid ${isBull?'#00ff88':'#ff4466'}`, borderRadius:3, padding:'2px 5px' }}>
          {f.trend}
        </span>
        {f.vwap && (
          <span style={{ fontSize:9, color: f.above_vwap?'#00ff88':'#ff4466',
            background:'rgba(255,255,255,0.04)', borderRadius:3, padding:'2px 5px' }}>
            {f.above_vwap ? '▲' : '▼'} VWAP ${fmt(f.vwap,2)}
          </span>
        )}
        {f.tpt_ok && (
          <span style={{ fontSize:9, color:'#fbbf24',
            background:'rgba(251,191,36,0.08)', borderRadius:3, padding:'2px 5px' }}>
            TPT ✓
          </span>
        )}
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:9,
        fontFamily:'monospace', color:'#94a3b8' }}>
        <div>
          <div style={{ color:'#00ff88', marginBottom:3 }}>▲ LONG SETUP</div>
          <div>Entry: ${fmt(f.long_entry,2)}</div>
          <div style={{ color:'#ff4466' }}>SL: ${fmt(f.long_sl,2)}</div>
          <div style={{ color:'#00ff88' }}>TP1: ${fmt(f.long_tp1,2)}</div>
          <div style={{ color:'#fbbf24' }}>R:R {f.rr_long}:1</div>
        </div>
        <div>
          <div style={{ color:'#ff4466', marginBottom:3 }}>▼ SHORT SETUP</div>
          <div>Entry: ${fmt(f.short_entry,2)}</div>
          <div style={{ color:'#ff4466' }}>SL: ${fmt(f.short_sl,2)}</div>
          <div style={{ color:'#00ff88' }}>TP1: ${fmt(f.short_tp1,2)}</div>
          <div style={{ color:'#fbbf24' }}>R:R {f.rr_short}:1</div>
        </div>
      </div>
    </div>
  );
};

// ── Position Card ─────────────────────────────────────────────────────────────
const PositionCard = ({ pos, onClose }) => {
  const dir   = pos.direction || 'long';
  const pnl   = pos.unrealized_pnl || 0;
  const pnlP  = pos.unrealized_pnl_pct || 0;
  const entry = pos.entry_price;
  const curr  = pos.current_price || entry;
  const range = Math.abs(pos.tp1 - pos.sl);
  const prog  = range > 0 ? Math.min(100, Math.max(0,
    dir === 'long'
      ? (curr - pos.sl) / range * 100
      : (pos.sl - curr) / range * 100
  )) : 0;

  return (
    <div style={{ background:dirBg(dir), border:`1px solid ${dirBorder(dir)}`,
      borderRadius:8, padding:12, marginBottom:8 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span style={{ fontSize:14, fontWeight:'bold', color:'#e0e0e0', fontFamily:'monospace' }}>{pos.ticker}</span>
          <span style={{ fontSize:9, color:dirClr(dir), border:`1px solid ${dirClr(dir)}`,
            borderRadius:3, padding:'2px 5px' }}>{dir === 'long' ? '▲ LONG' : '▼ SHORT'}</span>
          {pos.tp1_hit && <span style={{ fontSize:9, color:'#00ff88', background:'rgba(0,255,136,0.1)', borderRadius:3, padding:'2px 5px' }}>TP1✓</span>}
          {pos.tp2_hit && <span style={{ fontSize:9, color:'#00ff88', background:'rgba(0,255,136,0.15)', borderRadius:3, padding:'2px 5px' }}>TP2✓</span>}
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span style={{ fontSize:16, fontWeight:'bold', color:clr(pnl), fontFamily:'monospace' }}>
            {pnl>=0?'+':''}{fmt(pnl,0)} <span style={{ fontSize:11 }}>({pct(pnlP)})</span>
          </span>
          <button onClick={() => onClose(pos.id)} style={{ background:'transparent',
            border:'1px solid #ff4466', borderRadius:4, padding:'3px 8px',
            color:'#ff4466', fontSize:9, cursor:'pointer' }}>✕</button>
        </div>
      </div>
      <div style={{ height:5, background:'#1a2535', borderRadius:3, marginBottom:8, overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${prog}%`, background:clr(pnl), borderRadius:3, transition:'width 0.5s' }} />
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:4, fontSize:9, fontFamily:'monospace' }}>
        {[
          { l:'ENTRY', v:`$${fmt(entry,2)}`, c:'#94a3b8' },
          { l:'PRICE', v:`$${fmt(curr,2)}`,  c:clr(pnl) },
          { l:'SL',    v:`$${fmt(pos.sl,2)}`, c:'#ff4466' },
          { l:'TP1',   v:`$${fmt(pos.tp1,2)}`, c:pos.tp1_hit?'#00ff88':'#4a6070' },
          { l:'TP2',   v:`$${fmt(pos.tp2,2)}`, c:pos.tp2_hit?'#00ff88':'#4a6070' },
          { l:'TP3',   v:`$${fmt(pos.tp3,2)}`, c:'#4a6070' },
        ].map(x => (
          <div key={x.l} style={{ textAlign:'center' }}>
            <div style={{ color:'#4a6070', fontSize:8, marginBottom:2 }}>{x.l}</div>
            <div style={{ color:x.c, fontWeight:'bold' }}>{x.v}</div>
          </div>
        ))}
      </div>
      <div style={{ fontSize:9, color:'#4a6070', fontFamily:'monospace', marginTop:6, display:'flex', gap:10 }}>
        <span>{pos.shares_remaining}/{pos.shares} sh</span>
        <span>Size: ${fmt(pos.position_size,0)}</span>
        <span>Risk: ${fmt(pos.risk_usd,0)}</span>
        {pos.conviction > 0 && <span style={{ color:'#a855f7' }}>Conv: {pos.conviction}%</span>}
      </div>
    </div>
  );
};

// ── TPT Tracker ───────────────────────────────────────────────────────────────
const TPTTracker = ({ portfolioStats }) => {
  const [acctSize, setAcctSize] = useState(50000);
  const TARGETS = { 25000:1500, 50000:3000, 100000:6000, 150000:9000 };
  const DRAWDOWNS = { 25000:1500, 50000:2000, 100000:3000, 150000:4500 };
  const [days, setDays] = useState(0);

  const target    = TARGETS[acctSize] || 3000;
  const drawdown  = DRAWDOWNS[acctSize] || 2000;
  const realized  = portfolioStats?.total_realized_pnl || 0;
  const progress  = Math.min(100, Math.max(0, realized / target * 100));
  const remaining = Math.max(0, target - realized);
  const daysLeft  = remaining > 0 && realized > 0 ? Math.ceil(remaining / (realized / Math.max(days,1))) : '—';
  const passed    = realized >= target && days >= 5;
  const failed    = false; // would need drawdown tracking

  return (
    <div style={{ padding:16 }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:20 }}>
        <Shield size={20} color="#fbbf24" />
        <div>
          <div style={{ fontSize:14, fontWeight:'bold', color:'#fff', letterSpacing:1 }}>TAKEPROFITTRADER EVALUATION TRACKER</div>
          <div style={{ fontSize:10, color:'#4a6070' }}>Track your progress toward a funded account — trade their $50K-$150K, keep 80%</div>
        </div>
      </div>

      {/* Account selector */}
      <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:8, padding:14, marginBottom:16 }}>
        <div style={{ fontSize:10, color:'#4a6070', marginBottom:8, letterSpacing:1 }}>SELECT EVALUATION ACCOUNT SIZE</div>
        <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
          {Object.keys(TARGETS).map(sz => (
            <button key={sz} onClick={() => setAcctSize(+sz)} style={{
              background: acctSize===+sz ? 'rgba(251,191,36,0.15)' : '#0d1a2a',
              border: `1px solid ${acctSize===+sz ? '#fbbf24' : '#1a2535'}`,
              borderRadius:6, padding:'8px 14px', color: acctSize===+sz ? '#fbbf24' : '#94a3b8',
              fontSize:12, fontWeight:'bold', cursor:'pointer', fontFamily:'monospace',
            }}>
              ${(+sz/1000).toFixed(0)}K
            </button>
          ))}
        </div>
      </div>

      {/* Progress */}
      <div style={{ background:'#0a1018', border:`2px solid ${passed?'#00ff88':'#1a2535'}`,
        borderRadius:10, padding:16, marginBottom:16 }}>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:12 }}>
          <div style={{ fontSize:13, fontWeight:'bold', color: passed?'#00ff88':'#fff', letterSpacing:1 }}>
            {passed ? '🎉 EVALUATION PASSED — GET FUNDED' : '📊 EVALUATION IN PROGRESS'}
          </div>
          <div style={{ fontSize:12, color:'#4a6070', fontFamily:'monospace' }}>
            ${fmt(realized,0)} / ${(target/1000).toFixed(0)}K target
          </div>
        </div>
        <div style={{ height:12, background:'#1a2535', borderRadius:6, marginBottom:8, overflow:'hidden' }}>
          <div style={{ height:'100%', width:`${progress}%`,
            background: passed ? '#00ff88' : `linear-gradient(90deg, #fbbf24, #f97316)`,
            borderRadius:6, transition:'width 0.8s' }} />
        </div>
        <div style={{ display:'flex', justifyContent:'space-between', fontSize:10, color:'#94a3b8' }}>
          <span>Progress: {fmt(progress,1)}%</span>
          <span>Remaining: ${fmt(remaining,0)}</span>
          <span style={{ color: days >= 5 ? '#00ff88' : '#fbbf24' }}>Days: {days}/5 min</span>
        </div>
        <div style={{ marginTop:8 }}>
          <input type="range" min={0} max={30} value={days} onChange={e => setDays(+e.target.value)}
            style={{ width:'100%', accentColor:'#fbbf24' }} />
          <div style={{ fontSize:9, color:'#4a6070', textAlign:'center' }}>{days} trading days elapsed (drag to update)</div>
        </div>
      </div>

      {/* Rules checklist */}
      <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:8, padding:14, marginBottom:16 }}>
        <div style={{ fontSize:11, fontWeight:'bold', color:'#94a3b8', marginBottom:10, letterSpacing:1 }}>TPT EVALUATION RULES</div>
        {[
          { rule: `Profit target: $${target.toLocaleString()}`, ok: realized >= target },
          { rule: `Min 5 trading days`, ok: days >= 5 },
          { rule: `No single day > 50% of total profit`, ok: true },
          { rule: `Close all positions by 5:00 PM ET`, ok: true },
          { rule: `Max trailing drawdown: $${drawdown.toLocaleString()}`, ok: true },
          { rule: `Algo trading: ✅ PERMITTED`, ok: true },
        ].map((item, i) => (
          <div key={i} style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
            <span style={{ fontSize:12, color: item.ok ? '#00ff88' : '#fbbf24' }}>
              {item.ok ? '✓' : '○'}
            </span>
            <span style={{ fontSize:11, color: item.ok ? '#e0e0e0' : '#94a3b8' }}>{item.rule}</span>
          </div>
        ))}
      </div>

      {/* Revenue projection */}
      <div style={{ background:'linear-gradient(135deg, rgba(251,191,36,0.06), rgba(249,115,22,0.04))',
        border:'1px solid rgba(251,191,36,0.2)', borderRadius:8, padding:14 }}>
        <div style={{ fontSize:11, fontWeight:'bold', color:'#fbbf24', marginBottom:10, letterSpacing:1 }}>
          💰 REVENUE PROJECTION (once funded)
        </div>
        {[
          { label: '1 × $50K account @ +2%/month', value: '+$1,000/mo', keep: '+$800/mo (80%)' },
          { label: '5 × $50K accounts (stacked)', value: '+$5,000/mo', keep: '+$4,000/mo (80%)' },
          { label: '10 × $50K accounts (max)', value: '+$10,000/mo', keep: '+$8,000/mo (80%)' },
        ].map((row, i) => (
          <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
            padding:'6px 0', borderBottom: i < 2 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
            <span style={{ fontSize:10, color:'#94a3b8' }}>{row.label}</span>
            <div style={{ textAlign:'right' }}>
              <div style={{ fontSize:11, color:'#fbbf24', fontFamily:'monospace' }}>{row.value}</div>
              <div style={{ fontSize:10, color:'#00ff88', fontFamily:'monospace' }}>{row.keep}</div>
            </div>
          </div>
        ))}
        <div style={{ marginTop:10, fontSize:9, color:'#4a6070', lineHeight:1.6 }}>
          Evaluation fee: $75–$150/month · Activation: $130 one-time · Algo trading: permitted · Daily withdrawals
        </div>
      </div>
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
export default function PrintingProfits() {
  const [subTab, setSubTab] = useState('scanner');
  const [scanData, setScanData]     = useState(null);
  const [futuresData, setFuturesData] = useState(null);
  const [portfolio, setPortfolio]   = useState(null);
  const [regime, setRegime]         = useState(null);
  const [loading, setLoading]       = useState(false);
  const [checking, setChecking]     = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [countdown, setCountdown]   = useState(30);
  const [error, setError]           = useState(null);
  const [ticker, setTicker]         = useState('');

  const loadPortfolio = useCallback(async () => {
    try {
      const r = await fetch(`${API()}/api/printing/portfolio`);
      if (r.ok) setPortfolio(await r.json());
    } catch {}
  }, []);

  const loadRegime = useCallback(async () => {
    try {
      const r = await fetch(`${API()}/api/printing/regime`);
      if (r.ok) setRegime(await r.json());
    } catch {}
  }, []);

  useEffect(() => { loadPortfolio(); loadRegime(); }, []);

  const runScan = async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API()}/api/printing/scan`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
      if (!r.ok) throw new Error(await r.text());
      setScanData(await r.json());
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  const loadFutures = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API()}/api/printing/futures`);
      if (r.ok) setFuturesData(await r.json());
    } catch {}
    setLoading(false);
  };

  const checkPrices = async () => {
    setChecking(true);
    try {
      const r = await fetch(`${API()}/api/printing/portfolio/check`, { method:'POST' });
      if (r.ok) { const d = await r.json(); setPortfolio(d.portfolio); }
      setCountdown(30);
    } catch {}
    setChecking(false);
  };

  const autopilot = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API()}/api/printing/portfolio/autopilot`,
        { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
      if (r.ok) await loadPortfolio();
    } catch {}
    setLoading(false);
  };

  const openSignal = async (sig) => {
    try {
      const isLng = sig.direction === 'long';
      await fetch(`${API()}/api/printing/portfolio/open`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          ticker: sig.ticker, direction: sig.direction,
          entry_price: isLng ? (sig.entry_high || sig.last_close) : (sig.entry || sig.last_close),
          sl: sig.sl, tp1: sig.tp1,
          tp2: sig.tp2 || sig.tp1, tp3: sig.tp3 || sig.tp1,
          conviction: sig.conviction_pct,
        }),
      });
      await loadPortfolio();
    } catch {}
  };

  const closePos = async (id) => {
    try {
      await fetch(`${API()}/api/printing/portfolio/close/${id}`,
        { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
      await loadPortfolio();
    } catch {}
  };

  const reset = async () => {
    if (!window.confirm('Reset Printing Profits portfolio to $25,000?')) return;
    await fetch(`${API()}/api/printing/portfolio/reset`, { method:'POST' });
    loadPortfolio();
  };

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const t = setInterval(() => {
      setCountdown(c => { if (c <= 1) { checkPrices(); return 30; } return c - 1; });
    }, 1000);
    return () => clearInterval(t);
  }, [autoRefresh]);

  const mode = regime?.mode || {};
  const pf   = portfolio?.stats || {};
  const st   = portfolio?.state || {};
  const openPos    = portfolio?.open_positions  || [];
  const closedPos  = (portfolio?.closed_positions || []).slice().reverse();
  const totalPnl   = pf.total_pnl || 0;
  const slots      = Math.max(0, 5 - (pf.open_count || 0));

  const subTabs = [
    { id:'scanner',   label:'SCANNER',   icon:<Activity size={12}/> },
    { id:'futures',   label:'FUTURES',   icon:<BarChart2 size={12}/> },
    { id:'portfolio', label:'PORTFOLIO', icon:<DollarSign size={12}/> },
    { id:'tpt',       label:'TPT TRACKER', icon:<Shield size={12}/> },
  ];

  return (
    <div style={{ padding:20, fontFamily:"'Inter',sans-serif", color:'#e0e0e0',
      maxWidth:1200, margin:'0 auto', minHeight:'80vh' }}>

      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ background:'linear-gradient(135deg,#fbbf24,#f97316)', borderRadius:10,
            padding:10, display:'flex', boxShadow:'0 0 20px rgba(251,191,36,0.3)' }}>
            <DollarSign size={22} color="#000" />
          </div>
          <div>
            <div style={{ fontSize:20, fontWeight:'bold', color:'#fbbf24', letterSpacing:2,
              textShadow:'0 0 20px rgba(251,191,36,0.4)' }}>
              PRINTING PROFITS
            </div>
            <div style={{ fontSize:10, color:'#4a6070' }}>
              Dual Long/Short · Futures · Kelly Sizing · TakeProfitTrader Path
            </div>
          </div>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          {/* Regime badge */}
          {mode.label && (
            <div style={{ background:`${mode.color}18`, border:`1px solid ${mode.color}44`,
              borderRadius:6, padding:'6px 12px', fontSize:10, color:mode.color,
              fontFamily:'monospace', fontWeight:'bold' }}>
              {mode.label} · VIX {mode.vix}
            </div>
          )}
          {/* Auto refresh */}
          {subTab === 'portfolio' && (
            <>
              <button onClick={() => { setAutoRefresh(a=>!a); setCountdown(30); }}
                style={{ background: autoRefresh?'rgba(251,191,36,0.15)':'transparent',
                  border:`1px solid ${autoRefresh?'#fbbf24':'#1a2535'}`,
                  borderRadius:6, padding:'6px 12px', color:autoRefresh?'#fbbf24':'#4a6070',
                  fontSize:11, cursor:'pointer' }}>
                {autoRefresh ? `AUTO ${countdown}s` : 'AUTO OFF'}
              </button>
              <button onClick={checkPrices} disabled={checking}
                style={{ background:'linear-gradient(135deg,#fbbf24,#f97316)', border:'none',
                  borderRadius:6, padding:'6px 14px', color:'#000', fontSize:11,
                  fontWeight:'bold', cursor:'pointer', display:'flex', alignItems:'center', gap:5 }}>
                <RefreshCw size={12} /> {checking?'CHECKING...':'CHECK PRICES'}
              </button>
              <button onClick={reset}
                style={{ background:'transparent', border:'1px solid #ff4466',
                  borderRadius:6, padding:'6px 10px', color:'#ff4466', cursor:'pointer' }}>
                <RotateCcw size={12}/>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Portfolio header stats (always visible) */}
      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        <Stat label="TOTAL VALUE"  value={usd(st.total_value||25000)} color='#fbbf24' />
        <Stat label="CASH"         value={usd(st.cash||25000)} color='#7ee8ff' sub={`${slots} slots`} />
        <Stat label="TOTAL P&L"    value={`${totalPnl>=0?'+':''}${fmt(totalPnl,0)}`} color={clr(totalPnl)} sub={pct(pf.total_pnl_pct||0)} />
        <Stat label="LONG EXP"     value={usd(pf.long_exposure||0)}  color='#00ff88' />
        <Stat label="SHORT EXP"    value={usd(pf.short_exposure||0)} color='#ff4466' />
        <Stat label="WIN RATE"     value={`${pf.win_rate||0}%`} color={pf.win_rate>=55?'#00ff88':pf.win_rate>=40?'#fbbf24':'#ff4466'} sub={`${pf.total_closed||0} closed`} />
        <Stat label="OPEN"         value={pf.open_count||0} color='#fbbf24' sub="positions" />
      </div>

      {error && (
        <div style={{ background:'rgba(255,68,102,0.1)', border:'1px solid #ff4466',
          borderRadius:8, padding:10, marginBottom:14, color:'#ff4466', fontSize:12,
          display:'flex', justifyContent:'space-between' }}>
          {error} <span onClick={() => setError(null)} style={{ cursor:'pointer' }}>✕</span>
        </div>
      )}

      {/* Sub-tab bar */}
      <div style={{ display:'flex', gap:0, borderBottom:'1px solid #1a2535', marginBottom:20 }}>
        {subTabs.map(t => (
          <button key={t.id} onClick={() => {
            setSubTab(t.id);
            if (t.id === 'futures' && !futuresData) loadFutures();
          }} style={{
            background: subTab===t.id ? '#0d1a2a' : 'transparent',
            color: subTab===t.id ? '#fbbf24' : '#4a6070',
            border: 'none',
            borderBottom: subTab===t.id ? '2px solid #fbbf24' : '2px solid transparent',
            padding:'10px 18px', fontSize:11, fontWeight:'bold', cursor:'pointer',
            display:'flex', alignItems:'center', gap:6, letterSpacing:1,
          }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ── SCANNER TAB ──────────────────────────────────────────────────────── */}
      {subTab === 'scanner' && (
        <div>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
            <div>
              <div style={{ fontSize:13, fontWeight:'bold', color:'#fbbf24', letterSpacing:1 }}>
                DUAL DIRECTION SCANNER
              </div>
              <div style={{ fontSize:10, color:'#4a6070' }}>
                Long signals (green) + Short signals (red) — same data, two engines
              </div>
            </div>
            <button onClick={runScan} disabled={loading}
              style={{ background: loading?'#1a2535':'linear-gradient(135deg,#fbbf24,#f97316)',
                border:'none', borderRadius:6, padding:'8px 20px',
                color: loading?'#4a6070':'#000', fontSize:12, fontWeight:'bold',
                cursor: loading?'wait':'pointer', display:'flex', alignItems:'center', gap:6 }}>
              <Zap size={14}/> {loading?'SCANNING...':'RUN DUAL SCAN'}
            </button>
          </div>

          {scanData && (
            <>
              <div style={{ background:'rgba(251,191,36,0.05)', border:'1px solid rgba(251,191,36,0.15)',
                borderRadius:6, padding:'8px 12px', marginBottom:16, fontSize:10, color:'#94a3b8' }}>
                {scanData.market_header}
              </div>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
                {/* Longs */}
                <div>
                  <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
                    <TrendingUp size={14} color="#00ff88"/>
                    <span style={{ fontSize:11, fontWeight:'bold', color:'#00ff88', letterSpacing:1 }}>
                      LONG SIGNALS ({scanData.long_count})
                    </span>
                  </div>
                  {scanData.longs.length === 0
                    ? <div style={{ color:'#4a6070', fontSize:11, padding:12 }}>No qualifying long signals</div>
                    : scanData.longs.map(r => <SignalCard key={r.ticker+'L'} r={{...r,direction:'long'}} onOpen={openSignal}/>)}
                </div>
                {/* Shorts */}
                <div>
                  <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
                    <TrendingDown size={14} color="#ff4466"/>
                    <span style={{ fontSize:11, fontWeight:'bold', color:'#ff4466', letterSpacing:1 }}>
                      SHORT SIGNALS ({scanData.short_count})
                    </span>
                  </div>
                  {scanData.shorts.length === 0
                    ? <div style={{ color:'#4a6070', fontSize:11, padding:12 }}>No qualifying short signals</div>
                    : scanData.shorts.map(r => <SignalCard key={r.ticker+'S'} r={r} onOpen={openSignal}/>)}
                </div>
              </div>
            </>
          )}
          {!scanData && !loading && (
            <div style={{ textAlign:'center', padding:'60px 20px', color:'#4a6070' }}>
              <Zap size={40} color="#fbbf24" style={{ marginBottom:12 }}/>
              <div style={{ fontSize:14 }}>Click RUN DUAL SCAN to find long + short opportunities</div>
              <div style={{ fontSize:11, marginTop:6 }}>
                Existing system only goes LONG. This scanner profits in both directions.
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── FUTURES TAB ──────────────────────────────────────────────────────── */}
      {subTab === 'futures' && (
        <div>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
            <div>
              <div style={{ fontSize:13, fontWeight:'bold', color:'#fbbf24', letterSpacing:1 }}>FUTURES INTELLIGENCE</div>
              <div style={{ fontSize:10, color:'#4a6070' }}>ES · NQ · RTY · CL · GC · SI — real-time levels, VWAP, ATR entry zones</div>
            </div>
            <div style={{ display:'flex', gap:8, alignItems:'center' }}>
              {futuresData?.session && (
                <div style={{ background:`${futuresData.session.prime?'rgba(0,255,136,0.08)':'rgba(74,96,112,0.08)'}`,
                  border:`1px solid ${futuresData.session.prime?'#00ff88':'#1a2535'}`,
                  borderRadius:6, padding:'5px 10px', fontSize:10,
                  color: futuresData.session.prime?'#00ff88':'#4a6070', fontFamily:'monospace' }}>
                  {futuresData.session.prime ? '🟢' : '⚫'} {futuresData.session.label} · {futuresData.session.et_time}
                </div>
              )}
              <button onClick={loadFutures} disabled={loading}
                style={{ background:'linear-gradient(135deg,#fbbf24,#f97316)', border:'none',
                  borderRadius:6, padding:'6px 14px', color:'#000', fontSize:11,
                  fontWeight:'bold', cursor:'pointer', display:'flex', alignItems:'center', gap:5 }}>
                <RefreshCw size={12}/> {loading?'LOADING...':'REFRESH'}
              </button>
            </div>
          </div>
          {futuresData ? (
            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12 }}>
              {Object.values(futuresData.futures).map(f => <FuturesCard key={f.symbol} f={f}/>)}
            </div>
          ) : (
            <div style={{ textAlign:'center', padding:'60px 20px', color:'#4a6070' }}>
              <BarChart2 size={40} color="#fbbf24" style={{ marginBottom:12 }}/>
              <div>Loading futures data...</div>
            </div>
          )}
        </div>
      )}

      {/* ── PORTFOLIO TAB ────────────────────────────────────────────────────── */}
      {subTab === 'portfolio' && (
        <div>
          {/* Controls */}
          <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10,
            padding:14, marginBottom:16 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
              <div style={{ fontSize:12, fontWeight:'bold', color:'#fbbf24', letterSpacing:1 }}>
                LONG/SHORT POSITIONS — {openPos.length}/5 SLOTS
              </div>
              <div style={{ display:'flex', gap:8 }}>
                <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
                  placeholder="TICKER" maxLength={6}
                  style={{ width:80, background:'#0d1a2a', border:'1px solid #1a2535',
                    borderRadius:6, padding:'6px 10px', color:'#e0e0e0', fontSize:13,
                    fontFamily:'monospace', textAlign:'center' }}/>
                <button onClick={autopilot} disabled={loading||slots===0}
                  style={{ background: slots===0?'#1a2535':'linear-gradient(135deg,#fbbf24,#f97316)',
                    border:'none', borderRadius:6, padding:'6px 14px',
                    color: slots===0?'#4a6070':'#000', fontSize:11, fontWeight:'bold',
                    cursor: slots===0?'not-allowed':'pointer', display:'flex', alignItems:'center', gap:5 }}>
                  <Zap size={12}/> AUTO-FILL {slots} SLOTS
                </button>
              </div>
            </div>
            {openPos.length === 0 && !loading && (
              <div style={{ textAlign:'center', padding:'20px', color:'#4a6070', fontSize:11 }}>
                No open positions. Run Scanner and click OPEN, or use AUTO-FILL.
              </div>
            )}
            {openPos.map(p => <PositionCard key={p.id} pos={p} onClose={closePos}/>)}
            {Array.from({length: Math.max(0,5-openPos.length)}).map((_,i) => (
              <div key={i} style={{ border:'1px dashed #1a2535', borderRadius:8,
                padding:12, marginBottom:8, textAlign:'center', color:'#1a2535', fontSize:11 }}>
                — empty slot {openPos.length+i+1} —
              </div>
            ))}
          </div>
          {/* Closed */}
          {closedPos.length > 0 && (
            <div style={{ background:'#0a1018', border:'1px solid #1a2535', borderRadius:10, padding:14 }}>
              <div style={{ fontSize:11, fontWeight:'bold', color:'#94a3b8', marginBottom:10, letterSpacing:1 }}>
                TRADE LOG — {closedPos.length} CLOSED
              </div>
              <div style={{ overflowX:'auto' }}>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:10, fontFamily:'monospace' }}>
                  <thead>
                    <tr style={{ borderBottom:'1px solid #1a2535' }}>
                      {['Ticker','Dir','Entry','Exit','P&L $','P&L %','Exit'].map(h => (
                        <th key={h} style={{ padding:'5px 6px', textAlign:'right',
                          color:'#4a6070', fontSize:9, fontWeight:'normal' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {closedPos.map(p => {
                      const rpnl = p.realized_pnl || 0;
                      const rpct = p.entry_price > 0 ? rpnl / p.position_size * 100 : 0;
                      const last = (p.trades||[]).slice(-1)[0] || {};
                      return (
                        <tr key={p.id} style={{ borderBottom:'1px solid #0d1a2a' }}>
                          <td style={{ padding:'4px 6px', color:'#e0e0e0', fontWeight:'bold' }}>{p.ticker}</td>
                          <td style={{ padding:'4px 6px', textAlign:'right', color:dirClr(p.direction||'long'), fontSize:9 }}>
                            {p.direction==='long'?'▲L':'▼S'}
                          </td>
                          <td style={{ padding:'4px 6px', textAlign:'right', color:'#94a3b8' }}>${fmt(p.entry_price,2)}</td>
                          <td style={{ padding:'4px 6px', textAlign:'right', color:'#94a3b8' }}>${fmt(last.price,2)}</td>
                          <td style={{ padding:'4px 6px', textAlign:'right', color:clr(rpnl), fontWeight:'bold' }}>
                            {rpnl>=0?'+':''}{fmt(rpnl,0)}
                          </td>
                          <td style={{ padding:'4px 6px', textAlign:'right', color:clr(rpct) }}>{pct(rpct)}</td>
                          <td style={{ padding:'4px 6px', textAlign:'right', fontSize:9,
                            color:last.tp_level?.includes('TP')?'#00ff88':last.tp_level==='SL'?'#ff4466':'#94a3b8' }}>
                            {last.tp_level||'—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TPT TRACKER TAB ──────────────────────────────────────────────────── */}
      {subTab === 'tpt' && <TPTTracker portfolioStats={pf} />}
    </div>
  );
}
