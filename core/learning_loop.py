"""
learning_loop.py — Self-improving calibration from closed signal history.
Reads closed signals from Supabase, calculates what conviction thresholds
actually worked, and updates calibration_params.json automatically.
Runs weekly as a background thread.
"""
import threading
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

CALIBRATION_FILE = Path(__file__).parent.parent / "calibration" / "calibration_params.json"
CALIBRATION_FILE.parent.mkdir(exist_ok=True)

_INTERVAL = 7 * 24 * 3600   # weekly
_MIN_SAMPLES = 20            # need at least 20 closed signals to learn


def _load_closed_signals() -> List[Dict]:
    """Load closed signals — Supabase first, JSON fallback."""
    try:
        from core.signal_store import load_closed
        return load_closed()
    except Exception as e:
        logger.error(f"[LEARN] load closed signals: {e}")
        return []


def _analyze(signals: List[Dict]) -> Dict[str, Any]:
    """
    Crunch closed signals into calibration insights.
    Returns dict with conviction bracket performance + recommended offsets.
    """
    brackets = {
        "85-100": [], "75-84": [], "65-74": [],
        "60-64": [], "50-59": [], "40-49": [],
    }

    for s in signals:
        conv = s.get("conviction", 0)
        status = s.get("status", "")
        tp1_hit = status in ("TP1_HIT", "TP2_HIT", "TP3_HIT")
        win     = tp1_hit or s.get("realized_pnl", 0) > 0

        if conv >= 85:   brackets["85-100"].append(win)
        elif conv >= 75: brackets["75-84"].append(win)
        elif conv >= 65: brackets["65-74"].append(win)
        elif conv >= 60: brackets["60-64"].append(win)
        elif conv >= 50: brackets["50-59"].append(win)
        elif conv >= 40: brackets["40-49"].append(win)

    stats = {}
    offsets = {}

    for label, results in brackets.items():
        if not results:
            stats[label] = None
            continue
        win_rate  = round(sum(results) / len(results) * 100, 1)
        mid_conv  = (int(label.split("-")[0]) + int(label.split("-")[1])) / 2
        # If win_rate < mid_conviction - 10 → system is overconfident → negative offset
        # If win_rate > mid_conviction + 10 → underrated → positive offset
        offset = round((win_rate - mid_conv) * 0.3, 1)  # dampen to 30%
        stats[label]   = {"win_rate": win_rate, "samples": len(results), "offset": offset}
        offsets[label] = offset

    return {"bracket_stats": stats, "offsets": offsets}


def _apply_calibration(analysis: Dict):
    """Write updated calibration params to file."""
    existing = {}
    if CALIBRATION_FILE.exists():
        try:
            existing = json.loads(CALIBRATION_FILE.read_text())
        except:
            pass

    existing["conviction_offsets"] = analysis["offsets"]
    existing["bracket_stats"]      = analysis["bracket_stats"]
    existing["last_updated"]       = datetime.utcnow().isoformat()
    existing["sample_count"]       = sum(
        v["samples"] for v in analysis["bracket_stats"].values() if v
    )

    CALIBRATION_FILE.write_text(json.dumps(existing, indent=2))
    logger.info(f"[LEARN] Calibration updated. Offsets: {analysis['offsets']}")


def run_once() -> Dict:
    """Run one learning cycle. Called manually or by scheduler."""
    signals = _load_closed_signals()
    if len(signals) < _MIN_SAMPLES:
        msg = f"Only {len(signals)} closed signals — need {_MIN_SAMPLES} to learn"
        logger.info(f"[LEARN] {msg}")
        return {"status": "insufficient_data", "message": msg, "count": len(signals)}

    analysis = _analyze(signals)
    _apply_calibration(analysis)

    # Send Telegram summary
    try:
        from core.telegram_alerts import _send
        lines = [f"🧠 <b>Weekly Self-Calibration Complete</b>"]
        lines.append(f"📊 Signals analyzed: {len(signals)}")
        for label, stat in analysis["bracket_stats"].items():
            if stat:
                sign = "+" if stat["offset"] > 0 else ""
                lines.append(
                    f"  {label}%: win {stat['win_rate']}% "
                    f"({stat['samples']} trades) → offset {sign}{stat['offset']}"
                )
        lines.append(f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        _send("\n".join(lines))
    except Exception as e:
        logger.warning(f"[LEARN] Telegram notify failed: {e}")

    return {"status": "ok", "signals_analyzed": len(signals), **analysis}


def _loop():
    time.sleep(3600)   # wait 1 hour after startup before first run
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"[LEARN] Loop error: {e}")
        time.sleep(_INTERVAL)


def start():
    t = threading.Thread(target=_loop, daemon=True, name="learning_loop")
    t.start()
    logger.info("[LEARN] Self-improvement loop started (weekly)")
