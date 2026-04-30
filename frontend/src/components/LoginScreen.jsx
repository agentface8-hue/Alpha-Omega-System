import React, { useState } from 'react';
import { Activity, Lock, User, Eye, EyeOff } from 'lucide-react';

// SHA-256 of the password — plaintext never stored in code
const VALID_USER = 'aviandjhon';
const VALID_HASH = '3b233de2d3124fbd02ba28cf35824c76725c020258fb347f5a20f9f077ace9db';

async function sha256(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,'0')).join('');
}

const LoginScreen = ({ onLogin }) => {
  const [user, setUser]       = useState('');
  const [pass, setPass]       = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);

  const handle = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    const hash = await sha256(pass);
    if (user === VALID_USER && hash === VALID_HASH) {
      localStorage.setItem('ao_auth', '1');
      onLogin();
    } else {
      setError('Invalid username or password.');
    }
    setLoading(false);
  };

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
      <form onSubmit={handle} style={{ background:'#080c14', border:'1px solid #1a2535', borderRadius:12,
        padding:'32px 36px', width:340, display:'flex', flexDirection:'column', gap:20 }}>

        <div style={{ display:'flex', alignItems:'center', gap:8, color:'#8899aa', fontSize:11,
          letterSpacing:2, fontFamily:'sans-serif', marginBottom:4 }}>
          <Lock size={12} /> SECURE ACCESS
        </div>

        {/* Username */}
        <div>
          <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>USERNAME</div>
          <div style={{ display:'flex', alignItems:'center', background:'#050810', border:'1px solid #1a2535',
            borderRadius:6, padding:'10px 12px', gap:8 }}>
            <User size={14} color="#8899aa" />
            <input value={user} onChange={e => setUser(e.target.value)}
              placeholder="Enter username"
              style={{ background:'transparent', border:'none', outline:'none', color:'#c9d8e8',
                fontFamily:"'Courier New',monospace", fontSize:13, flex:1 }} />
          </div>
        </div>

        {/* Password */}
        <div>
          <div style={{ color:'#2a4a5a', fontSize:9, letterSpacing:1.5, fontFamily:'sans-serif', marginBottom:6 }}>PASSWORD</div>
          <div style={{ display:'flex', alignItems:'center', background:'#050810', border:'1px solid #1a2535',
            borderRadius:6, padding:'10px 12px', gap:8 }}>
            <Lock size={14} color="#8899aa" />
            <input value={pass} onChange={e => setPass(e.target.value)}
              type={showPass ? 'text' : 'password'} placeholder="Enter password"
              style={{ background:'transparent', border:'none', outline:'none', color:'#c9d8e8',
                fontFamily:"'Courier New',monospace", fontSize:13, flex:1 }} />
            <button type="button" onClick={() => setShowPass(p => !p)}
              style={{ background:'transparent', border:'none', cursor:'pointer', padding:0, display:'flex' }}>
              {showPass ? <EyeOff size={14} color="#8899aa" /> : <Eye size={14} color="#8899aa" />}
            </button>
          </div>
        </div>

        {error && (
          <div style={{ background:'rgba(255,68,102,0.08)', border:'1px solid rgba(255,68,102,0.3)',
            borderRadius:6, padding:'8px 12px', color:'#ff4466', fontSize:11, fontFamily:'sans-serif' }}>
            ⚠ {error}
          </div>
        )}

        <button type="submit" disabled={loading || !user || !pass}
          style={{ background:'linear-gradient(135deg,#0d2040,#0a1628)', border:'1px solid #1e3a5a',
            borderRadius:8, padding:'12px', color:'#00d4ff', fontSize:12, fontWeight:'bold',
            letterSpacing:2, cursor: loading || !user || !pass ? 'not-allowed' : 'pointer',
            fontFamily:'sans-serif', opacity: !user || !pass ? 0.5 : 1, marginTop:4 }}>
          {loading ? 'VERIFYING...' : 'ACCESS SYSTEM'}
        </button>
      </form>

      <div style={{ color:'#1a2535', fontSize:9, marginTop:24, letterSpacing:1, fontFamily:'sans-serif' }}>
        AUTHORIZED PERSONNEL ONLY
      </div>
    </div>
  );
};

export default LoginScreen;
