import React, { useState } from 'react';
import { Search, RefreshCw, Flame, BarChart2 } from 'lucide-react';

// ── Color helpers (from SwingTrader v4.3) ──
const convColor = p => p >= 75 ? "#00ff88" : p >= 60 ? "#fbbf24" : p >= 45 ? "#94a3b8" : "#ff4466";
const convIcon = p => p >= 75 ? "🟢" : p >= 60 ? "🟡" : p >= 45 ? "⬜" : "🔴";
const trendColor = t => t === "BULL" ? "#00ff88" : t === "BEAR" ? "#ff4466" : "#fbbf24";
const tasColor = t => { const n = parseInt(t); return n >= 4 ? "#00ff88" : n === 3 ? "#7ee8ff" : n === 2 ? "#fbbf24" : "#ff4466"; };
const maColor = m => m === "above" ? "#00ff88" : "#ff4466";
const volDirColor = v => v === "ACCUMULATION" ? "#00ff88" : v === "DISTRIBUTION" ? "#ff4466" : "#fbbf24";
const regimeColor = r => r?.includes("Bull") ? "#00ff88" : r?.includes("Bear") ? "#ff4466" : "#fbbf24";
const heatColors = {
  TOP: { bg: "rgba(0,255,136,0.12)", fg: "#00ff88", border: "rgba(0,255,136,0.3)" },
  Hot: { bg: "rgba(251,191,36,0.12)", fg: "#fbbf24", border: "rgba(251,191,36,0.3)" },
  Neutral: { bg: "rgba(148,163,184,0.1)", fg: "#94a3b8", border: "rgba(148,163,184,0.2)" },
  Cold: { bg: "rgba(255,68,102,0.1)", fg: "#ff4466", border: "rgba(255,68,102,0.2)" },
};

// ── TF Breakdown badges ──
const TFBadges = ({ tf }) => {
  if (!tf) return null;
  return (
    <div style={{ display: "flex", gap: 3, marginTop: 4, flexWrap: "wrap" }}>
      {[["tf_65m","65m"],["tf_240m","4H"],["tf_daily","1D"],["tf_weekly","1W"]].map(([key,label]) => {
        const val = tf[key] || "—";
        const c = val === "BULL" ? "#00ff88" : val === "BEAR" ? "#ff4466" : "#fbbf24";
        return <span key={key} style={{ fontSize:8, background:`${c}18`, color:c, border:`1px solid ${c}44`, padding:"1px 4px", borderRadius:2, fontFamily:"monospace" }}>{label}</span>;
      })}
    </div>
  );
};

// ── Pillar mini bars ──
const PillarBar = ({ scores }) => {
  if (!scores) return null;
  const pillars = [["p1","P1","#00d4ff"],["p2","P2","#7c3aed"],["p3","P3","#00ff88"],["p4","P4","#fbbf24"],["p5","P5","#ff4466"]];
  return (
    <div style={{ display:"flex", gap:3, marginTop:5 }}>
      {pillars.map(([key,label,color]) => (
        <div key={key} style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:2 }}>
          <div style={{ width:18, height:32, background:"rgba(255,255,255,0.05)", borderRadius:2, position:"relative", overflow:"hidden" }}>
            <div style={{ position:"absolute", bottom:0, left:0, right:0, height:`${scores[key]||0}%`, background:color, opacity:0.75, transition:"height 0.8s ease" }} />
          </div>
          <span style={{ fontSize:8, color:"#8899aa", fontFamily:"monospace" }}>{label}</span>
        </div>
      ))}
    </div>
  );
};

