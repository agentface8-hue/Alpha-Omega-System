"""
autoresearch.py — ATLAS/Karpathy-style keep/revert loop for Alpha-Omega calibration.

Scores closed-trade expectancy before/after learning updates and logs experiments.
Does not auto-deploy live trading; paper-only guardrails.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LOG_FILE = Path(__file__).parent.parent / "calibration" / "autoresearch_log.json"
MIN_CLOSES = 10
PROFIT_READY_MIN_CLOSES = 30
PROFIT_READY_MIN_WIN_RATE = 52.0
PROFIT_READY_MIN_AVG_PNL = 0.0


def _pnl_pct(trade: Dict) -> float:
    v = trade.get("realized_pnl", trade.get("pnl_pct", 0))
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def compute_expectancy(signals: List[Dict]) -> Dict[str, Any]:
    """Aggregate closed-trade stats for autoresearch scoring."""
    if not signals:
        return {"count": 0, "win_rate": 0.0, "avg_pnl_pct": 0.0, "expectancy": 0.0}

    pnls = [_pnl_pct(s) for s in signals]
    wins = sum(1 for p in pnls if p > 0)
    count = len(pnls)
    win_rate = round(wins / count * 100, 1) if count else 0.0
    avg_pnl = round(sum(pnls) / count, 3) if count else 0.0
    avg_win = round(sum(p for p in pnls if p > 0) / wins, 3) if wins else 0.0
    losses = [p for p in pnls if p <= 0]
    avg_loss = round(sum(losses) / len(losses), 3) if losses else 0.0
    loss_rate = (count - wins) / count if count else 0
    expectancy = round((win_rate / 100) * avg_win + loss_rate * avg_loss, 3)

    by_regime: Dict[str, Dict] = {}
    for s in signals:
        regime = (s.get("entry_market_context") or {}).get("regime", s.get("regime", "Unknown"))
        by_regime.setdefault(regime, []).append(_pnl_pct(s))
    regime_stats = {}
    for regime, ps in by_regime.items():
        if len(ps) < 3:
            continue
        w = sum(1 for p in ps if p > 0)
        regime_stats[regime] = {
            "samples": len(ps),
            "win_rate": round(w / len(ps) * 100, 1),
            "avg_pnl_pct": round(sum(ps) / len(ps), 3),
        }

    return {
        "count": count,
        "win_rate": win_rate,
        "avg_pnl_pct": avg_pnl,
        "expectancy": expectancy,
        "regime_stats": regime_stats,
    }


def profit_readiness(signals: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Paper-profit readiness gate — not a guarantee of live edge."""
    if signals is None:
        from core.learning_loop import _load_closed
        signals = _load_closed()
    exp = compute_expectancy(signals)
    count = exp["count"]
    ready = (
        count >= PROFIT_READY_MIN_CLOSES
        and exp["win_rate"] >= PROFIT_READY_MIN_WIN_RATE
        and exp["expectancy"] > PROFIT_READY_MIN_AVG_PNL
    )
    blockers = []
    if count < PROFIT_READY_MIN_CLOSES:
        blockers.append(f"need {PROFIT_READY_MIN_CLOSES}+ closes (have {count})")
    if exp["win_rate"] < PROFIT_READY_MIN_WIN_RATE:
        blockers.append(f"win_rate {exp['win_rate']}% < {PROFIT_READY_MIN_WIN_RATE}%")
    if exp["expectancy"] <= PROFIT_READY_MIN_AVG_PNL:
        blockers.append(f"expectancy {exp['expectancy']}% not positive")

    from core.calibrator import load_calibration
    cal = load_calibration()
    wired = bool(cal.get("conviction_offsets")) and bool(cal.get("regime_thresholds"))

    return {
        "paper_profit_ready": ready and wired,
        "live_ready": False,
        "live_note": "IBKR + 50 post-wiring paper closes required before live",
        "calibration_wired": wired,
        "blockers": blockers,
        "metrics": exp,
    }


def _load_log() -> List[Dict]:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except Exception:
            pass
    return []


def _save_log(entries: List[Dict]):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(entries[-100:], indent=2))


def record_experiment(
    kind: str,
    before: Dict[str, Any],
    after: Dict[str, Any],
    learning_result: Optional[Dict] = None,
    verdict: Optional[str] = None,
) -> Dict[str, Any]:
    """Log one learning experiment; verdict defaults to expectancy delta."""
    delta_exp = round(after.get("expectancy", 0) - before.get("expectancy", 0), 3)
    delta_wr = round(after.get("win_rate", 0) - before.get("win_rate", 0), 1)
    if verdict is None:
        verdict = "keep" if delta_exp > 0 or (delta_exp == 0 and delta_wr > 0) else "revert_suggested"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "verdict": verdict,
        "before": before,
        "after": after,
        "delta_expectancy": delta_exp,
        "delta_win_rate": delta_wr,
        "learning": learning_result,
    }
    log = _load_log()
    log.append(entry)
    _save_log(log)
    logger.info(f"[AUTORESEARCH] {kind} verdict={verdict} dE={delta_exp}")
    return entry


def run_autoresearch_fast() -> Dict[str, Any]:
    """Run fast learning + score before/after on same closed set."""
    from core.learning_loop import _load_closed, run_fast

    signals = _load_closed()
    if len(signals) < MIN_CLOSES:
        return {"status": "insufficient_data", "count": len(signals), "need": MIN_CLOSES}

    before = compute_expectancy(signals)
    learning_result = run_fast(signals)
    after = compute_expectancy(_load_closed())
    v = "keep" if learning_result.get("status") == "ok" else "fail"
    experiment = record_experiment("fast", before, after, learning_result, verdict=v)
    readiness = profit_readiness(signals)

    return {
        "status": "ok",
        "experiment": experiment,
        "readiness": readiness,
        "learning": learning_result,
    }
