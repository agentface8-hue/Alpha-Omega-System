import React, { useState, useEffect } from 'react';
import { Search, Activity, BarChart3, Brain, Briefcase, DollarSign, Moon,
         Maximize2, LayoutGrid, ChevronLeft } from 'lucide-react';
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
import DeepScan from './components/DeepScan';
import DreamLog           from './components/DreamLog';
import SystemMonitor      from './components/SystemMonitor';
import LoginScreen        from './components/LoginScreen';
import AmaStatus          from './components/AmaStatus';
import PipelineBar        from './components/PipelineBar';
import { playThinkingSound, playSuccessSound, playErrorSound } from './utils/sounds';
import { warmupBackend } from './utils/api';

// ── Mobile detection ──────────────────────────────────────────────────────────
const useMobile = () => {
  const [m, setM] = useState(() => window.innerWidth < 768);
  useEffect(() => {
    const fn = () => setM(window.innerWidth < 768);
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);
  return m;
};

// ── Dashboard panels ──────────────────────────────────────────────────────────
const PANELS = [
  { id:'portfolio', label:'PORTFOLIO',      icon:'📊', short:'PORT',    color:'#00ff88' },
  { id:'tracker',   label:'SIGNAL TRACKER', icon:'📈', short:'SIGNALS', color:'#c084fc' },
  { id:'scan',      label:'SWING SCAN',     icon:'🔍', short:'SCAN',    color:'#00d4ff' },
  { id:'dreams',    label:'DREAM LOG',      icon:'🌙', short:'DREAM',   color:'#a78bfa' },
];

// ── Panel renderer ────────────────────────────────────────────────────────────
const PanelContent = ({ id, autoRun, compact = false, isOwner = false, backendReady = true }) => {
  if (id === 'portfolio') return <PortfolioTab compact={compact} isOwner={isOwner} backendReady={backendReady} />;
  if (id === 'tracker')   return <SignalTracker compact={compact} isOwner={isOwner} backendReady={backendReady} />;
  if (id === 'scan')      return <ScanDashboard autoScan={autoRun && backendReady} compact={compact} isOwner={isOwner} />;
  if (id === 'dreams')    return <DreamLog backendReady={backendReady} />;
  if (id === 'deepscan')  return <DeepScan />;
  return null;
};

const App = () => {
  const isMobile = useMobile();

  // Force re-login if old session has no role
  const hasValidSession = () => {
    const auth = localStorage.getItem('ao_auth') === '1';
    const role = localStorage.getItem('ao_role');
    if (auth && !role) {
      // Old session — clear it
      localStorage.removeItem('ao_auth');
      localStorage.removeItem('ao_username');
      localStorage.removeItem('ao_display_name');
      return false;
    }
    return auth;
  };

  const [authed,        setAuthed]        = useState(() => hasValidSession());
  const [userRole,      setUserRole]      = useState(() => localStorage.getItem('ao_role') || 'owner');
  const [displayName,   setDisplayName]   = useState(() => localStorage.getItem('ao_display_name') || '');
  const [viewMode,      setViewMode]      = useState('dashboard');
  const [focusedPanel,  setFocusedPanel]  = useState(null);
  const [activeTab,     setActiveTab]     = useState('analyze');
  const [mountedPanels, setMountedPanels] = useState([]);
  const [backendStatus, setBackendStatus] = useState('connecting');
  const [backendReady,  setBackendReady]  = useState(false);
  const [pipelineTick,  setPipelineTick]  = useState(0);
  const [mobilePanel,   setMobilePanel]   = useState('portfolio'); // active panel on mobile

  const isOwner = userRole === 'owner';

  const handleLogin = ({ username, role, display_name }) => {
    setUserRole(role);
    setDisplayName(display_name || username);
    setAuthed(true);
  };

  // ── Warm Render backend, then mount dashboard panels (staggered) ─────────
  React.useEffect(() => {
    if (!authed) return;
    let cancelled = false;
    setBackendStatus('connecting');
    setBackendReady(false);
    setMountedPanels([]);
    (async () => {
      const ok = await warmupBackend((st) => { if (!cancelled) setBackendStatus(st); });
      if (cancelled) return;
      setBackendReady(ok);
      setBackendStatus(ok ? 'ready' : 'slow');
      if (!ok) return;
      setMountedPanels(['portfolio']);
      setTimeout(() => setMountedPanels(p => [...p, 'tracker']), 400);
      setTimeout(() => setMountedPanels(p => [...p, 'scan']), 800);
      setTimeout(() => setMountedPanels(p => [...p, 'dreams']), 1200);
    })();
    return () => { cancelled = true; };
  }, [authed, pipelineTick]);

  // Council Analyze state
  const [symbol,    setSymbol]    = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [logs,      setLogs]      = useState([]);
  const [result,    setResult]    = useState(null);
  const [error,     setError]     = useState(null);

  const getTimestamp = () => new Date().toLocaleTimeString('en-US',
    { hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:true });

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
    { id:'monitor',   label:'LIVE MONITOR',     color:'#00ff88' },
    { id:'deepscan',  label:'DEEP SCAN',        color:'#1D9E75' },
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
          <PanelContent id={focusedPanel} autoRun={true} isOwner={isOwner} backendReady={backendReady} />
        </div>
      </div>
    );
  };

  // ── Dashboard (desktop 2x2 / mobile single panel) ───────────────────────────
  const renderDashboard = () => {
    // Backend waking screen
    if (!backendReady && mountedPanels.length === 0) {
      return (
        <div style={{ height: isMobile ? 'calc(100vh - 110px)' : 'calc(100vh - 152px)',
          display:'flex', alignItems:'center', justifyContent:'center',
          flexDirection:'column', gap:16, background:'#050810' }}>
          <div style={{ fontSize:28 }}>⧗</div>
          <div style={{ color:'#00d4ff', fontFamily:'monospace', fontSize:13, letterSpacing:3 }}>
            {backendStatus === 'slow' ? 'BACKEND WAKING UP...' : 'CONNECTING...'}
          </div>
          <div style={{ color:'#4a6a8a', fontSize:10, fontFamily:'sans-serif', textAlign:'center', padding:'0 20px' }}>
            {backendStatus === 'slow' ? 'Render free tier cold-starting — usually 30-60s' : 'Checking backend...'}
          </div>
        </div>
      );
    }

    // ── MOBILE: one panel at a time + bottom nav ──
    if (isMobile) {
      const panel = PANELS.find(p => p.id === mobilePanel) || PANELS[0];
      return (
        <div style={{ display:'flex', flexDirection:'column', height:'calc(100vh - 110px)' }}>
          {/* Panel content */}
          <div style={{ flex:1, overflow:'auto', background:'#050810' }}>
            {mountedPanels.includes(panel.id)
              ? <PanelContent id={panel.id} autoRun={true} compact={false} isOwner={isOwner} backendReady={backendReady} />
              : <div style={{ display:'flex', alignItems:'center', justifyContent:'center',
                  height:'200px', color:'#2a4a5a', fontSize:11, fontFamily:'monospace' }}>
                  ⧗ LOADING...
                </div>
            }
          </div>
          {/* Bottom nav bar */}
          <div style={{ display:'flex', background:'#080c14',
            borderTop:'1px solid #1a2535', flexShrink:0 }}>
            {PANELS.map(p => (
              <button key={p.id} onClick={() => { setMobilePanel(p.id); }}
                style={{ flex:1, background:'transparent', border:'none',
                  borderTop: mobilePanel===p.id ? `2px solid ${p.color}` : '2px solid transparent',
                  padding:'10px 4px 8px',
                  color: mobilePanel===p.id ? p.color : '#4a6a8a',
                  cursor:'pointer', display:'flex', flexDirection:'column',
                  alignItems:'center', gap:3 }}>
                <span style={{ fontSize:16 }}>{p.icon}</span>
                <span style={{ fontSize:8, fontFamily:'sans-serif', fontWeight:'bold',
                  letterSpacing:0.5 }}>{p.short}</span>
              </button>
            ))}
          </div>
        </div>
      );
    }

    // ── DESKTOP: 2×2 grid ──
    return (
      <div style={{ display:'flex', flexDirection:'column', height:'calc(100vh - 152px)', background:'#0a0f18' }}>
        {isOwner && (
          <div style={{ padding:'8px 10px 0', flexShrink:0 }}>
            <PipelineBar
              disabled={!backendReady}
              onComplete={() => setPipelineTick(t => t + 1)}
            />
          </div>
        )}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gridTemplateRows:'1fr 1fr',
        flex:1, minHeight:0, gap:2 }}>
        {PANELS.map(panel => (
          <div key={panel.id} style={{ display:'flex', flexDirection:'column',
            background:'#050810', overflow:'hidden', minHeight:0 }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between',
              padding:'6px 14px', background:'#080c14',
              borderBottom:`1px solid ${panel.color}33`, flexShrink:0 }}>
              <span style={{ color:panel.color, fontSize:10, fontWeight:'bold',
                fontFamily:'monospace', letterSpacing:2 }}>
                {panel.icon} {panel.label}
              </span>
              <button onClick={() => setFocusedPanel(panel.id)}
                style={{ background:'transparent', border:`1px solid #1a2535`,
                  borderRadius:4, padding:'3px 8px', color:'#4a6a8a',
                  cursor:'pointer', display:'flex', alignItems:'center', gap:4,
                  fontSize:9, fontFamily:'monospace', letterSpacing:1 }}>
                <Maximize2 size={11}/> FOCUS
              </button>
            </div>
            <div style={{ flex:1, overflow:'auto', minHeight:0 }}>
              {mountedPanels.includes(panel.id)
                ? <PanelContent id={panel.id} autoRun={true} compact={true} isOwner={isOwner} backendReady={backendReady} />
                : <div style={{ display:'flex', alignItems:'center', justifyContent:'center',
                    height:'100%', color:'#2a4a5a', fontSize:10, fontFamily:'monospace',
                    letterSpacing:2, flexDirection:'column', gap:8 }}>
                    <span>⧗</span><span>LOADING...</span>
                  </div>
              }
            </div>
          </div>
        ))}
      </div>
      </div>
    );
  };

  // ── Tab content ─────────────────────────────────────────────────────────────
  const renderTabContent = () => {
    if (activeTab === 'alphamega') return <AlphaMegaDashboard />;
    if (activeTab === 'analytics') return <Analytics />;
    if (activeTab === 'printing')  return <PrintingProfits />;
    if (activeTab === 'backtest')  return <BacktestDashboard />;
    if (activeTab === 'monitor')   return <SystemMonitor />;
    if (activeTab === 'deepscan')  return <DeepScan />;
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
      {!authed && <LoginScreen onLogin={handleLogin} />}
      {authed && <>
        <LiveTicker />

        {/* Header */}
        <header className="header" style={{ padding: isMobile ? '10px 14px' : undefined }}>
          <div className="header-left">
            <div className="header-icon" style={{ display: isMobile ? 'none' : undefined }}>
              <Activity size={26} />
            </div>
            <div>
              <div className="header-title" style={{ fontSize: isMobile ? 16 : undefined }}>
                ALPHA - OMEGA
              </div>
              {!isMobile && <div className="header-subtitle">Council of Experts Trading System</div>}
            </div>
          </div>
          <div className="system-status" style={{ fontSize: isMobile ? 9 : undefined }}>
            {displayName && (
              <span style={{ fontSize: isMobile ? 9 : 10,
                color: isOwner ? '#00ff88' : '#c084fc',
                fontFamily:'monospace', marginRight: isMobile ? 6 : 12, letterSpacing:1 }}>
                {isOwner ? '👑' : '👤'} {displayName}
                {!isOwner && !isMobile && <span style={{ color:'#4a6a8a', fontSize:9 }}> · VIEWER</span>}
              </span>
            )}
            <AmaStatus compact={isMobile} />
            <span className="status-dot" style={{ background: backendReady ? '#00ff88' : '#fbbf24' }}></span>
            {!isMobile && (backendReady ? 'SYSTEM ONLINE' : 'WAKING UP…')}
          </div>
        </header>

        {/* Tab bar */}
        <div style={{ display:'flex', gap:0,
          padding: isMobile ? '0 8px' : '0 16px',
          background:'#080b0f', borderBottom:'1px solid #1a2535',
          overflowX:'auto', WebkitOverflowScrolling:'touch',
          scrollbarWidth:'none' }}>
          <button onClick={() => setViewMode('dashboard')}
            style={{ background: viewMode==='dashboard' ? '#0d1a2a' : 'transparent',
              color: viewMode==='dashboard' ? '#00ff88' : '#8899aa', border:'none',
              borderBottom: viewMode==='dashboard' ? '2px solid #00ff88' : '2px solid transparent',
              padding: isMobile ? '8px 10px' : '10px 18px',
              fontSize: isMobile ? 9 : 11, fontWeight:'bold', fontFamily:'sans-serif',
              cursor:'pointer', display:'flex', alignItems:'center', gap: isMobile ? 4 : 6,
              letterSpacing:1, whiteSpace:'nowrap', flexShrink:0 }}>
            <LayoutGrid size={isMobile ? 11 : 14}/> {isMobile ? 'HOME' : 'DASHBOARD'}
          </button>
          {TAB_ITEMS.map(({ id, label, color }) => (
            <button key={id}
              onClick={() => { setViewMode('tab'); setActiveTab(id); }}
              style={{ background: viewMode==='tab' && activeTab===id ? '#0d1a2a' : 'transparent',
                color: viewMode==='tab' && activeTab===id ? color : '#8899aa', border:'none',
                borderBottom: viewMode==='tab' && activeTab===id ? `2px solid ${color}` : '2px solid transparent',
                padding: isMobile ? '8px 10px' : '10px 18px',
                fontSize: isMobile ? 9 : 11, fontWeight:'bold', fontFamily:'sans-serif',
                cursor:'pointer', letterSpacing:1, whiteSpace:'nowrap', flexShrink:0 }}>
              {isMobile ? label.split(' ')[0] : label}
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
