import React, { useState } from 'react';
import { BarChart3, Play, RotateCcw, TrendingUp, TrendingDown, Target, AlertTriangle } from 'lucide-react';

const API = () => import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const pctColor = v => v > 0 ? "#00ff88" : v < 0 ? "#ff4466" : "#94a3b8";
const rateColor = v => v >= 75 ? "#00ff88" : v >= 50 ? "#fbbf24" : "#ff4466";
const verdictColor = v => v === "CALIBRATED" ? "#00ff88" : v === "UNDER-RATED" ? "#7ee8ff" : "#ff4466";

const Card = ({ title, value, sub, color }) => (
  <div style={{ background:"#0d1a2a", border:"1px solid #1a2535", borderRadius:8, padding:"14px 18px", minWidth:120, textAlign:"center" }}>
    <div style={{ fontSize:10, color:"#8899aa", letterSpacing:1, marginBottom:6, fontFamily:"monospace" }}>{title}</div>
    <div style={{ fontSize:22, fontWeight:"bold", color: color || "#00d4ff", fontFamily:"monospace" }}>{value}</div>
    {sub && <div style={{ fontSize:10, color:"#8899aa", marginTop:4 }}>{sub}</div>}
  </div>
);

const BacktestDashboard = () => {
  const [tickers, setTickers] = useState('AAPL, NVDA, MSFT, GOOGL, META, AMZN, TSLA, AMD, CRM, NFLX');
  const [lookback, setLookback] = useState(180);
  const [forward, setForward] = useState(15);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [calibData, setCalibData] = useState(null);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState('backtest'); // backtest or calibrate

  const runBacktest = async () => {
    setLoading(true); setError(null); setData(null); setCalibData(null);
    const symbols = tickers.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    try {
      const url = mode === 'calibrate' ? `${API()}/api/calibrate` : `${API()}/api/backtest`;
      const res = await fetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols, lookback_days: lookback, forward_days: forward, sample_every: 5 })
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      const d = await res.json();
      if (mode === 'calibrate') { setCalibData(d); setData(d.calibration?.baseline_stats ? { summary: d.calibration.baseline_stats, brackets: d.calibration.brackets } : null); }
      else setData(d);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  const resetCalib = async () => {
    try {
      await fetch(`${API()}/api/calibration/reset`, { method: 'POST' });
      alert('Calibration reset to raw scores');
    } catch (e) { alert('Error: ' + e.message); }
  };

  const s = data?.summary || {};
  const brackets = data?.brackets || [];
  const gaps = data?.accuracy_gap || [];
  const signals = data?.signals || [];
  const perTicker = data?.per_ticker || [];
  const tp = calibData?.calibration?.tp_analysis || {};
  const recs = calibData?.recommendation || [];
  const preview = calibData?.preview || {};

  return (
    <div style={{ padding: "20px", fontFamily: "'Inter', sans-serif", color: "#e0e0e0", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:20 }}>
        <div style={{ background:"linear-gradient(135deg, #7c3aed, #a855f7)", borderRadius:10, padding:10, display:"flex" }}>
          <Target size={22} color="#fff" />
        </div>
        <div>
          <div style={{ fontSize:18, fontWeight:"bold", color:"#fff", letterSpacing:1 }}>WALK-FORWARD BACKTESTER</div>
          <div style={{ fontSize:11, color:"#8899aa" }}>Score historical data • Check if TP1 was hit • Measure real accuracy</div>
        </div>
      </div>

      {/* Controls */}
      <div style={{ background:"#0a1018", border:"1px solid #1a2535", borderRadius:10, padding:16, marginBottom:20 }}>
        <div style={{ display:"flex", gap:12, alignItems:"end", flexWrap:"wrap" }}>
          <div style={{ flex:1, minWidth:250 }}>
            <label style={{ fontSize:10, color:"#8899aa", letterSpacing:1, display:"block", marginBottom:4 }}>TICKERS</label>
            <input value={tickers} onChange={e => setTickers(e.target.value.toUpperCase())} style={{ width:"100%", background:"#0d1a2a", border:"1px solid #1a2535", borderRadius:6, padding:"8px 12px", color:"#e0e0e0", fontSize:13, fontFamily:"monospace" }} />
          </div>
          <div>
            <label style={{ fontSize:10, color:"#8899aa", letterSpacing:1, display:"block", marginBottom:4 }}>LOOKBACK</label>
            <select value={lookback} onChange={e => setLookback(+e.target.value)} style={{ background:"#0d1a2a", border:"1px solid #1a2535", borderRadius:6, padding:"8px 10px", color:"#e0e0e0", fontSize:12 }}>
              <option value={60}>60 days</option><option value={120}>120 days</option><option value={180}>180 days</option><option value={365}>1 year</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize:10, color:"#8899aa", letterSpacing:1, display:"block", marginBottom:4 }}>FORWARD</label>
            <select value={forward} onChange={e => setForward(+e.target.value)} style={{ background:"#0d1a2a", border:"1px solid #1a2535", borderRadius:6, padding:"8px 10px", color:"#e0e0e0", fontSize:12 }}>
              <option value={5}>5 days</option><option value={10}>10 days</option><option value={15}>15 days</option><option value={20}>20 days</option>
            </select>
          </div>
          <div style={{ display:"flex", gap:6 }}>
            <button onClick={() => { setMode('backtest'); setTimeout(runBacktest, 50); }} disabled={loading} style={{ background: loading ? "#1a2535" : "linear-gradient(135deg, #00d4ff, #0088cc)", border:"none", borderRadius:6, padding:"8px 16px", color:"#fff", fontSize:12, fontWeight:"bold", cursor: loading?"wait":"pointer", display:"flex", alignItems:"center", gap:6 }}>
              <Play size={14} /> {loading && mode==='backtest' ? "RUNNING..." : "BACKTEST"}
            </button>
            <button onClick={() => { setMode('calibrate'); setTimeout(runBacktest, 50); }} disabled={loading} style={{ background: loading ? "#1a2535" : "linear-gradient(135deg, #7c3aed, #a855f7)", border:"none", borderRadius:6, padding:"8px 16px", color:"#fff", fontSize:12, fontWeight:"bold", cursor: loading?"wait":"pointer", display:"flex", alignItems:"center", gap:6 }}>
              <Target size={14} /> {loading && mode==='calibrate' ? "CALIBRATING..." : "CALIBRATE"}
            </button>
            <button onClick={resetCalib} style={{ background:"transparent", border:"1px solid #ff4466", borderRadius:6, padding:"8px 12px", color:"#ff4466", fontSize:11, cursor:"pointer", display:"flex", alignItems:"center", gap:4 }}>
              <RotateCcw size={12} /> RESET
            </button>
          </div>
        </div>
        {loading && <div style={{ marginTop:12, padding:10, background:"#0d1a2a", borderRadius:6, fontSize:11, color:"#fbbf24", fontFamily:"monospace" }}>⏳ Processing {tickers.split(',').length} tickers × {lookback} days... This takes 30-90 seconds.</div>}
      </div>

      {error && <div style={{ background:"rgba(255,68,102,0.1)", border:"1px solid #ff4466", borderRadius:8, padding:12, marginBottom:16, color:"#ff4466", fontSize:12 }}><AlertTriangle size={14} style={{verticalAlign:"middle"}} /> {error}</div>}

      {/* Summary Cards */}
      {data && (
        <div style={{ display:"flex", gap:12, marginBottom:20, flexWrap:"wrap" }}>
          <Card title="SIGNALS" value={s.total_signals || 0} sub={`${(s.symbols_tested||[]).length} tickers`} />
          <Card title="WIN RATE" value={`${s.overall_win_rate||0}%`} color={rateColor(s.overall_win_rate||0)} sub={`${s.total_wins||0} wins`} />
          <Card title="TP1 HIT" value={`${s.overall_tp1_rate||0}%`} color={rateColor(s.overall_tp1_rate||0)} />
          <Card title="AVG P&L" value={`${s.avg_pnl>0?'+':''}${s.avg_pnl||0}%`} color={pctColor(s.avg_pnl||0)} sub="per trade" />
          <Card title="PROFIT FACTOR" value={s.profit_factor >= 999 ? '∞' : s.profit_factor || 0} color={s.profit_factor >= 1.5 ? "#00ff88" : s.profit_factor >= 1.0 ? "#fbbf24" : "#ff4466"} sub={`W:${s.avg_win||0}% L:${s.avg_loss||0}%`} />
          <Card title="WIN/LOSS RATIO" value={s.win_loss_ratio >= 999 ? '∞' : `${s.win_loss_ratio||0}x`} color={s.win_loss_ratio >= 1.5 ? "#00ff88" : "#fbbf24"} />
          <Card title="BEST" value={`+${s.best_trade?.pnl||0}%`} color="#00ff88" sub={s.best_trade?.symbol} />
          <Card title="WORST" value={`${s.worst_trade?.pnl||0}%`} color="#ff4466" sub={s.worst_trade?.symbol} />
        </div>
      )}

      {/* Buy & Hold vs Strategy Benchmark */}
      {data && perTicker.length > 0 && (
        <div style={{ background:"#0a1018", border:"1px solid #1a2535", borderRadius:10, padding:16, marginBottom:20 }}>
          <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:4 }}>
            <div style={{ fontSize:13, fontWeight:"bold", color:"#fbbf24", letterSpacing:1 }}>📈 STRATEGY vs BUY & HOLD</div>
            <div style={{ fontSize:10, color:"#8899aa" }}>Avg P&L per {forward}d trade vs holding the full {lookback}d period</div>
          </div>
          <div style={{ fontSize:10, color:"#8899aa", marginBottom:12, background:"rgba(251,191,36,0.06)", borderRadius:4, padding:"6px 10px", borderLeft:"2px solid #fbbf24" }}>
            ⚠️ These are not directly comparable — strategy P&L is per trade (~{forward}d), Buy&Hold is over the full {lookback}d period.
            A +3% avg trade every {forward}d compounded is far stronger than it looks against a single Buy&Hold return.
          </div>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12, fontFamily:"monospace" }}>
            <thead>
              <tr style={{ borderBottom:"1px solid #1a2535" }}>
                {["Ticker","Signals","Win%","TP1%","Avg Trade P&L","Buy&Hold ({lookback}d)","Note"].map(h => (
                  <th key={h} style={{ padding:"6px 6px", textAlign:"right", color:"#8899aa", fontSize:10, fontWeight:"normal", letterSpacing:1 }}>{h.replace("{lookback}", lookback)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {perTicker.map(t => {
                const bh = t.buy_hold_return;
                const ap = t.avg_pnl;
                const note = ap > 0 && bh < 0 ? "✅ +alpha in down market" :
                             ap > 0 && bh > 0 ? "📊 both positive" :
                             ap < 0 && bh < 0 ? "⚠️ challenged market" :
                             "📉 underperformed";
                return (
                  <tr key={t.symbol} style={{ borderBottom:"1px solid #0d1a2a" }}>
                    <td style={{ padding:"6px 6px", color:"#e0e0e0", fontWeight:"bold" }}>{t.symbol}</td>
                    <td style={{ padding:"6px 6px", textAlign:"right", color:"#94a3b8" }}>{t.signals}</td>
                    <td style={{ padding:"6px 6px", textAlign:"right", color:rateColor(t.win_rate) }}>{t.win_rate}%</td>
                    <td style={{ padding:"6px 6px", textAlign:"right", color:rateColor(t.tp1_rate) }}>{t.tp1_rate}%</td>
                    <td style={{ padding:"6px 6px", textAlign:"right", color:pctColor(ap), fontWeight:"bold" }}>{ap>0?'+':''}{ap}%</td>
                    <td style={{ padding:"6px 6px", textAlign:"right", color:pctColor(bh) }}>{bh>0?'+':''}{bh}%</td>
                    <td style={{ padding:"6px 6px", textAlign:"right", color:"#94a3b8", fontSize:10 }}>{note}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Accuracy by Bracket */}
      {brackets.length > 0 && (
        <div style={{ background:"#0a1018", border:"1px solid #1a2535", borderRadius:10, padding:16, marginBottom:20 }}>
          <div style={{ fontSize:13, fontWeight:"bold", color:"#00d4ff", marginBottom:12, letterSpacing:1 }}>📊 ACCURACY BY CONVICTION BRACKET</div>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12, fontFamily:"monospace" }}>
            <thead>
              <tr style={{ borderBottom:"1px solid #1a2535" }}>
                {["Bracket","Signals","Win%","TP1%","TP2%","Avg P&L","Avg Days","Max DD"].map(h => (
                  <th key={h} style={{ padding:"8px 6px", textAlign:"right", color:"#8899aa", fontSize:10, fontWeight:"normal", letterSpacing:1 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {brackets.filter(b => b.count > 0).map(b => (
                <tr key={b.label} style={{ borderBottom:"1px solid #0d1a2a" }}>
                  <td style={{ padding:"8px 6px", color:"#e0e0e0", fontWeight:"bold" }}>{b.label}</td>
                  <td style={{ padding:"8px 6px", textAlign:"right", color:"#94a3b8" }}>{b.count}</td>
                  <td style={{ padding:"8px 6px", textAlign:"right", color:rateColor(b.win_rate) }}>{b.win_rate}%</td>
                  <td style={{ padding:"8px 6px", textAlign:"right", color:rateColor(b.tp1_rate) }}>{b.tp1_rate}%</td>
                  <td style={{ padding:"8px 6px", textAlign:"right", color:rateColor(b.tp2_rate) }}>{b.tp2_rate}%</td>
                  <td style={{ padding:"8px 6px", textAlign:"right", color:pctColor(b.avg_pnl) }}>{b.avg_pnl>0?'+':''}{b.avg_pnl}%</td>
                  <td style={{ padding:"8px 6px", textAlign:"right", color:"#94a3b8" }}>{b.avg_days}d</td>
                  <td style={{ padding:"8px 6px", textAlign:"right", color:"#ff4466" }}>{b.avg_drawdown}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Accuracy Gap */}
      {gaps.length > 0 && (
        <div style={{ background:"#0a1018", border:"1px solid #1a2535", borderRadius:10, padding:16, marginBottom:20 }}>
          <div style={{ fontSize:13, fontWeight:"bold", color:"#fbbf24", marginBottom:12, letterSpacing:1 }}>🎯 CALIBRATION CHECK — Score vs Reality</div>
          <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
            {gaps.map(g => (
              <div key={g.bracket} style={{ display:"flex", alignItems:"center", gap:12, background:"#0d1a2a", borderRadius:6, padding:"10px 14px" }}>
                <span style={{ fontFamily:"monospace", color:"#e0e0e0", fontWeight:"bold", minWidth:70 }}>{g.bracket}</span>
                <div style={{ flex:1, position:"relative", height:24, background:"#1a2535", borderRadius:4, overflow:"hidden" }}>
                  <div style={{ position:"absolute", left:0, top:0, height:"100%", width:`${g.actual_tp1_rate}%`, background: g.verdict==="CALIBRATED" ? "#00ff8844" : "#ff446644", borderRadius:4 }} />
                  <div style={{ position:"absolute", left:`${g.expected}%`, top:0, height:"100%", width:2, background:"#fff" }} />
                  <span style={{ position:"absolute", left:8, top:3, fontSize:10, fontFamily:"monospace", color:"#e0e0e0" }}>Actual: {g.actual_tp1_rate}%</span>
                </div>
                <span style={{ fontSize:11, color:verdictColor(g.verdict), fontWeight:"bold", minWidth:110 }}>
                  {g.verdict === "OVER-CONFIDENT" ? "⚠️" : g.verdict === "CALIBRATED" ? "✅" : "📈"} {g.verdict}
                </span>
                <span style={{ fontSize:10, color: g.gap > 0 ? "#00ff88" : "#ff4466", fontFamily:"monospace", minWidth:50 }}>{g.gap > 0 ? "+" : ""}{g.gap}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TP Distance Analysis (calibration only) */}
      {tp.tp_results && (
        <div style={{ background:"#0a1018", border:"1px solid #1a2535", borderRadius:10, padding:16, marginBottom:20 }}>
          <div style={{ fontSize:13, fontWeight:"bold", color:"#a855f7", marginBottom:12, letterSpacing:1 }}>📐 OPTIMAL TP1 DISTANCE</div>
          <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
            {tp.tp_results.map(t => {
              const is85 = tp.best_for_85pct && t.tp_pct === tp.best_for_85pct.tp_pct;
              return (
                <div key={t.tp_pct} style={{
                  background: is85 ? "rgba(0,255,136,0.12)" : "#0d1a2a",
                  border: is85 ? "2px solid #00ff88" : "1px solid #1a2535",
                  borderRadius:8, padding:"10px 14px", textAlign:"center", minWidth:80,
                }}>
                  <div style={{ fontSize:15, fontWeight:"bold", color: is85 ? "#00ff88" : "#e0e0e0", fontFamily:"monospace" }}>+{t.tp_pct}%</div>
                  <div style={{ fontSize:18, fontWeight:"bold", color: rateColor(t.hit_rate), marginTop:4 }}>{t.hit_rate}%</div>
                  <div style={{ fontSize:9, color:"#8899aa", marginTop:2 }}>{t.hits} hits</div>
                  {is85 && <div style={{ fontSize:9, color:"#00ff88", marginTop:4, fontWeight:"bold" }}>← 85% TARGET</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {recs.length > 0 && (
        <div style={{ background:"#0a1018", border:"1px solid #7c3aed44", borderRadius:10, padding:16, marginBottom:20 }}>
          <div style={{ fontSize:13, fontWeight:"bold", color:"#a855f7", marginBottom:12, letterSpacing:1 }}>💡 RECOMMENDATIONS</div>
          {recs.map((r, i) => (
            <div key={i} style={{ background:"#0d1a2a", borderRadius:6, padding:"10px 14px", marginBottom:6, fontSize:12, color:"#e0e0e0", lineHeight:1.5, borderLeft:"3px solid #7c3aed" }}>
              {r}
            </div>
          ))}
        </div>
      )}

      {/* Recent Signals Table */}
      {signals.length > 0 && (
        <div style={{ background:"#0a1018", border:"1px solid #1a2535", borderRadius:10, padding:16 }}>
          <div style={{ fontSize:13, fontWeight:"bold", color:"#00d4ff", marginBottom:12, letterSpacing:1 }}>📋 SIGNAL LOG ({signals.length} signals)</div>
          <div style={{ maxHeight:400, overflowY:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:11, fontFamily:"monospace" }}>
              <thead>
                <tr style={{ borderBottom:"1px solid #1a2535", position:"sticky", top:0, background:"#0a1018" }}>
                  {["Symbol","Date","Entry","Conv","TAS","SL","TP1","R:R","Outcome","P&L","Days"].map(h => (
                    <th key={h} style={{ padding:"6px 4px", textAlign:"right", color:"#8899aa", fontSize:9, fontWeight:"normal", letterSpacing:1 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {signals.slice(0, 100).map((s, i) => (
                  <tr key={i} style={{ borderBottom:"1px solid #0d1a2a" }}>
                    <td style={{ padding:"5px 4px", color:"#e0e0e0", fontWeight:"bold" }}>{s.symbol}</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color:"#8899aa", fontSize:10 }}>{s.date}</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color:"#94a3b8" }}>${s.entry_price}</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color: s.conviction>=75?"#00ff88":s.conviction>=60?"#fbbf24":"#94a3b8" }}>{s.conviction}%</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color:"#7ee8ff" }}>{s.tas}</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color:"#ff4466" }}>${s.sl}</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color:"#00ff88" }}>${s.tp1}</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color:"#fbbf24" }}>{s.rr}:1</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color: s.outcome?.includes("TP")?"#00ff88":s.outcome==="SL_HIT"?"#ff4466":"#94a3b8", fontWeight:"bold" }}>
                      {s.outcome === "TP2_HIT" ? "🎯 TP2" : s.outcome === "TP1_HIT" ? "✅ TP1" : s.outcome === "SL_HIT" ? "❌ SL" : "⏳ TIME"}
                    </td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color: pctColor(s.pnl_pct), fontWeight:"bold" }}>{s.pnl_pct>0?'+':''}{s.pnl_pct}%</td>
                    <td style={{ padding:"5px 4px", textAlign:"right", color:"#8899aa" }}>{s.exit_day}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {signals.length > 100 && <div style={{ textAlign:"center", color:"#8899aa", fontSize:10, marginTop:8 }}>Showing first 100 of {signals.length} signals</div>}
        </div>
      )}
    </div>
  );
};

export default BacktestDashboard;
