import React, { useState } from 'react';
import { Activity, Lock, User, Eye, EyeOff, UserPlus } from 'lucide-react';
import { API_BASE } from '../utils/api';

const API = API_BASE;

function getVisitorId() {
  let id = localStorage.getItem('ao_visitor_id');
  if (!id) {
    id = 'v_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    localStorage.setItem('ao_visitor_id', id);
  }
  return id;
}

function getVisitCount() {
  const count = parseInt(localStorage.getItem('ao_visit_count') || '0') + 1;
  localStorage.setItem('ao_visit_count', String(count));
  return count;
}

const INPUT = {
  display:'flex', alignItems:'center', background:'#050810',
  border:'1px solid #1a2535', borderRadius:6, padding:'10px 12px', gap:8,
};
const BTN_PRIMARY = {
  background:'linear-gradient(135deg,#0d2040,#0a1628)',
  border:'1px solid #1e3a5a', borderRadius:8, padding:'12px',
  color:'#00d4ff', fontSize:12, fontWeight:'bold', letterSpacing:2,
  cursor:'pointer', fontFamily:'sans-serif', marginTop:4,
};

const LoginScreen = ({ onLogin }) => {
  const [tab,      setTab]      = useState('signin');  // 'signin' | 'register'
  const [username, setUsername] = useState('');
  const [name,     setName]     = useState('');
  const [pass,     setPass]     = useState('');
  const [pass2,    setPass2]    = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  const reset = (newTab) => {
    setTab(newTab); setError('');
    setUsername(''); setPass(''); setPass2(''); setName('');
  };

  const handleSignIn = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res  = await fetch(`${API}/api/auth/login`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ username: username.trim().toLowerCase(), password: pass }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');

      // Store session
      localStorage.setItem('ao_auth', '1');
      localStorage.setItem('ao_username', data.username);
      localStorage.setItem('ao_display_name', data.display_name || data.username);
      localStorage.setItem('ao_role', data.role);

      // Fire browser fingerprint in background
      fetch(`${API}/api/login-event`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          username:    data.username,
          user_agent:  navigator.userAgent,
          screen:      `${screen.width}×${screen.height}`,
          timezone:    Intl.DateTimeFormat().resolvedOptions().timeZone,
          language:    navigator.language,
          visitor_id:  getVisitorId(),
          visit_count: getVisitCount(),
        }),
      }).catch(() => {});

      onLogin({ username: data.username, role: data.role, display_name: data.display_name });
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    if (pass !== pass2) { setError("Passwords don't match"); return; }
    if (pass.length < 6) { setError("Password must be at least 6 characters"); return; }
    setLoading(true);
    try {
      const res  = await fetch(`${API}/api/auth/register`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          username: username.trim().toLowerCase(),
          password: pass,
          display_name: name.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');
      // Auto-login after register
      setTab('signin');
      setError('');
      setPass(''); setPass2('');
      setError('✅ Account created! Sign in now.');
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const isSuccess = error.startsWith('✅');

  return (
    <div style={{ minHeight:'100vh', background:'#050810', display:'flex', flexDirection:'column',
      alignItems:'center', justifyContent:'center', fontFamily:"'Courier New',monospace" }}>

      {/* Logo */}
      <div style={{ display:'flex', alignItems:'center', gap:14, marginBottom:40 }}>
        <div style={{ background:'linear-gradient(135deg,#00d4ff22,#7c3aed22)', border:'1px solid #1a2535',
          borderRadius:12, padding:14, display:'flex' }}>
          <Activity size={32} color="#00d4ff" />
        </div>
        <div>
          <div style={{ fontSize:28, fontWeight:800, letterSpacing:4, color:'#c9d8e8' }}>
            ALPHA <span style={{ color:'#00d4ff' }}>—</span> OMEGA
          </div>
          <div style={{ fontSize:11, color:'#2a4a5a', letterSpacing:2, fontFamily:'sans-serif' }}>
            COUNCIL OF EXPERTS TRADING SYSTEM
          </div>
        </div>
      </div>

      {/* Card */}
      <div style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:12,
        padding:'28px 36px', width:360, display:'flex', flexDirection:'column', gap:0 }}>

        {/* Tabs */}
        <div style={{ display:'flex', marginBottom:24, borderBottom:'1px solid #1a2535' }}>
          {[['signin','SIGN IN',<Lock size={11}/>], ['register','REGISTER',<UserPlus size={11}/>]].map(([id,label,icon]) => (
            <button key={id} onClick={() => reset(id)}
              style={{ flex:1, background:'transparent', border:'none',
                borderBottom: tab===id ? '2px solid #00d4ff' : '2px solid transparent',
                color: tab===id ? '#00d4ff' : '#4a6a8a',
                padding:'8px 0', fontSize:10, fontWeight:'bold', letterSpacing:2,
                fontFamily:'sans-serif', cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center', gap:5 }}>
              {icon} {label}
            </button>
          ))}
        </div>

        {/* Sign In Form */}
        {tab === 'signin' && (
          <form onSubmit={handleSignIn} style={{ display:'flex', flexDirection:'column', gap:16 }}>
            <div>
              <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>USERNAME</div>
              <div style={INPUT}>
                <User size={14} color="#8899aa" />
                <input value={username} onChange={e => setUsername(e.target.value)}
                  placeholder="Enter username" autoComplete="username"
                  style={{ background:'transparent', border:'none', outline:'none', color:'#c9d8e8',
                    fontFamily:"'Courier New',monospace", fontSize:13, flex:1 }} />
              </div>
            </div>
            <div>
              <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>PASSWORD</div>
              <div style={INPUT}>
                <Lock size={14} color="#8899aa" />
                <input value={pass} onChange={e => setPass(e.target.value)}
                  type={showPass ? 'text' : 'password'} placeholder="Enter password" autoComplete="current-password"
                  style={{ background:'transparent', border:'none', outline:'none', color:'#c9d8e8',
                    fontFamily:"'Courier New',monospace", fontSize:13, flex:1 }} />
                <button type="button" onClick={() => setShowPass(p => !p)}
                  style={{ background:'transparent', border:'none', cursor:'pointer', padding:0, display:'flex' }}>
                  {showPass ? <EyeOff size={14} color="#8899aa" /> : <Eye size={14} color="#8899aa" />}
                </button>
              </div>
            </div>
            {error && (
              <div style={{ background: isSuccess ? 'rgba(0,255,136,0.08)' : 'rgba(255,68,102,0.08)',
                border: `1px solid ${isSuccess ? 'rgba(0,255,136,0.3)' : 'rgba(255,68,102,0.3)'}`,
                borderRadius:6, padding:'8px 12px',
                color: isSuccess ? '#00ff88' : '#ff4466',
                fontSize:11, fontFamily:'sans-serif' }}>
                {error}
              </div>
            )}
            <button type="submit" disabled={loading || !username || !pass}
              style={{ ...BTN_PRIMARY, opacity: !username || !pass ? 0.5 : 1 }}>
              {loading ? 'SIGNING IN...' : 'ACCESS SYSTEM'}
            </button>
          </form>
        )}

        {/* Register Form */}
        {tab === 'register' && (
          <form onSubmit={handleRegister} style={{ display:'flex', flexDirection:'column', gap:14 }}>
            <div>
              <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>DISPLAY NAME</div>
              <div style={INPUT}>
                <User size={14} color="#8899aa" />
                <input value={name} onChange={e => setName(e.target.value)}
                  placeholder="Your name (e.g. John)"
                  style={{ background:'transparent', border:'none', outline:'none', color:'#c9d8e8',
                    fontFamily:"'Courier New',monospace", fontSize:13, flex:1 }} />
              </div>
            </div>
            <div>
              <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>USERNAME</div>
              <div style={INPUT}>
                <User size={14} color="#8899aa" />
                <input value={username} onChange={e => setUsername(e.target.value)}
                  placeholder="Choose a username"
                  style={{ background:'transparent', border:'none', outline:'none', color:'#c9d8e8',
                    fontFamily:"'Courier New',monospace", fontSize:13, flex:1 }} />
              </div>
            </div>
            <div>
              <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>PASSWORD</div>
              <div style={INPUT}>
                <Lock size={14} color="#8899aa" />
                <input value={pass} onChange={e => setPass(e.target.value)}
                  type={showPass ? 'text' : 'password'} placeholder="Min 6 characters"
                  style={{ background:'transparent', border:'none', outline:'none', color:'#c9d8e8',
                    fontFamily:"'Courier New',monospace", fontSize:13, flex:1 }} />
                <button type="button" onClick={() => setShowPass(p => !p)}
                  style={{ background:'transparent', border:'none', cursor:'pointer', padding:0, display:'flex' }}>
                  {showPass ? <EyeOff size={14} color="#8899aa" /> : <Eye size={14} color="#8899aa" />}
                </button>
              </div>
            </div>
            <div>
              <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>CONFIRM PASSWORD</div>
              <div style={INPUT}>
                <Lock size={14} color="#8899aa" />
                <input value={pass2} onChange={e => setPass2(e.target.value)}
                  type="password" placeholder="Repeat password"
                  style={{ background:'transparent', border:'none', outline:'none', color:'#c9d8e8',
                    fontFamily:"'Courier New',monospace", fontSize:13, flex:1 }} />
              </div>
            </div>
            {error && (
              <div style={{ background:'rgba(255,68,102,0.08)', border:'1px solid rgba(255,68,102,0.3)',
                borderRadius:6, padding:'8px 12px', color:'#ff4466', fontSize:11, fontFamily:'sans-serif' }}>
                {error}
              </div>
            )}
            <div style={{ color:'#2a4a5a', fontSize:9, fontFamily:'sans-serif', textAlign:'center' }}>
              Visitor accounts have read-only access
            </div>
            <button type="submit" disabled={loading || !username || !pass || !pass2}
              style={{ ...BTN_PRIMARY, color:'#c084fc', borderColor:'#3a1a5a',
                opacity: !username || !pass || !pass2 ? 0.5 : 1 }}>
              {loading ? 'CREATING ACCOUNT...' : 'CREATE ACCOUNT'}
            </button>
          </form>
        )}
      </div>

      <div style={{ color:'#1a2535', fontSize:9, marginTop:24, letterSpacing:1, fontFamily:'sans-serif' }}>
        AUTHORIZED PERSONNEL ONLY
      </div>
    </div>
  );
};

export default LoginScreen;
