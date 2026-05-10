import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Target, Activity, BarChart3, AlertTriangle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const StatBox = ({ label, value, color, sub }) => (
  <div style={{ background:'#0a0f18', border:'1px solid #1a2535', borderRadius:8, padding:'12px 16px', flex:1, minWidth:120 }}>
    <div style={{ color:'#3a5060', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:4 }}>{label}</div>
    <div style={{ color:color||'#c9d8e8', fontSize:22, fontWeight:'bold', fontFamily:'monospace' }}>{value}</div>
    {sub && <div style={{ color:'#8899aa', fontSize:9, fontFamily:'sans-serif', marginTop:2 }}>{sub}</div>}
  </div>
);

const BarRow = ({ label, pct, count, color }) => (
  <div style={{ marginBottom:8 }}>
    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
      <span style={{ color:'#94a3b8', fontSize:10, fontFamily:'sans-serif' }}>{label}</span>
      <span style={{ color:color||'#c9d8e8', fontSize:10, fontFamily:'monospace', fontWeight:'bold' }}>
        {pct}% <span style={{ color:'#8899aa', fontWeight:'normal' }}>({count} trades)</span>
      </span>
    </div>
    <div style={{ background:'#1a2535', borderRadius:3, height:6, overflow:'hidden' }}>
      <div style={{ background:color||'#00d4ff', width:`${Math.min(pct,100)}%`, height:'100%', borderRadius:3, transition:'width 0.5s' }} />
    </div>
  </div>
);

