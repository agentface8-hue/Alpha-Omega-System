"""
outcomes_grader.py — Automatic post-trade grader powered by Opus.

Fires on every signal close (non-blocking background thread).
Opus reads the full closed signal + case report, grades A-F,
explains whether the conviction engine was correct, extracts one lesson.

Main entry point: grade_outcome(signal)
"""
import os
import json
import logging
import threading
import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

OPUS_MODEL = "claude-opus-4-7"   # upgraded from 4.6

_GRADE_SYSTEM = """You are the Alpha-Omega Outcomes Grader. Your job is to grade completed trades.
You receive a closed signal with full entry/exit context and conviction data.
Grade the DECISION QUALITY, not just the P&L — a good decision can lose money, a bad one can win.

Return ONLY a valid JSON object:
{
  "grade": "A" | "B" | "C" | "D" | "F",
  "was_conviction_right": true | false,
  "pnl_outcome": "WIN" | "LOSS" | "BREAKEVEN",
  "lesson": "<1-2 sentences: the most important thing to learn from this trade>",
  "improvement": "<1 sentence: what should have been done differently, or 'None — execution was correct'>",
  "conviction_accuracy": "OVERCONFIDENT" | "CALIBRATED" | "UNDERCONFIDENT"
}

Grade guide:
  A = Excellent: right thesis, right entry, good execution
  B = Good: right thesis, minor timing or execution issues
  C = Acceptable: mixed signals, outcome in line with risk taken
  D = Poor: ignored warning signs, poor risk management
  F = Should not have entered: thesis was wrong from the start

No markdown, no extra keys."""


def _build_grade_prompt(signal: Dict) -> str:
    ticker    = signal.get("ticker", "?")
    entry     = signal.get("entry_price", 0)
    close_p   = signal.get("close_price", 0)
    pnl       = signal.get("pnl_pct", 0)
    reason    = signal.get("close_reason", "?")
    conv      = signal.get("conviction", 0)
    regime    = signal.get("regime", "?")
    vix       = signal.get("vix_at_entry", signal.get("entry_market_context", {}).get("vix", "?"))
    tas       = signal.get("tas", "?")
    ps        = signal.get("pillar_scores") or {}
    mae       = signal.get("mae_pct", 0)
    mfe       = signal.get("mfe_pct", 0)
    tp1_hit   = signal.get("tp1_hit", False)
    tp2_hit   = signal.get("tp2_hit", False)
    tp3_hit   = signal.get("tp3_hit", False)
    advisor   = signal.get("advisor_verdict", "")
    adv_thesis = signal.get("advisor_thesis", "")
    bars      = signal.get("bars_held", 0)
    session   = signal.get("entry_session", "?")
    close_ctx = signal.get("close_market_context") or {}

    p_str = "  ".join(f"P{i+1}={ps.get(f'p{i+1}','?')}%" for i in range(5)) if ps else "not captured"

    lines = [
        f"Ticker: {ticker}",
        f"Entry: ${entry}  |  Exit: ${close_p}  |  P&L: {pnl:+.1f}%",
        f"Close reason: {reason}",
        f"Held: {bars} bars  |  Session at entry: {session}",
        f"Conviction at entry: {conv}%  |  TAS: {tas}",
        f"Pillars: {p_str}",
        f"Regime at entry: {regime}  |  VIX: {vix}",
        f"MAE (worst drawdown): {mae}%  |  MFE (best unrealized): +{mfe}%",
        f"TP1 hit: {tp1_hit}  |  TP2 hit: {tp2_hit}  |  TP3 hit: {tp3_hit}",
    ]
    if close_ctx:
        lines.append(f"Regime at exit: {close_ctx.get('regime','?')}  |  VIX at exit: {close_ctx.get('vix','?')}")
    if advisor:
        lines.append(f"Advisor verdict at entry: {advisor} — {adv_thesis}")

    return "\n".join(lines)


def _call_opus_grade(prompt: str) -> Dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=220,
        system=_GRADE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _save_outcome(outcome: Dict) -> bool:
    """Persist to Supabase outcomes table, JSON fallback."""
    try:
        import os
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if url and key:
            sb = create_client(url, key)
            sb.table("outcomes").insert(outcome).execute()
            return True
    except Exception as e:
        logger.debug(f"[GRADER] Supabase save failed: {e}")

    try:
        from pathlib import Path
        log_path = Path(__file__).parent.parent / "signals" / "outcomes_log.json"
        existing = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text())
            except Exception:
                pass
        existing.append(outcome)
        existing = existing[-200:]
        log_path.write_text(json.dumps(existing, indent=2, default=str))
        return True
    except Exception as e:
        logger.error(f"[GRADER] JSON fallback failed: {e}")
        return False


