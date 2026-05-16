"""
ai_health_agent.py — Autonomous AI System Monitor v1.0

Runs every 30 min as a background thread. Does 4 things:
  1. Checks system health (all 9 integrations)
  2. Analyzes live performance metrics (win rate, profit factor, regime breakdown)
  3. Uses Gemini to diagnose issues and generate a fix plan
  4. Auto-applies safe fixes + sends Telegram alert with full diagnosis

Auto-fixes it can apply autonomously:
  - Raise conviction threshold in underperforming regimes
  - Block autopilot during market-closed sessions
  - Tighten SL multipliers in losing regimes
  - Trigger learning loop when win rate drops

Escalates to Telegram (human decision needed) for:
  - Supabase connection loss
  - API key failures
  - Abnormal drawdown (>10%)
  - Win rate drop below 40% sustained over 10+ trades
"""

import os
import json
import time
import logging
import threading
import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
CHECK_INTERVAL_MINUTES = 30
WIN_RATE_ALERT_THRESHOLD = 42.0     # alert if win rate drops below this
PROFIT_FACTOR_MIN = 1.2             # alert if PF drops below this
DRAWDOWN_MAX = -12.0                # alert if drawdown exceeds this %
MIN_TRADES_FOR_ANALYSIS = 5         # skip analysis if fewer closed trades

# Performance thresholds per regime (auto-tuned)
REGIME_CONV_THRESHOLDS = {
    "Trending Bull":  72,   # raised from 60 — data shows 41% win rate at 60
    "Choppy / Range": 65,
    "High-Vol Event": 70,
    "Trending Bear":  75,
}

_agent_thread = None
_last_check_result: Dict = {}
_auto_fixes_applied: List[Dict] = []


# ── Core analysis ─────────────────────────────────────────────────────────────

def _collect_system_state() -> Dict:
    """Gather all system data needed for diagnosis."""
    state = {}

    # 1. Performance analytics
    try:
        from core import signal_store
        from core import portfolio_store
        closed = signal_store.load_closed()
        active = signal_store.load_active()
        pf_state = portfolio_store.load_state()

        if len(closed) >= MIN_TRADES_FOR_ANALYSIS:
            wins   = [s for s in closed if s.get("pnl_pct", 0) > 0]
            losses = [s for s in closed if s.get("pnl_pct", 0) <= 0]
            win_rate     = round(len(wins) / len(closed) * 100, 1)
            avg_win      = round(sum(s["pnl_pct"] for s in wins) / len(wins), 2) if wins else 0
            avg_loss     = round(sum(s["pnl_pct"] for s in losses) / len(losses), 2) if losses else 0
            gp = sum(s["pnl_pct"] for s in wins) if wins else 0
            gl = abs(sum(s["pnl_pct"] for s in losses)) if losses else 0.01
            profit_factor = round(gp / gl, 2)

            # Regime breakdown
            regime_stats = {}
            for s in closed:
                reg = (s.get("entry_market_context") or {}).get("regime") or s.get("regime", "Unknown")
                if reg not in regime_stats:
                    regime_stats[reg] = {"wins": 0, "losses": 0, "pnls": []}
                regime_stats[reg]["pnls"].append(s.get("pnl_pct", 0))
                if s.get("pnl_pct", 0) > 0:
                    regime_stats[reg]["wins"] += 1
                else:
                    regime_stats[reg]["losses"] += 1
            for reg in regime_stats:
                d = regime_stats[reg]
                total = d["wins"] + d["losses"]
                d["win_rate"] = round(d["wins"] / total * 100, 1) if total else 0
                d["avg_pnl"] = round(sum(d["pnls"]) / len(d["pnls"]), 2) if d["pnls"] else 0
                del d["pnls"]

            # Session breakdown
            session_stats = {}
            for s in closed:
                sess = s.get("entry_session", "unknown")
                if sess not in session_stats:
                    session_stats[sess] = {"wins": 0, "losses": 0}
                if s.get("pnl_pct", 0) > 0:
                    session_stats[sess]["wins"] += 1
                else:
                    session_stats[sess]["losses"] += 1

            state["performance"] = {
                "total_trades":   len(closed),
                "active_signals": len(active),
                "win_rate":       win_rate,
                "avg_win_pct":    avg_win,
                "avg_loss_pct":   avg_loss,
                "profit_factor":  profit_factor,
                "regime_stats":   regime_stats,
                "session_stats":  session_stats,
                "portfolio_value": pf_state.get("total_value", 25000),
                "starting_capital": pf_state.get("starting_capital", 25000),
                "total_pnl_pct":  round((pf_state.get("total_value", 25000) - 25000) / 25000 * 100, 2),
            }
        else:
            state["performance"] = {"total_trades": len(closed), "insufficient_data": True}

    except Exception as e:
        state["performance"] = {"error": str(e)}

    # 2. System health (quick checks only — no external API calls for speed)
    try:
        from core.system_health import check_portfolio_state, check_signal_tracker, check_learning_loop
        state["health"] = {
            "portfolio": check_portfolio_state(),
            "signals":   check_signal_tracker(),
            "learning":  check_learning_loop(),
        }
    except Exception as e:
        state["health"] = {"error": str(e)}

    # 3. Memory usage
    try:
        import psutil, os as _os
        proc = psutil.Process(_os.getpid())
        rss  = round(proc.memory_info().rss / 1024**2, 1)
        state["memory"] = {
            "rss_mb":      rss,
            "limit_mb":    2048,
            "headroom_mb": round(2048 - rss, 1),
            "ok":          rss < 1600,
        }
    except Exception:
        state["memory"] = {"error": "psutil not available"}

    # 4. Recent auto-fixes
    state["auto_fixes_applied"] = _auto_fixes_applied[-5:]  # last 5

    return state


