"""
advisor.py — Two-layer AI advisor for Alpha-Omega signals.

  screen_signal()  — Sonnet 4.6 automatic pre-trade screener.
                     Runs on every new signal. Returns APPROVE / FLAG / VETO.

  ask_opus()       — Opus 4.6 on-demand deep oracle.
                     Called explicitly by the trader with a free-text question.
                     Reads full signal context, returns a thoughtful answer.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"
OPUS_MODEL   = "claude-opus-4-6"

_SCREEN_SYSTEM = """You are a trading signal screener for the Alpha-Omega AI system.
Review the conviction data and return ONLY a valid JSON object — no markdown, no explanation.

Verdict rules:
- VETO  : conviction < 55%, OR VIX > 35 with conviction < 70%, OR 3+ pillars below 40%
- FLAG  : conviction 55-64%, OR any single pillar < 40%, OR TAS <= 2/4, OR multiple minor concerns
- APPROVE: conviction >= 65% with no major structural weaknesses

Response format (strict JSON, no extra keys):
{
  "verdict": "APPROVE" | "FLAG" | "VETO",
  "confidence": <integer 0-100>,
  "concerns": ["<specific concern>", "<specific concern>"],
  "thesis": "<one sentence — what makes or breaks this trade>"
}

Keep concerns specific and actionable (max 3). Thesis must be one sentence."""

_OPUS_SYSTEM = """You are the senior trading advisor for Alpha-Omega, an AI-powered paper trading system.
The trader will give you a live signal's context and ask a specific question.
Be direct, concise, and insightful. Max 3 sentences. No bullet points. No fluff.
Think like an experienced prop trader reviewing a position, not like a financial advisor giving disclaimers."""


def _get_client():
    """Return an Anthropic client, raises RuntimeError if key missing."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def _build_screen_prompt(scan_data: Dict, market_context: Dict) -> str:
    """Build the compact signal summary for Sonnet screening."""
    ticker   = scan_data.get("ticker", "?")
    conv     = scan_data.get("conviction_pct") or scan_data.get("conviction", 0)
    ps       = scan_data.get("pillar_scores") or {}
    p1       = ps.get("p1", "?")
    p2       = ps.get("p2", "?")
    p3       = ps.get("p3", "?")
    p4       = ps.get("p4", "?")
    p5       = ps.get("p5", "?")
    tas      = scan_data.get("tas") or scan_data.get("indicators", {}).get("tas", "?")
    regime   = market_context.get("regime", "?")
    vix      = market_context.get("vix", "?")
    spy_chg  = market_context.get("spy_change_pct", "?")
    entry    = scan_data.get("entry") or scan_data.get("entry_high", "?")
    sl       = scan_data.get("sl", "?")
    tp1      = scan_data.get("tp1", "?")
    tp3      = scan_data.get("tp3", "?")
    rsi      = scan_data.get("indicators", {}).get("rsi14") or scan_data.get("rsi", "?")
    atype    = scan_data.get("asset_type", "stock").upper()

    return (
        f"Ticker: {ticker} ({atype})\n"
        f"Conviction: {conv}%\n"
        f"Pillars: P1={p1}%  P2={p2}%  P3={p3}%  P4={p4}%  P5={p5}%\n"
        f"TAS: {tas} timeframes aligned\n"
        f"RSI: {rsi}\n"
        f"Regime: {regime}  |  VIX: {vix}  |  SPY today: {spy_chg}%\n"
        f"Levels: Entry=${entry}  SL=${sl}  TP1=${tp1}  TP3=${tp3}"
    )


def _build_opus_prompt(signal: Dict, question: str) -> str:
    """Build the full signal summary for Opus."""
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", "?")
    sl      = signal.get("sl", "?")
    tp1     = signal.get("tp1", "?")
    tp3     = signal.get("tp3", "?")
    conv    = signal.get("conviction", "?")
    regime  = signal.get("regime", "?")
    vix     = signal.get("vix_at_entry", "?")
    pnl     = signal.get("pnl_pct", 0)
    state   = signal.get("trade_state", "RUNNING")
    price   = signal.get("current_price", entry)
    tsl     = signal.get("sl")          # current SL (may have been trailed)
    tas     = signal.get("tas", "?")
    ps      = signal.get("pillar_scores") or {}
    p_str   = "  ".join(f"P{i+1}={ps.get(f'p{i+1}','?')}%" for i in range(5)) if ps else "not available"

    advisor = signal.get("advisor_verdict", "")
    adv_note = ""
    if advisor:
        concerns = signal.get("advisor_concerns", [])
        adv_note = (
            f"\nAdvisor at entry: {advisor}"
            + (f" — {', '.join(concerns)}" if concerns else "")
        )

    summary = (
        f"Signal: {ticker}\n"
        f"Entry: ${entry}  |  Current: ${price}  |  P&L: {pnl:+.1f}%\n"
        f"SL: ${tsl}  |  TP1: ${tp1}  |  TP3: ${tp3}\n"
        f"Conviction: {conv}%  |  TAS: {tas}  |  Trade state: {state}\n"
        f"Pillars: {p_str}\n"
        f"Regime at entry: {regime}  |  VIX at entry: {vix}"
        f"{adv_note}"
    )
    return f"Signal context:\n{summary}\n\nTrader question: {question}"


# ── Public API ────────────────────────────────────────────────────────────────

