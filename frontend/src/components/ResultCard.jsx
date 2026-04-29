import React from 'react';
import { TrendingUp, TrendingDown, ShieldAlert, ShieldCheck, Minus, AlertTriangle } from 'lucide-react';
import { useState, useEffect } from 'react';

const DecisionRow = ({ label, value, suffix, color }) => (
  <div style={{ display:'flex', alignItems:'center', gap:8, padding:'3px 0' }}>
    <span style={{ color:'#4a6070', fontSize:10, width:60, fontFamily:'sans-serif', flexShrink:0 }}>{label}:</span>
    <span style={{ color:color||'#c9d8e8', fontWeight:'bold', fontSize:13, fontFamily:"'Courier New',monospace" }}>{value}</span>
    {suffix && <span style={{ color:'#94a3b8', fontSize:11, fontFamily:'sans-serif' }}>({suffix})</span>}
  </div>
);

const MTFRow = ({ label, val }) => {
  const isBull = val === 'BULL';
  const isBear = val === 'BEAR';
  const c = isBull ? '#00ff88' : isBear ? '#ff4466' : '#fbbf24';
  const Icon = isBull ? TrendingUp : isBear ? TrendingDown : Minus;
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8, padding:'2px 0' }}>
      <span style={{ color:'#4a6070', fontSize:10, width:30, fontFamily:'sans-serif', flexShrink:0 }}>{label}</span>
      <span style={{ background:`${c}14`, color:c, border:`1px solid ${c}33`, fontSize:10,
        fontWeight:'bold', padding:'1px 9px', borderRadius:3, fontFamily:'sans-serif', letterSpacing:1 }}>
        {val || '—'}
      </span>
      <Icon size={10} color={c} />
    </div>
  );
};