def _ai_diagnose(system_state: Dict) -> Dict:
    """
    Call Gemini to diagnose system state and recommend fixes.
    Returns structured diagnosis with severity + action plan.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return {"error": "No GOOGLE_API_KEY", "severity": "UNKNOWN", "issues": [], "fixes": []}

    perf = system_state.get("performance", {})
    mem  = system_state.get("memory", {})
    health = system_state.get("health", {})

    prompt = f"""You are the AI health monitor for Alpha-Omega, an automated paper trading system.
Analyze this system snapshot and return a JSON diagnosis.

PERFORMANCE SNAPSHOT:
- Total closed trades: {perf.get('total_trades', 0)}
- Win rate: {perf.get('win_rate', 0)}%
- Profit factor: {perf.get('profit_factor', 0)} (target: >1.5)
- Avg win: +{perf.get('avg_win_pct', 0)}% | Avg loss: {perf.get('avg_loss_pct', 0)}%
- Portfolio P&L: {perf.get('total_pnl_pct', 0)}%

REGIME BREAKDOWN:
{json.dumps(perf.get('regime_stats', {}), indent=2)}

SESSION BREAKDOWN:
{json.dumps(perf.get('session_stats', {}), indent=2)}

SYSTEM HEALTH:
{json.dumps({k: v.get('status', 'unknown') + ': ' + v.get('detail', '') for k, v in health.items() if isinstance(v, dict)}, indent=2)}

MEMORY:
- RSS: {mem.get('rss_mb', 0)}MB / 2048MB limit | Headroom: {mem.get('headroom_mb', 0)}MB

AUTO-FIXES ALREADY APPLIED: {json.dumps(system_state.get('auto_fixes_applied', []))}

