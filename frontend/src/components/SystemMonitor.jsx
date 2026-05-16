import { useState, useEffect, useRef } from "react";

const API = "https://alpha-omega-system.onrender.com";
const REFRESH = 30000;

const STATUS_COLOR = { GREEN: "#1D9E75", YELLOW: "#BA7517", RED: "#E24B4A", running: "#1D9E75", stopped: "#E24B4A", unknown: "#888780" };
const STATUS_BG    = { GREEN: "#EAF3DE", YELLOW: "#FAEEDA", RED: "#FCEBEB" };
const STATUS_TEXT  = { GREEN: "#27500A", YELLOW: "#633806", RED: "#791F1F" };

function Dot({ status }) {
  const c = STATUS_COLOR[status] || "#888780";
  return <span style={{ width: 9, height: 9, borderRadius: "50%", background: c, display: "inline-block", marginRight: 7, flexShrink: 0 }} />;
}

function Badge({ status, label }) {
  const s = status || "unknown";
  return (
    <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, fontWeight: 500, background: STATUS_BG[s] || "#F1EFE8", color: STATUS_TEXT[s] || "#5F5E5A" }}>
      {label || s}
    </span>
  );
}

function Card({ title, children }) {
  return (
    <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-tertiary)", borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12 }}>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10, color: "var(--color-text-primary)" }}>{title}</div>
      {children}
    </div>
  );
}

function Row({ status, label, detail }) {
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "7px 0", borderBottom: "0.5px solid var(--color-border-tertiary)", fontSize: 13 }}>
      <Dot status={status} />
      <span style={{ flex: 1, color: "var(--color-text-primary)" }}>{label}</span>
      {detail != null && (
        <span style={{ fontSize: 12, color: status === "RED" ? "#E24B4A" : status === "YELLOW" ? "#BA7517" : "var(--color-text-secondary)", textAlign: "right", maxWidth: 260 }}>
          {String(detail)}
        </span>
      )}
    </div>
  );
}

function safeNum(val, decimals = 0) {
  const n = Number(val);
  if (isNaN(n) || val == null) return null;
  return decimals > 0 ? n.toFixed(decimals) : Math.round(n);
}

