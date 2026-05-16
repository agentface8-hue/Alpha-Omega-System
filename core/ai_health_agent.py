"""
ai_health_agent.py - Autonomous AI System Monitor v1.0

KEY FIX: Added 24h cooldown per fix action.
Same fix (RAISE_REGIME_THRESHOLD, BLOCK_SESSION, etc.) will NOT be re-applied
within 24 hours of the last application. Cooldown timestamps stored in
calibration_params.json so they survive server restarts.

Telegram alerts only fire on:
  - RED severity
  - Severity worsening (GREEN->YELLOW on first occurrence)
  NOT on every recurring YELLOW cycle.
"""

import os
import json
import time
import logging
import threading
import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

CHECK_INTERVAL_MINUTES  = 30
WIN_RATE_ALERT_THRESHOLD = 42.0
PROFIT_FACTOR_MIN        = 1.2
DRAWDOWN_MAX             = -12.0
MIN_TRADES_FOR_ANALYSIS  = 5
FIX_COOLDOWN_HOURS       = 24   # Don't re-apply same fix within this window

REGIME_CONV_THRESHOLDS = {
    "Trending Bull":  72,
    "Choppy / Range": 65,
    "High-Vol Event": 70,
    "Trending Bear":  75,
}

_agent_thread = None
_last_check_result: Dict = {}
_auto_fixes_applied: List[Dict] = []
_last_severity = "GREEN"


# -- Fix cooldown helpers ------------------------------------------------------

def _fix_key(action: str, params: Dict) -> str:
    return f"{action}_{json.dumps(params, sort_keys=True)}".replace(" ","").replace('"','').replace("{","").replace("}","").replace(":","_").replace(",","_")


def _is_fix_on_cooldown(action: str, params: Dict) -> bool:
    """Return True if this fix was applied within FIX_COOLDOWN_HOURS."""
    try:
        from pathlib import Path
        cal = Path(__file__).parent.parent / "calibration" / "calibration_params.json"
        if not cal.exists():
            return False
        data = json.loads(cal.read_text())
        cooldowns = data.get("fix_cooldowns", {})
        last_ts = cooldowns.get(_fix_key(action, params), "")
        if not last_ts:
            return False
        age_h = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last_ts)).total_seconds() / 3600
        if age_h < FIX_COOLDOWN_HOURS:
            logger.info(f"[AI-HEALTH] SKIP {action} - applied {age_h:.1f}h ago (cooldown={FIX_COOLDOWN_HOURS}h)")
            return True
        return False
    except Exception as e:
        logger.warning(f"[AI-HEALTH] Cooldown check error: {e}")
        return False


def _record_cooldown(action: str, params: Dict):
    """Record fix timestamp so it won't run again for FIX_COOLDOWN_HOURS."""
    try:
        from pathlib import Path
        cal = Path(__file__).parent.parent / "calibration" / "calibration_params.json"
        cal.parent.mkdir(exist_ok=True)
        data = {}
        if cal.exists():
            try:
                data = json.loads(cal.read_text())
            except Exception:
                pass
        if "fix_cooldowns" not in data:
            data["fix_cooldowns"] = {}
        data["fix_cooldowns"][_fix_key(action, params)] = datetime.datetime.utcnow().isoformat()
        cal.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning(f"[AI-HEALTH] Cooldown record error: {e}")


# -- Core analysis -------------------------------------------------------------

