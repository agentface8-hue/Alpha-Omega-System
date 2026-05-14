"""
agent_council.py — Multi-agent Bull/Bear debate with Opus Moderator.

Architecture:
  - Bull Agent  (Sonnet 4.6): argues for the trade
  - Bear Agent  (Sonnet 4.6): argues against the trade
  - Moderator   (Opus 4.6):   weighs both sides, delivers final verdict

Triggered for high-conviction signals (>= 70%) before entry.
Non-blocking when called from advisor.py — result is attached to signal.

Main entry point: run_council(signal_data, market_context) -> dict
"""
import os
import json
import logging
import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"
OPUS_MODEL   = "claude-opus-4-7"   # upgraded from 4.6

# ── System Prompts ────────────────────────────────────────────────────────────

_BULL_SYSTEM = """You are the Bull Agent on the Alpha-Omega Trading Council.
Your job: make the strongest possible case FOR entering this trade.
Focus on: momentum signals, technical setup quality, regime alignment, risk/reward.
Be specific and cite the data provided. Be concise but persuasive.

Return ONLY valid JSON:
{
  "case": "<3-4 sentences making the bull case>",
  "top_reasons": ["<reason 1>", "<reason 2>", "<reason 3>"],
  "confidence": <50-100 integer>
}
No markdown, no extra keys."""

_BEAR_SYSTEM = """You are the Bear Agent on the Alpha-Omega Trading Council.
Your job: make the strongest possible case AGAINST entering this trade.
Focus on: risks, warning signs, regime concerns, position sizing issues, timing problems.
Be specific and cite the data provided. Be concise but sharp.

Return ONLY valid JSON:
{
  "case": "<3-4 sentences making the bear case>",
  "top_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "confidence": <50-100 integer>
}
No markdown, no extra keys."""