export default function SystemMonitor() {
  const [health, setHealth]         = useState(null);
  const [agentStatus, setAgentStatus] = useState(null);
  const [aiHealth, setAiHealth]     = useState(null);
  const [perf, setPerf]             = useState(null);
  const [memData, setMemData]       = useState(null);
  const [log, setLog]               = useState([]);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [loading, setLoading]       = useState(true);
  const [countdown, setCountdown]   = useState(30);
  const timerRef = useRef(null);
  const countRef = useRef(null);

  function addLog(msg, level = "info") {
    const ts = new Date().toLocaleTimeString();
    setLog(prev => [{ ts, msg, level }, ...prev].slice(0, 50));
  }

  async function fetchAll() {
    setLoading(true);
    setCountdown(30);
    try {
      const [h, a, ai, p, m] = await Promise.allSettled([
        fetch(`${API}/api/health/full`).then(r => r.json()),
        fetch(`${API}/api/agent/status`).then(r => r.json()),
        fetch(`${API}/api/health/agent`).then(r => r.json()),
        fetch(`${API}/api/analytics/performance`).then(r => r.json()),
        fetch(`${API}/api/memory`).then(r => r.json()),
      ]);
      if (h.status === "fulfilled") {
        setHealth(h.value);
        if (h.value.reds?.length) addLog(`${h.value.reds.length} RED: ${h.value.reds.map(r => r.name).join(", ")}`, "error");
      }
      if (a.status === "fulfilled") setAgentStatus(a.value);
      if (ai.status === "fulfilled") {
        setAiHealth(ai.value);
        if (ai.value.applied_fixes?.length) addLog(`AI fixed: ${ai.value.applied_fixes.map(f => f.action).join(", ")}`, "warn");
      }
      if (p.status === "fulfilled") setPerf(p.value);
      if (m.status === "fulfilled") {
        const md = m.value || {};
        const rss      = md.rss_mb      ?? md.memory?.rss_mb      ?? null;
        const headroom = md.headroom_mb ?? md.memory?.headroom_mb ?? null;
        setMemData({ rss_mb: rss, headroom_mb: headroom, ok: md.ok ?? md.memory?.ok ?? true });
        if (rss != null && rss > 1600) addLog(`Memory WARNING: ${rss}MB used`, "warn");
      }
      setLastRefresh(new Date().toLocaleTimeString());
      addLog("Health check complete", "info");
    } catch (e) {
      addLog(`Fetch error: ${e.message}`, "error");
    }
    setLoading(false);
  }

  async function runAgentNow() {
    addLog("Forcing AI health agent run...", "info");
    try {
      const r = await fetch(`${API}/api/health/agent/run`, { method: "POST" });
      const d = await r.json();
      setAiHealth(d);
      addLog(`Agent: ${d.severity} - ${d.headline}`, d.severity === "RED" ? "error" : "info");
    } catch (e) { addLog(`Agent run failed: ${e.message}`, "error"); }
  }

  async function runLearning() {
    addLog("Triggering learning loop...", "info");
    try {
      await fetch(`${API}/api/learning/run-fast`, { method: "POST" });
      addLog("Learning loop triggered", "info");
    } catch (e) { addLog(`Learning failed: ${e.message}`, "error"); }
  }

  useEffect(() => {
    fetchAll();
    timerRef.current = setInterval(fetchAll, REFRESH);
    countRef.current = setInterval(() => setCountdown(c => c > 0 ? c - 1 : 30), 1000);
    return () => { clearInterval(timerRef.current); clearInterval(countRef.current); };
  }, []);

  const overall  = health?.overall || "unknown";
  const checks   = health?.checks  || [];
  const rssNum   = safeNum(memData?.rss_mb);
  const memLabel = rssNum != null ? `${rssNum} MB` : "…";
  const memWarn  = rssNum != null && rssNum > 1600;
  const wrLabel  = perf?.win_rate      != null ? `${perf.win_rate}%`      : "…";
  const pfLabel  = perf?.profit_factor != null ? `${perf.profit_factor}`  : "…";

  const stats = [
    { label: "overall",       value: overall,  color: STATUS_COLOR[overall] || "#888780" },
    { label: "memory",        value: memLabel, color: memWarn ? "#BA7517" : "#1D9E75"   },
    { label: "win rate",      value: wrLabel,  color: "#1D9E75"                          },
    { label: "profit factor", value: pfLabel,  color: "#1D9E75"                          },
  ];

  return (
    <div style={{ padding: "1rem", fontFamily: "var(--font-sans)", maxWidth: 900 }}>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Dot status={overall} />
          <span style={{ fontSize: 18, fontWeight: 500, color: "var(--color-text-primary)" }}>System Monitor</span>
          <span style={{ fontSize: 12, color: "var(--color-text-secondary)", background: "var(--color-background-secondary)", padding: "2px 8px", borderRadius: 4 }}>
            {loading ? "refreshing..." : `updated ${lastRefresh}`}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={fetchAll} style={{ fontSize: 12, padding: "4px 12px", cursor: "pointer" }}>Refresh</button>
          <button onClick={runAgentNow} style={{ fontSize: 12, padding: "4px 12px", cursor: "pointer" }}>Run AI check</button>
          <span style={{ fontSize: 12, color: "var(--color-text-tertiary)", display: "flex", alignItems: "center" }}>next in {countdown}s</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 10, marginBottom: 16 }}>
        {stats.map(s => (
          <div key={s.label} style={{ background: "var(--color-background-secondary)", borderRadius: 8, padding: "0.9rem", textAlign: "center" }}>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 22, fontWeight: 500, color: s.color, marginTop: 4 }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>

        <Card title="background agents (render)">
          {agentStatus ? (
            <>
              <Row status={agentStatus.keepalive_running ? "GREEN" : "RED"} label="Keepalive" detail={agentStatus.keepalive_running ? "running" : "stopped"} />
              <Row status={agentStatus.agent_running ? "GREEN" : "RED"} label="Telegram AI Agent" detail={agentStatus.agent_running ? "polling" : "stopped"} />
              <Row status={agentStatus.active_threads?.includes("ai_health_agent") ? "GREEN" : "RED"} label="AI Health Monitor" detail="every 30 min" />
              <Row status={agentStatus.active_threads?.includes("learn_fast") ? "GREEN" : "YELLOW"} label="Learning Loop" detail="fast + deep" />
              <Row status={agentStatus.active_threads?.includes("dreaming_agent") ? "GREEN" : "YELLOW"} label="Dreaming Agent" detail="every 4h" />
            </>
          ) : <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>loading...</div>}
        </Card>

        <Card title="integrations">
          {checks.map(c => (
            <Row key={c.name} status={c.status} label={c.name} detail={c.detail?.slice(0, 45)} />
          ))}
        </Card>

        <Card title="AI health agent - last check">
          {aiHealth ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <Badge status={aiHealth.severity} label={aiHealth.severity} />
                <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>{aiHealth.headline}</span>
              </div>
              {(aiHealth.issues || []).map((i, idx) => (
                <Row key={idx} status={i.severity === "HIGH" ? "RED" : "YELLOW"} label={i.issue} detail={i.data} />
              ))}
              {aiHealth.applied_fixes?.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 12, color: "#27500A", background: "#EAF3DE", padding: "6px 10px", borderRadius: 6 }}>
                  Auto-fixed: {aiHealth.applied_fixes.map(f => f.action).join(", ")}
                </div>
              )}
              <button onClick={runAgentNow} style={{ marginTop: 10, fontSize: 12, padding: "4px 12px", cursor: "pointer", width: "100%" }}>Force run now</button>
            </>
          ) : <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>loading...</div>}
        </Card>

        <Card title="performance">
          {perf && (perf.total_trades > 0 || perf.total > 0) ? (
            <>
              <Row status="GREEN" label="Total trades" detail={perf.total_trades ?? perf.total} />
              <Row status="GREEN" label="Avg win"      detail={perf.avg_win_pct  != null ? `+${perf.avg_win_pct}%`  : "-"} />
              <Row status="GREEN" label="Avg loss"     detail={perf.avg_loss_pct != null ? `${perf.avg_loss_pct}%`  : "-"} />
              <Row status="GREEN" label="TP1 hit rate" detail={perf.tp1_hit_rate != null ? `${perf.tp1_hit_rate}%`  : "-"} />
              <Row status={(perf.stopped_out_rate ?? 0) > 60 ? "YELLOW" : "GREEN"} label="Stopped out" detail={perf.stopped_out_rate != null ? `${perf.stopped_out_rate}%` : "-"} />
              <button onClick={runLearning} style={{ marginTop: 10, fontSize: 12, padding: "4px 12px", cursor: "pointer", width: "100%" }}>Run learning loop</button>
            </>
          ) : <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>loading performance...</div>}
        </Card>

      </div>

      <Card title="live activity log">
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, maxHeight: 200, overflowY: "auto" }}>
          {log.length === 0 && <div style={{ color: "var(--color-text-tertiary)" }}>waiting for events...</div>}
          {log.map((e, i) => (
            <div key={i} style={{ padding: "3px 0", borderBottom: "0.5px solid var(--color-border-tertiary)", color: e.level === "error" ? "#E24B4A" : e.level === "warn" ? "#BA7517" : "var(--color-text-secondary)" }}>
              <span style={{ color: "var(--color-text-tertiary)", marginRight: 8 }}>{e.ts}</span>{e.msg}
            </div>
          ))}
        </div>
      </Card>

    </div>
  );
}
