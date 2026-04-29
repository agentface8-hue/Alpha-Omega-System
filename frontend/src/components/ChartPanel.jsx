import React, { useState, useEffect, useRef } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';

const PAD = { l:66, r:70, t:20, b:36 };

const INTERVALS = [
  { key:'1h', label:'1H' }, { key:'4h', label:'4H' },
  { key:'1d', label:'1D' }, { key:'1w', label:'1W' }
];
const PERIODS = [
  { key:'1M', label:'1M' }, { key:'3M', label:'3M' }, { key:'6M', label:'6M' },
  { key:'1Y', label:'1Y' }, { key:'3Y', label:'3Y' }, { key:'5Y', label:'5Y' }
];
const VALID_COMBOS = {
  '1h': ['1M','3M'], '4h': ['1M','3M','6M'],
  '1d': ['1M','3M','6M','1Y','3Y','5Y'], '1w': ['1M','3M','6M','1Y','3Y','5Y']
};

function py(price, minP, maxP, h) {
  return PAD.t + (1 - (price - minP) / (maxP - minP)) * (h - PAD.t - PAD.b);
}
function ix(i, total, w) {
  return PAD.l + (i + 0.5) * ((w - PAD.l - PAD.r) / total);
}

const MTFBlock = ({ mtf }) => {
  if (!mtf || !Object.keys(mtf).length) return null;
  const rows = [['1H','tf_1h'],['4H','tf_4h'],['1D','tf_1d'],['1W','tf_1w']];
  return (
    <div style={{ borderLeft:'1px solid #1a2535', paddingLeft:12, minWidth:90 }}>
      <div style={{ color:'#2a4a5a', fontSize:8, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>MTF</div>
      {rows.map(([label, key]) => {
        const val = mtf[key] || '—';
        const isBull = val === 'BULL', isBear = val === 'BEAR';
        const c = isBull ? '#00ff88' : isBear ? '#ff4466' : '#fbbf24';
        const Icon = isBull ? TrendingUp : isBear ? TrendingDown : Minus;
        return (
          <div key={key} style={{ display:'flex', alignItems:'center', gap:5, marginBottom:3 }}>
            <span style={{ color:'#4a6070', fontSize:9, width:20, fontFamily:'sans-serif' }}>{label}</span>
            <Icon size={9} color={c} />
            <span style={{ color:c, fontSize:9, fontWeight:'bold', fontFamily:'sans-serif' }}>{val}</span>
          </div>
        );
      })}
    </div>
  );
};

const ChartPanel = ({ symbol, tradeParams }) => {
  const [data, setData]       = useState(null);
  const [interval, setIv]     = useState('1d');
  const [period, setPeriod]   = useState('6M');
  const [chartType, setType]  = useState('candle');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [dims, setDims]       = useState({ w:900, h:480 });
  const wrapRef = useRef(null);

  useEffect(() => {
    const ro = new ResizeObserver(entries => {
      const w = entries[0].contentRect.width;
      if (w > 0) setDims({ w, h: Math.max(400, Math.round(w * 0.52)) });
    });
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => { if (symbol) fetchChart(); }, [symbol, interval, period]);

  const fetchChart = async () => {
    setLoading(true); setError(null); setData(null);
    try {
      const base = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
      const res  = await fetch(`${base}/api/chart/${symbol}?interval=${interval}&period=${period}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  const setInterval = (iv) => {
    setIv(iv);
    // Auto-adjust period if not valid for this interval
    if (!VALID_COMBOS[iv]?.includes(period)) {
      setPeriod(VALID_COMBOS[iv]?.[VALID_COMBOS[iv].length - 1] || '6M');
    }
  };

  const btnStyle = (active, color='#00d4ff') => ({
    background: active ? '#1a2535' : 'transparent',
    color: active ? color : '#4a6070',
    border: `1px solid ${active ? '#1e3040' : '#0d1420'}`,
    borderRadius: 4, padding: '3px 8px', fontSize: 10,
    fontWeight: 'bold', cursor: 'pointer', fontFamily: 'sans-serif', transition: 'all 0.15s'
  });

  const renderSVG = () => {
    if (!data?.candles?.length) return null;
    const { candles, sr_levels = [], channel, signals = [] } = data;
    const { w, h } = dims;
    const tp = tradeParams;

    const allPrices = candles.flatMap(c => [c.h, c.l]);
    if (tp) allPrices.push(tp.entry_low, tp.entry_high, tp.sl, tp.tp1);
    if (channel) allPrices.push(...channel.upper, ...channel.lower);
    sr_levels.forEach(s => allPrices.push(s.level));
    signals.forEach(s => allPrices.push(s.price));

    const rawMin = Math.min(...allPrices);
    const rawMax = Math.max(...allPrices);
    const pad    = (rawMax - rawMin) * 0.07;
    const minP   = rawMin - pad;
    const maxP   = rawMax + pad;

    const cw  = Math.max(1.5, (w - PAD.l - PAD.r) / candles.length - 0.8);
    const pyf = p => py(p, minP, maxP, h);
    const ixf = i => ix(i, candles.length, w);
    const n   = candles.length - 1;

    // Build date label index map for signal positioning
    const tMap = {};
    candles.forEach((c, i) => { tMap[c.t] = i; });

    // Y ticks
    const ticks = [];
    for (let i = 0; i <= 7; i++) {
      const p = minP + i * (maxP - minP) / 7;
      ticks.push({ p, y: pyf(p) });
    }

    // X labels every N candles
    const every = Math.max(1, Math.round(candles.length / 8));
    const dateLabels = candles
      .map((c, i) => ({ i, t: c.t }))
      .filter((_, i) => i % every === 0);

    return (
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display:'block' }}>
        {/* Plot background */}
        <rect x={PAD.l} y={PAD.t} width={w - PAD.l - PAD.r} height={h - PAD.t - PAD.b} fill="#050810" rx="2" />

        {/* Grid */}
        {ticks.map(({ p, y }, i) => (
          <g key={i}>
            <line x1={PAD.l} y1={y} x2={w - PAD.r} y2={y} stroke="#1a2535" strokeWidth="0.5" />
            <text x={PAD.l - 4} y={y + 4} textAnchor="end" fontSize="9" fill="#3a5060" fontFamily="monospace">
              {p >= 1000 ? p.toFixed(0) : p.toFixed(2)}
            </text>
          </g>
        ))}

        {/* X date labels */}
        {dateLabels.map(({ i, t }) => (
          <text key={i} x={ixf(i)} y={h - 8} textAnchor="middle" fontSize="8" fill="#3a5060" fontFamily="monospace">
            {interval === '1h' || interval === '4h' ? t.slice(5, 13) : t.slice(5)}
          </text>
        ))}

        {/* Channel */}
        {channel && (
          <g opacity="0.45">
            <line x1={PAD.l} y1={pyf(channel.upper[0])} x2={w-PAD.r} y2={pyf(channel.upper[1])} stroke="#7c3aed" strokeWidth="1.2" strokeDasharray="5 3" />
            <line x1={PAD.l} y1={pyf(channel.mid[0])}   x2={w-PAD.r} y2={pyf(channel.mid[1])}   stroke="#7c3aed" strokeWidth="0.7" strokeDasharray="2 5" />
            <line x1={PAD.l} y1={pyf(channel.lower[0])} x2={w-PAD.r} y2={pyf(channel.lower[1])} stroke="#7c3aed" strokeWidth="1.2" strokeDasharray="5 3" />
          </g>
        )}

        {/* S/R levels */}
        {sr_levels.map((s, i) => {
          const c = s.type === 'resistance' ? '#ff4466' : '#00ff88';
          return (
            <g key={i}>
              <line x1={PAD.l} y1={pyf(s.level)} x2={w-PAD.r} y2={pyf(s.level)} stroke={c} strokeWidth="0.8" strokeDasharray="5 4" opacity="0.5" />
              <text x={w-PAD.r+3} y={pyf(s.level)+3} fontSize="7" fill={c} fontFamily="monospace" opacity="0.8">{s.level}</text>
            </g>
          );
        })}

        {/* Trade params */}
        {tp && (
          <g>
            <rect x={PAD.l} y={pyf(tp.entry_high)} width={w-PAD.l-PAD.r}
              height={Math.max(2, Math.abs(pyf(tp.entry_low) - pyf(tp.entry_high)))}
              fill="rgba(0,255,136,0.07)" stroke="rgba(0,255,136,0.25)" strokeWidth="0.5" />
            <line x1={PAD.l} y1={pyf(tp.sl)} x2={w-PAD.r} y2={pyf(tp.sl)} stroke="#ff4466" strokeWidth="1.5" strokeDasharray="6 3" />
            <text x={PAD.l+4} y={pyf(tp.sl)-4} fontSize="8" fill="#ff4466" fontFamily="sans-serif">SL ${tp.sl}</text>
            <text x={PAD.l+4} y={pyf(tp.entry_low)+11} fontSize="8" fill="#00ff88" fontFamily="sans-serif">Entry ${tp.entry_low}–${tp.entry_high}</text>
          </g>
        )}

        {/* Candles or Line */}
        {chartType === 'candle' ? candles.map((c, i) => {
          const x   = ixf(i);
          const isG = c.c >= c.o;
          const col = isG ? '#00c97a' : '#ff4466';
          const top = pyf(Math.max(c.o, c.c));
          const bot = pyf(Math.min(c.o, c.c));
          const bh  = Math.max(1, bot - top);
          return (
            <g key={i}>
              <line x1={x} y1={pyf(c.h)} x2={x} y2={pyf(c.l)} stroke={col} strokeWidth="0.9" opacity="0.8" />
              <rect x={x - cw/2} y={top} width={cw} height={bh} fill={col} opacity="0.88" />
            </g>
          );
        }) : (
          <polyline points={candles.map((c,i)=>`${ixf(i)},${pyf(c.c)}`).join(' ')}
            fill="none" stroke="#00d4ff" strokeWidth="1.8" />
        )}

        {/* Buy/Sell signal markers */}
        {signals.map((sig, i) => {
          const idx = tMap[sig.t];
          if (idx === undefined) return null;
          const x   = ixf(idx);
          const yp  = pyf(sig.price);
          const isBuy = sig.type === 'BUY';
          const c   = isBuy ? '#00ff88' : '#ff4466';
          const arrowY = isBuy ? yp + 14 : yp - 14;
          const labelY = isBuy ? yp + 26 : yp - 18;
          return (
            <g key={i}>
              <polygon
                points={isBuy
                  ? `${x},${yp} ${x-5},${arrowY} ${x+5},${arrowY}`
                  : `${x},${yp} ${x-5},${arrowY} ${x+5},${arrowY}`}
                fill={c} opacity="0.9" />
              <text x={x} y={labelY} textAnchor="middle" fontSize="7" fill={c}
                fontFamily="sans-serif" fontWeight="bold">
                {isBuy ? 'BUY' : 'SELL'}
              </text>
            </g>
          );
        })}

        {/* Axes */}
        <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={h-PAD.b} stroke="#1e2d3d" strokeWidth="1" />
        <line x1={PAD.l} y1={h-PAD.b} x2={w-PAD.r} y2={h-PAD.b} stroke="#1e2d3d" strokeWidth="1" />
      </svg>
    );
  };

  return (
    <div ref={wrapRef} style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:10,
      marginTop:14, overflow:'hidden', fontFamily:"'Courier New',monospace" }}>

      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap',
        gap:8, borderBottom:'1px solid #1a2535', padding:'8px 14px', background:'#0a0f18' }}>
        <span style={{ color:'#00d4ff', fontSize:11, fontWeight:'bold', letterSpacing:1 }}>
          📊 {symbol || '—'} CHART
        </span>
        <div style={{ display:'flex', gap:4, alignItems:'center', flexWrap:'wrap' }}>
          {/* Interval */}
          {INTERVALS.map(iv => (
            <button key={iv.key} style={btnStyle(interval===iv.key)} onClick={() => setInterval(iv.key)}>{iv.label}</button>
          ))}
          <div style={{ width:1, height:14, background:'#1a2535', margin:'0 2px' }} />
          {/* Period */}
          {PERIODS.map(p => {
            const valid = VALID_COMBOS[interval]?.includes(p.key);
            return (
              <button key={p.key} style={{ ...btnStyle(period===p.key,'#fbbf24'), opacity: valid?1:0.3, cursor: valid?'pointer':'default' }}
                onClick={() => valid && setPeriod(p.key)}>{p.label}</button>
            );
          })}
          <div style={{ width:1, height:14, background:'#1a2535', margin:'0 2px' }} />
          <button style={btnStyle(chartType==='candle')} onClick={() => setType('candle')}>Candles</button>
          <button style={btnStyle(chartType==='line')}   onClick={() => setType('line')}>Line</button>
          <button onClick={fetchChart} style={{ background:'transparent', border:'none', color:'#4a6070', cursor:'pointer', padding:'2px 4px' }}>
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      {/* Chart + MTF side panel */}
      <div style={{ display:'flex', gap:0 }}>
        <div style={{ flex:1, padding:'8px 4px 4px', minWidth:0 }}>
          {loading && <div style={{ color:'#4a6070', fontSize:11, padding:30, textAlign:'center', fontFamily:'sans-serif' }}>Loading chart...</div>}
          {error   && <div style={{ color:'#ff4466', fontSize:11, padding:30, textAlign:'center', fontFamily:'sans-serif' }}>⚠ {error}</div>}
          {!loading && !error && renderSVG()}
        </div>
        {/* MTF panel */}
        {data?.mtf && (
          <div style={{ padding:'12px 14px', display:'flex', alignItems:'flex-start', borderLeft:'1px solid #1a2535' }}>
            <MTFBlock mtf={data.mtf} />
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{ borderTop:'1px solid #1a2535', padding:'6px 14px', display:'flex', gap:14, flexWrap:'wrap', alignItems:'center' }}>
        {[['🟢 BUY signal','#00ff88'],['🔴 SELL signal','#ff4466'],['Channel','#7c3aed'],['S/R','#94a3b8']].map(([lbl,c])=>(
          <div key={lbl} style={{ display:'flex', alignItems:'center', gap:4 }}>
            <div style={{ width:14, height:2, background:c, borderRadius:1 }} />
            <span style={{ color:'#4a6070', fontSize:9, fontFamily:'sans-serif' }}>{lbl}</span>
          </div>
        ))}
        {data?.signals?.length > 0 && (
          <span style={{ color:'#4a6070', fontSize:9, fontFamily:'sans-serif', marginLeft:'auto' }}>
            {data.signals.filter(s=>s.type==='BUY').length} buys · {data.signals.filter(s=>s.type==='SELL').length} sells
          </span>
        )}
      </div>
    </div>
  );
};

export default ChartPanel;
