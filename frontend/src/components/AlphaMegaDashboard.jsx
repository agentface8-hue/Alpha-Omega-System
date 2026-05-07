import React, { useState, useEffect } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, BarChart2, Star, X } from 'lucide-react';
import ChartPanel from './ChartPanel';

const convC  = p => p >= 75 ? "#00ff88" : p >= 60 ? "#fbbf24" : p >= 45 ? "#94a3b8" : "#ff4466";
const trendC = t => t === "BULL" ? "#00ff88" : t === "BEAR" ? "#ff4466" : "#fbbf24";
const pnlC   = p => p > 0 ? "#00ff88" : p < 0 ? "#ff4466" : "#94a3b8";
const heatC  = h => h === "HOT" ? "#00ff88" : h === "WARM" ? "#fbbf24" : "#ff4466";

const SECTOR_LABELS = {
  information_technology:"Info Tech", financials:"Financials", health_care:"Health Care",
  industrials:"Industrials", consumer_discretionary:"Cons. Disc.", consumer_staples:"Cons. Staples",
  energy:"Energy", communication_services:"Comm. Svcs", utilities:"Utilities",
  materials:"Materials", real_estate:"Real Estate"
};

const AlphaMegaDashboard = () => {
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [lookback, setLookback] = useState(30);
  const [chartTicker, setChartTicker] = useState(null);
  const [lastTs, setLastTs]     = useState(null);

  const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

  const fetchData = async (lb = lookback) => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/alpha-mega?lookback_days=${lb}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setData(d);
      setLastTs(d.last_updated ? new Date(d.last_updated * 1000).toLocaleString() : null);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const changeLookback = (lb) => {
    setLookback(lb);
    fetchData(lb);
  };

  const top20    = data?.top20 || [];
  const portfolio = data?.portfolio || [];

  return (
    <div style={{ background:"#050810", padding:"20px 16px", fontFamily:"'Courier New',monospace", color:"#c9d8e8", minHeight:"100vh" }}>

      {/* ── Header ── */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", borderBottom:"1px solid #1a2535", paddingBottom:14, marginBottom:16 }}>
        <div>
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <span style={{ fontWeight:"bold", fontSize:22 }}>Alpha<span style={{ color:"#c084fc" }}>Mega</span></span>
            <span style={{ color:"#c084fc", fontSize:11, fontWeight:"bold", background:"rgba(192,132,252,0.15)", border:"1px solid rgba(192,132,252,0.3)", padding:"1px 8px", borderRadius:3 }}>TOP 20</span>
          </div>
          <div style={{ color:"#2a4a5a", fontSize:10, marginTop:2, fontFamily:"sans-serif" }}>
            MCap &gt;$10B · Daily refresh · MTF channel scoring · {data?.total_scanned || 0} stocks analyzed
          </div>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          {lastTs && <span style={{ color:"#2a4a5a", fontSize:9, fontFamily:"sans-serif" }}>Updated: {lastTs}</span>}
          <button onClick={() => fetchData(lookback)} disabled={loading}
            style={{ background:"linear-gradient(135deg,#1a0a2e,#0d0a1e)", border:"1px solid #7c3aed44",
              color:"#c084fc", fontSize:10, fontWeight:"bold", padding:"6px 14px", borderRadius:6,
              cursor:loading?"wait":"pointer", fontFamily:"sans-serif", display:"flex", alignItems:"center", gap:5 }}>
            {loading ? <RefreshCw size={12} className="spin" /> : <RefreshCw size={12} />}
            {loading ? "SCANNING..." : "REFRESH"}
          </button>
        </div>
      </div>

      {/* ── Lookback toggle ── */}
      <div style={{ display:"flex", gap:6, marginBottom:14 }}>
        {[30,90,180,360].map(d => (
          <button key={d} onClick={() => changeLookback(d)}
            style={{ background:lookback===d?"#1a2535":"#080c14", border:`1px solid ${lookback===d?"#c084fc":"#1a2535"}`,
              color:lookback===d?"#c084fc":"#8899aa", fontSize:10, fontWeight:"bold",
              padding:"4px 12px", borderRadius:5, cursor:"pointer", fontFamily:"sans-serif" }}>
            {d}D
          </button>
        ))}
        <span style={{ color:"#2a4a5a", fontSize:9, fontFamily:"sans-serif", alignSelf:"center", marginLeft:4 }}>P&L lookback</span>
      </div>

      {/* ── Portfolio optimizer ── */}
      {portfolio.length > 0 && (
        <div style={{ background:"linear-gradient(135deg,#0d0a1e,#0a0f18)", border:"1px solid rgba(192,132,252,0.25)",
          borderRadius:8, padding:"12px 16px", marginBottom:16 }}>
          <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:8 }}>
            <Star size={12} color="#c084fc" />
            <span style={{ color:"#c084fc", fontSize:10, fontWeight:"bold", letterSpacing:1.5, fontFamily:"sans-serif" }}>OPTIMAL PORTFOLIO — TOP 5 (DIVERSIFIED)</span>
          </div>
          <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
            {portfolio.map((t, i) => {
              const stock = top20.find(r => r.ticker === t);
              return (
                <div key={t} style={{ background:"rgba(192,132,252,0.08)", border:"1px solid rgba(192,132,252,0.3)",
                  borderRadius:6, padding:"6px 14px", display:"flex", alignItems:"center", gap:8 }}>
                  <span style={{ color:"#8899aa", fontSize:10, fontFamily:"sans-serif" }}>#{i+1}</span>
                  <span style={{ color:"#c084fc", fontWeight:"bold", fontSize:14 }}>{t}</span>
                  {stock && <>
                    <span style={{ color:convC(stock.alpha_score), fontSize:11, fontFamily:"sans-serif" }}>{stock.alpha_score}%</span>
                    <span style={{ color:pnlC(stock.pnl_pct), fontSize:11, fontFamily:"sans-serif" }}>
                      {stock.pnl_pct > 0 ? "+" : ""}{stock.pnl_pct}%
                    </span>
                  </>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {error && <div style={{ background:"rgba(255,68,102,0.08)", border:"1px solid rgba(255,68,102,0.3)", borderRadius:8, padding:16, color:"#ff4466", fontFamily:"sans-serif", marginBottom:14 }}>❌ {error}</div>}

      {/* ── Top 20 Table ── */}
      {top20.length > 0 && (
        <div style={{ overflowX:"auto", borderRadius:8, border:"1px solid #1a2535" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", background:"#080c14", whiteSpace:"nowrap", minWidth:900 }}>
            <thead>
              <tr>
                {["#","Ticker","Sector","α Score","Conviction","Trend","TAS",`P&L ${lookback}D`,"Signal","Chart"].map(h => (
                  <th key={h} style={{ background:"#0a0f18", color:"#2a4a5a", fontSize:9, letterSpacing:1.2,
                    padding:"10px 10px", textAlign:"left", borderBottom:"1px solid #1a2535", fontFamily:"sans-serif" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {top20.map((r, i) => {
                const isPortfolio = portfolio.includes(r.ticker);
                const td = { padding:"9px 10px", borderBottom:"1px solid #0d1420", verticalAlign:"middle",
                  background: isPortfolio ? "rgba(192,132,252,0.04)" : "transparent" };
                const signal = r.trend === "BULL" ? "BUY" : r.trend === "BEAR" ? "SELL" : "WATCH";
                const sigC   = signal === "BUY" ? "#00ff88" : signal === "SELL" ? "#ff4466" : "#fbbf24";
                return (
                  <tr key={r.ticker} style={{ transition:"background 0.15s" }}
                    onMouseOver={e => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
                    onMouseOut={e => e.currentTarget.style.background = "transparent"}>
                    <td style={td}>
                      <span style={{ color: isPortfolio ? "#c084fc" : "#8899aa", fontSize:11, fontFamily:"sans-serif" }}>
                        {isPortfolio ? "★" : i+1}
                      </span>
                    </td>
                    <td style={td}>
                      <div style={{ color:"#00d4ff", fontWeight:"bold", fontSize:14 }}>{r.ticker}</div>
                      <div style={{ color:"#8899aa", fontSize:9, fontFamily:"sans-serif" }}>
                        ${r.last_close}
                      </div>
                    </td>
                    <td style={td}>
                      <span style={{ color:"#94a3b8", fontSize:10, fontFamily:"sans-serif" }}>
                        {SECTOR_LABELS[r.sector_key] || r.sector_key || "—"}
                      </span>
                    </td>
                    <td style={td}>
                      <span style={{ color:convC(r.alpha_score), fontWeight:"bold", fontSize:15 }}>{r.alpha_score}%</span>
                    </td>
                    <td style={td}>
                      <span style={{ color:convC(r.conviction_pct), fontWeight:"bold", fontSize:13 }}>{r.conviction_pct}%</span>
                    </td>
                    <td style={td}>
                      <span style={{ color:trendC(r.trend), fontWeight:"bold", fontSize:12 }}>
                        {r.trend === "BULL" ? "▲" : r.trend === "BEAR" ? "▼" : "—"} {r.trend}
                      </span>
                    </td>
                    <td style={td}>
                      <span style={{ color:"#7ee8ff", fontWeight:"bold", fontSize:12 }}>{r.tas || "—"}</span>
                    </td>
                    <td style={td}>
                      <span style={{ color:pnlC(r.pnl_pct), fontWeight:"bold", fontSize:13, fontFamily:"sans-serif" }}>
                        {r.pnl_pct > 0 ? "+" : ""}{r.pnl_pct}%
                      </span>
                    </td>
                    <td style={td}>
                      <span style={{ background:`${sigC}15`, color:sigC, border:`1px solid ${sigC}33`,
                        fontSize:10, fontWeight:"bold", padding:"2px 8px", borderRadius:3, fontFamily:"sans-serif" }}>
                        {signal}
                      </span>
                    </td>
                    <td style={td}>
                      <button onClick={() => setChartTicker(r.ticker)}
                        style={{ background:"#0d1520", border:"1px solid #1a2535", borderRadius:4,
                          color:"#00d4ff", padding:"3px 8px", cursor:"pointer", fontSize:11 }}>
                        📊
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Chart Modal ── */}
      {chartTicker && (
        <div style={{ position:"fixed", top:0, left:0, right:0, bottom:0, background:"rgba(0,0,0,0.85)",
          display:"flex", alignItems:"center", justifyContent:"center", zIndex:1000 }}
          onClick={() => setChartTicker(null)}>
          <div onClick={e => e.stopPropagation()}
            style={{ background:"#080c14", border:"1px solid #1a2535", borderRadius:12,
              padding:16, width:"90%", maxWidth:900, maxHeight:"85vh", overflowY:"auto" }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
              <span style={{ color:"#c084fc", fontWeight:"bold", fontSize:14 }}>{chartTicker}</span>
              <button onClick={() => setChartTicker(null)}
                style={{ background:"transparent", border:"none", color:"#8899aa", cursor:"pointer" }}>
                <X size={18} />
              </button>
            </div>
            <ChartPanel symbol={chartTicker} tradeParams={null} />
          </div>
        </div>
      )}
    </div>
  );
};

export default AlphaMegaDashboard;
