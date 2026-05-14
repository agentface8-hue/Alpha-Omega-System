import React, { useState } from 'react';
import { Search, Activity, BarChart3, Brain, Briefcase, DollarSign, Moon,
         Maximize2, Minimize2, LayoutGrid, ChevronLeft } from 'lucide-react';
import Terminal           from './components/Terminal';
import ResultCard         from './components/ResultCard';
import LiveTicker         from './components/LiveTicker';
import TopStocks          from './components/TopStocks';
import ScanDashboard      from './components/ScanDashboard';
import BacktestDashboard  from './components/BacktestDashboard';
import SignalTracker      from './components/SignalTracker';
import ChartPanel         from './components/ChartPanel';
import AlphaMegaDashboard from './components/AlphaMegaDashboard';
import Analytics          from './components/Analytics';
import PortfolioTab       from './components/PortfolioTab';
import PrintingProfits    from './components/PrintingProfits';
import DreamLog           from './components/DreamLog';
import LoginScreen        from './components/LoginScreen';
import { playThinkingSound, playSuccessSound, playErrorSound } from './utils/sounds';

// ── Dashboard grid panels ─────────────────────────────────────────────────────
const PANELS = [
  { id:'portfolio', label:'PORTFOLIO',     icon:'📊', color:'#00ff88' },
  { id:'tracker',   label:'SIGNAL TRACKER',icon:'📈', color:'#c084fc' },
  { id:'scan',      label:'SWING SCAN v4.4',icon:'🔍', color:'#00d4ff' },
  { id:'dreams',    label:'DREAM LOG',     icon:'🌙', color:'#a78bfa' },
];

// ── Panel renderer ────────────────────────────────────────────────────────────
const PanelContent = ({ id, autoRun, compact = false }) => {
  if (id === 'portfolio')  return <PortfolioTab compact={compact} />;
  if (id === 'tracker')    return <SignalTracker compact={compact} />;
  if (id === 'scan')       return <ScanDashboard autoScan={autoRun} compact={compact} />;
  if (id === 'dreams')     return <DreamLog />;
  return null;
};