def _send_grade_alert(signal: Dict, outcome: Dict):
    """Telegram alert with the grade — delegates to telegram_alerts module."""
    try:
        from core.telegram_alerts import alert_outcome_graded
        alert_outcome_graded(signal, outcome)
    except Exception as e:
        logger.warning(f"[GRADER] Telegram alert failed: {e}")


def _grade_in_background(signal: Dict):
    """Run the full grading flow — called in a daemon thread."""
    signal_id = signal.get("id", "?")
    ticker    = signal.get("ticker", "?")
    try:
        prompt  = _build_grade_prompt(signal)
        result  = _call_opus_grade(prompt)
    except Exception as e:
        logger.warning(f"[GRADER] {ticker} grading failed: {e}")
        result = {
            "grade": "C",
            "was_conviction_right": None,
            "pnl_outcome": "WIN" if signal.get("pnl_pct", 0) > 0 else "LOSS",
            "lesson": f"Grading unavailable: {str(e)[:60]}",
            "improvement": "N/A",
            "conviction_accuracy": "CALIBRATED",
            "error": str(e),
        }

    outcome = {
        "signal_id":   signal_id,
        "ticker":      ticker,
        "ts":          datetime.datetime.utcnow().isoformat(),
        "pnl_pct":     signal.get("pnl_pct", 0),
        "close_reason":signal.get("close_reason", ""),
        **result,
        "model": OPUS_MODEL,
    }

    _save_outcome(outcome)
    _send_grade_alert(signal, outcome)

    # Write grade back to signal in storage
    try:
        from core import signal_store as store
        closed = store.load_closed()
        for s in closed:
            if s.get("id") == signal_id:
                s["outcome_grade"]    = result.get("grade")
                s["outcome_lesson"]   = result.get("lesson", "")
                s["outcome_improvement"] = result.get("improvement", "")
                s["was_conviction_right"] = result.get("was_conviction_right")
                s["conviction_accuracy"]  = result.get("conviction_accuracy", "")
                break
        store.save_closed(closed)
    except Exception as e:
        logger.warning(f"[GRADER] Could not write grade back to signal: {e}")

    logger.info(f"[GRADER] {ticker} graded {result.get('grade')} — {result.get('lesson','')[:60]}")


# ── Public API ────────────────────────────────────────────────────────────────

def grade_outcome(signal: Dict) -> None:
    """
    Non-blocking entry point. Call from close_signal() after saving.
    Spawns a daemon thread — never blocks the close flow.
    """
    t = threading.Thread(
        target=_grade_in_background,
        args=(signal,),
        name=f"grader_{signal.get('id','?')}",
        daemon=True,
    )
    t.start()


def load_outcomes_summary() -> Dict[str, Any]:
    """Load outcomes from storage and return summary stats + recent lessons."""
    outcomes = []

    try:
        from core import signal_store as store
        if store._sb():
            result = (store._sb().table("outcomes")
                      .select("*").order("ts", desc=True).limit(100).execute())
            outcomes = result.data or []
    except Exception:
        pass

    if not outcomes:
        try:
            from pathlib import Path
            log_path = Path(__file__).parent.parent / "signals" / "outcomes_log.json"
            if log_path.exists():
                outcomes = list(reversed(json.loads(log_path.read_text())))
        except Exception:
            pass

    if not outcomes:
        return {"total": 0, "grade_distribution": {}, "lessons": []}

    from collections import Counter
    grades = [o.get("grade", "?") for o in outcomes]
    grade_dist = dict(Counter(grades))
    conviction_right = [o for o in outcomes if o.get("was_conviction_right") is True]
    conviction_wrong = [o for o in outcomes if o.get("was_conviction_right") is False]

    return {
        "total": len(outcomes),
        "grade_distribution": grade_dist,
        "conviction_accuracy_pct": (
            round(len(conviction_right) / len(outcomes) * 100, 1) if outcomes else 0
        ),
        "recent_lessons": [
            {"ticker": o.get("ticker"), "grade": o.get("grade"),
             "pnl_pct": o.get("pnl_pct"), "lesson": o.get("lesson", "")}
            for o in outcomes[:10]
        ],
    }