def screen_signal(scan_data: Dict, market_context: Dict) -> Dict[str, Any]:
    """
    Sonnet 4.6 pre-trade screener. Runs automatically on new signal creation.
    Always returns a dict — never raises. Fails gracefully to APPROVE on error
    so a Sonnet outage never blocks trading.

    Returns:
        {
            "verdict":    "APPROVE" | "FLAG" | "VETO",
            "confidence": int,
            "concerns":   List[str],
            "thesis":     str,
            "model":      str,
            "error":      str  (only on failure)
        }
    """
    # Skip low-conviction signals — conviction engine already filtered them
    conv = scan_data.get("conviction_pct") or scan_data.get("conviction", 0)
    if conv and float(conv) < 55:
        return {
            "verdict": "VETO",
            "confidence": 95,
            "concerns": [f"Conviction {conv}% below 55% threshold"],
            "thesis": "Conviction engine already flagged this as below threshold.",
            "model": "local-rule",
        }

    try:
        client = _get_client()
        prompt = _build_screen_prompt(scan_data, market_context)
        msg = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=180,
            system=_SCREEN_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        result["model"] = SONNET_MODEL
        # Normalise fields
        result.setdefault("verdict", "APPROVE")
        result.setdefault("confidence", 70)
        result.setdefault("concerns", [])
        result.setdefault("thesis", "")
        result["verdict"] = result["verdict"].upper()
        if result["verdict"] not in ("APPROVE", "FLAG", "VETO"):
            result["verdict"] = "APPROVE"
        return result

    except Exception as e:
        logger.warning(f"[ADVISOR] screen_signal failed ({e}) — defaulting to APPROVE")
        return {
            "verdict": "APPROVE",
            "confidence": 50,
            "concerns": [],
            "thesis": "",
            "model": SONNET_MODEL,
            "error": str(e),
        }


def run_council_screen(scan_data: Dict, market_context: Dict) -> Optional[Dict[str, Any]]:
    """
    Run the Bull/Bear/Moderator council for high-conviction signals (>= 70%).
    Returns the council result dict, or None if conviction is below threshold.
    Always returns gracefully — never raises.
    """
    conv = scan_data.get("conviction_pct") or scan_data.get("conviction", 0)
    try:
        conv_f = float(conv)
    except (TypeError, ValueError):
        conv_f = 0

    if conv_f < 70:
        logger.debug(f"[ADVISOR] Council skipped — conviction {conv_f}% < 70%")
        return None

    ticker = scan_data.get("ticker", "?")
    logger.info(f"[ADVISOR] Launching council for {ticker} (conviction {conv_f}%)")
    try:
        from core.agent_council import run_council, _send_council_alert
        result = run_council(scan_data, market_context)
        # Send Telegram alert for strong verdicts
        if result.get("verdict") in ("VETO", "PROCEED_STRONG"):
            _send_council_alert(ticker, result)
        return result
    except Exception as e:
        logger.warning(f"[ADVISOR] Council failed for {ticker}: {e}")
        return {
            "verdict": "PROCEED_CAUTIOUS",
            "reasoning": f"Council unavailable: {str(e)[:80]}",
            "key_factor": "System error",
            "size_guidance": "HALF",
            "bull_case": "", "bull_reasons": [], "bull_confidence": 50,
            "bear_case": "", "bear_risks":   [], "bear_confidence": 50,
            "error": str(e),
        }


def ask_opus(signal: Dict, question: str) -> Dict[str, Any]:
    """
    Opus 4.6 on-demand deep oracle. Called explicitly by the trader.
    Reads full signal context and answers the trader's specific question.

    Returns:
        {
            "answer": str,
            "model":  str,
            "error":  str  (only on failure)
        }
    """
    if not question or not question.strip():
        return {"answer": "Please ask a specific question about this signal.", "model": OPUS_MODEL}

    try:
        client = _get_client()
        prompt = _build_opus_prompt(signal, question.strip())
        msg = client.messages.create(
            model=OPUS_MODEL,
            max_tokens=250,
            system=_OPUS_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "answer": msg.content[0].text.strip(),
            "model":  OPUS_MODEL,
        }

    except Exception as e:
        logger.error(f"[ADVISOR] ask_opus failed: {e}")
        return {
            "answer": f"Opus unavailable: {str(e)[:120]}",
            "model":  OPUS_MODEL,
            "error":  str(e),
        }
}")
        return {
            "verdict": "PROCEED_CAUTIOUS",
            "reasoning": f"Council unavailable: {str(e)[:80]}",
            "key_factor": "System error",
            "size_guidance": "HALF",
            "bull_case": "", "bull_reasons": [], "bull_confidence": 50,
            "bear_case": "", "bear_risks":   [], "bear_confidence": 50,
            "error": str(e),
        }


def ask_opus(signal: Dict, question: str) -> Dict[str, Any]:
    """
    Opus 4.6 on-demand deep oracle. Called explicitly by the trader.
    Reads full signal context and answers the trader's specific question.

    Returns:
        {
            "answer": str,
            "model":  str,
            "error":  str  (only on failure)
        }
    """
    if not question or not question.strip():
        return {"answer": "Please ask a specific question about this signal.", "model": OPUS_MODEL}

    try:
        client = _get_client()
        prompt = _build_opus_prompt(signal, question.strip())
        msg = client.messages.create(
            model=OPUS_MODEL,
            max_tokens=250,
            system=_OPUS_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "answer": msg.content[0].text.strip(),
            "model":  OPUS_MODEL,
        }

    except Exception as e:
        logger.error(f"[ADVISOR] ask_opus failed: {e}")
        return {
            "answer": f"Opus unavailable: {str(e)[:120]}",
            "model":  OPUS_MODEL,
            "error":  str(e),
        }
