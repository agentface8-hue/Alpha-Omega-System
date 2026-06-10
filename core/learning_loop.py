"""
learning_loop.py — Self-improving calibration engine v2.0

Architecture: Actor → Judge → Meta-Judge (inspired by Meta-RL research, 2025)

  Actor    : Every closed trade is a data point
  Judge    : Analyzes patterns across 5 dimensions after every 5 new closes
  Meta-Judge: Weekly deep analysis — rewrites calibration_params.json

The 5 dimensions analyzed:
  1. Conviction brackets     — are 70% signals actually winning 70%?
  2. Regime performance      — what works in Bull vs Bear vs Choppy?
  3. Sector win rates        — which sectors are hot/cold right now?
  4. Advisor accuracy        — is Sonnet's APPROVE/FLAG/VETO call correct?
  5. DTP effectiveness       — do wider TPs at high conviction actually pay off?

Output: calibration_params.json gets updated with:
  - conviction_offsets       — per-bracket score adjustments
  - regime_thresholds        — min conviction per regime
  - sector_bias              — boost/penalty per sector
  - advisor_weight           — how much to trust Sonnet veto
  - dtp_effectiveness        — are TP scale multipliers calibrated?

Triggers:
  - After every 5 new closed signals (fast loop, lightweight)
  - Weekly deep analysis (full Opus-powered Meta-Judge)
"""
import os
import threading
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

CALIBRATION_FILE = Path(__file__).parent.parent / "calibration" / "calibration_params.json"
CALIBRATION_FILE.parent.mkdir(exist_ok=True)

_FAST_INTERVAL   = 3600        # check every hour if 5+ new closes
_WEEKLY_INTERVAL = 7 * 24 * 3600
_MIN_SAMPLES     = 10          # minimum closes to run fast analysis
_DEEP_MIN        = 25          # minimum for deep weekly analysis
_last_analyzed_count = 0       # track how many signals we've seen


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_closed() -> List[Dict]:
    """Load live closed signals merged with full signal history (74+ trades)."""
    try:
        from core.signal_store import load_closed
        live = load_closed()
    except Exception as e:
        logger.error(f"[LEARN] load_closed failed: {e}")
        live = []
    try:
        from core.signal_history import load_merged
        merged = load_merged(live)
    except Exception as e:
        logger.warning(f"[LEARN] history merge failed, using live only: {e}")
        merged = live
    return _enrich_signal_metadata(merged)


def _resolve_sector(signal: Dict) -> str:
    sector = signal.get("sector") or (signal.get("entry_snapshot") or {}).get("sector") or ""
    if sector and sector not in ("Unknown", "Other", ""):
        return sector
    try:
        from core.universe_builder import get_ticker_sector
        return get_ticker_sector(signal.get("ticker", "")) or "Unknown"
    except Exception:
        return "Unknown"


def _enrich_signal_metadata(signals: List[Dict]) -> List[Dict]:
    """Backfill sector/regime on historical rows missing metadata."""
    out = []
    for s in signals:
        row = dict(s)
        row["sector"] = _resolve_sector(row)
        if not row.get("regime"):
            row["regime"] = (row.get("entry_market_context") or {}).get("regime", "")
        out.append(row)
    return out