const App = () => {
  const [authed,        setAuthed]        = useState(() => localStorage.getItem('ao_auth') === '1');
  const [viewMode,      setViewMode]      = useState('dashboard');
  const [focusedPanel,  setFocusedPanel]  = useState(null);
  const [activeTab,     setActiveTab]     = useState('analyze');
  const [mountedPanels, setMountedPanels] = useState(['portfolio']); // staggered mount

  // Council Analyze state
  const [symbol,    setSymbol]    = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [logs,      setLogs]      = useState([]);
  const [result,    setResult]    = useState(null);
  const [error,     setError]     = useState(null);

  const getTimestamp = () => new Date().toLocaleTimeString('en-US',
    { hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:true });

  // Stagger panel mounts on dashboard load — one API at a time
  React.useEffect(() => {
    if (viewMode !== 'dashboard') return;
    setMountedPanels(['portfolio']); // reset on every dashboard open
    const t1 = setTimeout(() => setMountedPanels(p => [...p, 'tracker']), 900);
    const t2 = setTimeout(() => setMountedPanels(p => [...p, 'scan']),    1800);
    const t3 = setTimeout(() => setMountedPanels(p => [...p, 'dreams']),  2700);
    return () => [t1, t2, t3].forEach(clearTimeout);
  }, [viewMode]);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!symbol || isLoading) return;
    setIsLoading(true); setLogs([]); setResult(null); setError(null);
    const steps = [
      { agent:'The Historian',      action:'is analyzing...' },
      { agent:'The Newsroom',       action:'is analyzing...' },
      { agent:'The Macro-Strategist',action:'is analyzing...' },
      { agent:'Synthesis Engine',   action:'is analyzing...' },
      { agent:'The Contrarian',     action:'is analyzing...' },
      { agent:'The Executioner',    action:'is analyzing...' },
    ];
    let stepIndex = 0;
    const interval = setInterval(() => {
      if (stepIndex < steps.length) {
        const step = steps[stepIndex];
        playThinkingSound();
        setLogs(prev => [...prev, { timestamp:getTimestamp(),
          message:`>> ${step.agent} ${step.action}`, type:'info' }]);
        stepIndex++;
      } else { clearInterval(interval); }
    }, 800);
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
      const response = await fetch(`${apiUrl}/api/analyze`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ symbol }),
      });
      if (!response.ok) throw new Error(`Analysis failed (${response.status})`);
      const data = await response.json();
      setTimeout(() => {
        playSuccessSound(); setResult(data);
        setLogs(prev => [...prev, { timestamp:getTimestamp(),
          message:`✓ Analysis complete. Confidence: ${(data.confidence_score*100).toFixed(0)}%`,
          type:'success' }]);
        setIsLoading(false);
      }, steps.length * 800 + 500);
    } catch (err) {
      setTimeout(() => {
        playErrorSound(); setError(err.message);
        setLogs(prev => [...prev, { timestamp:getTimestamp(),
          message:`ERROR: ${err.message}`, type:'error' }]);
        setIsLoading(false);
      }, steps.length * 800 + 500);
    }
  };

  // ── Tab bar items ───────────────────────────────────────────────────────────
  const TAB_ITEMS = [
    { id:'alphamega', label:'ALPHA-MEGA',       color:'#c084fc' },
    { id:'analytics', label:'ANALYTICS',        color:'#00d4ff' },
    { id:'analyze',   label:'COUNCIL ANALYZE',  color:'#00d4ff' },
    { id:'printing',  label:'PRINTING PROFITS', color:'#fbbf24' },
    { id:'backtest',  label:'BACKTESTER',        color:'#a855f7' },
  ];

  // ── Focus mode: single panel full screen ────────────────────────────────────
  const renderFocused = () => {
    const panel = PANELS.find(p => p.id === focusedPanel);
    return (
      <div style={{ position:'fixed', inset:0, zIndex:100, background:'#050810',
        display:'flex', flexDirection:'column' }}>
        {/* Focus bar */}
        <div style={{ display:'flex', alignItems:'center', gap:12, padding:'8px 16px',
          background:'#080c14', borderBottom:`2px solid ${panel.color}`,
          flexShrink:0 }}>
          <button onClick={() => setFocusedPanel(null)}
            style={{ background:'transparent', border:`1px solid #1a2535`, borderRadius:6,
              padding:'5px 14px', color:'#8899aa', fontSize:11, fontFamily:'monospace',
              cursor:'pointer', display:'flex', alignItems:'center', gap:6, letterSpacing:1 }}>
            <ChevronLeft size={13}/> BACK TO GRID
          </button>
          <span style={{ color:panel.color, fontFamily:'monospace', fontWeight:'bold',
            fontSize:13, letterSpacing:2 }}>{panel.icon} {panel.label}</span>
        </div>
        {/* Full content */}
        <div style={{ flex:1, overflow:'auto' }}>
          <PanelContent id={focusedPanel} autoRun={true} />
        </div>
      </div>
    );
  };

  // ── Dashboard grid: 2×2 panels ──────────────────────────────────────────────
  const renderDashboard = () => (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gridTemplateRows:'1fr 1fr',
      height:'calc(100vh - 152px)', gap:2, background:'#0a0f18' }}>
      {PANELS.map(panel => (
        <div key={panel.id} style={{ display:'flex', flexDirection:'column',
          background:'#050810', overflow:'hidden', minHeight:0 }}>
          {/* Panel header */}
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between',
            padding:'6px 14px', background:'#080c14',
            borderBottom:`1px solid ${panel.color}33`, flexShrink:0 }}>
            <span style={{ color:panel.color, fontSize:10, fontWeight:'bold',
              fontFamily:'monospace', letterSpacing:2 }}>
              {panel.icon} {panel.label}
            </span>
            <button onClick={() => setFocusedPanel(panel.id)}
              title="Expand to full screen"
              style={{ background:'transparent', border:`1px solid #1a2535`,
                borderRadius:4, padding:'3px 8px', color:'#4a6a8a',
                cursor:'pointer', display:'flex', alignItems:'center', gap:4,
                fontSize:9, fontFamily:'monospace', letterSpacing:1 }}>
              <Maximize2 size={11}/> FOCUS
            </button>
          </div>
          {/* Scrollable content — only mount when it's this panel's turn */}
          <div style={{ flex:1, overflow:'auto', minHeight:0 }}>
            {mountedPanels.includes(panel.id)
              ? <PanelContent id={panel.id} autoRun={true} compact={true} />
              : <div style={{ display:'flex', alignItems:'center', justifyContent:'center',
                  height:'100%', color:'#2a4a5a', fontSize:11, fontFamily:'monospace',
                  letterSpacing:1 }}>
                  ⧗ QUEUED...
                </div>
            }
          </div>
        </div>
      ))}
    </div>
  );

  // ── Tab content ─────────────────────────────────────────────────────────────
  const renderTabContent = () => {
    if (activeTab === 'alphamega') return <AlphaMegaDashboard />;
    if (activeTab === 'analytics') return <Analytics />;
    if (activeTab === 'printing')  return <PrintingProfits />;
    if (activeTab === 'backtest')  return <BacktestDashboard />;
    // Council Analyze
    return (
      <main className="main-container">
        <form className="search-form" onSubmit={handleAnalyze}>
          <div className="search-input-wrapper">
            <input type="text" className="search-input" value={symbol}
              onChange={e => setSymbol(e.target.value.toUpperCase())}
              placeholder="ENTER TICKER" disabled={isLoading} />
            <button type="submit" className="search-button" disabled={isLoading || !symbol}>
              <Search size={20} />
            </button>
          </div>
        </form>
        <div className="search-hint">Press Enter to analyze a stock symbol</div>
        <div className="dashboard-grid">
          <div className="dashboard-main">
            <Terminal logs={logs} />
            {error && <div className="error-banner"><div className="error-icon">!</div><span>{error}</span></div>}
            <ResultCard result={result} />
            <ChartPanel symbol={result ? result.symbol : symbol} tradeParams={result?.trade_params} />
          </div>
          <div className="dashboard-sidebar"><TopStocks onSelectTicker={setSymbol} /></div>
        </div>
      </main>
    );
  };

  return (
    <div>
      {!authed && <LoginScreen onLogin={() => setAuthed(true)} />}
      {authed && <>
        <LiveTicker />

        {/* Header */}
        <header className="header">
          <div className="header-left">
            <div className="header-icon"><Activity size={26} /></div>
            <div>
              <div className="header-title">ALPHA - OMEGA</div>
              <div className="header-subtitle">Council of Experts Trading System</div>
            </div>
          </div>
          <div className="system-status">
            <span className="status-dot"></span>SYSTEM ONLINE
          </div>
        </header>

        {/* Tab bar */}
        <div style={{ display:'flex', gap:0, padding:'0 16px', background:'#080b0f',
          borderBottom:'1px solid #1a2535', overflowX:'auto' }}>
          {/* Dashboard toggle */}
          <button onClick={() => setViewMode('dashboard')}
            style={{ background: viewMode==='dashboard' ? '#0d1a2a' : 'transparent',
              color: viewMode==='dashboard' ? '#00ff88' : '#8899aa', border:'none',
              borderBottom: viewMode==='dashboard' ? '2px solid #00ff88' : '2px solid transparent',
              padding:'10px 18px', fontSize:11, fontWeight:'bold', fontFamily:'sans-serif',
              cursor:'pointer', display:'flex', alignItems:'center', gap:6,
              letterSpacing:1, whiteSpace:'nowrap' }}>
            <LayoutGrid size={14}/> DASHBOARD
          </button>
          {/* Other tabs */}
          {TAB_ITEMS.map(({ id, label, color }) => (
            <button key={id}
              onClick={() => { setViewMode('tab'); setActiveTab(id); }}
              style={{ background: viewMode==='tab' && activeTab===id ? '#0d1a2a' : 'transparent',
                color: viewMode==='tab' && activeTab===id ? color : '#8899aa', border:'none',
                borderBottom: viewMode==='tab' && activeTab===id ? `2px solid ${color}` : '2px solid transparent',
                padding:'10px 18px', fontSize:11, fontWeight:'bold', fontFamily:'sans-serif',
                cursor:'pointer', letterSpacing:1, whiteSpace:'nowrap' }}>
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        {focusedPanel
          ? renderFocused()
          : viewMode === 'dashboard'
            ? renderDashboard()
            : renderTabContent()
        }
      </>}
    </div>
  );
};

export default App;
