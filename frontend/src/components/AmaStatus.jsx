import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "https://289c4c10-4400-4814-b389-cf8b47133fc3.clouding.host";

export default function AmaStatus({ compact = false }) {
  const [st, setSt] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetch(`${API}/api/ama/status`)
        .then(r => r.json())
        .then(d => { if (alive) setSt(d); })
        .catch(() => {});
    };
    load();
    const t = setInterval(load, 60000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!st) return null;
  const color = st.paused ? "#fbbf24" : st.running ? "#00ff88" : "#ff4466";
  const label = st.paused ? "PAUSED" : st.running ? "ACTIVE" : "OFF";

  if (compact) {
    return (
      <span style={{ fontSize: 9, fontFamily: "monospace", color, letterSpacing: 1 }}>
        🤖 AMA {label} #{st.cycle_number || 0}
      </span>
    );
  }

  return (
    <span style={{
      fontSize: 10, fontFamily: "monospace", color, letterSpacing: 1,
      marginRight: 12, padding: "2px 8px", border: `1px solid ${color}44`, borderRadius: 4,
    }}>
      🤖 AMA · {label} · cycle {st.cycle_number || 0} · {st.actions_today || 0} actions today
    </span>
  );
}
