import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Target, Activity, BarChart3, AlertTriangle } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const StatBox = ({ label, value, color, sub }) => (
  <div style={{ background:'#0a0f18', border:'1px solid #1a2535', borderRadius:8, padding:'12px 16px', flex:1, minWidth:120 }}>
    <div style={{ color:'#3a5060', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:4 }}>{label}</div>
    <div style={{ color:color||'#c9d8e8', fontSize:22, fontWeight:'bold', fontFamily:'monospace' }}>{value}</div>
    {sub && <div style={{ color:'#4a6070', fontSize:9, fontFamily:'sans-serif', marginTop:2 }}>{sub}</div>}
  </div>
);

const BarRow = ({ label, pct, count, color }) => (
  <div style={{ marginBottom:8 }}>
    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
      <span style={{ color:'#94a3b8', fontSize:10, fontFamily:'sans-serif' }}>{label}</span>
      <span style={{ color:color||'#c9d8e8', fontSize:10, fontFamily:'monospace', fontWeight:'bold' }}>
        {pct}% <span style={{ color:'#4a6070', fontWeight:'normal' }}>({count} trades)</span>
      </span>
    </div>
    <div style={{ background:'#1a2535', borderRadius:3, height:6, overflow:'hidden' }}>
      <div style={{ background:color||'#00d4ff', width:`${Math.min(pct,100)}%`, height:'100%', borderRadius:3, transition:'width 0.5s' }} />
    </div>
  </div>
);

const Analytics = () => {
  const [data, setData]     = useState(null);
  const [risk, setRisk]     = useState(null);
  const [source, setSource] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [perfRes, riskRes, srcRes] = await Promise.all([
          fetch(`${API}/api/analytics/performance`),
          fetch(`${API}/api/portfolio/risk`),
          fetch(`${API}/api/data/source`),
        ]);
        if (perfRes.ok) setData(await perfRes.json());
        if (riskRes.ok) setRisk(await riskRes.json());
        if (srcRes.ok)  setSource(await srcRes.json());
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

      {loading && <div style={{ color:'#4a6070', textAlign:'center', padding:40, fontFamily:'sans-serif' }}>Loading analytics...</div>}

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

          {/* ── Performance Stats ── */}
          {data?.total > 0 ? (
            <>
              <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10, padding:'16px 20px' }}>
                <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:2, fontFamily:'sans-serif', marginBottom:14 }}>OVERALL PERFORMANCE</div>
                <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
                  <StatBox label="TOTAL TRADES"   value={data.total}          color="#c9d8e8" />
                  <StatBox label="WIN RATE"        value={`${data.win_rate}%`} color={data.win_rate >= 55 ? '#00ff88' : data.win_rate >= 45 ? '#fbbf24' : '#ff4466'} />
                  <StatBox label="AVG WIN"         value={`+${data.avg_win_pct}%`}  color="#00ff88" />
                  <StatBox label="AVG LOSS"        value={`${data.avg_loss_pct}%`}  color="#ff4466" />
                  <StatBox label="PROFIT FACTOR"   value={data.profit_factor}  color={data.profit_factor >= 1.5 ? '#00ff88' : data.profit_factor >= 1 ? '#fbbf24' : '#ff4466'} sub=">1.5 = excellent" />
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

              {/* Regime breakdown */}
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
              <div style={{ color:'#4a6070', fontSize:12, fontFamily:'sans-serif' }}>No closed signals yet</div>
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
