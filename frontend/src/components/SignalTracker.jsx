import React, { useState, useEffect } from 'react';
import { Activity, RefreshCw, X, TrendingUp, TrendingDown, Target, AlertTriangle, Clock, BarChart3 } from 'lucide-react';

const pnlColor = v => v > 0 ? "#00ff88" : v < 0 ? "#ff4466" : "#94a3b8";
const statusColor = s => {
  if (s === "OPEN") return "#00d4ff";
  if (s === "TP3_HIT" || s === "TP2_HIT" || s === "TP1_HIT") return "#00ff88";
  if (s === "STOPPED_OUT") return "#ff4466";
  return "#fbbf24";
};
const statusLabel = s => {
  if (s === "OPEN") return "OPEN";
  if (s === "TP3_HIT") return "TP3 ✓";
  if (s === "TP2_HIT") return "TP2 ✓";
  if (s === "TP1_HIT") return "TP1 ✓";
  if (s === "STOPPED_OUT") return "STOPPED";
  if (s === "TIMEOUT") return "TIMEOUT";
  if (s === "MANUAL_CLOSE") return "CLOSED";
  return s;
};
const sessionColor = s => {
  if (s === "regular") return "#00ff88";
  if (s === "premarket") return "#fbbf24";
  if (s === "afterhours") return "#f97316";
  return "#ff4466";
};

// Format duration between two ISO timestamps (or from start to now)
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