const ResultCard = ({ result }) => {
  if (!result) return null;
  const { consensus_view, confidence_score, executioner_decision, full_report, trade_params, mtf_analysis, symbol } = result;

  const [earnings, setEarnings] = useState(null);
  const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

  useEffect(() => {
    if (!symbol && !result.symbol) return;
    const sym = symbol || result.symbol;
    fetch(`${API}/api/earnings/${sym}`)
      .then(r => r.json()).then(d => setEarnings(d)).catch(() => {});
  }, [result]);

  const decision = executioner_decision || 'PENDING';
  const upper = decision.toUpperCase();
  const isBuy  = upper.includes('BUY');
  const isSell = upper.includes('SELL') || upper.includes('HALT');

  let decisionColor = '#fbbf24';
  let Icon = ShieldCheck;
  let actionLabel = 'HOLD';
  if (isBuy)  { decisionColor = '#00ff88'; Icon = TrendingUp;  actionLabel = 'BUY'; }
  if (isSell) { decisionColor = '#ff4466'; Icon = ShieldAlert; actionLabel = upper.includes('SELL') ? 'SELL' : 'HALT'; }

  const convPct = (confidence_score * 100).toFixed(1);

  return (
    <div style={{ background:'linear-gradient(135deg,#080c14,#0a1020)', border:`1px solid ${decisionColor}33`,
      borderRadius:10, marginTop:16, overflow:'hidden', fontFamily:"'Courier New',monospace" }}>

      {/* ── Header ── */}
      <div style={{ background:`${decisionColor}10`, borderBottom:`1px solid ${decisionColor}22`,
        padding:'10px 16px', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8, color:decisionColor, fontSize:11, fontWeight:'bold', letterSpacing:2 }}>
          <Icon size={14} /> FINAL DECISION
        </div>
        <div style={{ color:'#4a6070', fontSize:10, fontFamily:'sans-serif', letterSpacing:1 }}>
          CONFIDENCE: <span style={{ color:decisionColor, fontWeight:'bold' }}>{convPct}%</span>
        </div>
      </div>

      <div style={{ padding:'14px 16px' }}>
      {/* ── Earnings Warning ── */}
      {earnings?.warning && (
        <div style={{ background:'#2a1500', border:'1px solid #f97316', borderRadius:6,
          padding:'8px 12px', marginBottom:12, display:'flex', alignItems:'center', gap:8 }}>
          <AlertTriangle size={13} color="#f97316" />
          <span style={{ color:'#f97316', fontSize:11, fontFamily:'sans-serif', fontWeight:'bold' }}>
            {earnings.warning_msg}
          </span>
          <span style={{ color:'#7c4a1e', fontSize:10, fontFamily:'sans-serif', marginLeft:'auto' }}>
            {earnings.earnings_date}
          </span>
        </div>
      )}
      {earnings && !earnings.warning && earnings.earnings_date && (
        <div style={{ color:'#2a4a5a', fontSize:9, fontFamily:'sans-serif', marginBottom:8 }}>
          Next earnings: {earnings.earnings_date} ({earnings.days_until}d)
        </div>
      )}

      {/* ── Structured trade rows ── */}
        {trade_params ? (
          <div style={{ display:'flex', flexDirection:'column', gap:2, marginBottom:12 }}>
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:4 }}>
              <span style={{ color:decisionColor, fontWeight:800, fontSize:20, letterSpacing:2 }}>{actionLabel}</span>
              <span style={{ color:'#94a3b8', fontSize:12 }}>—</span>
              <span style={{ color:'#c9d8e8', fontSize:12, fontFamily:'sans-serif' }}>
                Strong conviction at <span style={{ color:decisionColor, fontWeight:'bold' }}>{convPct}%</span>
              </span>
            </div>
            <DecisionRow label="Entry"    value={`$${trade_params.entry_low}–$${trade_params.entry_high}`}        color="#c9d8e8" />
            <DecisionRow label="SL"       value={`$${trade_params.sl}`}    suffix={trade_params.sl_note}           color="#ff4466" />
            <DecisionRow label="TP1"      value={`$${trade_params.tp1}`}   suffix={`R:R ${trade_params.rr}:1`}     color="#00ff88" />
            <DecisionRow label="Position" value={`${trade_params.qty} shares ($${trade_params.risk_usd} risk)`}   color="#c084fc" />
          </div>
        ) : (
          <div style={{ color:decisionColor, fontWeight:800, fontSize:18, letterSpacing:2, marginBottom:12 }}>{actionLabel}</div>
        )}

        {/* ── Consensus view ── */}
        <div style={{ borderLeft:`2px solid ${decisionColor}44`, paddingLeft:12, marginBottom:14 }}>
          <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:4 }}>CONSENSUS VIEW</div>
          <p style={{ color:'#94a3b8', fontSize:12, fontStyle:'italic', lineHeight:1.6, fontFamily:'sans-serif', margin:0 }}>
            "{consensus_view}"
          </p>
        </div>

        {/* ── MTF Block ── */}
        {mtf_analysis && (
          <div style={{ borderTop:'1px solid #1a2535', paddingTop:12 }}>
            <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:8 }}>
              MULTI-TIMEFRAME ANALYSIS
            </div>
            <div style={{ display:'flex', gap:24 }}>
              <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
                <MTFRow label="1H" val={mtf_analysis.tf_1h} />
                <MTFRow label="4H" val={mtf_analysis.tf_4h} />
              </div>
              <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
                <MTFRow label="1D" val={mtf_analysis.tf_1d} />
                <MTFRow label="1W" val={mtf_analysis.tf_1w} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Agent badges ── */}
      <div style={{ borderTop:'1px solid #1a2535', padding:'10px 16px', display:'flex', gap:8, flexWrap:'wrap' }}>
        {[['HISTORIAN', full_report?.historian], ['NEWSROOM', full_report?.newsroom], ['MACRO', full_report?.macro]].map(([lbl, d]) => (
          <div key={lbl} style={{ background:'#0a0f18', border:'1px solid #1a2535', borderRadius:4, padding:'4px 10px' }}>
            <div style={{ color:'#2a4a5a', fontSize:8, letterSpacing:1, fontFamily:'sans-serif' }}>{lbl}</div>
            <div style={{ color:d ? '#00ff88' : '#4a6070', fontSize:9, fontFamily:'sans-serif' }}>{d ? 'Complete' : 'Pending'}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ResultCard;