def _load_calibration() -> Dict:
    if CALIBRATION_FILE.exists():
        try:
            return json.loads(CALIBRATION_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_calibration(params: Dict):
    params["last_updated"] = datetime.utcnow().isoformat()
    CALIBRATION_FILE.write_text(json.dumps(params, indent=2))


# ── Dimension 1: Conviction bracket performance ───────────────────────────────

def _analyze_conviction(signals: List[Dict]) -> Dict:
    brackets = {"85-100": [], "75-84": [], "65-74": [], "60-64": [], "50-59": []}
    for s in signals:
        conv = s.get("conviction", 0)
        win  = s.get("realized_pnl", s.get("pnl_pct", 0)) > 0
        if   conv >= 85: brackets["85-100"].append(win)
        elif conv >= 75: brackets["75-84"].append(win)
        elif conv >= 65: brackets["65-74"].append(win)
        elif conv >= 60: brackets["60-64"].append(win)
        elif conv >= 50: brackets["50-59"].append(win)

    result = {}
    offsets = {}
    for label, wins in brackets.items():
        if not wins:
            continue
        wr = round(sum(wins) / len(wins) * 100, 1)
        mid = (int(label.split("-")[0]) + int(label.split("-")[1])) / 2
        offset = round((wr - mid) * 0.25, 1)  # dampen to 25%
        result[label]  = {"win_rate": wr, "samples": len(wins), "offset": offset}
        offsets[label] = offset
    return {"stats": result, "offsets": offsets}


# ── Dimension 2: Regime performance ──────────────────────────────────────────

def _analyze_regime(signals: List[Dict]) -> Dict:
    regimes = defaultdict(list)
    for s in signals:
        regime = (s.get("entry_market_context") or {}).get("regime", s.get("regime", "Unknown"))
        win    = s.get("realized_pnl", s.get("pnl_pct", 0)) > 0
        regimes[regime].append(win)

    result = {}
    thresholds = {}
    for regime, wins in regimes.items():
        if len(wins) < 3:
            continue
        wr = round(sum(wins) / len(wins) * 100, 1)
        # If win rate < 40% in a regime → raise minimum conviction threshold
        if   wr < 40:  thresh = 75
        elif wr < 50:  thresh = 70
        elif wr < 60:  thresh = 65
        else:          thresh = 60
        result[regime]     = {"win_rate": wr, "samples": len(wins), "min_conviction": thresh}
        thresholds[regime] = thresh
    return {"stats": result, "thresholds": thresholds}


# ── Dimension 3: Sector win rates ─────────────────────────────────────────────

def _analyze_sectors(signals: List[Dict]) -> Dict:
    sectors = defaultdict(list)
    for s in signals:
        sector = s.get("sector", "Unknown")
        pnl    = s.get("realized_pnl", s.get("pnl_pct", 0))
        sectors[sector].append(pnl)

    result = {}
    bias   = {}
    for sector, pnls in sectors.items():
        if len(pnls) < 3:
            continue
        wins   = [p for p in pnls if p > 0]
        wr     = round(len(wins) / len(pnls) * 100, 1)
        avg_pl = round(sum(pnls) / len(pnls), 2)
        # Bias: HOT if win_rate > 60% and avg_pnl > 0, COLD if win_rate < 40%
        b = "HOT" if wr > 60 and avg_pl > 0 else "COLD" if wr < 40 else "NEUTRAL"
        result[sector] = {"win_rate": wr, "avg_pnl": avg_pl, "samples": len(pnls), "bias": b}
        bias[sector]   = b
    return {"stats": result, "bias": bias}


# ── Dimension 4: Advisor accuracy ────────────────────────────────────────────

def _analyze_advisor(signals: List[Dict]) -> Dict:
    correct = wrong = 0
    veto_saved = veto_wrong = 0
    for s in signals:
        verdict = s.get("advisor_verdict", "")
        win     = s.get("realized_pnl", s.get("pnl_pct", 0)) > 0
        if verdict == "APPROVE" and win:     correct    += 1
        elif verdict == "APPROVE" and not win: wrong    += 1
        elif verdict == "VETO" and not win:  veto_saved += 1
        elif verdict == "VETO" and win:      veto_wrong += 1

    total = correct + wrong + veto_saved + veto_wrong
    if total == 0:
        return {"accuracy_pct": None, "weight": 1.0}

    accuracy = round((correct + veto_saved) / total * 100, 1)
    # Advisor weight: 1.0 = trust fully, 0.5 = half weight
    weight = round(min(1.0, max(0.5, accuracy / 100)), 2)
    return {
        "accuracy_pct": accuracy,
        "correct": correct, "wrong": wrong,
        "veto_saved": veto_saved, "veto_wrong": veto_wrong,
        "weight": weight,
    }


# ── Dimension 5: DTP effectiveness ───────────────────────────────────────────

def _analyze_dtp(signals: List[Dict]) -> Dict:
    """Did higher conviction → wider TPs actually produce better outcomes?"""
    high_conv   = [s for s in signals if s.get("conviction", 0) >= 75]
    normal_conv = [s for s in signals if 60 <= s.get("conviction", 0) < 75]

    def _avg_pnl(group):
        pnls = [s.get("realized_pnl", s.get("pnl_pct", 0)) for s in group]
        return round(sum(pnls) / len(pnls), 2) if pnls else 0

    high_pnl   = _avg_pnl(high_conv)
    normal_pnl = _avg_pnl(normal_conv)

    # If high_conv trades are NOT outperforming → DTP is too aggressive
    dtp_working = high_pnl > normal_pnl if (high_conv and normal_conv) else None
    return {
        "high_conv_avg_pnl":   high_pnl,
        "normal_conv_avg_pnl": normal_pnl,
        "dtp_working":         dtp_working,
        "high_conv_samples":   len(high_conv),
        "normal_conv_samples": len(normal_conv),
    }


# ── Deep research (Opus Meta-Judge) ───────────────────────────────────────────

OPUS_MODEL = "claude-opus-4-6"
_DEEP_RESEARCH_LOG = Path(__file__).parent.parent / "calibration" / "deep_research_log.json"

_META_JUDGE_SYSTEM = """You are the Alpha-Omega Meta-Judge — deep research layer on top of quantitative trade analytics.
You receive aggregate statistics from closed paper trades (conviction brackets, regimes, sectors, advisor, DTP).
Your job: strategic calibration guidance for a swing trading system. Be conservative and evidence-based.

Return ONLY valid JSON (no markdown):
{
  "headline": "<one line executive summary>",
  "conviction_verdict": "<KEEP_72|RAISE_TO_X|LOWER_TO_X with brief reason>",
  "regime_insights": ["<insight>", "..."],
  "sector_insights": ["<insight>", "..."],
  "advisor_insights": "<1-2 sentences>",
  "dtp_insights": "<1-2 sentences>",
  "top_3_actions": ["<actionable>", "<actionable>", "<actionable>"],
  "risk_flags": ["<flag if any>"],
  "confidence": "HIGH" | "MEDIUM" | "LOW"
}"""


def _build_research_prompt(signals: List[Dict], conviction: Dict, regime: Dict,
                           sector: Dict, advisor: Dict, dtp: Dict) -> str:
    wins = sum(1 for s in signals if (s.get("realized_pnl", s.get("pnl_pct", 0)) or 0) > 0)
    wr = round(wins / len(signals) * 100, 1) if signals else 0
    payload = {
        "trade_count": len(signals),
        "portfolio_win_rate_pct": wr,
        "conviction_stats": conviction.get("stats", {}),
        "regime_stats": regime.get("stats", {}),
        "sector_stats": sector.get("stats", {}),
        "advisor": advisor,
        "dtp": dtp,
        "current_autopilot_threshold": 72,
        "volume_gate": "block vol_ratio < 1.0x",
    }
    return (
        "Analyze this closed-trade calibration dataset and recommend threshold/strategy adjustments.\n\n"
        + json.dumps(payload, indent=2, default=str)
    )


def _parse_research_json(raw: str) -> Dict:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _call_opus_research(prompt: str) -> Dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=900,
        system=_META_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return _parse_research_json(raw)


def _save_deep_research_log(entry: Dict):
    try:
        existing = []
        if _DEEP_RESEARCH_LOG.exists():
            try:
                existing = json.loads(_DEEP_RESEARCH_LOG.read_text())
            except Exception:
                pass
        existing.append(entry)
        existing = existing[-20:]
        _DEEP_RESEARCH_LOG.write_text(json.dumps(existing, indent=2, default=str))
    except Exception as e:
        logger.warning(f"[LEARN] deep research log save failed: {e}")


def run_deep_research(signals: List[Dict], conviction: Dict, regime: Dict,
                      sector: Dict, advisor: Dict, dtp: Dict) -> Dict:
    """
    Opus meta-judge: strategic insights on top of 5D stats.
    Never raises — returns error dict on failure so run_deep still completes.
    """
    t0 = time.time()
    try:
        if len(signals) < _DEEP_MIN:
            return {"status": "skipped", "reason": f"need {_DEEP_MIN}+ trades, have {len(signals)}"}
        prompt = _build_research_prompt(signals, conviction, regime, sector, advisor, dtp)
        research = _call_opus_research(prompt)
        elapsed_ms = int((time.time() - t0) * 1000)
        out = {
            "status": "ok",
            "model": OPUS_MODEL,
            "elapsed_ms": elapsed_ms,
            "generated_at": datetime.utcnow().isoformat(),
            **research,
        }
        _save_deep_research_log(out)
        return out
    except Exception as e:
        logger.warning(f"[LEARN] Deep research failed: {e}")
        return {"status": "error", "detail": str(e)[:200]}


def _analyze_themes() -> Dict[str, Any]:
    """Score closed portfolio trades by entry_themes; tune registry strengths."""
    try:
        from core.portfolio_store import load_positions
        from core.theme_engine import analyze_theme_performance, load_registry, save_registry
    except Exception as e:
        logger.warning(f"[LEARN] theme analysis skipped: {e}")
        return {"stats": {}}

    closed = load_positions("closed")
    stats = analyze_theme_performance(closed)
    if not stats:
        return {"stats": stats}

    reg = load_registry()
    for t in reg.get("themes", []):
        tid = t.get("id")
        if tid not in stats or stats[tid].get("samples", 0) < 3:
            continue
        wr = float(stats[tid]["win_rate"])
        s = float(t.get("strength", 0.5))
        if wr < 35:
            t["strength"] = round(max(0.25, s - 0.12), 2)
        elif wr > 60:
            t["strength"] = round(min(1.0, s + 0.06), 2)
        t["active"] = t["strength"] >= 0.55
    save_registry(reg)
    return {"stats": stats}


# ── Fast analysis (every 5 new closes) ───────────────────────────────────────

def run_fast(signals: Optional[List[Dict]] = None) -> Dict:
    """
    Lightweight analysis. Runs after every 5 new closed signals.
    Updates calibration_params.json with conviction + regime data only.
    """
    global _last_analyzed_count
    signals = signals or _load_closed()
    if len(signals) < _MIN_SAMPLES:
        return {"status": "insufficient_data", "count": len(signals), "need": _MIN_SAMPLES}

    conviction_data = _analyze_conviction(signals)
    regime_data     = _analyze_regime(signals)
    sector_data     = _analyze_sectors(signals)
    advisor_data    = _analyze_advisor(signals)
    theme_data      = _analyze_themes()

    params = _load_calibration()
    params["conviction_offsets"]   = conviction_data["offsets"]
    params["conviction_stats"]     = conviction_data["stats"]
    params["regime_thresholds"]    = regime_data["thresholds"]
    params["regime_stats"]         = regime_data["stats"]
    params["sector_bias"]          = sector_data["bias"]
    params["sector_stats"]         = sector_data["stats"]
    params["advisor_accuracy"]     = advisor_data
    params["theme_performance"]    = theme_data.get("stats", {})
    params["fast_run_count"]       = params.get("fast_run_count", 0) + 1
    params["last_fast_run"]        = datetime.utcnow().isoformat()
    params["signals_analyzed"]     = len(signals)
    _save_calibration(params)

    _last_analyzed_count = len(signals)
    logger.info(f"[LEARN] Fast analysis done — {len(signals)} signals, "
                f"offsets={conviction_data['offsets']} themes={list(theme_data.get('stats', {}).keys())}")

    autoresearch_entry = None
    try:
        from core.autoresearch import compute_expectancy, record_experiment
        exp = compute_expectancy(signals)
        autoresearch_entry = record_experiment(
            "fast_inline", exp, exp, {"status": "ok", "type": "fast"}
        )
    except Exception as e:
        logger.warning(f"[LEARN] autoresearch log skipped: {e}")

    return {"status": "ok", "type": "fast", "signals": len(signals),
            "conviction_offsets": conviction_data["offsets"],
            "regime_thresholds": regime_data["thresholds"],
            "sector_bias": sector_data["bias"],
            "theme_performance": theme_data.get("stats", {}),
            "autoresearch": autoresearch_entry}


# ── Deep weekly analysis (Meta-Judge) ────────────────────────────────────────

def run_deep(signals: Optional[List[Dict]] = None) -> Dict:
    """
    Full 5-dimension analysis. Runs weekly.
    Updates all calibration dimensions + sends Telegram summary.
    """
    signals = signals or _load_closed()
    if len(signals) < _MIN_SAMPLES:
        return {"status": "insufficient_data", "count": len(signals), "need": _MIN_SAMPLES}

    conviction_data = _analyze_conviction(signals)
    regime_data     = _analyze_regime(signals)
    sector_data     = _analyze_sectors(signals)
    advisor_data    = _analyze_advisor(signals)
    dtp_data        = _analyze_dtp(signals)

    params = _load_calibration()
    params["conviction_offsets"]   = conviction_data["offsets"]
    params["conviction_stats"]     = conviction_data["stats"]
    params["regime_thresholds"]    = regime_data["thresholds"]
    params["regime_stats"]         = regime_data["stats"]
    params["sector_bias"]          = sector_data["bias"]
    params["sector_stats"]         = sector_data["stats"]
    params["advisor_accuracy"]     = advisor_data
    params["dtp_effectiveness"]    = dtp_data
    params["deep_run_count"]       = params.get("deep_run_count", 0) + 1
    params["last_deep_run"]        = datetime.utcnow().isoformat()
    params["signals_analyzed"]     = len(signals)

    research = run_deep_research(
        signals, conviction_data, regime_data, sector_data, advisor_data, dtp_data
    )
    params["deep_research"] = research
    _save_calibration(params)

    _send_deep_summary(signals, conviction_data, regime_data,
                       sector_data, advisor_data, dtp_data, research)

    logger.info(f"[LEARN] Deep analysis done — {len(signals)} signals analyzed")
    return {
        "status":       "ok",
        "type":         "deep",
        "signals":      len(signals),
        "conviction":   conviction_data,
        "regimes":      regime_data,
        "sectors":      sector_data,
        "advisor":      advisor_data,
        "dtp":          dtp_data,
        "deep_research": research,
    }


# ── Telegram summary ──────────────────────────────────────────────────────────

def _send_deep_summary(signals, conviction, regime, sector, advisor, dtp, research=None):
    try:
        from core.telegram_alerts import _send

        lines = ["🧠 <b>Weekly Self-Calibration</b>",
                 f"📊 {len(signals)} trades analyzed",
                 ""]

        # Conviction
        lines.append("📈 <b>Conviction brackets:</b>")
        for label, stat in conviction["stats"].items():
            sign = "+" if stat["offset"] > 0 else ""
            lines.append(f"  {label}%: {stat['win_rate']}% WR "
                         f"({stat['samples']} trades) → offset {sign}{stat['offset']}")

        # Regime
        if regime["stats"]:
            lines.append("\n🌍 <b>Regime performance:</b>")
            for r, stat in regime["stats"].items():
                lines.append(f"  {r}: {stat['win_rate']}% WR → min conviction {stat['min_conviction']}%")

        # Sectors
        hot   = [s for s, v in sector["bias"].items() if v == "HOT"]
        cold  = [s for s, v in sector["bias"].items() if v == "COLD"]
        if hot:   lines.append(f"\n🟢 Hot sectors: {', '.join(hot)}")
        if cold:  lines.append(f"🔴 Cold sectors: {', '.join(cold)}")

        # Advisor
        if advisor.get("accuracy_pct") is not None:
            lines.append(f"\n🤖 Advisor accuracy: {advisor['accuracy_pct']}% "
                         f"(weight={advisor['weight']})")

        # DTP
        if dtp.get("dtp_working") is not None:
            status = "✅ working" if dtp["dtp_working"] else "⚠️ needs review"
            lines.append(f"\n🎯 DTP: {status} | high-conv avg {dtp['high_conv_avg_pnl']:+.1f}% "
                         f"vs normal {dtp['normal_conv_avg_pnl']:+.1f}%")

        if research and research.get("status") == "ok":
            lines.append("\n🧠 <b>Meta-Judge (Opus):</b>")
            lines.append(f"  {research.get('headline', '')}")
            lines.append(f"  Conviction: {research.get('conviction_verdict', '?')}")
            for act in (research.get("top_3_actions") or [])[:3]:
                lines.append(f"  • {act}")
            if research.get("risk_flags"):
                lines.append(f"  ⚠️ {', '.join(research['risk_flags'][:2])}")
        elif research and research.get("status") == "error":
            lines.append(f"\n🧠 Meta-Judge skipped: {research.get('detail', '?')[:80]}")

        lines.append(f"\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        _send("\n".join(lines))
    except Exception as e:
        logger.warning(f"[LEARN] Telegram summary failed: {e}")


# ── Public API ─────────────────────────────────────────────────────────────────

def run_once() -> Dict:
    """Alias for run_fast — called by scheduler and API endpoint."""
    return run_fast()


def trigger_if_new_closes(threshold: int = 5) -> Optional[Dict]:
    """
    Called after every signal close. Runs fast analysis if
    >= threshold new closes have happened since last analysis.
    """
    global _last_analyzed_count
    signals = _load_closed()
    new_closes = len(signals) - _last_analyzed_count
    if new_closes >= threshold:
        logger.info(f"[LEARN] {new_closes} new closes → triggering fast analysis")
        return run_fast(signals)
    return None


# ── Background threads ─────────────────────────────────────────────────────────

def _fast_loop():
    time.sleep(1800)   # 30 min warm-up
    while True:
        try:
            trigger_if_new_closes(threshold=5)
        except Exception as e:
            logger.error(f"[LEARN] Fast loop error: {e}")
        time.sleep(_FAST_INTERVAL)


def _deep_loop():
    time.sleep(3600)   # 1 hour warm-up
    while True:
        try:
            run_deep()
        except Exception as e:
            logger.error(f"[LEARN] Deep loop error: {e}")
        time.sleep(_WEEKLY_INTERVAL)


def get_summary_fast() -> Dict[str, Any]:
    """Lightweight summary for API — skips per-signal sector enrich (can exceed 10s on Render)."""
    import concurrent.futures

    def _with_timeout(fn, seconds: float, default=None):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(fn)
            try:
                return fut.result(timeout=seconds)
            except Exception as e:
                logger.warning(f"[LEARN] summary step timed out/failed: {e}")
                return default

    params = _load_calibration()

    def _count_closed() -> int:
        from core.signal_store import load_closed
        from core.signal_history import load_merged
        return len(load_merged(load_closed()))

    def _outcomes() -> Dict[str, Any]:
        from core.outcomes_grader import load_outcomes_summary
        return load_outcomes_summary()

    total_closed = _with_timeout(_count_closed, 12, default=0) or 0
    outcomes = _with_timeout(
        _outcomes, 8,
        default={"total": 0, "grade_distribution": {}, "recent_lessons": []},
    ) or {"total": 0, "grade_distribution": {}, "recent_lessons": []}

    research_log: List[Any] = []
    try:
        rp = Path(__file__).parent.parent / "calibration" / "deep_research_log.json"
        if rp.exists():
            research_log = json.loads(rp.read_text())[-3:]
    except Exception:
        pass
    return {
        "calibration": params,
        "outcomes": outcomes,
        "total_closed": total_closed,
        "deep_research_latest": params.get("deep_research"),
        "deep_research_history": research_log,
    }


def start():
    """Start both loops as daemon threads."""
    t1 = threading.Thread(target=_fast_loop, daemon=True, name="learn_fast")
    t2 = threading.Thread(target=_deep_loop, daemon=True, name="learn_deep")
    t1.start()
    t2.start()
    logger.info("[LEARN] Self-improvement engine started (fast=hourly, deep=weekly)")