const SignalTracker = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState('active');
  const [turboTicker, setTurboTicker] = useState('');
  const [turboLoading, setTurboLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [countdown, setCountdown] = useState(30);
  const [autopilotLoading, setAutopilotLoading] = useState(false);
  const [autopilotResult, setAutopilotResult] = useState(null);
  const [cryptoLoading, setCryptoLoading] = useState(false);
  const [expandedSignal, setExpandedSignal] = useState(null);
  const [now, setNow] = useState(new Date());
  const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

  // Tick every minute so durations on open signals stay live
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(t);
  }, []);

  const fetchSignals = async (refresh = false) => {
    if (refresh) setRefreshing(true); else setLoading(true);
    try {
      const endpoint = refresh ? '/api/signals/check' : '/api/signals';
      const method = refresh ? 'POST' : 'GET';
      const res = await fetch(`${apiUrl}${endpoint}`, { method });
      const json = await res.json();
      setData(json);
      if (refresh && autoRefresh) setCountdown(30);
    } catch (e) { console.error(e); }
    setLoading(false); setRefreshing(false);
  };

  const closeSignal = async (id) => { await fetch(`${apiUrl}/api/signals/close/${id}`, { method: 'POST' }); fetchSignals(); };
  const clearAll = async () => { if (!confirm('Clear ALL signals?')) return; await fetch(`${apiUrl}/api/signals/clear`, { method: 'POST' }); fetchSignals(); };

  const launchTurbo = async () => {
    if (!turboTicker.trim()) return;
    setTurboLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/signals/turbo/${turboTicker.trim().toUpperCase()}`, { method: 'POST' });
      if (!res.ok) { const e = await res.json(); alert(e.detail || 'Error'); }
      else { setTurboTicker(''); fetchSignals(true); }
    } catch (e) { alert(e.message); }
    setTurboLoading(false);
  };

  const runAutopilot = async () => {
    setAutopilotLoading(true); setAutopilotResult(null);
    try {
      const res = await fetch(`${apiUrl}/api/autopilot`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json(); setAutopilotResult(d); setAutoRefresh(true); fetchSignals(true);
    } catch (e) { alert('Autopilot error: ' + e.message); }
    setAutopilotLoading(false);
  };

  const runCryptoAutopilot = async () => {
    setCryptoLoading(true); setAutopilotResult(null);
    try {
      const res = await fetch(`${apiUrl}/api/autopilot/crypto`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json(); setAutopilotResult(d); setAutoRefresh(true); fetchSignals(true);
    } catch (e) { alert('Crypto autopilot error: ' + e.message); }
    setCryptoLoading(false);
  };

  useEffect(() => {
    if (!autoRefresh) return;
    setCountdown(30);
    const priceInterval = setInterval(() => fetchSignals(true), 30000);
    const tickInterval  = setInterval(() => setCountdown(c => c <= 1 ? 30 : c - 1), 1000);
    return () => { clearInterval(priceInterval); clearInterval(tickInterval); };
  }, [autoRefresh]);

  useEffect(() => {
    if (data?.active?.length > 0 && !autoRefresh) setAutoRefresh(true);
  }, [data?.active?.length]);

  useEffect(() => { fetchSignals(); }, []);

  const stats    = data?.stats || {};
  const active   = data?.active || [];
  const closed   = data?.closed || [];
  const mktStatus = data?.market_status || {};
  const warnings  = data?.warnings || [];
  const display   = tab === 'active' ? active : closed;

  return (
    <div style={{ background:"#050810", padding:"20px 16px", fontFamily:"'Courier New',monospace", color:"#c9d8e8" }}>
      {/* Header + Market Status */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", borderBottom:"1px solid #1a2535", paddingBottom:14, marginBottom:16 }}>
        <div>
          <span style={{ fontWeight:"bold", fontSize:22 }}>Signal<span style={{ color:"#c084fc" }}>Tracker</span></span>
          <span style={{ color:"#c084fc", fontSize:11, fontWeight:"bold", background:"rgba(192,132,252,0.15)", border:"1px solid rgba(192,132,252,0.3)", padding:"1px 7px", borderRadius:3, marginLeft:10 }}>v2.0</span>
          <div style={{ color:"#2a4a5a", fontSize:10, marginTop:2, fontFamily:"sans-serif" }}>FULL AUDIT TRAIL · GAP DETECTION · ATR TARGETS · MAE/MFE</div>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          {mktStatus.session && (
            <div style={{ background:`${sessionColor(mktStatus.session)}10`, border:`1px solid ${sessionColor(mktStatus.session)}33`, borderRadius:6, padding:"4px 10px", display:"flex", alignItems:"center", gap:5 }}>
              <div style={{ width:6, height:6, borderRadius:3, background:sessionColor(mktStatus.session), animation:mktStatus.market_open?"pulse 2s infinite":"none" }} />
              <span style={{ fontSize:10, fontWeight:"bold", color:sessionColor(mktStatus.session), fontFamily:"sans-serif", textTransform:"uppercase" }}>{mktStatus.session || "?"}</span>
              {mktStatus.et_time && <span style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif" }}>{mktStatus.et_time}</span>}
            </div>
          )}
          <button onClick={() => fetchSignals(true)} disabled={refreshing}
            style={{ background:"#0d1520", border:"1px solid #1a2535", borderRadius:4, padding:"6px 12px", color:"#c084fc", fontSize:10, fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:4 }}>
            <RefreshCw size={12} className={refreshing?"spin":""} /> {refreshing ? "CHECKING..." : "CHECK PRICES"}
          </button>
          <button onClick={clearAll} style={{ background:"#0d1520", border:"1px solid #ff446633", borderRadius:4, padding:"6px 12px", color:"#ff4466", fontSize:10, fontFamily:"sans-serif", cursor:"pointer" }}>RESET ALL</button>
        </div>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div style={{ background:"rgba(251,191,36,0.08)", border:"1px solid #fbbf2433", borderRadius:8, padding:"8px 12px", marginBottom:12, display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
          <AlertTriangle size={14} color="#fbbf24" />
          {warnings.map((w,i) => <span key={i} style={{ fontSize:10, color:"#fbbf24", fontFamily:"sans-serif" }}>{w.ticker}: {w.warning}</span>)}
        </div>
      )}

      {/* Turbo + Auto Refresh */}
      <div style={{ display:"flex", gap:12, marginBottom:16, alignItems:"center", flexWrap:"wrap" }}>
        <div style={{ display:"flex", gap:6, alignItems:"center", background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:"8px 12px", flex:1, minWidth:250 }}>
          <span style={{ fontSize:10, color:"#c084fc", fontWeight:"bold", fontFamily:"sans-serif", whiteSpace:"nowrap" }}>⚡ TURBO</span>
          <input value={turboTicker} onChange={e => setTurboTicker(e.target.value.toUpperCase())} placeholder="AAPL" onKeyDown={e => e.key === 'Enter' && launchTurbo()}
            style={{ flex:1, background:"#0d1a2a", border:"1px solid #1a2535", borderRadius:4, padding:"6px 10px", color:"#e0e0e0", fontSize:13, fontFamily:"monospace", minWidth:60 }} />
          <button onClick={launchTurbo} disabled={turboLoading || !turboTicker.trim()}
            style={{ background:turboLoading?"#1a2535":"linear-gradient(135deg,#c084fc,#7c3aed)", border:"none", borderRadius:4, padding:"6px 14px", color:"#fff", fontSize:11, fontWeight:"bold", fontFamily:"sans-serif", cursor:turboLoading?"wait":"pointer", whiteSpace:"nowrap" }}>
            {turboLoading ? "..." : "🚀 LAUNCH"}
          </button>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:8, background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:"8px 12px" }}>
          <span style={{ fontSize:10, color:"#8899aa", fontFamily:"sans-serif" }}>AUTO-REFRESH</span>
          <button onClick={() => setAutoRefresh(!autoRefresh)}
            style={{ width:40, height:22, borderRadius:11, border:"none", background:autoRefresh?"#00ff88":"#1a2535", cursor:"pointer", position:"relative", transition:"background 0.2s" }}>
            <div style={{ width:18, height:18, borderRadius:9, background:"#fff", position:"absolute", top:2, left:autoRefresh?20:2, transition:"left 0.2s" }} />
          </button>
          {autoRefresh && <span style={{ fontSize:11, color:"#00ff88", fontFamily:"monospace", fontWeight:"bold", minWidth:30 }}>{countdown}s</span>}
        </div>
      </div>

      {/* Auto-Pilot */}
      <div style={{ background:"linear-gradient(135deg, rgba(0,212,255,0.06), rgba(124,58,237,0.06))", border:"1px solid #7c3aed44", borderRadius:10, padding:16, marginBottom:16 }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", flexWrap:"wrap", gap:10 }}>
          <div>
            <div style={{ fontSize:14, fontWeight:"bold", color:"#e0e0e0", fontFamily:"sans-serif" }}>🤖 AUTO-PILOT</div>
            <div style={{ fontSize:10, color:"#8899aa", fontFamily:"sans-serif", marginTop:2 }}>Scan → Rank → Launch ATR-based turbo signals with full audit trail</div>
          </div>
          <div style={{ display:"flex", gap:10, flexWrap:"wrap" }}>
            <button onClick={runAutopilot} disabled={autopilotLoading}
              style={{ background:autopilotLoading?"#1a2535":"linear-gradient(135deg, #00d4ff, #7c3aed)", border:"none", borderRadius:8, padding:"12px 28px", color:"#fff", fontSize:14, fontWeight:"bold", fontFamily:"sans-serif", cursor:autopilotLoading?"wait":"pointer", letterSpacing:1, boxShadow:autopilotLoading?"none":"0 0 20px rgba(124,58,237,0.3)" }}>
              {autopilotLoading ? "⏳ SCANNING..." : "🚀 STOCKS (30)"}
            </button>
            <button onClick={runCryptoAutopilot} disabled={cryptoLoading}
              style={{ background:cryptoLoading?"#1a2535":"linear-gradient(135deg, #f7931a, #e2761b)", border:"none", borderRadius:8, padding:"12px 28px", color:"#fff", fontSize:14, fontWeight:"bold", fontFamily:"sans-serif", cursor:cryptoLoading?"wait":"pointer", letterSpacing:1, boxShadow:cryptoLoading?"none":"0 0 20px rgba(247,147,26,0.3)" }}>
              {cryptoLoading ? "⏳ SCANNING..." : "₿ CRYPTO (15)"}
            </button>
          </div>
        </div>
        {autopilotResult && (
          <div style={{ marginTop:14, background:"#0a0f18", borderRadius:8, padding:12 }}>
            <div style={{ display:"flex", gap:16, flexWrap:"wrap", marginBottom:10 }}>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif" }}>Scanned: <b style={{color:"#e0e0e0"}}>{autopilotResult.scanned}</b></span>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif" }}>Passed: <b style={{color:"#00ff88"}}>{autopilotResult.passed_filter}</b></span>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif" }}>Launched: <b style={{color:"#c084fc"}}>{autopilotResult.launched?.length || 0}</b></span>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif" }}>Regime: <b style={{color:"#fbbf24"}}>{autopilotResult.market_regime}</b></span>
            </div>
            {autopilotResult.launched?.length > 0 && (
              <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
                {autopilotResult.launched.map(l => (
                  <div key={l.ticker} style={{ background:"rgba(0,255,136,0.08)", border:"1px solid #00ff8833", borderRadius:6, padding:"6px 10px", textAlign:"center" }}>
                    <div style={{ fontSize:12, fontWeight:"bold", color:"#00ff88" }}>{l.ticker}</div>
                    <div style={{ fontSize:9, color:"#8899aa" }}>{l.conviction}% · ${l.entry} · {l.target_method || "atr"}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stats Cards */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8, marginBottom:12 }}>
        {[
          { label:"ACTIVE", val:active.length, color:"#00d4ff" },
          { label:"WIN RATE", val:`${stats.win_rate||0}%`, color:(stats.win_rate||0)>=50?"#00ff88":"#ff4466" },
          { label:"AVG P&L", val:`${stats.avg_pnl||0}%`, color:pnlColor(stats.avg_pnl||0) },
          { label:"PROFIT FACTOR", val:stats.profit_factor||0, color:(stats.profit_factor||0)>=1.5?"#00ff88":(stats.profit_factor||0)>=1?"#fbbf24":"#ff4466" },
        ].map(c => (
          <div key={c.label} style={{ background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:"10px", textAlign:"center" }}>
            <div style={{ fontSize:8, color:"#2a4a5a", letterSpacing:1.5, fontFamily:"sans-serif", marginBottom:4 }}>{c.label}</div>
            <div style={{ fontSize:18, fontWeight:"bold", color:c.color }}>{c.val}</div>
          </div>
        ))}
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(6,1fr)", gap:8, marginBottom:20 }}>
        {[
          { label:"WINS", val:stats.wins||0, color:"#00ff88" },
          { label:"LOSSES", val:stats.losses||0, color:"#ff4466" },
          { label:"TP1 HIT%", val:`${stats.tp1_hit_rate||0}%`, color:"#fbbf24" },
          { label:"AVG MAE", val:`${stats.avg_mae||0}%`, color:"#ff4466", sub:"max drawdown" },
          { label:"AVG MFE", val:`${stats.avg_mfe||0}%`, color:"#00ff88", sub:"max runup" },
          { label:"GAP TRADES", val:stats.gap_affected_trades||0, color:"#f97316", sub:`slip: ${stats.total_gap_slippage||0}%` },
        ].map(c => (
          <div key={c.label} style={{ background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:"10px", textAlign:"center" }}>
            <div style={{ fontSize:8, color:"#2a4a5a", letterSpacing:1.5, fontFamily:"sans-serif", marginBottom:4 }}>{c.label}</div>
            <div style={{ fontSize:16, fontWeight:"bold", color:c.color }}>{c.val}</div>
            {c.sub && <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif", marginTop:2 }}>{c.sub}</div>}
          </div>
        ))}
      </div>

      {/* Conviction Accuracy */}
      {(stats.avg_conviction_winners > 0 || stats.avg_conviction_losers > 0) && (
        <div style={{ display:"flex", gap:12, marginBottom:16 }}>
          <div style={{ flex:1, background:"rgba(0,255,136,0.05)", border:"1px solid #00ff8822", borderRadius:8, padding:"8px 12px", textAlign:"center" }}>
            <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>AVG CONVICTION (WINNERS)</div>
            <div style={{ fontSize:16, fontWeight:"bold", color:"#00ff88" }}>{stats.avg_conviction_winners||0}%</div>
          </div>
          <div style={{ flex:1, background:"rgba(255,68,102,0.05)", border:"1px solid #ff446622", borderRadius:8, padding:"8px 12px", textAlign:"center" }}>
            <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>AVG CONVICTION (LOSERS)</div>
            <div style={{ fontSize:16, fontWeight:"bold", color:"#ff4466" }}>{stats.avg_conviction_losers||0}%</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display:"flex", gap:0, marginBottom:14, borderBottom:"1px solid #1a2535" }}>
        {['active','closed'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ background:tab===t?"#0d1a2a":"transparent", color:tab===t?"#c084fc":"#8899aa", border:"none", borderBottom:tab===t?"2px solid #c084fc":"2px solid transparent", padding:"8px 20px", fontSize:11, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", textTransform:"uppercase" }}>
            {t} ({t==='active'?active.length:closed.length})
          </button>
        ))}
      </div>

      {display.length === 0 && (
        <div style={{ textAlign:"center", padding:"40px", color:"#2a4a5a", fontFamily:"sans-serif" }}>
          <Target size={32} style={{ marginBottom:10, opacity:0.3 }} />
          <div style={{ fontSize:14 }}>{tab === 'active' ? 'No active signals' : 'No closed signals yet'}</div>
          <div style={{ fontSize:11, marginTop:6, color:"#1a2535" }}>Run a scan or use Auto-Pilot to generate signals</div>
        </div>
      )}

      {/* Signal Cards */}
      {display.length > 0 && (
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {display.map(s => {
            const isExpanded = expandedSignal === s.id;
            const isStale    = s.price_stale_at_entry;
            const method     = s.target_method || (s.atr_at_entry > 0 ? "atr" : "pct");
            // Duration: open trades count from entry_time to now; closed from entry_time to close_time
            const closeTs    = s.close_time || s.closed_at || null;
            const isOpen     = s.status === "OPEN";
            const duration   = formatDuration(s.entry_time, isOpen ? null : closeTs);
            return (
              <div key={s.id} style={{ background:"#0a0f18", border:`1px solid ${isExpanded?"#c084fc33":"#1a2535"}`, borderRadius:10, overflow:"hidden" }}>
                {/* Main Row */}
                <div onClick={() => setExpandedSignal(isExpanded ? null : s.id)}
                  style={{ display:"grid", gridTemplateColumns:"120px 80px 1fr 100px 90px 60px", gap:8, padding:"12px 14px", alignItems:"center", cursor:"pointer" }}>

                  {/* Ticker + Date */}
                  <div>
                    <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                      <span style={{ color:s.asset_type==="crypto"?"#f7931a":"#00d4ff", fontWeight:"bold", fontSize:15 }}>{s.ticker}</span>
                      {s.turbo && <span style={{ fontSize:8, background:"rgba(192,132,252,0.15)", color:"#c084fc", padding:"1px 5px", borderRadius:3, fontFamily:"sans-serif" }}>TURBO</span>}
                      {method === "atr" && <span style={{ fontSize:8, background:"rgba(0,255,136,0.1)", color:"#00ff88", padding:"1px 5px", borderRadius:3, fontFamily:"sans-serif" }}>ATR</span>}
                    </div>
                    <div style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif", marginTop:2 }}>{s.entry_time?.slice(0,10)} · {s.entry_session || ""}</div>
                  </div>

                  {/* Conviction */}
                  <div style={{ textAlign:"center" }}>
                    <div style={{ fontSize:16, fontWeight:"bold", color:s.conviction>=70?"#00ff88":s.conviction>=60?"#fbbf24":s.conviction>0?"#94a3b8":"#2a4a5a" }}>{s.conviction||"—"}%</div>
                    <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>{s.tas}</div>
                  </div>

                  {/* Entry → Current | SL TP1 */}
                  <div style={{ display:"flex", gap:12, alignItems:"center", flexWrap:"wrap" }}>
                    <span style={{ fontSize:11, color:"#94a3b8" }}>${s.entry_price}</span>
                    <span style={{ color:"#2a4a5a" }}>→</span>
                    <span style={{ fontSize:13, fontWeight:"bold", color:pnlColor(s.pnl_pct) }}>${s.current_price || s.close_price}</span>
                    <span style={{ fontSize:9, color:"#ff4466", fontFamily:"sans-serif" }}>SL ${s.sl}</span>
                    <span style={{ fontSize:9, color:s.tp1_hit?"#00ff88":"#8899aa", fontWeight:s.tp1_hit?"bold":"normal", fontFamily:"sans-serif" }}>TP1 ${s.tp1}{s.tp1_hit?" ✓":""}</span>
                  </div>

                  {/* P&L */}
                  <div style={{ textAlign:"right" }}>
                    <div style={{ display:"flex", alignItems:"center", justifyContent:"flex-end", gap:4 }}>
                      {s.pnl_pct > 0 ? <TrendingUp size={14} color="#00ff88" /> : s.pnl_pct < 0 ? <TrendingDown size={14} color="#ff4466" /> : null}
                      <span style={{ color:pnlColor(s.pnl_pct), fontWeight:"bold", fontSize:16 }}>{s.pnl_pct > 0 ? "+" : ""}{s.pnl_pct}%</span>
                    </div>
                    {(s.mae_pct !== 0 || s.mfe_pct !== 0) && (
                      <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif", marginTop:2 }}>
                        MAE {s.mae_pct}% · MFE +{s.mfe_pct}%
                      </div>
                    )}
                  </div>

                  {/* Status + Duration + Close Reason */}
                  <div style={{ textAlign:"center" }}>
                    <span style={{ fontSize:10, fontWeight:"bold", padding:"3px 8px", borderRadius:3, fontFamily:"sans-serif",
                      background:`${statusColor(s.status)}15`, color:statusColor(s.status), border:`1px solid ${statusColor(s.status)}33` }}>
                      {statusLabel(s.status)}
                    </span>
                    {/* Duration */}
                    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:3, marginTop:4 }}>
                      <Clock size={9} color="#2a4a5a" />
                      <span style={{ fontSize:9, color: isOpen ? "#00d4ff" : "#8899aa", fontFamily:"sans-serif", fontWeight: isOpen ? "bold" : "normal" }}>
                        {duration}
                      </span>
                    </div>
                    {/* Close reason — visible inline for closed signals */}
                    {!isOpen && s.close_reason && (
                      <div style={{ fontSize:8, color:"#8899aa", fontFamily:"sans-serif", marginTop:2,
                        maxWidth:88, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
                        margin:"2px auto 0" }} title={s.close_reason}>
                        {s.close_reason}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div style={{ textAlign:"right" }}>
                    {tab === 'active' && (
                      <button onClick={(e) => { e.stopPropagation(); closeSignal(s.id); }}
                        style={{ background:"transparent", border:"1px solid #ff446633", borderRadius:3, padding:"3px 6px", color:"#ff4466", fontSize:9, cursor:"pointer", fontFamily:"sans-serif" }}>
                        <X size={10} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded Detail Panel */}
                {isExpanded && (
                  <div style={{ background:"#080c14", borderTop:"1px solid #1a2535", padding:"14px" }}>
                    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:16 }}>

                      {/* Entry Context */}
                      <div>
                        <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:8, letterSpacing:1 }}>ENTRY CONTEXT</div>
                        {s.entry_market_context && (
                          <div style={{ fontSize:10, color:"#94a3b8", fontFamily:"sans-serif", lineHeight:1.8 }}>
                            <div>VIX: <b>{s.entry_market_context.vix}</b> · SPY: <b>${s.entry_market_context.spy_close}</b> ({s.entry_market_context.spy_change_pct}%)</div>
                            <div>Regime: <b style={{ color:"#fbbf24" }}>{s.entry_market_context.regime}</b></div>
                            <div>Session: <b style={{ color:sessionColor(s.entry_session) }}>{s.entry_session}</b></div>
                          </div>
                        )}
                        {/* Time open — shown prominently in expanded view */}
                        <div style={{ marginTop:8, background:"#0d1520", borderRadius:4, padding:"6px 10px", display:"inline-flex", alignItems:"center", gap:5 }}>
                          <Clock size={10} color="#8899aa" />
                          <span style={{ fontSize:10, color: isOpen ? "#00d4ff" : "#8899aa", fontFamily:"sans-serif" }}>
                            {isOpen ? `Open for ${duration}` : `Held for ${duration}`}
                          </span>
                        </div>
                        {s.pillar_scores && Object.keys(s.pillar_scores).length > 0 && (
                          <div style={{ marginTop:8, display:"flex", gap:4 }}>
                            {Object.entries(s.pillar_scores).map(([k,v]) => (
                              <div key={k} style={{ background:"#0d1520", borderRadius:4, padding:"4px 8px", textAlign:"center" }}>
                                <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>{k.toUpperCase()}</div>
                                <div style={{ fontSize:12, fontWeight:"bold", color:v>=70?"#00ff88":v>=50?"#fbbf24":"#ff4466" }}>{v}</div>
                              </div>
                            ))}
                          </div>
                        )}
                        {isStale && <div style={{ fontSize:9, color:"#fbbf24", fontFamily:"sans-serif", marginTop:6 }}>⚠ Price may have been stale at entry</div>}
                      </div>

                      {/* Targets + Performance */}
                      <div>
                        <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:8, letterSpacing:1 }}>TARGETS ({method.toUpperCase()})</div>
                        <div style={{ fontSize:10, color:"#94a3b8", fontFamily:"sans-serif", lineHeight:1.8 }}>
                          <div>SL: <b style={{color:"#ff4466"}}>${s.sl}</b> · TP1: <b style={{color:s.tp1_hit?"#00ff88":"#94a3b8"}}>${s.tp1}</b>{s.tp1_hit?" ✓":""}</div>
                          <div>TP2: <b style={{color:s.tp2_hit?"#00ff88":"#94a3b8"}}>${s.tp2}</b>{s.tp2_hit?" ✓":""} · TP3: <b style={{color:s.tp3_hit?"#00ff88":"#94a3b8"}}>${s.tp3}</b>{s.tp3_hit?" ✓":""}</div>
                          <div>R:R: <b>{s.rr}</b>:1{s.atr_at_entry ? ` · ATR: $${s.atr_at_entry}` : ""}</div>
                        </div>
                        <div style={{ marginTop:8, fontSize:10, color:"#94a3b8", fontFamily:"sans-serif", lineHeight:1.8 }}>
                          <div>High: <b style={{color:"#00ff88"}}>${s.highest_price}</b> · Low: <b style={{color:"#ff4466"}}>${s.lowest_price}</b></div>
                          <div>MAE: <b style={{color:"#ff4466"}}>{s.mae_pct}%</b> · MFE: <b style={{color:"#00ff88"}}>+{s.mfe_pct}%</b></div>
                          {s.slippage_pct > 0 && <div>Gap Slippage: <b style={{color:"#f97316"}}>{s.slippage_pct}%</b></div>}
                        </div>
                      </div>

                      {/* Exit / Snapshot */}
                      <div>
                        {s.close_reason && (
                          <>
                            <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:8, letterSpacing:1 }}>EXIT</div>
                            <div style={{ fontSize:10, color:"#94a3b8", fontFamily:"sans-serif", lineHeight:1.8 }}>
                              {/* Full close reason on its own line */}
                              <div style={{ color:s.pnl_pct >= 0 ? "#00ff88" : "#ff4466", fontWeight:"bold", marginBottom:4 }}>{s.close_reason}</div>
                              <div>Close Price: <b>${s.close_price}</b></div>
                              {s.close_market_context && <div>Exit Regime: <b style={{color:"#fbbf24"}}>{s.close_market_context.regime}</b> · VIX: <b>{s.close_market_context.vix}</b></div>}
                              {s.gap_info && <div style={{ color:"#f97316" }}>⚠ Gap: {s.gap_info.note}</div>}
                            </div>
                          </>
                        )}
                        {s.entry_snapshot && Object.keys(s.entry_snapshot).length > 0 && !s.entry_snapshot.error && (
                          <>
                            <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:6, marginTop:s.close_reason?10:0, letterSpacing:1 }}>INDICATORS AT ENTRY</div>
                            <div style={{ fontSize:9, color:"#8899aa", fontFamily:"monospace", lineHeight:1.6, maxHeight:80, overflow:"auto" }}>
                              {Object.entries(s.entry_snapshot).filter(([k]) => !['price_data','error'].includes(k)).map(([k,v]) => (
                                <div key={k}>{k}: {typeof v === 'object' ? JSON.stringify(v) : String(v)}</div>
                              ))}
                            </div>
                          </>
                        )}
                      </div>
                    </div>

                    {s.ta_note && (
                      <div style={{ marginTop:10, fontSize:9, color:"#8899aa", fontFamily:"sans-serif", background:"#0d1520", borderRadius:4, padding:"6px 10px" }}>
                        📝 {s.ta_note}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default SignalTracker;
