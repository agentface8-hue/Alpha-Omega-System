import React, { useState, useEffect } from 'react';
import { Activity, RefreshCw, X, TrendingUp, TrendingDown, Target, AlertTriangle, Clock, BarChart3, Shield, Zap } from 'lucide-react';

const pnlColor   = v => v > 0 ? "#00ff88" : v < 0 ? "#ff4466" : "#94a3b8";
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
  if (s === "MOMENTUM_FADE") return "FADE ✓";
  return s;
};
const sessionColor = s => {
  if (s === "regular")    return "#00ff88";
  if (s === "premarket")  return "#fbbf24";
  if (s === "afterhours") return "#f97316";
  return "#ff4466";
};
const actionColor = cat => {
  if (cat === "profit") return "#00ff88";
  if (cat === "risk")   return "#ff4466";
  return "#00d4ff";
};
const PILLAR_LABELS = {
  trend: "P1 Trend", volume: "P2 Volume",
  supportresistance: "P3 S/R", sr: "P3 S/R",
  multitf: "P4 Multi-TF", riskreward: "P5 R/R", rr: "P5 R/R",
};
const pillarLabel = k => PILLAR_LABELS[k.toLowerCase().replace(/[^a-z]/g,"")] || k.toUpperCase();
const convictionLevel = c => {
  if (c >= 75) return { label:"HOT",  color:"#ff4466" };
  if (c >= 60) return { label:"WARM", color:"#fbbf24" };
  return          { label:"COOL", color:"#00d4ff"  };
};

// ── Trade State Badge (Phase 1 — observe only) ───────────────────────────────
const STATE_CFG = {
  RUNNING:    { color:"#00ff88", bg:"rgba(0,255,136,0.12)",  label:"RUNNING",    pulse:true  },
  DEVELOPING: { color:"#00d4ff", bg:"rgba(0,212,255,0.12)",  label:"DEVELOP",    pulse:false },
  PROTECTING: { color:"#fbbf24", bg:"rgba(251,191,36,0.12)", label:"PROTECT",    pulse:false },
  EXIT:       { color:"#ff4466", bg:"rgba(255,68,102,0.12)", label:"EXIT",       pulse:true  },
};
const TradeStateBadge = ({ state }) => {
  if (!state) return null;
  const cfg = STATE_CFG[state] || { color:"#8899aa", bg:"rgba(136,153,170,0.1)", label:state, pulse:false };
  return (
    <span style={{
      fontSize:7, fontWeight:"bold", fontFamily:"sans-serif",
      padding:"1px 4px", borderRadius:3,
      background:cfg.bg, color:cfg.color,
      border:`1px solid ${cfg.color}44`,
      animation: cfg.pulse ? "st-pulse 1.5s ease-in-out infinite" : "none",
      display:"inline-block", verticalAlign:"middle",
    }}>
      {cfg.label}
    </span>
  );
};
const ScoreTrendArrow = ({ score, prev }) => {
  if (score == null || prev == null) return null;
  const diff = score - prev;
  if (diff > 0.5)  return <span style={{ color:"#00ff88", fontSize:10 }}>&#8593;</span>;
  if (diff < -0.5) return <span style={{ color:"#ff4466", fontSize:10 }}>&#8595;</span>;
  return <span style={{ color:"#8899aa", fontSize:10 }}>&#8594;</span>;
};
const formatDuration = (startIso, endIso = null) => {
  if (!startIso) return '-';
  try {
    const start = new Date(startIso), end = endIso ? new Date(endIso) : new Date();
    const mins = Math.floor((end - start) / 60000);
    if (mins < 1) return '<1m'; if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60), rm = mins % 60;
    if (hrs < 24) return `${hrs}h ${rm}m`;
    return `${Math.floor(hrs/24)}d ${hrs%24}h`;
  } catch { return '-'; }
};
const fmt = ts => {
  if (!ts) return '-';
  try { return new Date(ts).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' }); }
  catch { return ts.slice(11,16) || '-'; }
};

// ── Sector map (mirrors backend SECTOR_MAP) ───────────────────────────────────
const SECTOR_MAP = {
  AAPL:'Tech', MSFT:'Tech', NVDA:'Tech', AMD:'Tech', GOOGL:'Tech', META:'Tech', AMZN:'Tech',
  TSLA:'Consumer', NFLX:'Consumer', DIS:'Consumer', NKE:'Consumer', SBUX:'Consumer',
  JPM:'Finance', GS:'Finance', BAC:'Finance', V:'Finance', MA:'Finance', BRK:'Finance',
  JNJ:'Health', PFE:'Health', UNH:'Health', ABBV:'Health', LLY:'Health', MRK:'Health',
  XOM:'Energy', CVX:'Energy', COP:'Energy', SLB:'Energy',
  BA:'Industrials', CAT:'Industrials', HON:'Industrials', GE:'Industrials',
  CRWD:'Tech', NET:'Tech', MRVL:'Tech', PANW:'Tech', ZS:'Tech', OKTA:'Tech',
  SHOP:'Tech', SNOW:'Tech', PLTR:'Tech', DDOG:'Tech', GTLB:'Tech',
  COIN:'Finance', SQ:'Finance', PYPL:'Finance',
  BTC:'Crypto', ETH:'Crypto', SOL:'Crypto', XRP:'Crypto', ADA:'Crypto',
};
const getSector = (ticker, signal = null) =>
  SECTOR_MAP[(ticker || '').toUpperCase()] ||
  signal?.entry_snapshot?.sector ||
  'Other';

// ── Extract SL change history from action_log ────────────────────────────────
// Filters OPENED, TSL MOVED UP, SL OVERRIDE entries.
// Enforces only-ascending rule (SL can never go down).
const extractSLHistory = signal => {
  const log     = signal.action_log || [];
  const entries = [];

  // Initial SL from OPENED entry (or original_sl field)
  const openEntry = log.find(e => e.action === 'OPENED');
  const origSL    = signal.original_sl || signal.sl;
  let origVal     = origSL;
  let origNote    = 'Entry SL';

  if (openEntry) {
    const m = openEntry.detail.match(/SL \$(\d+\.?\d*)/);
    if (m) origVal = parseFloat(m[1]);
    origNote = openEntry.detail.length > 60
      ? openEntry.detail.slice(0, 58) + '…'
      : openEntry.detail;
  }
  entries.push({ sl: origVal, note: origNote, ts: openEntry?.ts || signal.entry_time, label: 'Original' });

  // TSL ratchets + manual overrides
  log
    .filter(e => e.action === 'TSL MOVED UP' || e.action === 'SL OVERRIDE')
    .forEach(e => {
      const m = e.detail.match(/→ \$(\d+\.?\d*)/);
      if (!m) return;
      const newSL = parseFloat(m[1]);
      let note = '';
      if (e.action === 'TSL MOVED UP') {
        const highM = e.detail.match(/new high \$(\d+\.?\d*)/);
        note = highM ? `TSL: high $${highM[1]}` : 'TSL ratchet';
      } else {
        note = 'Manual SL override';
      }
      entries.push({ sl: newSL, note, ts: e.ts, label: null });
    });

  // Sort chronologically
  entries.sort((a, b) => (a.ts || '').localeCompare(b.ts || ''));

  // Enforce ascending-only rule
  let maxSL = -Infinity;
  const ascending = entries.filter(e => {
    if (e.sl >= maxSL) { maxSL = e.sl; return true; }
    return false;
  });

  // Mark last entry as "Current"
  if (ascending.length > 1) ascending[ascending.length - 1].label = 'Current';
  return ascending;
};

const PillarChart = ({ scores }) => {
  if (!scores || Object.keys(scores).length === 0) return null;
  return (
    <div style={{ marginTop:10 }}>
      <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif", letterSpacing:1.2, marginBottom:6 }}>CONVICTION PILLARS</div>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {Object.entries(scores).map(([k, v]) => {
          const pct = Math.min(Math.max(Number(v)||0,0),100);
          const col = pct>=70?"#00ff88":pct>=50?"#fbbf24":"#ff4466";
          return (
            <div key={k} style={{ display:"flex", alignItems:"center", gap:8 }}>
              <div style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif", width:82, flexShrink:0 }}>{pillarLabel(k)}</div>
              <div style={{ flex:1, background:"#1a2535", borderRadius:3, height:8, overflow:"hidden" }}>
                <div style={{ width:`${pct}%`, height:"100%", background:col, borderRadius:3 }} />
              </div>
              <div style={{ fontSize:10, fontWeight:"bold", color:col, width:26, textAlign:"right", fontFamily:"monospace" }}>{pct}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const EntryReasonPanel = ({ signal }) => {
  // Detect legacy signals (created before v2.1 -- scan_data not captured)
  const hasScanData =
    (signal.conviction > 0) ||
    (signal.pillar_scores && Object.keys(signal.pillar_scores).length > 0) ||
    (signal.entry_market_context && Object.keys(signal.entry_market_context).length > 0) ||
    !!signal.entry_session;

  if (!hasScanData) {
    return (
      <div>
        <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:10, letterSpacing:1 }}>ENTRY REASON</div>
        <div style={{ background:"#0d1520", borderRadius:8, padding:"20px 12px", textAlign:"center", border:"1px dashed #1a2535" }}>
          <div style={{ fontSize:18, marginBottom:8 }}>&#128203;</div>
          <div style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif", marginBottom:4 }}>No entry data</div>
          <div style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif" }}>Legacy signal &#8212; created before v2.1</div>
          <div style={{ fontSize:8, color:"#1a2535", fontFamily:"sans-serif", marginTop:8 }}>New signals capture full conviction context</div>
        </div>
      </div>
    );
  }

  const conv  = signal.conviction || 0;
  const level = convictionLevel(conv);
  const ctx   = signal.entry_market_context || {};
  const regime  = ctx.regime || signal.regime || "-";
  const session = signal.entry_session || "-";
  const vix     = ctx.vix ?? "-";
  const spyChg  = ctx.spy_change_pct ?? "-";
  const spyC    = ctx.spy_close ?? "-";
  const tas     = signal.tas || "-";
  const taNote  = signal.ta_note || "";
  return (
    <div>
      <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:10, letterSpacing:1 }}>ENTRY REASON</div>
      <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:10 }}>
        <div style={{ fontSize:26, fontWeight:"bold", color:level.color, fontFamily:"monospace", lineHeight:1 }}>{conv}%</div>
        <div>
          <div style={{ fontSize:11, fontWeight:"bold", color:level.color, fontFamily:"sans-serif", background:`${level.color}18`, padding:"2px 8px", borderRadius:3, display:"inline-block" }}>{level.label}</div>
          <div style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif", marginTop:2 }}>conviction score</div>
        </div>
      </div>
      <div style={{ background:"#0d1520", borderRadius:6, padding:"6px 10px", marginBottom:8, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <span style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif" }}>TIMEFRAMES ALIGNED</span>
        <span style={{ fontSize:12, fontWeight:"bold", color:"#fbbf24", fontFamily:"monospace" }}>{tas} bullish</span>
      </div>
      <div style={{ display:"flex", gap:6, marginBottom:8 }}>
        <div style={{ flex:1, background:"#0d1520", borderRadius:6, padding:"5px 8px" }}>
          <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>REGIME</div>
          <div style={{ fontSize:10, fontWeight:"bold", color:"#fbbf24", fontFamily:"sans-serif", marginTop:1 }}>{regime}</div>
        </div>
        <div style={{ flex:1, background:"#0d1520", borderRadius:6, padding:"5px 8px" }}>
          <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>SESSION</div>
          <div style={{ fontSize:10, fontWeight:"bold", color:sessionColor(session), fontFamily:"sans-serif", marginTop:1, textTransform:"uppercase" }}>{session}</div>
        </div>
      </div>
      <div style={{ display:"flex", gap:6, marginBottom:8 }}>
        <div style={{ flex:1, background:"#0d1520", borderRadius:6, padding:"5px 8px" }}>
          <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>VIX</div>
          <div style={{ fontSize:12, fontWeight:"bold", color:Number(vix)>25?"#ff4466":"#00ff88", fontFamily:"monospace", marginTop:1 }}>{vix}</div>
        </div>
        <div style={{ flex:1, background:"#0d1520", borderRadius:6, padding:"5px 8px" }}>
          <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>SPY</div>
          <div style={{ fontSize:11, fontWeight:"bold", color:Number(spyChg)>=0?"#00ff88":"#ff4466", fontFamily:"monospace", marginTop:1 }}>
            ${spyC} ({Number(spyChg)>=0?"+":""}{spyChg}%)
          </div>
        </div>
      </div>
      <PillarChart scores={signal.pillar_scores} />
      {taNote && (
        <div style={{ marginTop:8, fontSize:9, color:"#8899aa", fontFamily:"sans-serif", background:"#0d1520", borderRadius:4, padding:"6px 8px", lineHeight:1.5 }}>
          {taNote}
        </div>
      )}
    </div>
  );
};

