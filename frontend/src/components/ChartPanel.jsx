import React, { useState, useEffect, useRef } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';

const PAD = { l:66, r:72, t:22, b:36 };

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

function pyf(price, minP, maxP, h) {
  return PAD.t + (1 - (price - minP) / (maxP - minP)) * (h - PAD.t - PAD.b);
}
function ixf(i, total, w) {
  return PAD.l + (i + 0.5) * ((w - PAD.l - PAD.r) / total);
}

// ── MTF Block ──────────────────────────────────────────────
const MTFBlock = ({ mtf }) => {
  if (!mtf || !Object.keys(mtf).length) return null;
  const rows = [['1H','tf_1h'],['4H','tf_4h'],['1D','tf_1d'],['1W','tf_1w']];
  return (
    <div>
      <div style={{ color:'#2a4a5a', fontSize:8, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>MTF</div>
      {rows.map(([label, key]) => {
        const val = mtf[key] || '—';
        const isBull = val === 'BULL', isBear = val === 'BEAR';
        const c = isBull ? '#00ff88' : isBear ? '#ff4466' : '#fbbf24';
        const Icon = isBull ? TrendingUp : isBear ? TrendingDown : Minus;
        return (
          <div key={key} style={{ display:'flex', alignItems:'center', gap:5, marginBottom:4 }}>
            <span style={{ color:'#4a6070', fontSize:9, width:22, fontFamily:'sans-serif' }}>{label}</span>
            <Icon size={9} color={c} />
            <span style={{ color:c, fontSize:10, fontWeight:'bold', fontFamily:'sans-serif' }}>{val}</span>
          </div>
        );
      })}
    </div>
  );
};

// ── PnL Benchmark Block ───────────────────────────────────
const PnLBlock = ({ candles, signals }) => {
  if (!candles?.length) return null;

  // Buy & Hold: first close → last close
  const firstPrice = candles[0].c;
  const lastPrice  = candles[candles.length - 1].c;
  const bnh = ((lastPrice - firstPrice) / firstPrice * 100).toFixed(1);
  const bnhPos = parseFloat(bnh) >= 0;

  // Buy/Sell compound P&L: pair BUY→SELL signals in order
  let compound = 0;
  let trades = 0;
  if (signals?.length) {
    const buys  = signals.filter(s => s.type === 'BUY');
    const sells = signals.filter(s => s.type === 'SELL');
    // Pair them: earliest buy + earliest sell after that buy
    let usedSells = new Set();
    for (const buy of buys) {
      const matchSell = sells.find((s, i) => !usedSells.has(i) && s.t > buy.t);
      if (matchSell) {
        const idx = sells.indexOf(matchSell);
        usedSells.add(idx);
        const gain = (matchSell.price - buy.price) / buy.price * 100;
        compound += gain;
        trades++;
      }
    }
  }
  const bsPos = compound >= 0;

  return (
    <div style={{ marginTop:14, paddingTop:12, borderTop:'1px solid #1a2535' }}>
      <div style={{ color:'#2a4a5a', fontSize:8, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:8 }}>P&L BENCHMARK</div>
      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
        <div>
          <div style={{ color:'#4a6070', fontSize:8, fontFamily:'sans-serif', marginBottom:2 }}>Buy & Hold</div>
          <span style={{ color: bnhPos ? '#00ff88' : '#ff4466', fontSize:13, fontWeight:'bold', fontFamily:'monospace' }}>
            {bnhPos ? '+' : ''}{bnh}%
          </span>
        </div>
        <div>
          <div style={{ color:'#4a6070', fontSize:8, fontFamily:'sans-serif', marginBottom:2 }}>
            Buy/Sell {trades > 0 ? `(${trades} trades)` : '(no pairs)'}
          </div>
          <span style={{ color: bsPos ? '#00ff88' : '#ff4466', fontSize:13, fontWeight:'bold', fontFamily:'monospace' }}>
            {trades > 0 ? `${bsPos ? '+' : ''}${compound.toFixed(1)}%` : '—'}
          </span>
        </div>
      </div>
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
  const [dims, setDims]       = useState({ w:900, h:520 });
  const wrapRef = useRef(null);

  useEffect(() => {
    const ro = new ResizeObserver(entries => {
      const w = entries[0].contentRect.width;
      if (w > 0) setDims({ w, h: Math.max(460, Math.round(w * 0.58)) });
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
    if (!VALID_COMBOS[iv]?.includes(period)) setPeriod(VALID_COMBOS[iv]?.[VALID_COMBOS[iv].length - 1] || '6M');
  };

  const btnStyle = (active, color = '#00d4ff') => ({
    background: active ? '#1a2535' : 'transparent',
    color: active ? color : '#4a6070',
    border: `1px solid ${active ? '#1e3040' : '#0d1420'}`,
    borderRadius: 4, padding: '3px 8px', fontSize: 10,
    fontWeight: 'bold', cursor: 'pointer', fontFamily: 'sans-serif', transition: 'all 0.15s'
  });

  // Last price + day change from candles
  const lastCandle     = data?.candles?.[data.candles.length - 1];
  const prevCandle     = data?.candles?.[data.candles.length - 2];
  const lastPrice      = lastCandle?.c;
  const dayChange      = lastCandle && prevCandle ? ((lastCandle.c - prevCandle.c) / prevCandle.c * 100) : null;
  const changePositive = dayChange !== null && dayChange >= 0;

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
    const pad    = (rawMax - rawMin) * 0.09;
    const minP   = rawMin - pad;
    const maxP   = rawMax + pad;

    const cw   = Math.max(1.5, (w - PAD.l - PAD.r) / candles.length - 0.8);
    const priceFn = p => pyf(p, minP, maxP, h);
    const idxFn   = i => ixf(i, candles.length, w);

    // Date label index map for signal positioning
    const tMap = {};
    candles.forEach((c, i) => { tMap[c.t] = i; });

    // Y ticks
    const ticks = [];
    for (let i = 0; i <= 7; i++) ticks.push(minP + i * (maxP - minP) / 7);

    // X labels
    const every = Math.max(1, Math.round(candles.length / 8));
    const dateLabels = candles.map((c, i) => ({ i, t: c.t })).filter((_, i) => i % every === 0);

    return (
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display:'block' }}>
        {/* Plot bg */}
        <rect x={PAD.l} y={PAD.t} width={w - PAD.l - PAD.r} height={h - PAD.t - PAD.b} fill="#050810" rx="2" />

        {/* Grid + Y labels */}
        {ticks.map((p, i) => {
          const y = priceFn(p);
          return (
            <g key={i}>
              <line x1={PAD.l} y1={y} x2={w - PAD.r} y2={y} stroke="#1a2535" strokeWidth="0.5" />
              <text x={PAD.l - 4} y={y + 4} textAnchor="end" fontSize="9" fill="#3a5060" fontFamily="monospace">
                {p >= 1000 ? p.toFixed(0) : p.toFixed(2)}
              </text>
            </g>
          );
        })}

        {/* X date labels */}
        {dateLabels.map(({ i, t }) => (
          <text key={i} x={idxFn(i)} y={h - 8} textAnchor="middle" fontSize="8" fill="#3a5060" fontFamily="monospace">
            {interval === '1h' || interval === '4h' ? t.slice(5, 13) : t.slice(5)}
          </text>
        ))}

        {/* Channel */}
        {channel && (
          <g opacity="0.4">
            <line x1={PAD.l} y1={priceFn(channel.upper[0])} x2={w-PAD.r} y2={priceFn(channel.upper[1])} stroke="#7c3aed" strokeWidth="1.2" strokeDasharray="5 3" />
            <line x1={PAD.l} y1={priceFn(channel.mid[0])}   x2={w-PAD.r} y2={priceFn(channel.mid[1])}   stroke="#7c3aed" strokeWidth="0.7" strokeDasharray="2 5" />
            <line x1={PAD.l} y1={priceFn(channel.lower[0])} x2={w-PAD.r} y2={priceFn(channel.lower[1])} stroke="#7c3aed" strokeWidth="1.2" strokeDasharray="5 3" />
          </g>
        )}

        {/* S/R levels */}
        {sr_levels.map((s, i) => {
          const c = s.type === 'resistance' ? '#ff4466' : '#00ff88';
          return (
            <g key={i}>
              <line x1={PAD.l} y1={priceFn(s.level)} x2={w-PAD.r} y2={priceFn(s.level)} stroke={c} strokeWidth="0.8" strokeDasharray="5 4" opacity="0.45" />
              <text x={w-PAD.r+3} y={priceFn(s.level)+3} fontSize="7" fill={c} fontFamily="monospace" opacity="0.8">{s.level}</text>
            </g>
          );
        })}

        {/* Trade params: entry zone + SL */}
        {tp && (
          <g>
            <rect x={PAD.l} y={priceFn(tp.entry_high)} width={w-PAD.l-PAD.r}
              height={Math.max(2, Math.abs(priceFn(tp.entry_low) - priceFn(tp.entry_high)))}
              fill="rgba(0,255,136,0.07)" stroke="rgba(0,255,136,0.25)" strokeWidth="0.5" />
            <line x1={PAD.l} y1={priceFn(tp.sl)} x2={w-PAD.r} y2={priceFn(tp.sl)} stroke="#ff4466" strokeWidth="1.5" strokeDasharray="6 3" />
            <text x={PAD.l+4} y={priceFn(tp.sl)-4} fontSize="8" fill="#ff4466" fontFamily="sans-serif">SL ${tp.sl}</text>
          </g>
        )}

        {/* Candles or Line */}
        {chartType === 'candle' ? candles.map((c, i) => {
          const x   = idxFn(i);
          const isG = c.c >= c.o;
          const col = isG ? '#00c97a' : '#ff4466';
          const top = priceFn(Math.max(c.o, c.c));
          const bot = priceFn(Math.min(c.o, c.c));
          const bh  = Math.max(1, bot - top);
          return (
            <g key={i}>
              <line x1={x} y1={priceFn(c.h)} x2={x} y2={priceFn(c.l)} stroke={col} strokeWidth="0.9" opacity="0.8" />
              <rect x={x - cw/2} y={top} width={cw} height={bh} fill={col} opacity="0.88" />
            </g>
          );
        }) : (
          <polyline points={candles.map((c, i) => `${idxFn(i)},${priceFn(c.c)}`).join(' ')}
            fill="none" stroke="#00d4ff" strokeWidth="1.8" />
        )}

        {/* BUY/SELL signal markers — improved positioning */}
        {signals.map((sig, idx) => {
          const ci = tMap[sig.t];
          if (ci === undefined) return null;
          const x    = idxFn(ci);
          const candle = candles[ci];
          const isBuy  = sig.type === 'BUY';
          const c      = isBuy ? '#00ff88' : '#ff4466';
          const priceLabel = `$${sig.price}`;

          if (isBuy) {
            // BUY: below the candle low
            const lowY    = priceFn(candle ? candle.l : sig.price);
            const arrowTip = lowY + 14;
            const arrowBase = lowY + 6;
            return (
              <g key={idx}>
                {/* upward triangle below bar */}
                <polygon points={`${x},${arrowBase} ${x-6},${arrowTip} ${x+6},${arrowTip}`} fill={c} opacity="0.95" />
                <text x={x} y={arrowTip + 10} textAnchor="middle" fontSize="8" fill={c} fontFamily="sans-serif" fontWeight="bold">BUY</text>
                <text x={x} y={arrowTip + 20} textAnchor="middle" fontSize="7" fill={c} fontFamily="monospace" opacity="0.85">{priceLabel}</text>
              </g>
            );
          } else {
            // SELL: above the candle high
            const highY    = priceFn(candle ? candle.h : sig.price);
            const arrowTip = highY - 14;
            const arrowBase = highY - 6;
            return (
              <g key={idx}>
                <text x={x} y={arrowTip - 10} textAnchor="middle" fontSize="7" fill={c} fontFamily="monospace" opacity="0.85">{priceLabel}</text>
                <text x={x} y={arrowTip - 1} textAnchor="middle" fontSize="8" fill={c} fontFamily="sans-serif" fontWeight="bold">SELL</text>
                {/* downward triangle above bar */}
                <polygon points={`${x},${arrowBase} ${x-6},${arrowTip} ${x+6},${arrowTip}`} fill={c} opacity="0.95" />
              </g>
            );
          }
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

      {/* ── Header ── */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap',
        gap:8, borderBottom:'1px solid #1a2535', padding:'8px 14px', background:'#0a0f18' }}>

        {/* Left: symbol + last price + change */}
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <span style={{ color:'#00d4ff', fontSize:11, fontWeight:'bold', letterSpacing:1 }}>
            📊 {symbol || '—'} CHART
          </span>
          {lastPrice && (
            <span style={{ color:'#c9d8e8', fontSize:12, fontWeight:'bold', fontFamily:'monospace' }}>
              ${lastPrice.toFixed(2)}
            </span>
          )}
          {dayChange !== null && (
            <span style={{ color: changePositive ? '#00ff88' : '#ff4466', fontSize:11,
              fontFamily:'sans-serif', fontWeight:'bold' }}>
              {changePositive ? '▲' : '▼'} {Math.abs(dayChange).toFixed(2)}%
            </span>
          )}
        </div>

        {/* Right: controls */}
        <div style={{ display:'flex', gap:4, alignItems:'center', flexWrap:'wrap' }}>
          {INTERVALS.map(iv => (
            <button key={iv.key} style={btnStyle(interval === iv.key)} onClick={() => setInterval(iv.key)}>{iv.label}</button>
          ))}
          <div style={{ width:1, height:14, background:'#1a2535', margin:'0 2px' }} />
          {PERIODS.map(p => {
            const valid = VALID_COMBOS[interval]?.includes(p.key);
            return (
              <button key={p.key} onClick={() => valid && setPeriod(p.key)}
                style={{ ...btnStyle(period === p.key, '#fbbf24'), opacity: valid ? 1 : 0.3, cursor: valid ? 'pointer' : 'default' }}>
                {p.label}
              </button>
            );
          })}
          <div style={{ width:1, height:14, background:'#1a2535', margin:'0 2px' }} />
          <button style={btnStyle(chartType === 'candle')} onClick={() => setType('candle')}>Candles</button>
          <button style={btnStyle(chartType === 'line')}   onClick={() => setType('line')}>Line</button>
          <button onClick={fetchChart} style={{ background:'transparent', border:'none', color:'#4a6070', cursor:'pointer', padding:'2px 4px' }}>
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      {/* ── Chart + right panel ── */}
      <div style={{ display:'flex', gap:0 }}>

        {/* Chart SVG */}
        <div style={{ flex:1, padding:'8px 4px 4px', minWidth:0 }}>
          {loading && <div style={{ color:'#4a6070', fontSize:11, padding:40, textAlign:'center', fontFamily:'sans-serif' }}>Loading chart...</div>}
          {error   && <div style={{ color:'#ff4466', fontSize:11, padding:40, textAlign:'center', fontFamily:'sans-serif' }}>⚠ {error}</div>}
          {!loading && !error && renderSVG()}
        </div>

        {/* Right panel: MTF + PnL */}
        {(data?.mtf || data?.candles?.length) && (
          <div style={{ padding:'14px 14px 14px 12px', borderLeft:'1px solid #1a2535',
            display:'flex', flexDirection:'column', minWidth:110, flexShrink:0 }}>
            <MTFBlock mtf={data?.mtf} />
            <PnLBlock candles={data?.candles} signals={data?.signals} />
          </div>
        )}
      </div>

      {/* ── Legend ── */}
      <div style={{ borderTop:'1px solid #1a2535', padding:'6px 14px', display:'flex', gap:14, flexWrap:'wrap', alignItems:'center' }}>
        {[['🟢 BUY','#00ff88'],['🔴 SELL','#ff4466'],['Channel','#7c3aed'],['S/R','#94a3b8']].map(([lbl, c]) => (
          <div key={lbl} style={{ display:'flex', alignItems:'center', gap:4 }}>
            <div style={{ width:14, height:2, background:c, borderRadius:1 }} />
            <span style={{ color:'#4a6070', fontSize:9, fontFamily:'sans-serif' }}>{lbl}</span>
          </div>
        ))}
        {data?.signals?.length > 0 && (
          <span style={{ color:'#4a6070', fontSize:9, fontFamily:'sans-serif', marginLeft:'auto' }}>
            {data.signals.filter(s => s.type === 'BUY').length} buys · {data.signals.filter(s => s.type === 'SELL').length} sells
          </span>
        )}
      </div>
    </div>
  );
};

export default ChartPanel;
