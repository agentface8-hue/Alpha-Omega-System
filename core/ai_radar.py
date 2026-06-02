"""
ai_radar.py - observer-only scout for useful AI/platform upgrades.

It does not install packages, change code, or alter trading behavior. It only
collects public-source candidates, scores relevance to Alpha-Omega, and stores
a compact brief for review.
"""
from __future__ import annotations

import datetime
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

RADAR_FILE = Path(__file__).parent.parent / "signals" / "ai_radar_log.json"
MAX_BRIEFS = 40

WATCH_SOURCES = [
    {
        "name": "GitHub agentic AI",
        "url": "https://api.github.com/search/repositories?q=agentic+ai+created:%3E2026-05-01&sort=stars&order=desc&per_page=8",
        "kind": "github",
    },
    {
        "name": "GitHub financial AI",
        "url": "https://api.github.com/search/repositories?q=financial+ai+agent+created:%3E2026-05-01&sort=stars&order=desc&per_page=8",
        "kind": "github",
    },
    {
        "name": "Hacker News AI",
        "url": "https://hn.algolia.com/api/v1/search?query=AI%20agent%20trading%20finance&tags=story&hitsPerPage=8",
        "kind": "hn",
    },
]

HIGH_VALUE_TERMS = {
    "agent": 15,
    "agents": 15,
    "mcp": 14,
    "research": 12,
    "financial": 14,
    "finance": 14,
    "trading": 16,
    "backtest": 14,
    "risk": 12,
    "eval": 10,
    "benchmark": 10,
    "cursor": 8,
    "claude": 8,
    "openai": 7,
    "gemini": 7,
    "workflow": 6,
}
RISK_TERMS = {"crypto airdrop", "get rich", "pump", "meme", "unlimited", "jailbreak"}


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


def _score_text(text: str) -> int:
    lower = text.lower()
    score = 20
    for term, points in HIGH_VALUE_TERMS.items():
        if term in lower:
            score += points
    for term in RISK_TERMS:
        if term in lower:
            score -= 20
    return max(0, min(score, 100))


def _recommended_action(score: int) -> str:
    if score >= 85:
        return "test"
    if score >= 65:
        return "watch"
    if score >= 40:
        return "watch"
    return "ignore"


def _compare_to_alpha_omega_stack(
    *,
    title: str,
    url: str,
    summary: str = "",
    tags: Optional[List[str]] = None,
    score: int = 0,
) -> Dict[str, Any]:
    """Explain whether a candidate is duplicate, additive, or worth benchmarking."""
    text = " ".join([title or "", url or "", summary or "", " ".join(tags or [])]).lower()

    comparison = {
        "overlap": "unknown",
        "decision": "watch",
        "local_baseline": [
            "Alpha-Omega already has council agents, scanner, signal tracker, portfolio manager, safety gates, audit trail, learning loop, and paper execution.",
        ],
        "potential_advantages": [],
        "risks": [],
        "benchmark_plan": [],
    }

    is_financialdata = "financialdata.net" in text or "financialdata" in text
    is_market_data = any(term in text for term in [
        "stock price", "stock prices", "latest prices", "real-time", "realtime",
        "fundamental", "income statement", "balance sheet", "cash flow",
        "institutional", "insider", "etf", "mcp",
    ])
    is_agent_framework = any(term in text for term in ["multi-agent", "agent framework", "agents", "orchestration"])

    if is_financialdata or is_market_data:
        comparison["overlap"] = "partial"
        comparison["decision"] = "benchmark" if score >= 75 else "watch"
        comparison["local_baseline"].append(
            "Current market data is mainly yfinance/Finnhub/Alpha Vantage-style coverage with internal OHLCV-derived scoring."
        )
        comparison["potential_advantages"].extend([
            "May improve data breadth with fundamentals, statements, ETF data, insider/institutional holdings, and international coverage.",
            "MCP interface could let research agents request structured financial data without custom endpoint code.",
        ])
        comparison["risks"].extend([
            "FinancialData MCP requires a Professional or Enterprise subscription/API key before live verification.",
            "Provider quality, latency, coverage, rate limits, and cost must be benchmarked against existing sources before adoption.",
        ])
        comparison["benchmark_plan"].extend([
            "Run both providers on the same ticker set and timestamp.",
            "Compare price freshness, OHLCV completeness, fundamentals coverage, response time, failure rate, and cost.",
            "Keep results observer-only until the benchmark clearly beats the current source.",
        ])
    elif is_agent_framework:
        comparison["overlap"] = "high"
        comparison["decision"] = "study"
        comparison["potential_advantages"].append(
            "May contain useful orchestration or report-quality ideas."
        )
        comparison["risks"].append(
            "High duplication risk because Alpha-Omega already has specialized agents and trading guardrails."
        )
        comparison["benchmark_plan"].append(
            "Compare report quality on the same tickers before adopting any pattern."
        )
    elif score >= 85:
        comparison["overlap"] = "unknown"
        comparison["decision"] = "test"
        comparison["benchmark_plan"].append(
            "Do a sandbox review before any production change."
        )

    return comparison


