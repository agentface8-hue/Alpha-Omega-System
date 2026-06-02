import { useState, useEffect, useRef } from "react";
import AuditTrail from "./AuditTrail";
import SafetyControls from "./SafetyControls";
import AiRadar from "./AiRadar";

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

function safeNum(val) {
  const n = Number(val);
  return (isNaN(n) || val == null) ? null : Math.round(n);
}

function formatLogDate(date) {
  const now   = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const d     = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diff  = Math.round((today - d) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "long" });
}

function formatLogTime(date) {
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: true });
}

export default function SystemMonitor() {
  const [health, setHealth]           = useState(null);
  const [agentStatus, setAgentStatus] = useState(null);
  const [aiHealth, setAiHealth]       = useState(null);
  const [perf, setPerf]               = useState(null);
  const [memData, setMemData]         = useState(null);
  const [log, setLog]                 = useState([]);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [loading, setLoading]         = useState(true);
  const [countdown, setCountdown]     = useState(30);
  const timerRef = useRef(null);
  const countRef = useRef(null);
  const logRef   = useRef(null);
  const tickRef  = useRef(0);
  const [learningSummary, setLearningSummary] = useState(null);
  const [deepRunning, setDeepRunning] = useState(false);
  const [amaStatus, setAmaStatus] = useState(null);

  function addLog(msg, level = "info") {
    const now = new Date();
    setLog(prev => [{ date: now, msg, level }, ...prev].slice(0, 200));
  }

  async function fetchJson(path, ms = 20000) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), ms);
    try {
      const r = await fetch(`${API}${path}`, { signal: ctrl.signal });
      if (!r.ok) throw new Error(`${path} ${r.status}`);
      return await r.json();
    } finally {
      clearTimeout(t);
    }
  }

  async function fetchAll(forceFull = false) {
    setLoading(true);
    setCountdown(30);
    tickRef.current += 1;
    const runFull = forceFull || tickRef.current % 5 === 1;
    try {
      const healthPath = runFull ? "/api/health/full" : "/api/health/quick";
      const [h, a, ai, p, m, mon, learn, ama] = await Promise.allSettled([
        fetchJson(healthPath, runFull ? 22000 : 12000),
        fetchJson("/api/agent/status", 10000),
        fetchJson("/api/health/agent", 10000),
        fetchJson("/api/analytics/performance", 15000),
        fetchJson("/api/memory", 10000),
        fetchJson("/api/monitor/status", 10000),
        fetchJson("/api/learning/summary", 12000),
        fetchJson("/api/ama/status", 8000),
      ]);

      if (h.status === "fulfilled") {
        setHealth(h.value);
        const reds = h.value.checks?.filter(c => c.status === "RED") || h.value.reds || [];
        if (reds.length) addLog(`${reds.length} RED: ${reds.map(r => r.name).join(", ")}`, "error");
      } else {
        addLog(`Health ${runFull ? "full" : "quick"} failed`, "warn");
      }
      if (a.status === "fulfilled") setAgentStatus(a.value);
      if (ai.status === "fulfilled") {
        setAiHealth(ai.value);
        if (ai.value.applied_fixes?.length) addLog(`AI fixed: ${ai.value.applied_fixes.map(f => f.action).join(", ")}`, "warn");
      }
      if (p.status === "fulfilled") setPerf(p.value);
      if (m.status === "fulfilled") {
        const md  = m.value || {};
        const rss = md.process_rss_mb ?? md.rss_mb ?? md.memory?.rss_mb ?? null;
        const ok  = md.status === "OK" || md.ok || (rss != null && rss < 1600);
        setMemData({ rss_mb: rss, headroom_mb: md.headroom_mb ?? null, ok });
        if (rss != null && rss > 1600) addLog(`Memory WARNING: ${rss}MB used`, "warn");
      }
      if (mon.status === "fulfilled" && mon.value?.status === "RED") {
        addLog(`Monitor: ${mon.value.active_failures} active failures`, "error");
      }
      if (learn.status === "fulfilled") setLearningSummary(learn.value);
      if (ama.status === "fulfilled") setAmaStatus(ama.value);

      setLastRefresh(new Date());
      addLog(`Refresh OK (${runFull ? "full" : "quick"} health)`, "info");
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
      addLog(`Agent: ${d.severity} — ${d.headline}`, d.severity === "RED" ? "error" : "info");
    } catch (e) { addLog(`Agent run failed: ${e.message}`, "error"); }
  }

  async function runLearning() {
    addLog("Triggering fast learning...", "info");
    try {
      const r = await fetch(`${API}/api/learning/run-fast`, { method: "POST" });
      const d = await r.json();
      addLog(`Fast learning: ${d.status || "done"}`, "info");
      fetchAll(false);
    } catch (e) { addLog(`Learning failed: ${e.message}`, "error"); }
  }

  async function runAmaNow() {
    addLog("Running AMA cycle...", "info");
    try {
      const r = await fetch(`${API}/api/ama/run-now`, { method: "POST" });
      const d = await r.json();
      addLog(`AMA cycle ${d.cycle}: ${d.actions} actions`, "info");
      fetchAll(false);
    } catch (e) { addLog(`AMA failed: ${e.message}`, "error"); }
  }

  async function runDeepLearning() {
    setDeepRunning(true);
    addLog("Deep learning + Opus research (up to 2 min)...", "info");
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 125000);
      const r = await fetch(`${API}/api/learning/run-deep`, { method: "POST", signal: ctrl.signal });
      clearTimeout(t);
      const d = await r.json();
      const dr = d.deep_research || {};
      if (dr.status === "ok") {
        addLog(`Meta-Judge: ${dr.headline || "complete"}`, "info");
      } else {
        addLog(`Deep run done (${dr.status || d.status})`, "warn");
      }
      fetchAll(true);
    } catch (e) { addLog(`Deep learning failed: ${e.message}`, "error"); }
    setDeepRunning(false);
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

  const lastRefreshLabel = lastRefresh
    ? `${formatLogDate(lastRefresh)} ${formatLogTime(lastRefresh)}`
    : null;

  const stats = [
    { label: "overall",       value: overall,                                              color: STATUS_COLOR[overall] || "#888780" },
    { label: "memory",        value: memLabel,                                             color: memWarn ? "#BA7517" : "#1D9E75"   },
    { label: "win rate",      value: perf?.win_rate      != null ? `${perf.win_rate}%`     : "…", color: "#1D9E75" },
    { label: "profit factor", value: perf?.profit_factor != null ? `${perf.profit_factor}` : "…", color: "#1D9E75" },
  ];

  // Telegram-style log: date pill centered, timestamp right-aligned
  function renderLog() {
    if (log.length === 0) {
      return (
        <div style={{ textAlign: "center", color: "var(--color-text-tertiary)", padding: "16px 0", fontSize: 12 }}>
          waiting for events...
        </div>
      );
    }

    const items = [];
    let lastDateLabel = null;

    // log is newest-first; reverse to render oldest-first (like a chat)
    const ordered = [...log].reverse();

    for (let i = 0; i < ordered.length; i++) {
      const e = log[ordered.length - 1 - i]; // get from original array
      const entry = ordered[i];
      const dateLabel = formatLogDate(entry.date);

      // Date separator pill — Telegram style
      if (dateLabel !== lastDateLabel) {
        lastDateLabel = dateLabel;
        items.push(
          <div key={`sep-${i}`} style={{ display: "flex", justifyContent: "center", margin: "10px 0 6px" }}>
            <span style={{
              fontSize: 11, fontWeight: 600, padding: "3px 14px", borderRadius: 20,
              background: "var(--color-background-tertiary, rgba(0,0,0,0.25))",
              color: "var(--color-text-secondary)",
              letterSpacing: "0.01em",
            }}>
              {dateLabel}
            </span>
          </div>
        );
      }

      // Message row — text left, time right (like Telegram)
      const msgColor =
        entry.level === "error" ? "#E24B4A" :
        entry.level === "warn"  ? "#BA7517" :
        "var(--color-text-secondary)";

      items.push(
        <div key={i} style={{
          display: "flex", alignItems: "flex-end", justifyContent: "space-between",
          gap: 12, padding: "4px 2px",
          borderBottom: "0.5px solid var(--color-border-tertiary)",
        }}>
          <span style={{ fontSize: 12, color: msgColor, flex: 1, lineHeight: 1.4 }}>
            {entry.msg}
          </span>
          <span style={{ fontSize: 10, color: "var(--color-text-tertiary)", flexShrink: 0, whiteSpace: "nowrap" }}>
            {formatLogTime(entry.date)}
          </span>
        </div>
      );
    }

    return items;
  }

  return (
    <div style={{ padding: "1rem", fontFamily: "var(--font-sans)", maxWidth: 900 }}>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Dot status={overall} />
          <span style={{ fontSize: 18, fontWeight: 500, color: "var(--color-text-primary)" }}>System Monitor</span>
          {lastRefreshLabel && (
            <span style={{ fontSize: 12, color: "var(--color-text-secondary)", background: "var(--color-background-secondary)", padding: "2px 8px", borderRadius: 4 }}>
              {loading ? "refreshing..." : `updated ${lastRefreshLabel}`}
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => fetchAll(true)} style={{ fontSize: 12, padding: "4px 12px", cursor: "pointer" }}>Refresh</button>
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

        <div style={{ gridColumn: "1 / -1" }}>
          <SafetyControls />
          <AiRadar />
        </div>

        <Card title="background agents (render)">
          {agentStatus ? (
            <>
              <Row status={agentStatus.keepalive_running ? "GREEN" : "RED"} label="Keepalive" detail={agentStatus.keepalive_running ? "running" : "stopped"} />
              <Row status={agentStatus.agent_running ? "GREEN" : "RED"} label="Telegram AI Agent" detail={agentStatus.agent_running ? "polling" : "stopped"} />
              <Row status={agentStatus.active_threads?.includes("ai_health_agent") ? "GREEN" : "RED"} label="AI Health Monitor" detail="every 30 min" />
              <Row status={agentStatus.learning_running || agentStatus.active_threads?.includes("learn_fast") ? "GREEN" : "YELLOW"} label="Learning Loop" detail="fast + deep" />
              <Row status={agentStatus.monitor_running ? "GREEN" : "YELLOW"} label="Live Monitor" detail={agentStatus.monitor_running ? "L1/L2/L3" : "threads missing"} />
              <Row status={agentStatus.active_threads?.includes("dreaming_agent") ? "GREEN" : "YELLOW"} label="Dreaming Agent" detail="every 4h" />
            </>
          ) : <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>loading...</div>}
        </Card>

        <Card title="Autonomous Agent (AMA)">
          {amaStatus ? (
            <>
              <Row status={amaStatus.running && !amaStatus.paused ? "GREEN" : "YELLOW"} label="AMA" detail={amaStatus.paused ? "paused" : amaStatus.running ? "active" : "off"} />
              <Row status="GREEN" label="Cycle" detail={`#${amaStatus.cycle_number || 0}`} />
              <Row status="GREEN" label="Actions today" detail={amaStatus.actions_today ?? 0} />
              <button onClick={runAmaNow} style={{ marginTop: 10, fontSize: 12, padding: "4px 12px", cursor: "pointer", width: "100%" }}>Run AMA cycle now</button>
            </>
          ) : <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>loading...</div>}
        </Card>

        <Card title="integrations">
          {checks.map(c => (
            <Row key={c.name} status={c.status} label={c.name} detail={c.detail?.slice(0, 45)} />
          ))}
        </Card>

        <Card title="AI health agent — last check">
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
              <button onClick={runLearning} style={{ marginTop: 10, fontSize: 12, padding: "4px 12px", cursor: "pointer", width: "100%" }}>Run fast learning</button>
              <button onClick={runDeepLearning} disabled={deepRunning} style={{ marginTop: 6, fontSize: 12, padding: "4px 12px", cursor: deepRunning ? "wait" : "pointer", width: "100%" }}>
                {deepRunning ? "Deep research running…" : "Run deep research (Opus)"}
              </button>
              {learningSummary?.deep_research_latest?.headline && (
                <div style={{ marginTop: 8, fontSize: 11, color: "var(--color-text-secondary)", lineHeight: 1.4 }}>
                  Last research: {learningSummary.deep_research_latest.headline}
                </div>
              )}
            </>
          ) : <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>loading performance...</div>}
        </Card>

      </div>

      <Card title="live activity log">
        <div ref={logRef} style={{ fontSize: 12, maxHeight: 280, overflowY: "auto", paddingRight: 2 }}>
          {renderLog()}
        </div>
      </Card>

      <AuditTrail limit={15} />

    </div>
  );
}