const OverrideSLForm = ({ signal, onSave, onCancel }) => {
  const [val, setVal]     = useState(String(signal.sl));
  const [saving, setSaving] = useState(false);
  const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
  const save = async () => {
    const newSl = parseFloat(val);
    if (isNaN(newSl) || newSl <= 0) { alert("Invalid SL value"); return; }
    setSaving(true);
    try {
      const res = await fetch(`${apiUrl}/api/signals/override-sl/${signal.id}?new_sl=${newSl}`, { method:'POST' });
      if (!res.ok) { const e = await res.json(); alert(e.detail || 'Error'); setSaving(false); return; }
      onSave();
    } catch(e) { alert(e.message); }
    setSaving(false);
  };
  const newNum = parseFloat(val);
  const direction = !isNaN(newNum) ? (newNum > signal.sl ? "tightening up" : newNum < signal.sl ? "loosening down" : "no change") : "";
  const diff = !isNaN(newNum) ? (newNum - signal.sl).toFixed(2) : "";

  const askOpus = async (signalId) => {
    const q = (advisorInput[signalId] || '').trim();
    if (!q) return;
    setAdvisorReply(r => ({ ...r, [signalId]: { loading: true } }));
    try {
      const res = await fetch(`${apiUrl}/api/signals/ask-advisor/${signalId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      setAdvisorReply(r => ({ ...r, [signalId]: { answer: data.answer, loading: false } }));
    } catch (e) {
      setAdvisorReply(r => ({ ...r, [signalId]: { error: String(e), loading: false } }));
    }
  };
  return (
    <div style={{ background:"rgba(192,132,252,0.06)", border:"1px solid #c084fc33", borderRadius:8, padding:12, marginTop:10 }}>
      <div style={{ fontSize:10, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:8 }}>OVERRIDE STOP-LOSS</div>
      <div style={{ display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
        <div>
          <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif", marginBottom:3 }}>CURRENT SL</div>
          <div style={{ fontSize:13, color:"#ff4466", fontWeight:"bold", fontFamily:"monospace" }}>${signal.sl}</div>
        </div>
        <div style={{ color:"#2a4a5a", fontSize:16 }}>&#8594;</div>
        <div>
          <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif", marginBottom:3 }}>NEW SL</div>
          <input value={val} onChange={e => setVal(e.target.value)} onKeyDown={e => e.key==='Enter' && save()}
            style={{ width:90, background:"#0d1a2a", border:"1px solid #c084fc55", borderRadius:4, padding:"5px 8px", color:"#e0e0e0", fontSize:13, fontFamily:"monospace" }} />
        </div>
        {direction && <div style={{ fontSize:9, color:newNum>signal.sl?"#00ff88":"#fbbf24", fontFamily:"sans-serif" }}>{direction} ({diff>=0?"+":""}{diff})</div>}
        <button onClick={save} disabled={saving}
          style={{ background:saving?"#1a2535":"linear-gradient(135deg,#c084fc,#7c3aed)", border:"none", borderRadius:4, padding:"6px 14px", color:"#fff", fontSize:10, fontWeight:"bold", fontFamily:"sans-serif", cursor:saving?"wait":"pointer" }}>
          {saving?"...":"SAVE"}
        </button>
        <button onClick={onCancel} style={{ background:"transparent", border:"1px solid #2a4a5a", borderRadius:4, padding:"6px 10px", color:"#8899aa", fontSize:10, fontFamily:"sans-serif", cursor:"pointer" }}>Cancel</button>
      </div>
      {signal.original_sl && signal.sl !== signal.original_sl && (
        <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif", marginTop:6 }}>Original SL: ${signal.original_sl}</div>
      )}
    </div>
  );
};

// Always renders: shows empty state for legacy signals with no action_log
const SignalActionLog = ({ log }) => {
  if (!log || log.length === 0) return (
    <div style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif", padding:"8px 0", fontStyle:"italic" }}>No actions recorded yet &#8212; events will appear here as the trade progresses.</div>
  );
  return (
    <div style={{ maxHeight:160, overflowY:"auto" }}>
      {[...log].reverse().map((e, i) => (
        <div key={i} style={{ display:"grid", gridTemplateColumns:"50px 110px 1fr", gap:8, padding:"4px 0", borderBottom:"1px solid #0d1520", alignItems:"flex-start" }}>
          <span style={{ fontSize:9, color:"#2a4a5a", fontFamily:"monospace" }}>{fmt(e.ts)}</span>
          <span style={{ fontSize:9, fontWeight:"bold", color:actionColor(e.category), fontFamily:"monospace" }}>{e.action}</span>
          <span style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif", lineHeight:1.4 }}>{e.detail}</span>
        </div>
      ))}
    </div>
  );
};

const TSLStatusPanel = ({ signal }) => {
  const tslActive = signal.trailing_sl_active || false;
  const origSL    = signal.original_sl || signal.sl;
  const currSL    = signal.sl;
  const slMoved   = Number((currSL - origSL).toFixed(4));
  const entry     = signal.entry_price || 0;
  const lockedPct = entry > 0 ? ((currSL - entry) / entry * 100).toFixed(1) : null;
  return (
    <div>
      <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:10, letterSpacing:1 }}>STOP-LOSS STATUS</div>
      <div style={{ background:"#0d1520", borderRadius:6, padding:10, marginBottom:8 }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:6 }}>
          <span style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif" }}>CURRENT SL</span>
          <span style={{ fontSize:15, fontWeight:"bold", color:"#ff4466", fontFamily:"monospace" }}>${currSL}</span>
        </div>
        {tslActive ? (
          <>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:4 }}>
              <span style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif" }}>Original SL</span>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"monospace" }}>${origSL}</span>
            </div>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:4 }}>
              <span style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif" }}>SL moved up</span>
              <span style={{ fontSize:11, fontWeight:"bold", color:"#00ff88", fontFamily:"monospace" }}>+${slMoved}</span>
            </div>
            {lockedPct !== null && (
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
                <span style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif" }}>Min profit locked</span>
                <span style={{ fontSize:11, fontWeight:"bold", color:lockedPct>=0?"#00ff88":"#ff4466", fontFamily:"monospace" }}>{lockedPct>=0?"+":""}{lockedPct}%</span>
              </div>
            )}
          </>
        ) : (
          <div style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif", marginTop:4 }}>TSL activates at +0.5% profit</div>
        )}
      </div>
      <div style={{ display:"inline-flex", alignItems:"center", gap:5, background:tslActive?"rgba(0,255,136,0.08)":"rgba(42,74,90,0.3)", border:`1px solid ${tslActive?"#00ff8833":"#2a4a5a"}`, borderRadius:4, padding:"3px 8px" }}>
        <div style={{ width:5, height:5, borderRadius:"50%", background:tslActive?"#00ff88":"#2a4a5a" }} />
        <span style={{ fontSize:9, fontWeight:"bold", color:tslActive?"#00ff88":"#2a4a5a", fontFamily:"sans-serif" }}>{tslActive?"TRAILING SL ACTIVE":"FIXED SL"}</span>
      </div>
      <div style={{ marginTop:12, fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", letterSpacing:1, marginBottom:6 }}>TARGETS</div>
      <div style={{ fontSize:10, color:"#94a3b8", fontFamily:"sans-serif", lineHeight:2 }}>
        <div>TP1: <b style={{color:signal.tp1_hit?"#00ff88":"#94a3b8"}}>${signal.tp1}</b>{signal.tp1_hit?" ✓":""}</div>
        <div>TP2: <b style={{color:signal.tp2_hit?"#00ff88":"#94a3b8"}}>${signal.tp2}</b>{signal.tp2_hit?" ✓":""}</div>
        <div>TP3: <b style={{color:signal.tp3_hit?"#00ff88":"#94a3b8"}}>${signal.tp3}</b>{signal.tp3_hit?" ✓":""}</div>
        <div>R:R <b>{signal.rr}</b>:1 &middot; ATR <b>${signal.atr_at_entry||"-"}</b></div>
        <div>High <b style={{color:"#00ff88"}}>${signal.highest_price}</b> &middot; Low <b style={{color:"#ff4466"}}>${signal.lowest_price}</b></div>
        <div>MAE <b style={{color:"#ff4466"}}>{signal.mae_pct}%</b> &middot; MFE <b style={{color:"#00ff88"}}>+{signal.mfe_pct}%</b></div>
      </div>
    </div>
  );
};

// ── SL History Dropdown ──────────────────────────────────────────────────────
const SLHistoryPanel = ({ signal, entryTime, onClose }) => {
  const history = extractSLHistory(signal);
  if (history.length === 0) return null;

  const askOpus = async (signalId) => {
    const q = (advisorInput[signalId] || '').trim();
    if (!q) return;
    setAdvisorReply(r => ({ ...r, [signalId]: { loading: true } }));
    try {
      const res = await fetch(`${apiUrl}/api/signals/ask-advisor/${signalId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      setAdvisorReply(r => ({ ...r, [signalId]: { answer: data.answer, loading: false } }));
    } catch (e) {
      setAdvisorReply(r => ({ ...r, [signalId]: { error: String(e), loading: false } }));
    }
  };
  return (
    <div style={{ background:'#07101d', borderTop:'1px solid #1a2535', padding:'10px 14px' }}
      onClick={e => e.stopPropagation()}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
        <span style={{ fontSize:9, fontWeight:'bold', color:'#c084fc', fontFamily:'sans-serif', letterSpacing:1 }}>SL HISTORY</span>
        <button onClick={onClose}
          style={{ background:'transparent', border:'none', color:'#8899aa', cursor:'pointer', fontSize:14, lineHeight:1 }}>×</button>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
        {history.map((h, i) => {
          const isLast   = i === history.length - 1;
          const rowLabel = h.label || '+' + formatDuration(entryTime, h.ts);
          return (
            <div key={i} style={{ display:'grid', gridTemplateColumns:'70px 80px 1fr 60px', gap:8, alignItems:'center',
              opacity: isLast ? 1 : 0.65 }}>
              <span style={{ fontSize:9, color: isLast ? '#c084fc' : '#2a4a5a', fontFamily:'sans-serif', fontWeight: isLast ? 'bold' : 'normal' }}>
                {rowLabel}
              </span>
              <span style={{ fontSize:12, fontWeight:'bold', color:'#ff4466', fontFamily:'monospace' }}>
                ${h.sl.toFixed(2)}
              </span>
              <span style={{ fontSize:9, color:'#8899aa', fontFamily:'sans-serif', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                {h.note}
              </span>
              <span style={{ fontSize:8, color:'#2a4a5a', fontFamily:'monospace', textAlign:'right' }}>
                {fmt(h.ts)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ================================================
const SignalTracker = () => {
  const [data,             setData]             = useState(null);
  const [loading,          setLoading]          = useState(false);
  const [refreshing,       setRefreshing]       = useState(false);
  const [tab,              setTab]              = useState('active');
  const [turboTicker,      setTurboTicker]      = useState('');
  const [turboLoading,     setTurboLoading]     = useState(false);
  const [autoRefresh,      setAutoRefresh]      = useState(true);
  const [countdown,        setCountdown]        = useState(30);
  const [autopilotLoading, setAutopilotLoading] = useState(false);
  const [autopilotResult,  setAutopilotResult]  = useState(null);
  const [cryptoLoading,    setCryptoLoading]    = useState(false);
  const [expandedSignal,   setExpandedSignal]   = useState(null);
  const [overrideSLFor,    setOverrideSLFor]    = useState(null);
  const [now,              setNow]              = useState(new Date());
  const [slDropdown,       setSlDropdown]       = useState(null);   // signal id or null
  const [scanCandidates,   setScanCandidates]   = useState([]);     // bench cache
  const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

  useEffect(() => { const t = setInterval(() => setNow(new Date()), 60000); return () => clearInterval(t); }, []);

  // ── Bench candidate helpers ────────────────────────────────────────────────
  const fetchCandidates = async (activeTickers = []) => {
    try {
      const exclude = activeTickers.join(',');
      const url     = `${apiUrl}/api/scan/candidates${exclude ? `?exclude=${exclude}` : ''}`;
      const res     = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        setScanCandidates(json.candidates || []);
      }
    } catch (e) { console.error('[BENCH] scan failed:', e); }
  };

  // Returns top 2 bench candidates for a given signal, preferring same sector.
  const getBenchFor = (signal, candidates) => {
    if (!candidates || candidates.length === 0) return [];
    const activeTickers = new Set((data?.active || []).map(s => s.ticker));
    const available     = candidates.filter(c => !activeTickers.has(c.ticker));
    const signalSector  = getSector(signal.ticker, signal);
    const sameSector    = available.filter(c => getSector(c.ticker) === signalSector);
    const other         = available.filter(c => getSector(c.ticker) !== signalSector);
    return [...sameSector, ...other].slice(0, 2);
  };

  const openBenchTicker = async (candidate, e) => {
    e.stopPropagation();
    if (!confirm(`Open turbo signal for ${candidate.ticker} (${candidate.conviction_pct}%)?`)) return;
    try {
      const res = await fetch(`${apiUrl}/api/signals/turbo/${candidate.ticker}`, { method:'POST' });
      if (!res.ok) { const err = await res.json(); alert(err.detail || 'Error'); return; }
      fetchSignals(true);
    } catch (err) { alert(err.message); }
  };

  const fetchSignals = async (refresh = false) => {
    if (refresh) setRefreshing(true); else setLoading(true);
    try {
      const res  = await fetch(`${apiUrl}${refresh?'/api/signals/check':'/api/signals'}`, { method: refresh?'POST':'GET' });
      const json = await res.json();
      setData(json);
      if (refresh && autoRefresh) setCountdown(30);
      // Refresh bench candidates whenever prices are checked
      if (refresh) fetchCandidates((json.active || []).map(s => s.ticker));
    } catch (e) { console.error(e); }
    setLoading(false); setRefreshing(false);
  };

  const closeSignal = async id => { await fetch(`${apiUrl}/api/signals/close/${id}`, { method:'POST' }); fetchSignals(); };
  const clearAll    = async () => {
    if (!confirm('Clear ALL signals?')) return;
    await fetch(`${apiUrl}/api/signals/clear`, { method:'POST' }); fetchSignals();
  };
  const launchTurbo = async () => {
    if (!turboTicker.trim()) return; setTurboLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/signals/turbo/${turboTicker.trim().toUpperCase()}`, { method:'POST' });
      if (!res.ok) { const e = await res.json(); alert(e.detail||'Error'); }
      else { setTurboTicker(''); fetchSignals(true); }
    } catch(e) { alert(e.message); }
    setTurboLoading(false);
  };
  const runAutopilot = async () => {
    setAutopilotLoading(true); setAutopilotResult(null);
    try {
      const res = await fetch(`${apiUrl}/api/autopilot`, { method:'POST' });
      if (!res.ok) { const e = await res.json().catch(()=>({detail:'Autopilot error'})); alert('Autopilot error: '+(e.detail||e.error||JSON.stringify(e))); return; }
      const d = await res.json(); setAutopilotResult(d); setAutoRefresh(true); fetchSignals(true);
    } catch(e) { alert('Autopilot error: '+e.message); }
    setAutopilotLoading(false);
  };
  const runCryptoAutopilot = async () => {
    setCryptoLoading(true); setAutopilotResult(null);
    try {
      const res = await fetch(`${apiUrl}/api/autopilot/crypto`, { method:'POST' });
      if (!res.ok) { const e = await res.json().catch(()=>({detail:'Crypto autopilot error'})); alert('Crypto autopilot error: '+(e.detail||e.error||JSON.stringify(e))); return; }
      const d = await res.json(); setAutopilotResult(d); setAutoRefresh(true); fetchSignals(true);
    } catch(e) { alert('Crypto autopilot error: '+e.message); }
    setCryptoLoading(false);
  };

  useEffect(() => {
    if (!autoRefresh) return;
    setCountdown(30);
    const pi = setInterval(() => fetchSignals(true), 30000);
    const ti = setInterval(() => setCountdown(c => c<=1?30:c-1), 1000);
    return () => { clearInterval(pi); clearInterval(ti); };
  }, [autoRefresh]);
  useEffect(() => { if (data?.active?.length>0 && !autoRefresh) setAutoRefresh(true); }, [data?.active?.length]);
  useEffect(() => { fetchSignals(); fetchCandidates([]); }, []);

  const stats     = data?.stats || {};
  const active    = data?.active || [];
  const closed    = data?.closed || [];
  const mktStatus = data?.market_status || {};
  const warnings  = data?.warnings || [];
  const display   = tab==='active' ? active : closed;

  const allSignals = [...active, ...closed];
  const globalLog  = allSignals
    .flatMap(s => (s.action_log||[]))
    .sort((a,b) => b.ts.localeCompare(a.ts))
    .slice(0, 50);


  const askOpus = async (signalId) => {
    const q = (advisorInput[signalId] || '').trim();
    if (!q) return;
    setAdvisorReply(r => ({ ...r, [signalId]: { loading: true } }));
    try {
      const res = await fetch(`${apiUrl}/api/signals/ask-advisor/${signalId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      setAdvisorReply(r => ({ ...r, [signalId]: { answer: data.answer, loading: false } }));
    } catch (e) {
      setAdvisorReply(r => ({ ...r, [signalId]: { error: String(e), loading: false } }));
    }
  };
  return (
    <div style={{ background:"#050810", padding:"20px 16px", fontFamily:"'Courier New',monospace", color:"#c9d8e8" }}>
      <style>{`@keyframes st-pulse { 0%,100%{opacity:1} 50%{opacity:0.45} }`}</style>

      {/* Header */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", borderBottom:"1px solid #1a2535", paddingBottom:14, marginBottom:16 }}>
        <div>
          <span style={{ fontWeight:"bold", fontSize:22 }}>Signal<span style={{ color:"#c084fc" }}>Tracker</span></span>
          <span style={{ color:"#c084fc", fontSize:11, fontWeight:"bold", background:"rgba(192,132,252,0.15)", border:"1px solid rgba(192,132,252,0.3)", padding:"1px 7px", borderRadius:3, marginLeft:10 }}>v2.1</span>
          <div style={{ color:"#2a4a5a", fontSize:10, marginTop:2, fontFamily:"sans-serif" }}>FULL TRANSPARENCY &middot; TRAILING SL &middot; INTERVENTION &middot; ACTION LOG</div>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          {mktStatus.session && (
            <div style={{ background:`${sessionColor(mktStatus.session)}10`, border:`1px solid ${sessionColor(mktStatus.session)}33`, borderRadius:6, padding:"4px 10px", display:"flex", alignItems:"center", gap:5 }}>
              <div style={{ width:6, height:6, borderRadius:3, background:sessionColor(mktStatus.session) }} />
              <span style={{ fontSize:10, fontWeight:"bold", color:sessionColor(mktStatus.session), fontFamily:"sans-serif", textTransform:"uppercase" }}>{mktStatus.session||"?"}</span>
              {mktStatus.et_time && <span style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif" }}>{mktStatus.et_time}</span>}
            </div>
          )}
          <button onClick={() => fetchSignals(true)} disabled={refreshing}
            style={{ background:"#0d1520", border:"1px solid #1a2535", borderRadius:4, padding:"6px 12px", color:"#c084fc", fontSize:10, fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:4 }}>
            <RefreshCw size={12} />{refreshing?"CHECKING...":"CHECK PRICES"}
          </button>
          <button onClick={clearAll} style={{ background:"#0d1520", border:"1px solid #ff446633", borderRadius:4, padding:"6px 12px", color:"#ff4466", fontSize:10, fontFamily:"sans-serif", cursor:"pointer" }}>RESET ALL</button>
        </div>
      </div>

      {warnings.length>0 && (
        <div style={{ background:"rgba(251,191,36,0.08)", border:"1px solid #fbbf2433", borderRadius:8, padding:"8px 12px", marginBottom:12, display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
          <AlertTriangle size={14} color="#fbbf24" />
          {warnings.map((w,i) => <span key={i} style={{ fontSize:10, color:"#fbbf24", fontFamily:"sans-serif" }}>{w.ticker}: {w.warning}</span>)}
        </div>
      )}

      {/* Turbo + Auto Refresh */}
      <div style={{ display:"flex", gap:12, marginBottom:16, alignItems:"center", flexWrap:"wrap" }}>
        <div style={{ display:"flex", gap:6, alignItems:"center", background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:"8px 12px", flex:1, minWidth:250 }}>
          <span style={{ fontSize:10, color:"#c084fc", fontWeight:"bold", fontFamily:"sans-serif", whiteSpace:"nowrap" }}>&#9889; TURBO</span>
          <input value={turboTicker} onChange={e => setTurboTicker(e.target.value.toUpperCase())} placeholder="AAPL" onKeyDown={e => e.key==='Enter'&&launchTurbo()}
            style={{ flex:1, background:"#0d1a2a", border:"1px solid #1a2535", borderRadius:4, padding:"6px 10px", color:"#e0e0e0", fontSize:13, fontFamily:"monospace", minWidth:60 }} />
          <button onClick={launchTurbo} disabled={turboLoading||!turboTicker.trim()}
            style={{ background:turboLoading?"#1a2535":"linear-gradient(135deg,#c084fc,#7c3aed)", border:"none", borderRadius:4, padding:"6px 14px", color:"#fff", fontSize:11, fontWeight:"bold", fontFamily:"sans-serif", cursor:turboLoading?"wait":"pointer", whiteSpace:"nowrap" }}>
            {turboLoading?"...":"LAUNCH"}
          </button>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:8, background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:"8px 12px" }}>
          <span style={{ fontSize:10, color:"#8899aa", fontFamily:"sans-serif" }}>AUTO-REFRESH</span>
          <button onClick={() => setAutoRefresh(!autoRefresh)}
            style={{ width:40, height:22, borderRadius:11, border:"none", background:autoRefresh?"#00ff88":"#1a2535", cursor:"pointer", position:"relative" }}>
            <div style={{ width:18, height:18, borderRadius:9, background:"#fff", position:"absolute", top:2, left:autoRefresh?20:2, transition:"left 0.2s" }} />
          </button>
          {autoRefresh && <span style={{ fontSize:11, color:"#00ff88", fontFamily:"monospace", fontWeight:"bold", minWidth:30 }}>{countdown}s</span>}
        </div>
      </div>

      {/* Auto-Pilot */}
      <div style={{ background:"linear-gradient(135deg,rgba(0,212,255,0.06),rgba(124,58,237,0.06))", border:"1px solid #7c3aed44", borderRadius:10, padding:16, marginBottom:16 }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", flexWrap:"wrap", gap:10 }}>
          <div>
            <div style={{ fontSize:14, fontWeight:"bold", color:"#e0e0e0", fontFamily:"sans-serif" }}>AUTO-PILOT</div>
            <div style={{ fontSize:10, color:"#8899aa", fontFamily:"sans-serif", marginTop:2 }}>Scan &rarr; Rank &rarr; Launch ATR-based turbo signals</div>
          </div>
          <div style={{ display:"flex", gap:10, flexWrap:"wrap" }}>
            <button onClick={runAutopilot} disabled={autopilotLoading}
              style={{ background:autopilotLoading?"#1a2535":"linear-gradient(135deg,#00d4ff,#7c3aed)", border:"none", borderRadius:8, padding:"12px 28px", color:"#fff", fontSize:14, fontWeight:"bold", fontFamily:"sans-serif", cursor:autopilotLoading?"wait":"pointer", letterSpacing:1 }}>
              {autopilotLoading?"SCANNING...":"STOCKS (30)"}
            </button>
            <button onClick={runCryptoAutopilot} disabled={cryptoLoading}
              style={{ background:cryptoLoading?"#1a2535":"linear-gradient(135deg,#f7931a,#e2761b)", border:"none", borderRadius:8, padding:"12px 28px", color:"#fff", fontSize:14, fontWeight:"bold", fontFamily:"sans-serif", cursor:cryptoLoading?"wait":"pointer", letterSpacing:1 }}>
              {cryptoLoading?"SCANNING...":"CRYPTO (15)"}
            </button>
          </div>
        </div>
        {autopilotResult && (
          <div style={{ marginTop:14, background:"#0a0f18", borderRadius:8, padding:12 }}>
            <div style={{ display:"flex", gap:16, flexWrap:"wrap", marginBottom:10 }}>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif" }}>Scanned: <b style={{color:"#e0e0e0"}}>{autopilotResult.scanned}</b></span>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif" }}>Passed: <b style={{color:"#00ff88"}}>{autopilotResult.passed_filter}</b></span>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif" }}>Launched: <b style={{color:"#c084fc"}}>{autopilotResult.launched?.length||0}</b></span>
              <span style={{ fontSize:11, color:"#8899aa", fontFamily:"sans-serif" }}>Regime: <b style={{color:"#fbbf24"}}>{autopilotResult.market_regime}</b></span>
            </div>
            {autopilotResult.launched?.length>0 && (
              <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
                {autopilotResult.launched.map(l => (
                  <div key={l.ticker} style={{ background:"rgba(0,255,136,0.08)", border:"1px solid #00ff8833", borderRadius:6, padding:"6px 10px", textAlign:"center" }}>
                    <div style={{ fontSize:12, fontWeight:"bold", color:"#00ff88" }}>{l.ticker}</div>
                    <div style={{ fontSize:9, color:"#8899aa" }}>{l.conviction}% &middot; ${l.entry}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stats */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8, marginBottom:12 }}>
        {[
          { label:"ACTIVE",        val:active.length,            color:"#00d4ff" },
          { label:"WIN RATE",      val:`${stats.win_rate||0}%`,  color:(stats.win_rate||0)>=50?"#00ff88":"#ff4466" },
          { label:"AVG P&L",       val:`${stats.avg_pnl||0}%`,   color:pnlColor(stats.avg_pnl||0) },
          { label:"PROFIT FACTOR", val:stats.profit_factor||0,   color:(stats.profit_factor||0)>=1.5?"#00ff88":(stats.profit_factor||0)>=1?"#fbbf24":"#ff4466" },
        ].map(c => (
          <div key={c.label} style={{ background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:10, textAlign:"center" }}>
            <div style={{ fontSize:8, color:"#2a4a5a", letterSpacing:1.5, fontFamily:"sans-serif", marginBottom:4 }}>{c.label}</div>
            <div style={{ fontSize:18, fontWeight:"bold", color:c.color }}>{c.val}</div>
          </div>
        ))}
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(6,1fr)", gap:8, marginBottom:20 }}>
        {[
          { label:"WINS",       val:stats.wins||0,                   color:"#00ff88" },
          { label:"LOSSES",     val:stats.losses||0,                 color:"#ff4466" },
          { label:"TP1 HIT%",   val:`${stats.tp1_hit_rate||0}%`,     color:"#fbbf24" },
          { label:"AVG MAE",    val:`${stats.avg_mae||0}%`,          color:"#ff4466", sub:"max drawdown" },
          { label:"AVG MFE",    val:`${stats.avg_mfe||0}%`,          color:"#00ff88", sub:"max runup" },
          { label:"GAP TRADES", val:stats.gap_affected_trades||0,    color:"#f97316", sub:`slip: ${stats.total_gap_slippage||0}%` },
        ].map(c => (
          <div key={c.label} style={{ background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:10, textAlign:"center" }}>
            <div style={{ fontSize:8, color:"#2a4a5a", letterSpacing:1.5, fontFamily:"sans-serif", marginBottom:4 }}>{c.label}</div>
            <div style={{ fontSize:16, fontWeight:"bold", color:c.color }}>{c.val}</div>
            {c.sub && <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif", marginTop:2 }}>{c.sub}</div>}
          </div>
        ))}
      </div>

      {(stats.avg_conviction_winners>0||stats.avg_conviction_losers>0) && (
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
          <button key={t} onClick={() => setTab(t)}
            style={{ background:tab===t?"#0d1a2a":"transparent", color:tab===t?"#c084fc":"#8899aa", border:"none", borderBottom:tab===t?"2px solid #c084fc":"2px solid transparent", padding:"8px 20px", fontSize:11, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", textTransform:"uppercase" }}>
            {t} ({t==='active'?active.length:closed.length})
          </button>
        ))}
      </div>

      {display.length===0 && (
        <div style={{ textAlign:"center", padding:"40px", color:"#2a4a5a", fontFamily:"sans-serif" }}>
          <Target size={32} style={{ marginBottom:10, opacity:0.3 }} />
          <div style={{ fontSize:14 }}>{tab==='active'?'No active signals':'No closed signals yet'}</div>
          <div style={{ fontSize:11, marginTop:6, color:"#1a2535" }}>Run a scan or use Auto-Pilot to generate signals</div>
        </div>
      )}

      {/* Signal Cards */}
      {display.length>0 && (
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {display.map(s => {
            const isExpanded   = expandedSignal===s.id;
            const method       = s.target_method||(s.atr_at_entry>0?"atr":"pct");
            const closeTs      = s.close_time||s.closed_at||null;
            const isOpen       = s.status==="OPEN";
            const duration     = formatDuration(s.entry_time, isOpen?null:closeTs);
            const showOverride = overrideSLFor===s.id;
            return (
              <div key={s.id} style={{ background:"#0a0f18", border:`1px solid ${isExpanded?"#c084fc33":"#1a2535"}`, borderRadius:10, overflow:"hidden" }}>
                {/* Main Row */}
                <div onClick={() => setExpandedSignal(isExpanded?null:s.id)}
                  style={{ display:"grid", gridTemplateColumns:"120px 80px 1fr 100px 90px 80px", gap:8, padding:"12px 14px", alignItems:"center", cursor:"pointer" }}>
                  {/* Ticker */}
                  <div>
                    <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                      <span style={{ color:s.asset_type==="crypto"?"#f7931a":"#00d4ff", fontWeight:"bold", fontSize:15 }}>{s.ticker}</span>
                      {s.turbo && <span style={{ fontSize:8, background:"rgba(192,132,252,0.15)", color:"#c084fc", padding:"1px 5px", borderRadius:3, fontFamily:"sans-serif" }}>TURBO</span>}
                      {method==="atr" && <span style={{ fontSize:8, background:"rgba(0,255,136,0.1)", color:"#00ff88", padding:"1px 5px", borderRadius:3, fontFamily:"sans-serif" }}>ATR</span>}
                      {s.trailing_sl_active && <span style={{ fontSize:8, background:"rgba(0,212,255,0.1)", color:"#00d4ff", padding:"1px 5px", borderRadius:3, fontFamily:"sans-serif" }}>TSL</span>}
                      {s.advisor_verdict && s.advisor_verdict !== 'APPROVE' && (
                        <span style={{
                          fontSize:8,
                          background: s.advisor_verdict==='VETO' ? 'rgba(255,68,102,0.15)' : 'rgba(251,191,36,0.15)',
                          color:       s.advisor_verdict==='VETO' ? '#ff4466' : '#fbbf24',
                          padding:'1px 5px', borderRadius:3, fontFamily:'sans-serif',
                          border: `1px solid ${s.advisor_verdict==='VETO'?'#ff446644':'#fbbf2444'}`,
                        }}>
                          {s.advisor_verdict==='VETO' ? '\u26d4 VETOED' : '\u26a0\ufe0f FLAGGED'}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif", marginTop:2 }}>{s.entry_time?.slice(0,10)} &middot; {s.entry_session||""}</div>
                  </div>
                  {/* Conviction */}
                  <div style={{ textAlign:"center" }}>
                    <div style={{ fontSize:16, fontWeight:"bold", color:s.conviction>=70?"#00ff88":s.conviction>=60?"#fbbf24":s.conviction>0?"#94a3b8":"#2a4a5a" }}>{s.conviction||"-"}%</div>
                    <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif" }}>{s.tas}</div>
                    {isOpen && s.live_score != null && (
                      <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:3, marginTop:3 }}>
                        <span style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif" }}>{s.live_score}%</span>
                        <ScoreTrendArrow score={s.live_score} prev={s.live_score_prev} />
                        <TradeStateBadge state={s.trade_state} />
                      </div>
                    )}
                  </div>
                  {/* Price */}
                  <div style={{ display:"flex", gap:12, alignItems:"center", flexWrap:"wrap" }}>
                    <span style={{ fontSize:11, color:"#94a3b8" }}>${s.entry_price}</span>
                    <span style={{ color:"#2a4a5a" }}>&rarr;</span>
                    <span style={{ fontSize:13, fontWeight:"bold", color:pnlColor(s.pnl_pct) }}>${s.current_price||s.close_price}</span>
                    <span
                      onClick={e => { e.stopPropagation(); setSlDropdown(slDropdown===s.id?null:s.id); }}
                      title="Click to see SL history"
                      style={{ fontSize:9, color:s.trailing_sl_active?"#00d4ff":"#ff4466", fontFamily:"sans-serif", cursor:"pointer", textDecoration:"underline dotted", textUnderlineOffset:2 }}>
                      SL ${s.sl}{s.trailing_sl_active?" ⟳":""}
                    </span>
                    <span
                      onClick={e => { e.stopPropagation(); setSlDropdown(slDropdown===s.id?null:s.id); }}
                      title="Click to see SL/target history"
                      style={{ fontSize:9, color:s.tp1_hit?"#00ff88":"#8899aa", fontWeight:s.tp1_hit?"bold":"normal", fontFamily:"sans-serif", cursor:"pointer", textDecoration:"underline dotted", textUnderlineOffset:2 }}>
                      TP1 ${s.tp1}{s.tp1_hit?" ✓":""}
                    </span>
                  </div>
                  {/* P&L */}
                  <div style={{ textAlign:"right" }}>
                    <div style={{ display:"flex", alignItems:"center", justifyContent:"flex-end", gap:4 }}>
                      {s.pnl_pct>0?<TrendingUp size={14} color="#00ff88"/>:s.pnl_pct<0?<TrendingDown size={14} color="#ff4466"/>:null}
                      <span style={{ color:pnlColor(s.pnl_pct), fontWeight:"bold", fontSize:16 }}>{s.pnl_pct>0?"+":""}{s.pnl_pct}%</span>
                    </div>
                    {(s.mae_pct!==0||s.mfe_pct!==0) && (
                      <div style={{ fontSize:8, color:"#2a4a5a", fontFamily:"sans-serif", marginTop:2 }}>MAE {s.mae_pct}% &middot; MFE +{s.mfe_pct}%</div>
                    )}
                  </div>
                  {/* Status */}
                  <div style={{ textAlign:"center" }}>
                    <span style={{ fontSize:10, fontWeight:"bold", padding:"3px 8px", borderRadius:3, fontFamily:"sans-serif", background:`${statusColor(s.status)}15`, color:statusColor(s.status), border:`1px solid ${statusColor(s.status)}33` }}>
                      {statusLabel(s.status)}
                    </span>
                    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:3, marginTop:4 }}>
                      <Clock size={9} color="#2a4a5a" />
                      <span style={{ fontSize:9, color:isOpen?"#00d4ff":"#8899aa", fontFamily:"sans-serif", fontWeight:isOpen?"bold":"normal" }}>{duration}</span>
                    </div>
                    {!isOpen && s.close_reason && (
                      <div style={{ fontSize:8, color:"#8899aa", fontFamily:"sans-serif", marginTop:2, maxWidth:88, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", margin:"2px auto 0" }} title={s.close_reason}>{s.close_reason}</div>
                    )}
                  </div>
                  {/* Actions -- Override SL button always visible on active tab, no scan_data dependency */}
                  <div style={{ display:"flex", gap:4, justifyContent:"flex-end", alignItems:"center" }} onClick={e => e.stopPropagation()}>
                    {tab==='active' && (
                      <>
                        <button onClick={() => setOverrideSLFor(showOverride?null:s.id)} title="Override Stop-Loss"
                          style={{ background:showOverride?"rgba(192,132,252,0.15)":"transparent", border:`1px solid ${showOverride?"#c084fc":"#2a4a5a"}`, borderRadius:3, padding:"3px 6px", color:showOverride?"#c084fc":"#8899aa", fontSize:9, cursor:"pointer", fontFamily:"sans-serif", display:"flex", alignItems:"center", gap:3 }}>
                          <Shield size={10} /><span style={{fontSize:8}}>SL</span>
                        </button>
                        <button onClick={() => closeSignal(s.id)}
                          style={{ background:"transparent", border:"1px solid #ff446633", borderRadius:3, padding:"3px 6px", color:"#ff4466", fontSize:9, cursor:"pointer" }}>
                          <X size={10} />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* EXIT warning banner */}
                {isOpen && s.trade_state === 'EXIT' && (
                  <div style={{ borderTop:"1px solid #ff446633", padding:"7px 14px", background:"rgba(255,68,102,0.07)", display:"flex", alignItems:"center", gap:8 }}>
                    <AlertTriangle size={13} color="#ff4466" style={{ flexShrink:0, animation:"st-pulse 1.5s ease-in-out infinite" }} />
                    <span style={{ fontSize:10, color:"#ff4466", fontFamily:"sans-serif", fontWeight:"bold" }}>
                      &#9888; Score below threshold — consider closing this position
                    </span>
                    <span style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif", marginLeft:"auto" }}>
                      Live score: {s.live_score}%
                    </span>
                  </div>
                )}

                {/* SL History Dropdown — click SL or TP1 in the main row to toggle */}
                {slDropdown===s.id && isOpen && (
                  <SLHistoryPanel signal={s} entryTime={s.entry_time} onClose={() => setSlDropdown(null)} />
                )}

                {/* BENCH row — top 2 replacement candidates for this position */}
                {tab==='active' && isOpen && (() => {
                  const bench = getBenchFor(s, scanCandidates);
                  if (bench.length === 0) return null;
                  return (
                    <div style={{ borderTop:'1px solid #0d1520', padding:'5px 14px', display:'flex', alignItems:'center', gap:8, background:'rgba(0,212,255,0.025)', flexWrap:'wrap' }}
                      onClick={e => e.stopPropagation()}>
                      <span style={{ fontSize:8, color:'#2a4a5a', fontFamily:'sans-serif', fontWeight:'bold', whiteSpace:'nowrap' }}>BENCH →</span>
                      {bench.map((c, ci) => (
                        <React.Fragment key={c.ticker}>
                          <div style={{ display:'flex', alignItems:'center', gap:4 }}>
                            <span style={{ fontSize:10, fontWeight:'bold', color:'#00d4ff', fontFamily:'monospace' }}>{c.ticker}</span>
                            <span style={{ fontSize:9, color:'#8899aa', fontFamily:'sans-serif' }}>{c.conviction_pct}%</span>
                            <span style={{ fontSize:9, color:c.trend==='BULL'?'#00ff88':'#ff4466', fontFamily:'sans-serif' }}>{c.trend||'—'}</span>
                            <button onClick={e => openBenchTicker(c, e)}
                              style={{ background:'rgba(192,132,252,0.12)', border:'1px solid #c084fc44', borderRadius:3, padding:'1px 7px', color:'#c084fc', fontSize:8, cursor:'pointer', fontFamily:'sans-serif', fontWeight:'bold' }}>
                              OPEN
                            </button>
                          </div>
                          {ci < bench.length - 1 && <span style={{ color:'#1a2535', fontSize:10 }}>|</span>}
                        </React.Fragment>
                      ))}
                    </div>
                  );
                })()}

                {/* Override SL form -- renders for any active/open signal regardless of scan_data */}
                {showOverride && isOpen && (
                  <div style={{ padding:"0 14px 14px" }}>
                    <OverrideSLForm signal={s} onSave={() => { setOverrideSLFor(null); fetchSignals(true); }} onCancel={() => setOverrideSLFor(null)} />
                  </div>
                )}

                {/* Expanded Panel */}
                {isExpanded && (
                  <div style={{ background:"#080c14", borderTop:"1px solid #1a2535", padding:16 }}>
                    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:20, marginBottom:16 }}>
                      {/* EntryReasonPanel: shows legacy placeholder if no scan_data */}
                      <EntryReasonPanel signal={s} />
                      {isOpen
                        ? <TSLStatusPanel signal={s} />
                        : (
                          <div>
                            <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:10, letterSpacing:1 }}>TARGETS ({method.toUpperCase()})</div>
                            <div style={{ fontSize:10, color:"#94a3b8", fontFamily:"sans-serif", lineHeight:1.9 }}>
                              <div>SL: <b style={{color:"#ff4466"}}>${s.sl}</b>{s.original_sl&&s.sl!==s.original_sl?<span style={{color:"#2a4a5a"}}> (orig ${s.original_sl})</span>:null}</div>
                              <div>TP1: <b style={{color:s.tp1_hit?"#00ff88":"#94a3b8"}}>${s.tp1}</b>{s.tp1_hit?" ✓":""}</div>
                              <div>TP2: <b style={{color:s.tp2_hit?"#00ff88":"#94a3b8"}}>${s.tp2}</b>{s.tp2_hit?" ✓":""}</div>
                              <div>TP3: <b style={{color:s.tp3_hit?"#00ff88":"#94a3b8"}}>${s.tp3}</b>{s.tp3_hit?" ✓":""}</div>
                              <div>R:R <b>{s.rr}</b>:1{s.atr_at_entry?` &middot; ATR $${s.atr_at_entry}`:""}</div>
                              <div style={{marginTop:4}}>High <b style={{color:"#00ff88"}}>${s.highest_price}</b> &middot; Low <b style={{color:"#ff4466"}}>${s.lowest_price}</b></div>
                              <div>MAE <b style={{color:"#ff4466"}}>{s.mae_pct}%</b> &middot; MFE <b style={{color:"#00ff88"}}>+{s.mfe_pct}%</b></div>
                              {s.slippage_pct>0&&<div>Gap Slippage: <b style={{color:"#f97316"}}>{s.slippage_pct}%</b></div>}
                            </div>
                          </div>
                        )
                      }
                      <div>
                        {s.close_reason && (
                          <>
                            <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:8, letterSpacing:1 }}>EXIT</div>
                            <div style={{ fontSize:10, color:"#94a3b8", fontFamily:"sans-serif", lineHeight:1.8 }}>
                              <div style={{ color:s.pnl_pct>=0?"#00ff88":"#ff4466", fontWeight:"bold", marginBottom:4 }}>{s.close_reason}</div>
                              <div>Close: <b>${s.close_price}</b></div>
                              {s.close_market_context&&<div>Exit Regime: <b style={{color:"#fbbf24"}}>{s.close_market_context.regime}</b></div>}
                              {s.gap_info&&<div style={{color:"#f97316"}}>Gap: {s.gap_info.note}</div>}
                            </div>
                          </>
                        )}
                        {s.entry_snapshot&&Object.keys(s.entry_snapshot).length>0&&!s.entry_snapshot.error&&(
                          <>
                            <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:6, marginTop:s.close_reason?12:0, letterSpacing:1 }}>INDICATORS AT ENTRY</div>
                            <div style={{ fontSize:9, color:"#8899aa", fontFamily:"monospace", lineHeight:1.6, maxHeight:90, overflow:"auto" }}>
                              {Object.entries(s.entry_snapshot).filter(([k]) => !['price_data','error','fib_levels','tf_breakdown','fvg_zones','confluence_zones','lr_channel'].includes(k)).map(([k,v]) => (
                                <div key={k}>{k}: {typeof v==='object'?JSON.stringify(v):String(v)}</div>
                              ))}
                            </div>
                          </>
                        )}
                        <div style={{ marginTop:10, background:"#0d1520", borderRadius:4, padding:"6px 10px", display:"inline-flex", alignItems:"center", gap:5 }}>
                          <Clock size={10} color="#8899aa" />
                          <span style={{ fontSize:10, color:isOpen?"#00d4ff":"#8899aa", fontFamily:"sans-serif" }}>{isOpen?`Open for ${duration}`:`Held for ${duration}`}</span>
                        </div>
                      </div>
                    </div>


                    {/* Advisor Panel */}
                    {(s.advisor_verdict || isOpen) && (
                      <div style={{ borderTop:'1px solid #1a2535', paddingTop:14, marginTop:4 }}>
                        <div style={{ fontSize:9, fontWeight:'bold', color:'#c084fc', fontFamily:'sans-serif', marginBottom:8, letterSpacing:1, display:'flex', alignItems:'center', gap:6, justifyContent:'space-between' }}>
                          <span>&#129302; ADVISOR</span>
                          {isOpen && (
                            <button onClick={e => { e.stopPropagation(); setAskOpusOpen(askOpusOpen===s.id?null:s.id); }}
                              style={{ fontSize:8, background:'rgba(192,132,252,0.12)', border:'1px solid #c084fc44', color:'#c084fc', borderRadius:3, padding:'2px 7px', cursor:'pointer', fontFamily:'sans-serif' }}>
                              {askOpusOpen===s.id ? 'Close' : 'Ask Opus'}
                            </button>
                          )}
                        </div>
                        {s.advisor_verdict && (
                          <div style={{ display:'flex', alignItems:'flex-start', gap:8, marginBottom:8 }}>
                            <span style={{
                              fontSize:9, fontWeight:'bold', padding:'2px 7px', borderRadius:3, fontFamily:'sans-serif', whiteSpace:'nowrap',
                              background: s.advisor_verdict==='APPROVE' ? 'rgba(0,255,136,0.1)' : s.advisor_verdict==='FLAG' ? 'rgba(251,191,36,0.1)' : 'rgba(255,68,102,0.1)',
                              color:       s.advisor_verdict==='APPROVE' ? '#00ff88'             : s.advisor_verdict==='FLAG' ? '#fbbf24'             : '#ff4466',
                            }}>
                              {s.advisor_verdict==='APPROVE' ? '\u2705 APPROVED' : s.advisor_verdict==='FLAG' ? '\u26a0\ufe0f FLAGGED' : '\u26d4 VETOED'}
                              {s.advisor_confidence ? ` ${s.advisor_confidence}%` : ''}
                            </span>
                            {s.advisor_thesis && (
                              <span style={{ fontSize:9, color:'#8899aa', fontFamily:'sans-serif', lineHeight:1.5, fontStyle:'italic' }}>{s.advisor_thesis}</span>
                            )}
                          </div>
                        )}
                        {s.advisor_concerns && s.advisor_concerns.length > 0 && (
                          <div style={{ display:'flex', flexWrap:'wrap', gap:4, marginBottom:8 }}>
                            {s.advisor_concerns.map((c,i) => (
                              <span key={i} style={{ fontSize:8, background:'rgba(251,191,36,0.08)', border:'1px solid #fbbf2433', color:'#fbbf24', padding:'2px 6px', borderRadius:3, fontFamily:'sans-serif' }}>{c}</span>
                            ))}
                          </div>
                        )}
                        {askOpusOpen===s.id && (
                          <div style={{ marginTop:6 }}>
                            <div style={{ display:'flex', gap:6 }}>
                              <input
                                value={advisorInput[s.id]||''}
                                onChange={e => setAdvisorInput(v=>({...v,[s.id]:e.target.value}))}
                                onKeyDown={e => { e.stopPropagation(); if(e.key==='Enter') askOpus(s.id); }}
                                onClick={e => e.stopPropagation()}
                                placeholder="Ask Opus anything about this signal..."
                                style={{ flex:1, background:'#050810', border:'1px solid #c084fc44', borderRadius:4, padding:'5px 8px', color:'#e2e8f0', fontSize:10, fontFamily:'sans-serif', outline:'none' }}
                              />
                              <button onClick={e => { e.stopPropagation(); askOpus(s.id); }}
                                disabled={advisorReply[s.id]?.loading}
                                style={{ background:'#c084fc22', border:'1px solid #c084fc44', color:'#c084fc', borderRadius:4, padding:'4px 10px', fontSize:9, cursor:'pointer', fontFamily:'sans-serif' }}>
                                {advisorReply[s.id]?.loading ? '...' : 'Ask'}
                              </button>
                            </div>
                            {advisorReply[s.id]?.answer && (
                              <div style={{ marginTop:8, background:'rgba(192,132,252,0.06)', border:'1px solid #c084fc22', borderRadius:6, padding:'8px 10px', fontSize:10, color:'#c084fc', fontFamily:'sans-serif', lineHeight:1.6 }}>
                                <span style={{ fontSize:8, color:'#8899aa', display:'block', marginBottom:4 }}>OPUS SAYS</span>
                                {advisorReply[s.id].answer}
                              </div>
                            )}
                            {advisorReply[s.id]?.error && (
                              <div style={{ marginTop:6, fontSize:9, color:'#ff4466', fontFamily:'sans-serif' }}>Error: {advisorReply[s.id].error}</div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                    {/* Per-signal action log -- always renders, shows placeholder for legacy signals */}
                    <div style={{ borderTop:"1px solid #1a2535", paddingTop:14 }}>
                      <div style={{ fontSize:9, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", marginBottom:8, letterSpacing:1, display:"flex", alignItems:"center", gap:6 }}>
                        <Activity size={10} /> TRADE LOG &#8212; {s.ticker}
                      </div>
                      <SignalActionLog log={s.action_log} />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* SYSTEM ACTION LOG -- global feed, all signals */}
      <div style={{ marginTop:32, background:"#0a0f18", border:"1px solid #1a2535", borderRadius:12, overflow:"hidden" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"12px 16px", borderBottom:"1px solid #1a2535", background:"#080c14" }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <Zap size={14} color="#c084fc" />
            <span style={{ fontSize:12, fontWeight:"bold", color:"#c084fc", fontFamily:"sans-serif", letterSpacing:1 }}>SYSTEM ACTION LOG</span>
            <span style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif" }}>last {Math.min(globalLog.length,50)} events &middot; all signals</span>
          </div>
          <div style={{ display:"flex", gap:12, fontSize:9, fontFamily:"sans-serif" }}>
            <span style={{color:"#00ff88"}}>&#9679; profit</span>
            <span style={{color:"#ff4466"}}>&#9679; risk</span>
            <span style={{color:"#00d4ff"}}>&#9679; neutral</span>
          </div>
        </div>
        {globalLog.length===0 ? (
          <div style={{ padding:"30px", textAlign:"center", color:"#8899aa", fontFamily:"sans-serif", fontSize:12 }}>
            No actions recorded yet &#8212; start a signal to begin logging
          </div>
        ) : (
          <div style={{ maxHeight:400, overflowY:"auto" }}>
            {globalLog.map((e,i) => (
              <div key={i} style={{ display:"grid", gridTemplateColumns:"52px 58px 130px 1fr", padding:"7px 16px", borderBottom:"1px solid #0d1520", alignItems:"center", background:i%2===0?"transparent":"rgba(255,255,255,0.01)" }}>
                <span style={{ fontSize:9, color:"#2a4a5a", fontFamily:"monospace" }}>{fmt(e.ts)}</span>
                <span style={{ fontSize:10, fontWeight:"bold", color:e.category==="profit"?"#00ff88":e.category==="risk"?"#ff4466":"#00d4ff", fontFamily:"monospace" }}>{e.ticker||"-"}</span>
                <span style={{ fontSize:9, fontWeight:"bold", color:actionColor(e.category), fontFamily:"monospace", background:`${actionColor(e.category)}12`, padding:"1px 6px", borderRadius:3, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{e.action}</span>
                <span style={{ fontSize:9, color:"#8899aa", fontFamily:"sans-serif", paddingLeft:10 }}>{e.detail}</span>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
};

export default SignalTracker;