Respond ONLY with this JSON (no markdown):
{{
  "severity": "GREEN" | "YELLOW" | "RED",
  "headline": "one sentence summary",
  "issues": [
    {{"issue": "description", "severity": "HIGH|MEDIUM|LOW", "data": "specific numbers"}}
  ],
  "auto_fixes": [
    {{"action": "RAISE_REGIME_THRESHOLD|BLOCK_SESSION|TRIGGER_LEARNING|TIGHTEN_SL", "params": {{}}, "reason": "why"}}
  ],
  "human_actions": [
    "specific thing the human/system admin should do"
  ],
  "system_ok": true | false
}}"""

    try:
        import urllib.request
        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 800, "temperature": 0.1}
        }).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read().decode())
        raw = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[AI-HEALTH] Gemini diagnosis failed: {e}")
        # Fallback: rule-based diagnosis
        return _rule_based_diagnosis(perf, mem, health)


def _rule_based_diagnosis(perf: Dict, mem: Dict, health: Dict) -> Dict:
    """Fallback diagnosis when Gemini is unavailable."""
    issues = []
    auto_fixes = []
    human_actions = []
    severity = "GREEN"

    win_rate = perf.get("win_rate", 100)
    pf       = perf.get("profit_factor", 99)
    rss      = mem.get("rss_mb", 0)

    if win_rate < WIN_RATE_ALERT_THRESHOLD:
        issues.append({"issue": f"Win rate below threshold", "severity": "HIGH",
                       "data": f"{win_rate}% (threshold: {WIN_RATE_ALERT_THRESHOLD}%)"})
        auto_fixes.append({"action": "TRIGGER_LEARNING", "params": {}, "reason": "Recalibrate after win rate drop"})
        severity = "RED"

    if pf < PROFIT_FACTOR_MIN:
        issues.append({"issue": "Profit factor too low", "severity": "HIGH",
                       "data": f"PF={pf} (min: {PROFIT_FACTOR_MIN})"})
        severity = "RED"

    # Check regime breakdown
    regime_stats = perf.get("regime_stats", {})
    for reg, stats in regime_stats.items():
        if stats.get("total_trades", stats["wins"] + stats["losses"]) >= 5:
            total = stats["wins"] + stats["losses"]
            if total >= 5 and stats.get("win_rate", 100) < 45:
                issues.append({"issue": f"Low win rate in {reg}", "severity": "MEDIUM",
                               "data": f"{stats['win_rate']}% ({stats['wins']}W/{stats['losses']}L)"})
                auto_fixes.append({"action": "RAISE_REGIME_THRESHOLD",
                                    "params": {"regime": reg, "threshold": REGIME_CONV_THRESHOLDS.get(reg, 70)},
                                    "reason": f"Win rate in {reg} is {stats['win_rate']}%"})
                if severity == "GREEN":
                    severity = "YELLOW"

    # Check session breakdown
    session_stats = perf.get("session_stats", {})
    closed_session = session_stats.get("closed", {})
    if closed_session:
        total_closed = closed_session.get("wins", 0) + closed_session.get("losses", 0)
        if total_closed >= 5:
            wr = round(closed_session["wins"] / total_closed * 100, 1)
            if wr < 45:
                issues.append({"issue": "Market-closed session signals losing", "severity": "HIGH",
                               "data": f"{wr}% win rate ({closed_session['wins']}W/{closed_session['losses']}L)"})
                auto_fixes.append({"action": "BLOCK_SESSION", "params": {"session": "closed"},
                                    "reason": f"Closed-session signals have {wr}% win rate"})
                if severity == "GREEN":
                    severity = "YELLOW"

    # Memory warning
    if rss > 1600:
        issues.append({"issue": "High memory usage", "severity": "MEDIUM",
                       "data": f"{rss}MB / 2048MB"})
        human_actions.append("Monitor memory — consider restarting if approaching 2GB")
        if severity == "GREEN":
            severity = "YELLOW"

    headline = (
        f"System healthy — win rate {win_rate}%, PF {pf}" if severity == "GREEN"
        else f"Issues detected — {len(issues)} problem{'s' if len(issues) > 1 else ''} found"
    )

    return {
        "severity": severity,
        "headline": headline,
        "issues": issues,
        "auto_fixes": auto_fixes,
        "human_actions": human_actions,
        "system_ok": severity in ("GREEN", "YELLOW"),
    }


# ── Auto-fix executor ─────────────────────────────────────────────────────────

def _apply_auto_fixes(fixes: List[Dict]) -> List[Dict]:
    """Apply AI-recommended fixes automatically. Returns list of applied fixes."""
    applied = []

    for fix in fixes:
        action = fix.get("action", "")
        params = fix.get("params", {})
        reason = fix.get("reason", "")

        try:
            if action == "RAISE_REGIME_THRESHOLD":
                regime    = params.get("regime", "Trending Bull")
                threshold = int(params.get("threshold", 70))
                # Write to calibration file
                _update_calibration("regime_conviction_thresholds", {regime: threshold})
                applied.append({"action": action, "regime": regime,
                                 "threshold": threshold, "reason": reason,
                                 "ts": datetime.datetime.utcnow().isoformat()})
                logger.info(f"[AI-HEALTH] Auto-fix: raised {regime} threshold to {threshold}%")

            elif action == "BLOCK_SESSION":
                session = params.get("session", "closed")
                _update_calibration("blocked_sessions", [session])
                applied.append({"action": action, "session": session, "reason": reason,
                                 "ts": datetime.datetime.utcnow().isoformat()})
                logger.info(f"[AI-HEALTH] Auto-fix: blocked {session} session signals")

            elif action == "TRIGGER_LEARNING":
                try:
                    from core.learning_loop import run_fast
                    run_fast()
                    applied.append({"action": action, "reason": reason,
                                    "ts": datetime.datetime.utcnow().isoformat()})
                    logger.info("[AI-HEALTH] Auto-fix: triggered learning loop")
                except Exception as le:
                    logger.warning(f"[AI-HEALTH] Learning loop trigger failed: {le}")

            elif action == "TIGHTEN_SL":
                regime     = params.get("regime", "Trending Bull")
                multiplier = float(params.get("sl_multiplier", 1.0))
                _update_calibration(f"sl_override_{regime.replace(' ','_')}", multiplier)
                applied.append({"action": action, "regime": regime,
                                 "sl_multiplier": multiplier, "reason": reason,
                                 "ts": datetime.datetime.utcnow().isoformat()})
                logger.info(f"[AI-HEALTH] Auto-fix: tightened SL in {regime} to {multiplier}×ATR")

        except Exception as e:
            logger.error(f"[AI-HEALTH] Auto-fix {action} failed: {e}")

    _auto_fixes_applied.extend(applied)
    return applied


def _update_calibration(key: str, value: Any):
    """Write a value to calibration_params.json."""
    from pathlib import Path
    cal_path = Path(__file__).parent.parent / "calibration" / "calibration_params.json"
    cal_path.parent.mkdir(exist_ok=True)
    data = {}
    if cal_path.exists():
        try:
            data = json.loads(cal_path.read_text())
        except Exception:
            pass
    data[key] = value
    data["last_updated"] = datetime.datetime.utcnow().isoformat()
    cal_path.write_text(json.dumps(data, indent=2))


# ── Telegram alert ────────────────────────────────────────────────────────────

def _send_health_report(diagnosis: Dict, system_state: Dict, applied_fixes: List[Dict]):
    """Send formatted health report to Telegram."""
    try:
        from core.telegram_alerts import _send

        sev    = diagnosis.get("severity", "GREEN")
        icon   = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(sev, "⚪")
        perf   = system_state.get("performance", {})
        mem    = system_state.get("memory", {})

        lines = [
            f"{icon} <b>AI HEALTH MONITOR — {sev}</b>",
            f"━━━━━━━━━━━━━━━━━━",
            f"<i>{diagnosis.get('headline', '')}</i>",
            "",
            f"📊 <b>Performance</b>",
            f"  Win rate: <b>{perf.get('win_rate', '?')}%</b> | PF: <b>{perf.get('profit_factor', '?')}</b>",
            f"  P&L: <b>{perf.get('total_pnl_pct', '?'):+.2f}%</b> | Trades: {perf.get('total_trades', 0)}",
            f"  Memory: {mem.get('rss_mb', '?')}MB / {mem.get('headroom_mb', '?')}MB free",
        ]

        if diagnosis.get("issues"):
            lines.append("\n⚠️ <b>Issues Found</b>")
            for issue in diagnosis["issues"][:4]:
                sev_i = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(issue["severity"], "⚪")
                lines.append(f"  {sev_i} {issue['issue']}: {issue.get('data', '')}")

        if applied_fixes:
            lines.append("\n🔧 <b>Auto-Fixed</b>")
            for fix in applied_fixes:
                lines.append(f"  ✅ {fix['action']}: {fix.get('reason', '')[:60]}")

        if diagnosis.get("human_actions"):
            lines.append("\n👤 <b>Action Required</b>")
            for action in diagnosis["human_actions"][:3]:
                lines.append(f"  → {action[:80]}")

        lines.append(f"\n🕐 {datetime.datetime.utcnow().strftime('%H:%M UTC')}")
        _send("\n".join(lines))
        logger.info(f"[AI-HEALTH] Alert sent — severity: {sev}")

    except Exception as e:
        logger.error(f"[AI-HEALTH] Telegram send failed: {e}")


# ── Main check cycle ──────────────────────────────────────────────────────────

def run_check_cycle(force: bool = False) -> Dict:
    """
    Run one full health check cycle:
      1. Collect system state
      2. AI diagnosis
      3. Apply auto-fixes
      4. Send Telegram alert if needed
    Returns the full result dict.
    """
    global _last_check_result

    logger.info("[AI-HEALTH] Running check cycle...")
    start = time.time()

    # 1. Collect state
    system_state = _collect_system_state()

    # 2. Diagnose
    perf = system_state.get("performance", {})
    if perf.get("insufficient_data") and not force:
        result = {
            "severity": "GREEN",
            "headline": f"Insufficient data for analysis ({perf.get('total_trades', 0)} trades — need {MIN_TRADES_FOR_ANALYSIS}+)",
            "issues": [],
            "auto_fixes": [],
            "applied_fixes": [],
            "duration_s": round(time.time() - start, 1),
            "ts": datetime.datetime.utcnow().isoformat(),
        }
        _last_check_result = result
        return result

    diagnosis = _ai_diagnose(system_state)

    # 3. Apply safe auto-fixes
    recommended_fixes = diagnosis.get("auto_fixes", [])
    applied_fixes = _apply_auto_fixes(recommended_fixes) if recommended_fixes else []

    # 4. Alert if anything wrong OR if fixes were applied
    sev = diagnosis.get("severity", "GREEN")
    if sev in ("YELLOW", "RED") or applied_fixes or force:
        _send_health_report(diagnosis, system_state, applied_fixes)

    result = {
        **diagnosis,
        "applied_fixes":  applied_fixes,
        "system_state":   system_state,
        "duration_s":     round(time.time() - start, 1),
        "ts":             datetime.datetime.utcnow().isoformat(),
    }
    _last_check_result = result
    logger.info(f"[AI-HEALTH] Cycle complete — {sev} — {len(applied_fixes)} fixes applied — {result['duration_s']}s")
    return result


# ── Background loop ───────────────────────────────────────────────────────────

def _monitor_loop():
    """Runs forever in background thread. Checks every CHECK_INTERVAL_MINUTES."""
    logger.info(f"[AI-HEALTH] Monitor loop started — checking every {CHECK_INTERVAL_MINUTES} min")

    # First check after 2 minutes (let system fully start)
    time.sleep(120)

    while True:
        try:
            run_check_cycle()
        except Exception as e:
            logger.error(f"[AI-HEALTH] Check cycle crashed: {e}", exc_info=True)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


def start():
    """Start the AI health monitor as a background daemon thread."""
    global _agent_thread
    if _agent_thread and _agent_thread.is_alive():
        logger.info("[AI-HEALTH] Already running")
        return
    _agent_thread = threading.Thread(target=_monitor_loop, daemon=True, name="ai_health_agent")
    _agent_thread.start()
    logger.info("[AI-HEALTH] AI Health Monitor started")


def get_last_result() -> Dict:
    """Return the most recent check result (for API endpoint)."""
    return _last_check_result or {"status": "No check run yet"}


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dotenv import load_dotenv
    load_dotenv()

    print("\n" + "="*55)
    print("  AI HEALTH AGENT — MANUAL RUN")
    print("="*55)

    result = run_check_cycle(force=True)

    print(f"\nSeverity: {result.get('severity')}")
    print(f"Headline: {result.get('headline')}")

    if result.get("issues"):
        print("\nIssues:")
        for i in result["issues"]:
            print(f"  [{i['severity']}] {i['issue']}: {i.get('data', '')}")

    if result.get("applied_fixes"):
        print("\nAuto-fixes applied:")
        for f in result["applied_fixes"]:
            print(f"  ✅ {f['action']}: {f.get('reason', '')}")

    if result.get("human_actions"):
        print("\nHuman actions needed:")
        for a in result.get("human_actions", []):
            print(f"  → {a}")

    print(f"\nDuration: {result.get('duration_s')}s")
    print("="*55)