def make_finding(
    *,
    source: str,
    title: str,
    url: str,
    summary: str = "",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    text = " ".join([title or "", summary or "", " ".join(tags or [])])
    score = _score_text(text)
    comparison = _compare_to_alpha_omega_stack(
        title=title,
        url=url,
        summary=summary,
        tags=tags,
        score=score,
    )
    action = _recommended_action(score)
    if comparison.get("decision") in {"benchmark", "study"}:
        action = comparison["decision"]
    return {
        "id": re.sub(r"[^a-zA-Z0-9]+", "-", f"{source}-{title}")[:90].strip("-").lower(),
        "source": source,
        "title": (title or "Untitled")[:180],
        "url": url,
        "summary": (summary or "")[:500],
        "tags": tags or [],
        "relevance_score": score,
        "recommended_action": action,
        "status": "watch" if score >= 40 else "ignore",
        "alpha_omega_comparison": comparison,
        "captured_at": _now(),
    }


def _read_json() -> List[Dict[str, Any]]:
    if not RADAR_FILE.exists():
        return []
    try:
        data = json.loads(RADAR_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_json(briefs: List[Dict[str, Any]]) -> None:
    RADAR_FILE.parent.mkdir(exist_ok=True)
    RADAR_FILE.write_text(json.dumps(briefs[:MAX_BRIEFS], indent=2, default=str))


def save_radar_brief(findings: List[Dict[str, Any]], *, source: str = "manual") -> Dict[str, Any]:
    ranked = sorted(findings, key=lambda f: f.get("relevance_score", 0), reverse=True)
    brief = {
        "ts": _now(),
        "source": source,
        "count": len(ranked),
        "top_findings": ranked[:10],
        "observer_only": True,
        "summary": _summarize(ranked),
    }
    briefs = [brief] + _read_json()
    _write_json(briefs)
    return brief


def load_radar_log(limit: int = 10) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 10), 40))
    return _read_json()[:limit]


def _summarize(findings: List[Dict[str, Any]]) -> str:
    if not findings:
        return "No relevant AI/platform upgrades found in this run."
    top = findings[0]
    return f"Top candidate: {top['title']} ({top['relevance_score']}/100) — action: {top['recommended_action']}."


def _fetch_json(url: str, timeout: int = 12) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "Alpha-Omega-AI-Radar/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def _findings_from_github(source: Dict[str, str]) -> List[Dict[str, Any]]:
    data = _fetch_json(source["url"])
    findings = []
    for item in (data.get("items") or [])[:8]:
        findings.append(make_finding(
            source=source["name"],
            title=item.get("full_name") or item.get("name") or "GitHub repo",
            url=item.get("html_url", ""),
            summary=item.get("description") or "",
            tags=["github", "stars:" + str(item.get("stargazers_count", 0))],
        ))
    return findings


def _findings_from_hn(source: Dict[str, str]) -> List[Dict[str, Any]]:
    data = _fetch_json(source["url"])
    findings = []
    for item in (data.get("hits") or [])[:8]:
        url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}"
        findings.append(make_finding(
            source=source["name"],
            title=item.get("title") or "HN story",
            url=url,
            summary=item.get("story_text") or "",
            tags=["hn", "points:" + str(item.get("points", 0))],
        ))
    return findings


def run_radar_cycle(*, force: bool = False, sources: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Collect and score public AI/platform updates. Observer-only."""
    findings: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for source in (sources or WATCH_SOURCES):
        try:
            if source.get("kind") == "github":
                findings.extend(_findings_from_github(source))
            elif source.get("kind") == "hn":
                findings.extend(_findings_from_hn(source))
        except Exception as e:
            errors.append({"source": source.get("name", "?"), "error": str(e)[:180]})

    # De-dupe by URL/title.
    seen = set()
    deduped = []
    for f in findings:
        key = f.get("url") or f.get("title")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)

    brief = save_radar_brief(deduped, source="ai_radar")
    brief["errors"] = errors
    return brief