const ScanDashboard = () => {
  const [tickers, setTickers] = useState('AAPL, NVDA, TSLA, AMD, MSFT');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(new Set());
  const [watchlists, setWatchlists] = useState(null);
  const [sectorHeat, setSectorHeat] = useState(null);
  const [heatLoading, setHeatLoading] = useState(false);
  const [activeSector, setActiveSector] = useState(null);

  // Fetch watchlists on mount
  React.useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
    fetch(`${apiUrl}/api/watchlists`).then(r => r.json()).then(d => setWatchlists(d.watchlists)).catch(() => {});
  }, []);

  const fetchSectorHeat = async () => {
    setHeatLoading(true);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
    try {
      const res = await fetch(`${apiUrl}/api/sectors/heat`);
      const d = await res.json();
      setSectorHeat(d.sectors || []);
    } catch (e) { setSectorHeat([]); }
    setHeatLoading(false);
  };

  const loadSector = async (key) => {
    setActiveSector(key);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
    try {
      const res = await fetch(`${apiUrl}/api/sectors/watchlist/${key}`);
      const d = await res.json();
      setTickers(d.tickers.join(', '));
    } catch (e) {}
  };

  const loadWatchlist = async (name) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
    const res = await fetch(`${apiUrl}/api/watchlists/${name}`);
    const d = await res.json();
    setTickers(d.tickers.join(', '));
  };

  const runScan = async () => {
    setLoading(true);
    setError(null);
    setData(null);
    setProgress('Starting scan...');
    const symbols = tickers.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
    try {
      // Step 1 — start the job
      const startRes = await fetch(`${apiUrl}/api/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols })
      });
      if (!startRes.ok) throw new Error(`API error ${startRes.status}`);
      const { job_id } = await startRes.json();

      // Step 2 — poll for completion every 2 seconds
      await new Promise((resolve, reject) => {
        const poll = async () => {
          try {
            const statusRes = await fetch(`${apiUrl}/api/scan/status/${job_id}`);
            if (!statusRes.ok) throw new Error(`Status error ${statusRes.status}`);
            const job = await statusRes.json();
            setProgress(job.progress || '');
            if (job.status === 'complete') {
              const json = job.results;
              setData(json);
              const top3 = (json.results || []).filter(r => !r.hard_fail).slice(0,3).map(r => r.ticker);
              setExpanded(new Set(top3));
              resolve();
            } else if (job.status === 'error') {
              reject(new Error(job.error || 'Scan failed'));
            } else {
              setTimeout(poll, 2000);
            }
          } catch (e) { reject(e); }
        };
        poll();
      });
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
    setProgress('');
  };

  const toggleExpand = (ticker) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  };

  return (
    <div style={{ background:"#050810", padding:"20px 16px", fontFamily:"'Courier New',monospace", color:"#c9d8e8" }}>
      {/* Header */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", borderBottom:"1px solid #1a2535", paddingBottom:14, marginBottom:20 }}>
        <div>
          <span style={{ fontWeight:"bold", fontSize:22 }}>Swing<span style={{ color:"#00d4ff" }}>Trader</span> AI</span>
          <span style={{ color:"#7c3aed", fontSize:11, fontWeight:"bold", background:"rgba(124,58,237,0.15)", border:"1px solid rgba(124,58,237,0.3)", padding:"1px 7px", borderRadius:3, marginLeft:10 }}>v4.3</span>
          <div style={{ color:"#2a4a5a", fontSize:10, marginTop:2, fontFamily:"sans-serif" }}>TAS GATE · 150MA · VOL DIRECTION · 5-PILLAR</div>
        </div>
        {data?.market_regime && (
          <div style={{ display:"flex", gap:10, alignItems:"center" }}>
            <div style={{ background:"rgba(0,0,0,0.4)", border:`1px solid ${regimeColor(data.market_regime)}33`, borderRadius:6, padding:"5px 12px", fontFamily:"sans-serif" }}>
              <span style={{ color:"#8899aa", fontSize:9, letterSpacing:1.5 }}>REGIME </span>
              <span style={{ color:regimeColor(data.market_regime), fontSize:11, fontWeight:"bold" }}>{data.market_regime}</span>
              {data.vix_estimate > 0 && <span style={{ color:"#8899aa", fontSize:9, marginLeft:8 }}>VIX {data.vix_estimate}</span>}
            </div>
          </div>
        )}
      </div>

      {/* Sector Heat Map */}
      <div style={{ background:"#0a0f18", border:"1px solid #1a2535", borderRadius:8, padding:"12px 14px", marginBottom:12 }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:8 }}>
          <div style={{ display:"flex", alignItems:"center", gap:6, color:"#fbbf24", fontSize:10, fontWeight:"bold", fontFamily:"sans-serif", letterSpacing:1 }}>
            <Flame size={12} /> SECTOR HEAT
          </div>
          <button onClick={fetchSectorHeat} disabled={heatLoading}
            style={{ background:"#0d1520", border:"1px solid #1a2535", borderRadius:4, padding:"3px 10px",
              color:"#00d4ff", fontSize:10, fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:4 }}>
            {heatLoading ? <RefreshCw size={10} className="spin" /> : <BarChart2 size={10} />}
            {heatLoading ? 'Scoring...' : 'Score Sectors'}
          </button>
        </div>

        {/* 11 Sector buttons */}
        {[
          ["information_technology","💻 Info Tech"],["financials","🏦 Financials"],["health_care","💊 Health Care"],
          ["industrials","⚙️ Industrials"],["consumer_discretionary","🛍 Cons. Disc."],["consumer_staples","🛒 Cons. Staples"],
          ["energy","⛽ Energy"],["communication_services","📡 Comm. Svcs"],["utilities","⚡ Utilities"],
          ["materials","🪨 Materials"],["real_estate","🏢 Real Estate"]
        ].map(([key, label]) => {
          const heat = sectorHeat?.find(s => s.key === key);
          const isActive = activeSector === key;
          const heatC = heat ? (heat.heat === "HOT" ? "#00ff88" : heat.heat === "WARM" ? "#fbbf24" : "#ff4466") : "#8899aa";
          return (
            <button key={key} onClick={() => loadSector(key)}
              style={{ background: isActive ? "#1a2535" : "#080c14", border:`1px solid ${isActive ? heatC : "#1a2535"}`,
                borderRadius:5, padding:"5px 10px", color: isActive ? heatC : "#94a3b8",
                fontSize:10, fontFamily:"sans-serif", cursor:"pointer", margin:"2px 3px", display:"inline-flex", alignItems:"center", gap:5 }}>
              {label}
              {heat && <span style={{ color:heatC, fontWeight:"bold", fontSize:9 }}>{heat.score}%</span>}
            </button>
          );
        })}

        {/* Heat ranking */}
        {sectorHeat?.length > 0 && (
          <div style={{ marginTop:10, display:"flex", gap:5, flexWrap:"wrap" }}>
            {sectorHeat.map((s, i) => {
              const c = s.heat === "HOT" ? "#00ff88" : s.heat === "WARM" ? "#fbbf24" : "#ff4466";
              return (
                <div key={s.key} onClick={() => loadSector(s.key)}
                  style={{ background:`${c}10`, border:`1px solid ${c}33`, borderRadius:5, padding:"4px 10px",
                    cursor:"pointer", display:"flex", alignItems:"center", gap:6 }}>
                  <span style={{ color:"#8899aa", fontSize:8, fontFamily:"sans-serif" }}>#{i+1}</span>
                  <span style={{ color:"#c9d8e8", fontSize:10, fontFamily:"sans-serif" }}>{s.etf}</span>
                  <span style={{ color:c, fontWeight:"bold", fontSize:11 }}>{s.score}%</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Watchlist Quick-Select */}
      {watchlists && (
        <div style={{ display:"flex", gap:6, marginBottom:10, flexWrap:"wrap" }}>
          {Object.entries(watchlists).map(([k, v]) => (
            <button key={k} onClick={() => loadWatchlist(k)}
              style={{ background:"#0d1520", border:"1px solid #1a2535", borderRadius:4, padding:"4px 10px", color:"#7ee8ff", fontSize:10, fontFamily:"sans-serif", cursor:"pointer", transition:"all 0.2s" }}
              onMouseOver={e => { e.target.style.background="#1a2535"; e.target.style.borderColor="#7ee8ff"; }}
              onMouseOut={e => { e.target.style.background="#0d1520"; e.target.style.borderColor="#1a2535"; }}
            >{v.label} ({v.count})</button>
          ))}
        </div>
      )}

      {/* Ticker input */}
      <div style={{ display:"flex", gap:10, marginBottom:14 }}>
        <input
          value={tickers}
          onChange={e => setTickers(e.target.value.toUpperCase())}
          placeholder="AAPL, NVDA, TSLA, AMD..."
          style={{ flex:1, background:"#0a0f18", border:"1px solid #1a2535", borderRadius:6, padding:"10px 14px", color:"#c9d8e8", fontFamily:"monospace", fontSize:13, outline:"none" }}
          onKeyDown={e => e.key === 'Enter' && runScan()}
        />
        <button onClick={runScan} disabled={loading} style={{ background:"linear-gradient(135deg,#0d2040,#0a1628)", border:"1px solid #1e3a5a", color:"#00d4ff", fontSize:11, fontWeight:"bold", padding:"7px 16px", borderRadius:6, cursor:loading?"wait":"pointer", fontFamily:"sans-serif", display:"flex", alignItems:"center", gap:6 }}>
          {loading ? <RefreshCw size={14} className="spin" /> : <Search size={14} />}
          {loading ? (progress || 'SCANNING...') : 'RUN SCAN'}
        </button>
      </div>

      {/* Market header */}
      {data?.market_header && (
        <div style={{ background:"linear-gradient(135deg,#080c14,#0a1020)", border:"1px solid #1a2535", borderRadius:8, padding:"14px 18px", marginBottom:14 }}>
          <div style={{ color:"#2a4a5a", fontSize:9, letterSpacing:2, fontFamily:"sans-serif", fontWeight:"bold", marginBottom:8 }}>📡 MARKET CONTEXT</div>
          <div style={{ fontSize:12, lineHeight:1.9, color:"#94a3b8", fontFamily:"sans-serif" }}>{data.market_header}</div>
        </div>
      )}

      {error && <div style={{ background:"rgba(255,68,102,0.08)", border:"1px solid rgba(255,68,102,0.3)", borderRadius:8, padding:"16px", color:"#ff4466", fontFamily:"sans-serif" }}>❌ {error}</div>}

      {/* Results table */}
      {data?.results?.length > 0 && (
        <div style={{ overflowX:"auto", borderRadius:8, border:"1px solid #1a2535", marginBottom:14 }}>
          <table style={{ width:"100%", borderCollapse:"collapse", background:"#080c14", whiteSpace:"nowrap", minWidth:1400 }}>
            <thead>
              <tr>
                {["Ticker","Price","Cap","Conviction","Heat","TAS","MA150","Trend","Vol Dir","Entry","SL","TP1","TP2","Qty","Vol×","Earnings","TA Note"].map(h => (
                  <th key={h} style={{ background:"#0a0f18", color:"#2a4a5a", fontSize:9, letterSpacing:1.2, textTransform:"uppercase", padding:"10px 8px", textAlign:"left", borderBottom:"1px solid #1a2535", fontFamily:"sans-serif" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.results.map(r => {
                const hc = heatColors[r.heat] || heatColors.Neutral;
                const isHF = r.hard_fail;
                const isExp = expanded.has(r.ticker);
                const td = { padding:"10px 8px", borderBottom:"1px solid #0d1420", verticalAlign:"middle", background:isHF?"rgba(255,68,102,0.04)":"transparent", opacity:isHF?0.6:1 };
                return (
                  <React.Fragment key={r.ticker}>
                    <tr onClick={() => r.plan && toggleExpand(r.ticker)} style={{ cursor:r.plan?"pointer":"default" }}>
                      <td style={td}>
                        <div style={{ display:"flex", alignItems:"center", gap:5 }}>
                          {r.plan && <span style={{ color:"#2a4a5a", fontSize:10, transform:isExp?"rotate(90deg)":"none", display:"inline-block", transition:"transform 0.2s" }}>▶</span>}
                          <div>
                            <div style={{ color:"#00d4ff", fontWeight:"bold", fontSize:13 }}>{r.ticker}</div>
                            <div style={{ color:"#2a4a5a", fontSize:9, fontFamily:"sans-serif" }}>{r.name}</div>
                          </div>
                        </div>
                      </td>
                      <td style={td}><div style={{ fontWeight:"bold", fontSize:13 }}>{r.last_close ? `$${r.last_close}` : "—"}</div><div style={{ fontSize:9, color:"#2a4a5a", fontFamily:"sans-serif" }}>{r.last_date}</div></td>
                      <td style={{...td, fontFamily:"sans-serif", fontSize:11, color:"#8899aa"}}>{r.mkt_cap_b ? `$${r.mkt_cap_b}B` : "—"}</td>
                      <td style={td}>{isHF ? <div><span style={{ color:"#ff4466", fontSize:11, fontWeight:"bold" }}>HARD FAIL</span><div style={{ color:"#ff4466", fontSize:9, fontFamily:"sans-serif", maxWidth:130, whiteSpace:"normal", lineHeight:1.4 }}>{r.hard_fail_reason}</div></div> : <div><span style={{ color:convColor(r.conviction_pct), fontWeight:"bold", fontSize:15 }}>{convIcon(r.conviction_pct)} {r.conviction_pct}%</span><PillarBar scores={r.pillar_scores} /></div>}</td>
                      <td style={td}><span style={{ background:hc.bg, color:hc.fg, border:`1px solid ${hc.border}`, fontSize:10, fontWeight:"bold", padding:"3px 8px", borderRadius:3, fontFamily:"sans-serif" }}>{r.heat}</span></td>
                      <td style={td}><div style={{ fontWeight:"bold", fontSize:13, color:tasColor(r.tas) }}>{r.tas||"—"}</div><TFBadges tf={r.tf_breakdown} /></td>
                      <td style={td}><span style={{ fontSize:10, fontFamily:"sans-serif", fontWeight:"bold", color:maColor(r.ma150_position), background:`${maColor(r.ma150_position)}15`, border:`1px solid ${maColor(r.ma150_position)}33`, padding:"2px 7px", borderRadius:3 }}>{(r.ma150_position||"—").toUpperCase()}</span></td>
                      <td style={td}><span style={{ color:trendColor(r.trend), fontWeight:"bold", fontSize:12, fontFamily:"sans-serif" }}>{r.trend}</span></td>
                      <td style={td}>{r.vol_direction ? <span style={{ fontSize:9, fontFamily:"sans-serif", fontWeight:"bold", color:volDirColor(r.vol_direction), background:`${volDirColor(r.vol_direction)}10`, border:`1px solid ${volDirColor(r.vol_direction)}30`, padding:"2px 5px", borderRadius:3 }}>{r.vol_direction==="ACCUMULATION"?"ACCUM":r.vol_direction==="DISTRIBUTION"?"DIST":r.vol_direction}</span> : "—"}</td>
                      <td style={{...td, color:"#c9d8e8", fontSize:12}}>{r.entry_low ? `$${r.entry_low}–$${r.entry_high}` : "—"}</td>
                      <td style={{...td, color:"#ff4466", fontWeight:"bold", fontSize:12}}>{r.sl ? `$${r.sl}` : "—"}</td>
                      <td style={{...td, color:"#00ff88", fontWeight:"bold", fontSize:12}}>{r.tp1 ? `$${r.tp1}` : "—"}</td>
                      <td style={{...td, color:"#00d4ff", fontSize:12}}>{r.tp2 ? `$${r.tp2}` : "—"}</td>
                      <td style={{...td, color:"#c084fc", fontWeight:"bold", fontSize:13}}>{r.qty || "—"}</td>
                      <td style={{...td, color:r.vol_ratio>2?"#fbbf24":r.vol_ratio>1.5?"#00ff88":"#94a3b8", fontFamily:"sans-serif", fontSize:12}}>{r.vol_ratio ? `×${r.vol_ratio}` : "—"}</td>
                      <td style={{...td, color:r.earnings_warning?.includes("⚠")?"#ff4466":"#8899aa", fontFamily:"sans-serif", fontSize:10}}>{r.earnings_warning}</td>
                      <td style={{...td, fontSize:10, color:"#8899aa", maxWidth:200, whiteSpace:"normal", fontFamily:"sans-serif", lineHeight:1.5}}>
                        {r.early_exit_flag && (
                          <div style={{ marginBottom:4 }}>
                            <span style={{ background:"rgba(255,68,102,0.12)", color:"#ff4466", border:"1px solid rgba(255,68,102,0.3)", fontSize:9, padding:"2px 6px", borderRadius:3, fontWeight:"bold" }}>
                              ⚠️ SLOPE DECLINING — consider early exit
                            </span>
                          </div>
                        )}
                        {r.ta_note}
                      </td>
                    </tr>
                    {isExp && r.plan && (
                      <tr>
                        <td colSpan={17} style={{ padding:"12px 16px 16px 24px", background:"rgba(0,212,255,0.03)", borderBottom:"1px solid #1e2d3d", borderLeft:"2px solid #00d4ff" }}>
                          <div style={{ fontFamily:"sans-serif", fontSize:12, color:"#c9d8e8", lineHeight:1.8 }}>
                            <span style={{ color:"#00d4ff", fontWeight:"bold", marginRight:8 }}>🎯 TRADE PLAN</span>{r.plan}
                          </div>
                          {r.confluence_zones?.length > 0 && (
                            <div style={{ marginTop:8, display:"flex", gap:8, flexWrap:"wrap" }}>
                              <span style={{ color:"#8899aa", fontSize:11, fontFamily:"sans-serif" }}>Confluence:</span>
                              {r.confluence_zones.map((z,i) => <span key={i} style={{ background:"rgba(0,212,255,0.1)", color:"#00d4ff", fontSize:11, padding:"1px 7px", borderRadius:3, fontFamily:"sans-serif" }}>${z}</span>)}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ScanDashboard;