def _collect_system_state() -> Dict:
    state = {}
    try:
        from core import signal_store, portfolio_store
        closed = signal_store.load_closed()
        active = signal_store.load_active()
        pf_state = portfolio_store.load_state()

        if len(closed) >= MIN_TRADES_FOR_ANALYSIS:
            wins   = [s for s in closed if s.get("pnl_pct", 0) > 0]
            losses = [s for s in closed if s.get("pnl_pct", 0) <= 0]
            win_rate = round(len(wins) / len(closed) * 100, 1)
            avg_win  = round(sum(s["pnl_pct"] for s in wins) / len(wins), 2) if wins else 0
            avg_loss = round(sum(s["pnl_pct"] for s in losses) / len(losses), 2) if losses else 0
            gp = sum(s["pnl_pct"] for s in wins) if wins else 0
            gl = abs(sum(s["pnl_pct"] for s in losses)) if losses else 0.01
            profit_factor = round(gp / gl, 2)

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
                d["avg_pnl"]  = round(sum(d["pnls"]) / len(d["pnls"]), 2) if d["pnls"] else 0
                del d["pnls"]

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
                "total_trades": len(closed), "active_signals": len(active),
                "win_rate": win_rate, "avg_win_pct": avg_win, "avg_loss_pct": avg_loss,
                "profit_factor": profit_factor, "regime_stats": regime_stats,
                "session_stats": session_stats,
                "portfolio_value": pf_state.get("total_value", 25000),
                "starting_capital": pf_state.get("starting_capital", 25000),
                "total_pnl_pct": round((pf_state.get("total_value", 25000) - 25000) / 25000 * 100, 2),
            }
        else:
            state["performance"] = {"total_trades": len(closed), "insufficient_data": True}
    except Exception as e:
        state["performance"] = {"error": str(e)}

    try:
        from core.system_health import check_portfolio_state, check_signal_tracker, check_learning_loop
        state["health"] = {
            "portfolio": check_portfolio_state(),
            "signals":   check_signal_tracker(),
            "learning":  check_learning_loop(),
        }
    except Exception as e:
        state["health"] = {"error": str(e)}

    try:
        import psutil, os as _os
        proc = psutil.Process(_os.getpid())
        rss  = round(proc.memory_info().rss / 1024**2, 1)
        state["memory"] = {"rss_mb": rss, "limit_mb": 2048, "headroom_mb": round(2048 - rss, 1), "ok": rss < 1600}
    except Exception:
        state["memory"] = {"rss_mb": 0, "limit_mb": 2048, "headroom_mb": 2048, "ok": True}

    state["auto_fixes_applied"] = _auto_fixes_applied[-5:]
    return state


def _ai_diagnose(system_state: Dict) -> Dict:
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return {"error": "No GOOGLE_API_KEY", "severity": "UNKNOWN", "issues": [], "auto_fixes": []}

    perf   = system_state.get("performance", {})
    mem    = system_state.get("memory", {})
    health = system_state.get("health", {})

    prompt = f"""You are the AI health monitor for Alpha-Omega, an automated paper trading system.
Analyze this snapshot and return a JSON diagnosis.

PERFORMANCE:
- Total trades: {perf.get('total_trades', 0)}
- Win rate: {perf.get('win_rate', 0)}%
- Profit factor: {perf.get('profit_factor', 0)}
- Avg win: +{perf.get('avg_win_pct', 0)}% | Avg loss: {perf.get('avg_loss_pct', 0)}%
- P&L: {perf.get('total_pnl_pct', 0)}%

REGIME BREAKDOWN:
{json.dumps(perf.get('regime_stats', {}), indent=2)}

SESSION BREAKDOWN:
{json.dumps(perf.get('session_stats', {}), indent=2)}

MEMORY: {mem.get('rss_mb', 0)}MB / 2048MB

FIXES ALREADY APPLIED (do not suggest these again): {json.dumps(system_state.get('auto_fixes_applied', []))}

Respond ONLY with JSON:
{{
  "severity": "GREEN" | "YELLOW" | "RED",
  "headline": "one sentence",
  "issues": [{{"issue": "...", "severity": "HIGH|MEDIUM|LOW", "data": "..."}}],
  "auto_fixes": [{{"action": "RAISE_REGIME_THRESHOLD|BLOCK_SESSION|TRIGGER_LEARNING|TIGHTEN_SL", "params": {{}}, "reason": "..."}}],
  "human_actions": ["..."],
  "system_ok": true | false
}}"""

    try:
        import urllib.request
        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"maxOutputTokens": 800, "temperature": 0.1}}).encode()
        req  = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read().decode())
        raw = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[AI-HEALTH] Gemini failed: {e}")
        return _rule_based_diagnosis(perf, mem, health)


