"""
theme_engine.py — Macro/narrative themes for sector + ticker bias.

Detects active market themes (AI, memory, rates, energy, etc.) from sector
momentum + optional headline scan, persists to calibration/theme_registry.json,
and feeds autopilot + learning loop.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent.parent / "calibration" / "theme_registry.json"

# Curated theme catalog — extend over time; learning loop scores each id
DEFAULT_THEMES: List[Dict[str, Any]] = [
    {
        "id": "AI_CAPEX",
        "name": "AI infrastructure & datacenter",
        "sectors": ["Technology"],
        "keywords": ["ai", "gpu", "datacenter", "nvidia", "hyperscaler", "capex"],
        "tickers": ["NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "META", "SMCI", "ANET"],
    },
    {
        "id": "MEMORY_HBM",
        "name": "Memory / HBM shortage",
        "sectors": ["Technology"],
        "keywords": ["memory", "hbm", "dram", "nand", "micron", "semiconductor memory"],
        "tickers": ["MU", "WDC", "STX", "SKM"],
    },
    {
        "id": "CYBER_SECURITY",
        "name": "Cybersecurity spend",
        "sectors": ["Technology"],
        "keywords": ["cyber", "breach", "security", "zero trust"],
        "tickers": ["CRWD", "PANW", "ZS", "FTNT"],
    },
    {
        "id": "GLP1_HEALTH",
        "name": "GLP-1 / obesity chain",
        "sectors": ["Health Care"],
        "keywords": ["glp-1", "ozempic", "wegovy", "obesity", "weight loss"],
        "tickers": ["LLY", "NVO", "AMGN"],
    },
    {
        "id": "RATE_SENSITIVE",
        "name": "Rates / financials re-rating",
        "sectors": ["Financials", "Real Estate"],
        "keywords": ["fed", "rate cut", "yield", "banks", "reit"],
        "tickers": ["JPM", "BAC", "GS", "XLF"],
    },
    {
        "id": "ENERGY_SHOCK",
        "name": "Energy / oil strength",
        "sectors": ["Energy"],
        "keywords": ["oil", "opec", "crude", "natural gas", "energy"],
        "tickers": ["XOM", "CVX", "COP", "SLB"],
    },
    {
        "id": "DEFENSE",
        "name": "Defense & aerospace",
        "sectors": ["Industrials"],
        "keywords": ["defense", "pentagon", "military", "aerospace"],
        "tickers": ["LMT", "RTX", "NOC", "GD"],
    },
    {
        "id": "NUCLEAR_UTIL",
        "name": "Nuclear / power demand",
        "sectors": ["Utilities", "Industrials"],
        "keywords": ["nuclear", "uranium", "power grid", "utilities"],
        "tickers": ["CEG", "VST", "NRG"],
    },
]


def _default_registry() -> Dict[str, Any]:
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "themes": [{**t, "strength": 0.5, "active": False, "source": "catalog"} for t in DEFAULT_THEMES],
        "headline_hits": [],
    }


def load_registry() -> Dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text())
        except Exception:
            pass
    reg = _default_registry()
    save_registry(reg)
    return reg


def save_registry(data: Dict[str, Any]):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    REGISTRY_PATH.write_text(json.dumps(data, indent=2))


def get_active_themes(min_strength: float = 0.55) -> List[Dict[str, Any]]:
    reg = load_registry()
    return [t for t in reg.get("themes", []) if t.get("active") and float(t.get("strength", 0)) >= min_strength]


def _theme_performance() -> Dict[str, Any]:
    try:
        from core.calibrator import load_calibration
        return load_calibration().get("theme_performance") or {}
    except Exception:
        return {}


def theme_conviction_adjustment(ticker: str, sector: str = "") -> int:
    """Bonus (+) conviction points from active themes (skips themes with poor learned WR)."""
    t = ticker.upper().strip()
    sec = sector or ""
    if not sec:
        try:
            from core.universe_builder import get_ticker_sector
            sec = get_ticker_sector(t)
        except Exception:
            sec = "Unknown"
    perf = _theme_performance()
    adj = 0
    for th in get_active_themes():
        tid = th.get("id", "")
        ps = perf.get(tid) or {}
        if ps.get("samples", 0) >= 3 and float(ps.get("win_rate", 50)) < 35:
            continue
        if sec in th.get("sectors", []) or t in [x.upper() for x in th.get("tickers", [])]:
            s = float(th.get("strength", 0.5))
            bonus = 3 if s >= 0.75 else 2 if s >= 0.6 else 1
            if ps.get("samples", 0) >= 3 and float(ps.get("win_rate", 50)) > 60:
                bonus += 1
            adj += bonus
    return min(adj, 6)


def get_ticker_themes(ticker: str, sector: str = "") -> List[str]:
    t = ticker.upper()
    sec = sector
    if not sec:
        try:
            from core.universe_builder import get_ticker_sector
            sec = get_ticker_sector(t)
        except Exception:
            sec = ""
    ids = []
    for th in get_active_themes():
        if t in [x.upper() for x in th.get("tickers", [])] or sec in th.get("sectors", []):
            ids.append(th["id"])
    return ids


def _score_theme_from_sectors(theme: Dict, sector_rankings: List[Dict]) -> float:
    """Rule-based strength from sector momentum ranks."""
    sectors = theme.get("sectors", [])
    if not sector_rankings or not sectors:
        return 0.4
    scores = []
    for r in sector_rankings:
        if r.get("sector") in sectors:
            rank = r.get("rank", 99)
            score = r.get("score", 0)
            rank_bonus = max(0, (12 - rank) / 12) * 0.4
            score_bonus = min(0.4, max(0, score) / 5)
            scores.append(0.2 + rank_bonus + score_bonus)
    return round(min(1.0, max(scores) if scores else 0.35), 2)


def _scan_headlines_for_keywords() -> Dict[str, int]:
    """Light headline scan via yfinance on theme anchor tickers."""
    hits: Dict[str, int] = {t["id"]: 0 for t in DEFAULT_THEMES}
    try:
        import yfinance as yf
        anchors = ["SPY", "NVDA", "MU", "XOM", "LLY", "JPM"]
        for sym in anchors:
            try:
                for item in (yf.Ticker(sym).news or [])[:5]:
                    title = (item.get("title") or "").lower()
                    for th in DEFAULT_THEMES:
                        if any(kw in title for kw in th.get("keywords", [])):
                            hits[th["id"]] = hits.get(th["id"], 0) + 1
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[THEME] headline scan skipped: {e}")
    return hits


def refresh_themes(use_llm: bool = False) -> Dict[str, Any]:
    """Recompute theme strength from sector rank + headline keywords."""
    from core.sector_ranker import rank_sectors

    sector_rankings = rank_sectors(force=False) or []
    headline_hits = _scan_headlines_for_keywords()
    themes_out = []

    for base in DEFAULT_THEMES:
        tid = base["id"]
        strength = _score_theme_from_sectors(base, sector_rankings)
        hits = headline_hits.get(tid, 0)
        if hits >= 2:
            strength = round(min(1.0, strength + 0.15), 2)
        elif hits == 1:
            strength = round(min(1.0, strength + 0.08), 2)

        active = strength >= 0.55
        themes_out.append({
            **base,
            "strength": strength,
            "active": active,
            "headline_hits": hits,
            "source": "rules+headlines",
        })

    if use_llm and os.environ.get("GOOGLE_API_KEY"):
        try:
            themes_out = _llm_refine_themes(themes_out, sector_rankings)
        except Exception as e:
            logger.warning(f"[THEME] LLM refine skipped: {e}")

    reg = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "themes": themes_out,
        "headline_hits": headline_hits,
        "top_sectors": [r.get("sector") for r in sector_rankings[:3]],
    }
    save_registry(reg)
    active = [t["id"] for t in themes_out if t.get("active")]
    logger.info(f"[THEME] refresh active={active}")
    return reg


def _llm_refine_themes(themes: List[Dict], sector_rankings: List[Dict]) -> List[Dict]:
    """Optional Gemini pass — adjust strength for top 3 active narratives."""
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel("gemini-2.0-flash")
    top_s = ", ".join(f"{r['sector']}({r['score']})" for r in (sector_rankings or [])[:5])
    prompt = (
        "You are a macro trading desk. Given sector momentum and theme list, "
        "return JSON array: [{\"id\":\"THEME_ID\",\"strength\":0.0-1.0,\"active\":true|false}]. "
        f"Top sectors: {top_s}. Themes: {[t['id'] for t in themes]}. "
        "Only JSON, no markdown."
    )
    raw = model.generate_content(prompt).text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    adjustments = {a["id"]: a for a in json.loads(raw.strip())}
    out = []
    for t in themes:
        adj = adjustments.get(t["id"], {})
        if adj:
            t = {**t, "strength": float(adj.get("strength", t["strength"])), "active": bool(adj.get("active", t["active"]))}
        out.append(t)
    return out


def analyze_theme_performance(closed_positions: List[Dict]) -> Dict[str, Any]:
    """Learning: win rate / avg pnl per entry theme tag."""
    buckets: Dict[str, List[float]] = {}
    for p in closed_positions:
        themes = p.get("entry_themes") or []
        pnl = float(p.get("realized_pnl", p.get("pnl_pct", 0)) or 0)
        for tid in themes:
            buckets.setdefault(tid, []).append(pnl)
    stats = {}
    for tid, pnls in buckets.items():
        if len(pnls) < 2:
            continue
        wins = sum(1 for x in pnls if x > 0)
        stats[tid] = {
            "samples": len(pnls),
            "win_rate": round(wins / len(pnls) * 100, 1),
            "avg_pnl": round(sum(pnls) / len(pnls), 3),
        }
    return stats