// Breakdown table for regime / sector / session
const BreakdownTable = ({ title, data }) => {
  if (!data || Object.keys(data).length === 0) return null;
  return (
    <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10, padding:'16px 20px' }}>
      <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:2, fontFamily:'sans-serif', marginBottom:12 }}>{title}</div>
      <table style={{ width:'100%', borderCollapse:'collapse', fontSize:10, fontFamily:'monospace' }}>
        <thead>
          <tr style={{ borderBottom:'1px solid #1a2535' }}>
            <th style={{ textAlign:'left',  color:'#3a5060', padding:'4px 8px 6px 0', fontWeight:'normal', letterSpacing:1 }}>GROUP</th>
            <th style={{ textAlign:'right', color:'#3a5060', padding:'4px 8px 6px', fontWeight:'normal' }}>WINS</th>
            <th style={{ textAlign:'right', color:'#3a5060', padding:'4px 8px 6px', fontWeight:'normal' }}>LOSSES</th>
            {data[Object.keys(data)[0]]?.avg_pnl !== undefined && (
              <th style={{ textAlign:'right', color:'#3a5060', padding:'4px 0 6px 8px', fontWeight:'normal' }}>AVG P&L</th>
            )}
          </tr>
        </thead>
        <tbody>
          {Object.entries(data).map(([key, d]) => {
            const total = (d.wins || 0) + (d.losses || 0);
            const wr = total ? Math.round(d.wins / total * 100) : 0;
            return (
              <tr key={key} style={{ borderBottom:'1px solid #0d1520' }}>
                <td style={{ color:'#94a3b8', padding:'5px 8px 5px 0' }}>{key}</td>
                <td style={{ textAlign:'right', color:'#00ff88', padding:'5px 8px' }}>{d.wins || 0}</td>
                <td style={{ textAlign:'right', color:'#ff4466', padding:'5px 8px' }}>{d.losses || 0}</td>
                {d.avg_pnl !== undefined && (
                  <td style={{ textAlign:'right', color: d.avg_pnl >= 0 ? '#00ff88' : '#ff4466', padding:'5px 0 5px 8px', fontWeight:'bold' }}>
                    {d.avg_pnl >= 0 ? '+' : ''}{d.avg_pnl}%
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const Analytics = () => {
  const [data, setData]       = useState(null);
  const [risk, setRisk]       = useState(null);
  const [source, setSource]   = useState(null);
  const [port, setPort]       = useState(null);   // /api/analytics/portfolio
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [perfRes, riskRes, srcRes, portRes] = await Promise.all([
          fetch(`${API}/api/analytics/performance`),
          fetch(`${API}/api/portfolio/risk`),
          fetch(`${API}/api/data/source`),
          fetch(`${API}/api/analytics/portfolio`),
        ]);
        if (perfRes.ok) setData(await perfRes.json());
        if (riskRes.ok) setRisk(await riskRes.json());
        if (srcRes.ok)  setSource(await srcRes.json());
        if (portRes.ok) setPort(await portRes.json());
      } catch(e) { console.error(e); }
      setLoading(false);
    };
    load();
  }, []);

  const riskColor = risk?.risk_level === 'HIGH' ? '#ff4466' : risk?.risk_level === 'MEDIUM' ? '#fbbf24' : '#00ff88';

  return (
    <div style={{ padding:'24px 20px', maxWidth:1040, margin:'0 auto', fontFamily:"'Courier New',monospace" }}>

      {/* ── Header ── */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <Activity size={16} color="#00d4ff" />
          <span style={{ color:'#00d4ff', fontSize:13, fontWeight:'bold', letterSpacing:2 }}>INTELLIGENCE DASHBOARD</span>
          <span style={{ color:'#2a4a5a', fontSize:9, fontFamily:'sans-serif', letterSpacing:1 }}>LEARNING LOOP + RISK</span>
        </div>
        {source && (
          <div style={{ background: source.realtime ? '#00ff8820' : '#fbbf2420',
            border:`1px solid ${source.realtime ? '#00ff88' : '#fbbf24'}`,
            borderRadius:4, padding:'3px 10px', fontSize:9, fontFamily:'sans-serif',
            color: source.realtime ? '#00ff88' : '#fbbf24', fontWeight:'bold', letterSpacing:1 }}>
            {source.label}
          </div>
        )}
      </div>

      {loading && <div style={{ color:'#8899aa', textAlign:'center', padding:40, fontFamily:'sans-serif' }}>Loading analytics...</div>}

      {!loading && (
        <div style={{ display:'flex', flexDirection:'column', gap:20 }}>

          {/* ── Portfolio Risk ── */}
          {risk && (
            <div style={{ background:'#080c14', border:`1px solid ${riskColor}33`, borderRadius:10, padding:'16px 20px' }}>
              <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:14 }}>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <AlertTriangle size={13} color={riskColor} />
                  <span style={{ color:riskColor, fontSize:11, fontWeight:'bold', letterSpacing:2 }}>PORTFOLIO RISK</span>
                </div>
                <div style={{ background:`${riskColor}20`, border:`1px solid ${riskColor}44`, borderRadius:4,
                  padding:'2px 12px', color:riskColor, fontSize:11, fontWeight:'bold', letterSpacing:2 }}>
                  {risk.risk_level}
                </div>
              </div>
              <div style={{ display:'flex', gap:12, flexWrap:'wrap', marginBottom:14 }}>
                <StatBox label="OPEN SIGNALS" value={risk.signals} color="#c9d8e8" />
                <StatBox label="WORST CASE" value={`${risk.worst_case_loss_pct}%`}
                  color={risk.worst_case_loss_pct < -2 ? '#ff4466' : '#fbbf24'} sub="if all SLs hit" />
                {Object.entries(risk.sector_exposure||{}).map(([sec, cnt]) => (
                  <StatBox key={sec} label={sec.toUpperCase()} value={cnt}
                    color={cnt >= 3 ? '#ff4466' : cnt === 2 ? '#fbbf24' : '#00ff88'} sub="signals" />
                ))}
              </div>
              {risk.warnings?.length > 0 && (
                <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
                  {risk.warnings.map((w, i) => (
                    <div key={i} style={{ background:'#1a0a0a', border:'1px solid #ff446633', borderRadius:4,
                      padding:'6px 12px', color:'#ff8899', fontSize:10, fontFamily:'sans-serif' }}>{w}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Portfolio-level analytics (new) ── */}
          {port && port.total_signals > 0 && (
            <>
              {/* Summary cards */}
              <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10, padding:'16px 20px' }}>
                <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:2, fontFamily:'sans-serif', marginBottom:14 }}>PORTFOLIO SUMMARY</div>
                <div style={{ display:'flex', gap:10, flexWrap:'wrap', marginBottom:12 }}>
                  <StatBox label="WIN RATE"      value={`${port.win_rate}%`}
                    color={port.win_rate >= 55 ? '#00ff88' : port.win_rate >= 45 ? '#fbbf24' : '#ff4466'} />
                  <StatBox label="PROFIT FACTOR" value={port.profit_factor}
                    color={port.profit_factor >= 1.5 ? '#00ff88' : port.profit_factor >= 1 ? '#fbbf24' : '#ff4466'}
                    sub=">1.5 = excellent" />
                  <StatBox label="SHARPE RATIO"  value={port.sharpe_ratio}
                    color={port.sharpe_ratio >= 1 ? '#00ff88' : port.sharpe_ratio >= 0 ? '#fbbf24' : '#ff4466'}
                    sub="annualised" />
                  <StatBox label="MAX DRAWDOWN"  value={`${port.max_drawdown_pct}%`}
                    color={port.max_drawdown_pct > -10 ? '#fbbf24' : '#ff4466'} sub="equity curve" />
                  <StatBox label="AVG HOLD"      value={`${port.avg_hold_days}d`}  color="#00d4ff" />
                  <StatBox label="AVG P&L"       value={`${port.avg_pnl_pct >= 0 ? '+' : ''}${port.avg_pnl_pct}%`}
                    color={port.avg_pnl_pct >= 0 ? '#00ff88' : '#ff4466'} />
                </div>
                {/* Best / Worst trade */}
                <div style={{ display:'flex', gap:10 }}>
                  {port.best_trade && (
                    <div style={{ flex:1, background:'rgba(0,255,136,0.05)', border:'1px solid #00ff8822', borderRadius:6, padding:'8px 12px' }}>
                      <div style={{ fontSize:8, color:'#00ff88', letterSpacing:1, fontFamily:'sans-serif', marginBottom:4 }}>🏆 BEST TRADE</div>
                      <span style={{ fontSize:13, fontWeight:'bold', color:'#00ff88', fontFamily:'monospace' }}>{port.best_trade.ticker}</span>
                      <span style={{ fontSize:11, color:'#00ff88', fontFamily:'monospace', marginLeft:8 }}>+{port.best_trade.pnl_pct}%</span>
                      <div style={{ fontSize:9, color:'#2a4a5a', marginTop:2, fontFamily:'sans-serif' }}>{port.best_trade.date}</div>
                    </div>
                  )}
                  {port.worst_trade && (
                    <div style={{ flex:1, background:'rgba(255,68,102,0.05)', border:'1px solid #ff446622', borderRadius:6, padding:'8px 12px' }}>
                      <div style={{ fontSize:8, color:'#ff4466', letterSpacing:1, fontFamily:'sans-serif', marginBottom:4 }}>⚠️ WORST TRADE</div>
                      <span style={{ fontSize:13, fontWeight:'bold', color:'#ff4466', fontFamily:'monospace' }}>{port.worst_trade.ticker}</span>
                      <span style={{ fontSize:11, color:'#ff4466', fontFamily:'monospace', marginLeft:8 }}>{port.worst_trade.pnl_pct}%</span>
                      <div style={{ fontSize:9, color:'#2a4a5a', marginTop:2, fontFamily:'sans-serif' }}>{port.worst_trade.date}</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Monthly P&L bar chart */}
              {port.monthly_pnl?.length > 0 && (
                <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10, padding:'16px 20px' }}>
                  <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:2, fontFamily:'sans-serif', marginBottom:14 }}>MONTHLY P&L (%)</div>
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart data={port.monthly_pnl} margin={{ top:0, right:0, left:-20, bottom:0 }}>
                      <XAxis dataKey="month" tick={{ fill:'#3a5060', fontSize:9 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill:'#3a5060', fontSize:9 }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{ background:'#0a0f18', border:'1px solid #1a2535', borderRadius:6, fontSize:10 }}
                        labelStyle={{ color:'#94a3b8' }}
                        formatter={(v) => [`${v >= 0 ? '+' : ''}${v}%`, 'P&L']}
                      />
                      <Bar dataKey="pnl" radius={[3,3,0,0]}>
                        {port.monthly_pnl.map((entry, i) => (
                          <Cell key={i} fill={entry.pnl >= 0 ? '#00ff88' : '#ff4466'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Breakdown tables */}
              <BreakdownTable title="BY MARKET REGIME" data={port.by_regime} />
              <BreakdownTable title="BY SECTOR" data={port.by_sector} />
              <BreakdownTable title="BY SESSION" data={port.by_session} />
            </>
          )}

          {/* ── Performance Stats (existing) ── */}
          {data?.total > 0 ? (
            <>
              <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10, padding:'16px 20px' }}>
                <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:2, fontFamily:'sans-serif', marginBottom:14 }}>DETAILED PERFORMANCE</div>
                <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
                  <StatBox label="TOTAL TRADES"   value={data.total}          color="#c9d8e8" />
                  <StatBox label="AVG WIN"         value={`+${data.avg_win_pct}%`}  color="#00ff88" />
                  <StatBox label="AVG LOSS"        value={`${data.avg_loss_pct}%`}  color="#ff4466" />
                  <StatBox label="TP1 HIT RATE"    value={`${data.tp1_hit_rate}%`}  color="#00d4ff" />
                  <StatBox label="STOPPED OUT"     value={`${data.stopped_out_rate}%`} color="#ff4466" />
                  <StatBox label="AVG MFE"         value={`+${data.avg_mfe_pct}%`} color="#00ff88" sub="best unrealized" />
                  <StatBox label="AVG MAE"         value={`${data.avg_mae_pct}%`}  color="#ff4466" sub="worst drawdown" />
                </div>
              </div>

              {/* Conviction breakdown */}
              {Object.keys(data.conviction_breakdown||{}).length > 0 && (
                <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10, padding:'16px 20px' }}>
                  <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:2, fontFamily:'sans-serif', marginBottom:14 }}>
                    WIN RATE BY CONVICTION — does higher conviction actually win more?
                  </div>
                  {Object.entries(data.conviction_breakdown).map(([bucket, d]) => (
                    <BarRow key={bucket} label={`${bucket}% conviction`}
                      pct={d.win_rate} count={d.trades}
                      color={d.win_rate >= 60 ? '#00ff88' : d.win_rate >= 50 ? '#fbbf24' : '#ff4466'} />
                  ))}
                </div>
              )}

              {/* Regime breakdown (existing) */}
              {Object.keys(data.regime_breakdown||{}).length > 0 && (
                <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10, padding:'16px 20px' }}>
                  <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:2, fontFamily:'sans-serif', marginBottom:14 }}>
                    WIN RATE BY MARKET REGIME — when does the system perform best?
                  </div>
                  {Object.entries(data.regime_breakdown).map(([reg, d]) => (
                    <BarRow key={reg} label={reg || 'Unknown'} pct={d.win_rate} count={d.trades}
                      color={d.win_rate >= 60 ? '#00ff88' : d.win_rate >= 50 ? '#fbbf24' : '#ff4466'} />
                  ))}
                </div>
              )}
            </>
          ) : (
            <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10, padding:32, textAlign:'center' }}>
              <BarChart3 size={32} color="#1a2535" style={{ margin:'0 auto 12px' }} />
              <div style={{ color:'#8899aa', fontSize:12, fontFamily:'sans-serif' }}>No closed signals yet</div>
              <div style={{ color:'#2a4a5a', fontSize:10, fontFamily:'sans-serif', marginTop:6 }}>
                Run Auto-Pilot to generate signals. The learning loop activates once signals close.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Analytics;