def _rule_based_diagnosis(perf: Dict, mem: Dict, health: Dict) -> Dict:
    issues, auto_fixes, human_actions, severity = [], [], [], "GREEN"

    win_rate = perf.get("win_rate", 100)
    pf       = perf.get("profit_factor", 99)
    rss      = mem.get("rss_mb", 0)

    if win_rate < WIN_RATE_ALERT_THRESHOLD:
        issues.append({"issue": "Win rate below threshold", "severity": "HIGH",
                        "data": f"{win_rate}% (threshold: {WIN_RATE_ALERT_THRESHOLD}%)"})
        auto_fixes.append({"action": "TRIGGER_LEARNING", "params": {}, "reason": "Recalibrate after win rate drop"})
        severity = "RED"

    if pf < PROFIT_FACTOR_MIN:
        issues.append({"issue": "Profit factor too low", "severity": "HIGH", "data": f"PF={pf}"})
        severity = "RED"

    for reg, stats in perf.get("regime_stats", {}).items():
        total = stats["wins"] + stats["losses"]
        if total >= 5 and stats.get("win_rate", 100) < 45:
            issues.append({"issue": f"Low win rate in {reg}", "severity": "MEDIUM",
                            "data": f"{stats['win_rate']}% ({stats['wins']}W/{stats['losses']}L)"})
            auto_fixes.append({"action": "RAISE_REGIME_THRESHOLD",
                                 "params": {"regime": reg, "threshold": REGIME_CONV_THRESHOLDS.get(reg, 70)},
                                 "reason": f"Win rate in {reg} is {stats['win_rate']}%"})
            if severity == "GREEN":
                severity = "YELLOW"

    closed_s = perf.get("session_stats", {}).get("closed", {})
    if closed_s:
        tc = closed_s.get("wins", 0) + closed_s.get("losses", 0)
        if tc >= 5:
            wr = round(closed_s["wins"] / tc * 100, 1)
            if wr < 45:
                issues.append({"issue": "Market-closed session losing", "severity": "HIGH",
                                "data": f"{wr}% ({closed_s['wins']}W/{closed_s['losses']}L)"})
                auto_fixes.append({"action": "BLOCK_SESSION", "params": {"session": "closed"},
                                     "reason": f"Closed-session win rate {wr}%"})
                if severity == "GREEN":
                    severity = "YELLOW"

    if rss > 1600:
        issues.append({"issue": "High memory", "severity": "MEDIUM", "data": f"{rss}MB/2048MB"})
        if severity == "GREEN":
            severity = "YELLOW"

    headline = (f"System healthy - win rate {win_rate}%, PF {pf}" if severity == "GREEN"
                else f"Issues detected - {len(issues)} problem{'s' if len(issues)>1 else ''} found")

    return {"severity": severity, "headline": headline, "issues": issues,
            "auto_fixes": auto_fixes, "human_actions": human_actions, "system_ok": severity in ("GREEN","YELLOW")}


# -- Auto-fix executor (with 24h cooldown) ------------------------------------

def _apply_auto_fixes(fixes: List[Dict]) -> List[Dict]:
    """Apply fixes. Each fix is skipped if applied within FIX_COOLDOWN_HOURS."""
    applied = []

    for fix in fixes:
        action = fix.get("action", "")
        params = fix.get("params", {})
        reason = fix.get("reason", "")

        # COOLDOWN: skip if this exact fix was applied recently
        if _is_fix_on_cooldown(action, params):
            continue

        try:
            if action == "RAISE_REGIME_THRESHOLD":
                regime    = params.get("regime", "Trending Bull")
                threshold = int(params.get("threshold", 70))
                _update_calibration("regime_conviction_thresholds", {regime: threshold})
                applied.append({"action": action, "regime": regime, "threshold": threshold,
                                  "reason": reason, "ts": datetime.datetime.utcnow().isoformat()})
                _record_cooldown(action, params)
                logger.info(f"[AI-HEALTH] Fixed: raised {regime} threshold to {threshold}%")

            elif action == "BLOCK_SESSION":
                session = params.get("session", "closed")
                _update_calibration("blocked_sessions", [session])
                applied.append({"action": action, "session": session,
                                  "reason": reason, "ts": datetime.datetime.utcnow().isoformat()})
                _record_cooldown(action, params)
                logger.info(f"[AI-HEALTH] Fixed: blocked {session} session")

            elif action == "TRIGGER_LEARNING":
                try:
                    from core.learning_loop import run_fast
                    run_fast()
                    applied.append({"action": action, "reason": reason,
                                     "ts": datetime.datetime.utcnow().isoformat()})
                    _record_cooldown(action, params)
                    logger.info("[AI-HEALTH] Fixed: triggered learning loop")
                except Exception as le:
                    logger.warning(f"[AI-HEALTH] Learning trigger failed: {le}")

            elif action == "TIGHTEN_SL":
                regime     = params.get("regime", "Trending Bull")
                multiplier = float(params.get("sl_multiplier", 1.0))
                _update_calibration(f"sl_override_{regime.replace(' ','_')}", multiplier)
                applied.append({"action": action, "regime": regime, "sl_multiplier": multiplier,
                                  "reason": reason, "ts": datetime.datetime.utcnow().isoformat()})
                _record_cooldown(action, params)

        except Exception as e:
            logger.error(f"[AI-HEALTH] Fix {action} failed: {e}")

    _auto_fixes_applied.extend(applied)
    return applied


