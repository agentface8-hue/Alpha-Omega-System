import React, { useState } from 'react';
import { Search, Activity, BarChart3, Brain, Briefcase, DollarSign } from 'lucide-react';
import Terminal from './components/Terminal';
import ResultCard from './components/ResultCard';
import LiveTicker from './components/LiveTicker';
import TopStocks from './components/TopStocks';
import ScanDashboard from './components/ScanDashboard';
import BacktestDashboard from './components/BacktestDashboard';
import SignalTracker from './components/SignalTracker';
import ChartPanel from './components/ChartPanel';
import AlphaMegaDashboard from './components/AlphaMegaDashboard';
import Analytics from './components/Analytics';
import PortfolioTab from './components/PortfolioTab';
import PrintingProfits from './components/PrintingProfits';
import LoginScreen from './components/LoginScreen';
import { playThinkingSound, playSuccessSound, playErrorSound } from './utils/sounds';

const App = () => {
  const [authed, setAuthed] = useState(() => localStorage.getItem('ao_auth') === '1');
  const [activeTab, setActiveTab] = useState('analyze');
  const [symbol, setSymbol] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const getTimestamp = () => {
    return new Date().toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!symbol || isLoading) return;

    setIsLoading(true);
    setLogs([]);
    setResult(null);
    setError(null);

    const steps = [
      { agent: 'The Historian', action: 'is analyzing...' },
      { agent: 'The Newsroom', action: 'is analyzing...' },
      { agent: 'The Macro-Strategist', action: 'is analyzing...' },
      { agent: 'Synthesis Engine', action: 'is analyzing...' },
      { agent: 'The Contrarian', action: 'is analyzing...' },
      { agent: 'The Executioner', action: 'is analyzing...' },
    ];

    // Stream timestamped logs with sound effects
    let stepIndex = 0;
    const interval = setInterval(() => {
      if (stepIndex < steps.length) {
        const step = steps[stepIndex];
        playThinkingSound(); // Beep on each agent step
        setLogs(prev => [...prev, {
          timestamp: getTimestamp(),
          message: `>> ${step.agent} ${step.action}`,
          type: 'info'
        }]);
        stepIndex++;
      } else {
        clearInterval(interval);
      }
    }, 800);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
      const response = await fetch(`${apiUrl}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'Unknown server error' }));
        throw new Error(`Analysis failed (${response.status})`);
      }

      const data = await response.json();

      setTimeout(() => {
        playSuccessSound(); // Success chime
        setResult(data);
        setLogs(prev => [...prev, {
          timestamp: getTimestamp(),
          message: `✓ Analysis complete. Confidence: ${(data.confidence_score * 100).toFixed(0)}%`,
          type: 'success'
        }]);
        setIsLoading(false);
      }, steps.length * 800 + 500);

    } catch (err) {
      setTimeout(() => {
        playErrorSound(); // Error buzz
        setError(err.message);
        setLogs(prev => [...prev, {
          timestamp: getTimestamp(),
          message: `ERROR: ${err.message}`,
          type: 'error'
        }]);
        setIsLoading(false);
      }, steps.length * 800 + 500);
    }
  };

  const handleTickerSelect = (ticker) => {
    setSymbol(ticker);
  };

  return (
    <div>
      {!authed && <LoginScreen onLogin={() => setAuthed(true)} />}
      {authed && (<>
      {/* Live Ticker Bar */}
      <LiveTicker />

      {/* Header */}
      <header className="header">
        <div className="header-left">
          <div className="header-icon">
            <Activity size={26} />
          </div>
          <div>
            <div className="header-title">ALPHA - OMEGA</div>
            <div className="header-subtitle">Council of Experts Trading System</div>
          </div>
        </div>
        <div className="system-status">
          <span className="status-dot"></span>
          SYSTEM ONLINE
        </div>
      </header>

      {/* Tab Bar */}
      <div style={{ display:"flex", gap:0, padding:"0 20px", background:"#080b0f", borderBottom:"1px solid #1a2535" }}>
        <button onClick={() => setActiveTab('analyze')} style={{ background:activeTab==='analyze'?"#0d1a2a":"transparent", color:activeTab==='analyze'?"#00d4ff":"#8899aa", border:"none", borderBottom:activeTab==='analyze'?"2px solid #00d4ff":"2px solid transparent", padding:"10px 20px", fontSize:12, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:6, letterSpacing:1 }}>
          <Activity size={14} /> COUNCIL ANALYZE
        </button>
        <button onClick={() => setActiveTab('scan')} style={{ background:activeTab==='scan'?"#0d1a2a":"transparent", color:activeTab==='scan'?"#00d4ff":"#8899aa", border:"none", borderBottom:activeTab==='scan'?"2px solid #00d4ff":"2px solid transparent", padding:"10px 20px", fontSize:12, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:6, letterSpacing:1 }}>
          <BarChart3 size={14} /> SWING SCAN v4.4
        </button>
        <button onClick={() => setActiveTab('backtest')} style={{ background:activeTab==='backtest'?"#0d1a2a":"transparent", color:activeTab==='backtest'?"#a855f7":"#8899aa", border:"none", borderBottom:activeTab==='backtest'?"2px solid #a855f7":"2px solid transparent", padding:"10px 20px", fontSize:12, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:6, letterSpacing:1 }}>
          <BarChart3 size={14} /> BACKTESTER
        </button>
        <button onClick={() => setActiveTab('tracker')} style={{ background:activeTab==='tracker'?"#0d1a2a":"transparent", color:activeTab==='tracker'?"#c084fc":"#8899aa", border:"none", borderBottom:activeTab==='tracker'?"2px solid #c084fc":"2px solid transparent", padding:"10px 20px", fontSize:12, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:6, letterSpacing:1 }}>
          <Activity size={14} /> SIGNAL TRACKER
        </button>
        <button onClick={() => setActiveTab('alphamega')} style={{ background:activeTab==='alphamega'?"#0d1a2a":"transparent", color:activeTab==='alphamega'?"#c084fc":"#8899aa", border:"none", borderBottom:activeTab==='alphamega'?"2px solid #c084fc":"2px solid transparent", padding:"10px 20px", fontSize:12, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:6, letterSpacing:1 }}>
          <BarChart3 size={14} /> ALPHA-MEGA
        </button>
        <button onClick={() => setActiveTab('analytics')} style={{ background:activeTab==='analytics'?"#0d1a2a":"transparent", color:activeTab==='analytics'?"#00d4ff":"#8899aa", border:"none", borderBottom:activeTab==='analytics'?"2px solid #00d4ff":"2px solid transparent", padding:"10px 20px", fontSize:12, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:6, letterSpacing:1 }}>
          <Brain size={14} /> ANALYTICS
        </button>
        <button onClick={() => setActiveTab('portfolio')} style={{ background:activeTab==='portfolio'?"#0d1a2a":"transparent", color:activeTab==='portfolio'?"#00ff88":"#8899aa", border:"none", borderBottom:activeTab==='portfolio'?"2px solid #00ff88":"2px solid transparent", padding:"10px 20px", fontSize:12, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:6, letterSpacing:1 }}>
          <Briefcase size={14} /> PORTFOLIO
        </button>
        <button onClick={() => setActiveTab('printing')} style={{ background:activeTab==='printing'?"#0d1a2a":"transparent", color:activeTab==='printing'?"#fbbf24":"#8899aa", border:"none", borderBottom:activeTab==='printing'?"2px solid #fbbf24":"2px solid transparent", padding:"10px 20px", fontSize:12, fontWeight:"bold", fontFamily:"sans-serif", cursor:"pointer", display:"flex", alignItems:"center", gap:6, letterSpacing:1 }}>
          <DollarSign size={14} /> PRINTING PROFITS
        </button>
      </div>

      {/* Content */}
      {activeTab === 'scan' ? (
        <ScanDashboard />
      ) : activeTab === 'backtest' ? (
        <BacktestDashboard />
      ) : activeTab === 'tracker' ? (
        <SignalTracker />
      ) : activeTab === 'alphamega' ? (
        <AlphaMegaDashboard />
      ) : activeTab === 'analytics' ? (
        <Analytics />
      ) : activeTab === 'portfolio' ? (
        <PortfolioTab />
      ) : activeTab === 'printing' ? (
        <PrintingProfits />
      ) : (
      <main className="main-container">
        {/* Search */}
        <form className="search-form" onSubmit={handleAnalyze}>
          <div className="search-input-wrapper">
            <input
              type="text"
              className="search-input"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="ENTER TICKER"
              disabled={isLoading}
            />
            <button
              type="submit"
              className="search-button"
              disabled={isLoading || !symbol}
            >
              <Search size={20} />
            </button>
          </div>
        </form>
        <div className="search-hint">Press Enter to analyze a stock symbol</div>

        {/* Two-column layout */}
        <div className="dashboard-grid">
          {/* Left: Terminal + Results */}
          <div className="dashboard-main">
            <Terminal logs={logs} />

            {error && (
              <div className="error-banner">
                <div className="error-icon">!</div>
                <span>{error}</span>
              </div>
            )}

            <ResultCard result={result} />
            <ChartPanel symbol={result ? result.symbol : symbol} tradeParams={result?.trade_params} />
          </div>

          {/* Right: Top Stocks */}
          <div className="dashboard-sidebar">
            <TopStocks onSelectTicker={handleTickerSelect} />
          </div>
        </div>
      </main>
      )}
    </>)}
  </div>
  );
};

export default App;