_MODERATOR_SYSTEM = """You are the Moderator of the Alpha-Omega Trading Council.
You receive a Bull Agent's case and a Bear Agent's case for a potential trade.
Weigh both sides objectively and deliver a final verdict.

Verdict guide:
  PROCEED_STRONG    = Bull case clearly dominates, strong setup, take full size
  PROCEED_CAUTIOUS  = Good setup but real risks, take reduced size or tighter SL
  HOLD              = Mixed signals, wait for cleaner setup or confirmation
  VETO              = Bear case dominates, risk too high, do not enter

Return ONLY valid JSON:
{
  "verdict": "PROCEED_STRONG" | "PROCEED_CAUTIOUS" | "HOLD" | "VETO",
  "reasoning": "<2-3 sentences explaining the verdict>",
  "key_factor": "<the single most important factor in your decision>",
  "size_guidance": "FULL" | "HALF" | "QUARTER" | "NONE"
}
No markdown, no extra keys."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_signal_summary(signal: Dict, market_ctx: Dict) -> str:
    ticker   = signal.get("ticker", "?")
    entry    = signal.get("entry", signal.get("entry_price", 0))
    sl       = signal.get("sl", 0)
    tp1      = signal.get("tp1", 0)
    tp3      = signal.get("tp3", 0)
    conv     = signal.get("conviction_pct", signal.get("conviction", 0))
    tas      = signal.get("tas", "?")
    regime   = market_ctx.get("regime", signal.get("regime", "?"))
    vix      = market_ctx.get("vix", signal.get("vix_at_entry", "?"))
    spy      = market_ctx.get("spy_change_pct", "?")
    heat     = signal.get("heat", "?")
    ps       = signal.get("pillar_scores") or {}
    p_str    = "  ".join(f"P{i+1}={ps.get(f'p{i+1}','?')}%" for i in range(5)) if ps else "not captured"
    rr       = round((tp1 - entry) / (entry - sl), 2) if entry and sl and sl < entry and tp1 > entry else "?"
    adv      = signal.get("advisor_verdict", "")
    adv_th   = signal.get("advisor_thesis", "")

    lines = [
        f"Ticker: {ticker}  |  Heat: {heat}  |  TAS: {tas}",
        f"Entry: ${entry}  |  SL: ${sl}  |  TP1: ${tp1}  |  TP3: ${tp3}",
        f"R:R = {rr}:1",
        f"Conviction: {conv}%  |  Pillars: {p_str}",
        f"Market regime: {regime}  |  VIX: {vix}  |  SPY today: {spy}%",
    ]
    if adv and adv != "APPROVE":
        lines.append(f"Advisor pre-screen: {adv} — {adv_th}")
    return "\n".join(lines)


def _call_sonnet(system: str, prompt: str) -> Dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _call_opus_moderator(prompt: str) -> Dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=250,
        system=_MODERATOR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ── Public Entry Point ────────────────────────────────────────────────────────

def run_council(signal: Dict, market_ctx: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Run the Bull/Bear/Moderator council for a signal.

    Args:
        signal:     Signal dict (must have ticker, entry, sl, tp1, conviction_pct)
        market_ctx: Market context dict (regime, vix, spy_change_pct)

    Returns:
        {
          "verdict":      "PROCEED_STRONG" | "PROCEED_CAUTIOUS" | "HOLD" | "VETO",
          "reasoning":    str,
          "key_factor":   str,
          "size_guidance": "FULL" | "HALF" | "QUARTER" | "NONE",
          "bull_case":    str,
          "bull_reasons": list,
          "bull_confidence": int,
          "bear_case":    str,
          "bear_risks":   list,
          "bear_confidence": int,
          "ts":           str,
          "models":       {"bull": ..., "bear": ..., "moderator": ...},
          "error":        str (only if failed)
        }
    """
    market_ctx = market_ctx or {}
    ticker = signal.get("ticker", "?")
    summary = _build_signal_summary(signal, market_ctx)

    logger.info(f"[COUNCIL] Starting debate for {ticker}...")

    # Step 1: Bull Agent
    try:
        bull_prompt = f"Analyze this trade setup and make the bull case:\n\n{summary}"
        bull = _call_sonnet(_BULL_SYSTEM, bull_prompt)
    except Exception as e:
        logger.warning(f"[COUNCIL] Bull agent failed for {ticker}: {e}")
        bull = {
            "case": f"Bull analysis unavailable: {str(e)[:60]}",
            "top_reasons": [],
            "confidence": 50,
        }

    # Step 2: Bear Agent
    try:
        bear_prompt = f"Analyze this trade setup and make the bear case:\n\n{summary}"
        bear = _call_sonnet(_BEAR_SYSTEM, bear_prompt)
    except Exception as e:
        logger.warning(f"[COUNCIL] Bear agent failed for {ticker}: {e}")
        bear = {
            "case": f"Bear analysis unavailable: {str(e)[:60]}",
            "top_risks": [],
            "confidence": 50,
        }

    # Step 3: Opus Moderator — weighs both sides
    try:
        mod_prompt = (
            f"Trade setup:\n{summary}\n\n"
            f"BULL AGENT (confidence {bull.get('confidence',50)}%):\n{bull.get('case','')}\n"
            f"Reasons: {', '.join(bull.get('top_reasons', []))}\n\n"
            f"BEAR AGENT (confidence {bear.get('confidence',50)}%):\n{bear.get('case','')}\n"
            f"Risks: {', '.join(bear.get('top_risks', []))}\n\n"
            f"Deliver your verdict."
        )
        moderator = _call_opus_moderator(mod_prompt)
    except Exception as e:
        logger.warning(f"[COUNCIL] Moderator failed for {ticker}: {e}")
        # Default to PROCEED_CAUTIOUS on moderator failure — never block on error
        moderator = {
            "verdict": "PROCEED_CAUTIOUS",
            "reasoning": f"Moderator unavailable: {str(e)[:60]}. Defaulting to cautious.",
            "key_factor": "System error — review manually",
            "size_guidance": "HALF",
        }

    result = {
        "verdict":          moderator.get("verdict", "PROCEED_CAUTIOUS"),
        "reasoning":        moderator.get("reasoning", ""),
        "key_factor":       moderator.get("key_factor", ""),
        "size_guidance":    moderator.get("size_guidance", "FULL"),
        "bull_case":        bull.get("case", ""),
        "bull_reasons":     bull.get("top_reasons", []),
        "bull_confidence":  bull.get("confidence", 50),
        "bear_case":        bear.get("case", ""),
        "bear_risks":       bear.get("top_risks", []),
        "bear_confidence":  bear.get("confidence", 50),
        "ts":               datetime.datetime.utcnow().isoformat(),
        "models": {
            "bull":       SONNET_MODEL,
            "bear":       SONNET_MODEL,
            "moderator":  OPUS_MODEL,
        },
    }

    logger.info(f"[COUNCIL] {ticker} verdict: {result['verdict']} — {result['key_factor'][:60]}")
    return result


def _send_council_alert(ticker: str, result: Dict):
    """Telegram alert for VETO or PROCEED_STRONG verdicts."""
    try:
        from core.telegram_alerts import _send
        verdict = result.get("verdict", "")
        emoji = {
            "PROCEED_STRONG":   "\U0001f7e2",
            "PROCEED_CAUTIOUS": "\U0001f7e1",
            "HOLD":             "\U0001f7e0",
            "VETO":             "\U0001f534",
        }.get(verdict, "⚪")
        reasoning = result.get("reasoning", "")[:160]
        key = result.get("key_factor", "")[:100]
        size = result.get("size_guidance", "FULL")
        _send(
            f"{emoji} <b>COUNCIL VERDICT — {ticker}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Verdict: <b>{verdict}</b>  |  Size: <b>{size}</b>\n"
            f"\U0001f4ac {reasoning}\n"
            f"\U0001f511 Key factor: {key}\n"
            f"\U0001f550 {datetime.datetime.utcnow().strftime('%H:%M UTC')}"
        )
    except Exception as e:
        logger.warning(f"[COUNCIL] Telegram alert failed: {e}")