def _update_calibration(key: str, value: Any):
    from pathlib import Path
    cal = Path(__file__).parent.parent / "calibration" / "calibration_params.json"
    cal.parent.mkdir(exist_ok=True)
    data = {}
    if cal.exists():
        try:
            data = json.loads(cal.read_text())
        except Exception:
            pass
    data[key] = value
    data["last_updated"] = datetime.datetime.utcnow().isoformat()
    cal.write_text(json.dumps(data, indent=2))


# -- Telegram (only RED or first severity worsening) --------------------------

def _send_health_report(diagnosis: Dict, system_state: Dict, applied_fixes: List[Dict]):
    try:
        from core.telegram_alerts import _send
        sev  = diagnosis.get("severity", "GREEN")
        perf = system_state.get("performance", {})
        mem  = system_state.get("memory", {})
        lines = [
            f"AI HEALTH MONITOR - {sev}",
            diagnosis.get("headline", ""),
            f"Win rate: {perf.get('win_rate','?')}% | PF: {perf.get('profit_factor','?')}",
            f"Memory: {mem.get('rss_mb','?')}MB",
        ]
        for issue in (diagnosis.get("issues") or [])[:3]:
            lines.append(f"[{issue['severity']}] {issue['issue']}: {issue.get('data','')}")
        if applied_fixes:
            lines.append(f"Auto-fixed: {', '.join(f['action'] for f in applied_fixes)}")
        lines.append(datetime.datetime.utcnow().strftime("%H:%M UTC"))
        _send("\n".join(lines))
    except Exception as e:
        logger.error(f"[AI-HEALTH] Telegram failed: {e}")


# -- Main check cycle ----------------------------------------------------------

def run_check_cycle(force: bool = False) -> Dict:
    global _last_check_result, _last_severity

    logger.info("[AI-HEALTH] Running check cycle...")
    start = time.time()

    system_state = _collect_system_state()
    perf = system_state.get("performance", {})

    if perf.get("insufficient_data") and not force:
        result = {
            "severity": "GREEN",
            "headline": f"Insufficient data ({perf.get('total_trades',0)} trades - need {MIN_TRADES_FOR_ANALYSIS}+)",
            "issues": [], "auto_fixes": [], "applied_fixes": [],
            "duration_s": round(time.time() - start, 1),
            "ts": datetime.datetime.utcnow().isoformat(),
        }
        _last_check_result = result
        return result

    diagnosis     = _ai_diagnose(system_state)
    applied_fixes = _apply_auto_fixes(diagnosis.get("auto_fixes", []))

    sev      = diagnosis.get("severity", "GREEN")
    prev_sev = _last_severity

    # Only alert on RED, or when severity WORSENS for the first time
    severity_worsened = (prev_sev == "GREEN" and sev in ("YELLOW","RED")) or (prev_sev == "YELLOW" and sev == "RED")
    if force or sev == "RED" or (severity_worsened and applied_fixes):
        _send_health_report(diagnosis, system_state, applied_fixes)

    _last_severity = sev

    result = {
        **diagnosis,
        "applied_fixes": applied_fixes,
        "system_state":  system_state,
        "duration_s":    round(time.time() - start, 1),
        "ts":            datetime.datetime.utcnow().isoformat(),
    }
    _last_check_result = result
    logger.info(f"[AI-HEALTH] Done - {sev} - {len(applied_fixes)} fixes - {result['duration_s']}s")
    return result


# -- Background loop -----------------------------------------------------------

def _monitor_loop():
    logger.info(f"[AI-HEALTH] Started - every {CHECK_INTERVAL_MINUTES} min")
    time.sleep(120)
    while True:
        try:
            run_check_cycle()
        except Exception as e:
            logger.error(f"[AI-HEALTH] Crashed: {e}", exc_info=True)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


def start():
    global _agent_thread
    if _agent_thread and _agent_thread.is_alive():
        return
    _agent_thread = threading.Thread(target=_monitor_loop, daemon=True, name="ai_health_agent")
    _agent_thread.start()
    logger.info("[AI-HEALTH] Started")


def get_last_result() -> Dict:
    return _last_check_result or {"status": "No check run yet"}


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dotenv import load_dotenv
    load_dotenv()
    print("=" * 50 + "\n  AI HEALTH AGENT - MANUAL RUN\n" + "=" * 50)
    result = run_check_cycle(force=True)
    print(f"Severity: {result.get('severity')}")
    print(f"Headline: {result.get('headline')}")
    for i in result.get("issues", []):
        print(f"  [{i['severity']}] {i['issue']}: {i.get('data','')}")
    for f in result.get("applied_fixes", []):
        print(f"  Fixed: {f['action']}")
    print("=" * 50)
