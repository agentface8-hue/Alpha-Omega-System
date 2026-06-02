"""
Smoke tests: verify all recent changes are active.
- Attribution observe-only guardrail
- Regime persisted at decision time (ledger)
- Backend uses run_cycle_v2 (council + ledger + regime)
Run: python -m pytest tests/test_app_integration.py -v
Or:  python tests/test_app_integration.py
"""
import os
import sys

# Project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_attribution_observe_only():
    """Attribution must be observe-only; must not affect decisions."""
    from core.attribution import ATTRIBUTION_MODE
    assert ATTRIBUTION_MODE == "observe_only", "Attribution must be observe_only"


def test_ledger_persists_regime():
    """Decision ledger accepts and returns regime (persisted at decision time)."""
    from core.decision_ledger import record_decision, get_decision_by_id, _ensure_db
    _ensure_db()
    decision_data = {
        "symbol": "TEST",
        "recommendation": "HOLD",
        "confidence": 0.5,
        "regime": "RISK_ON",
        "agent_votes": {},
        "vetoed": False,
    }
    did = record_decision(decision_data)
    assert did > 0
    row = get_decision_by_id(did)
    assert row is not None
    assert row.get("regime") == "RISK_ON", "Regime must be persisted and readable"


def test_attribution_reads_regime_from_decision():
    """Attribution uses decision.regime, not agent_votes."""
    from core.attribution import _get_regime_from_decision
    assert _get_regime_from_decision({"regime": "CRISIS"}) == "CRISIS"
    assert _get_regime_from_decision({"regime": ""}) == "UNKNOWN"
    assert _get_regime_from_decision({}) == "UNKNOWN"


def test_orchestrator_has_run_cycle_v2():
    """Orchestrator exposes run_cycle_v2 (council + ledger + regime)."""
    from core.orchestrator import Orchestrator
    o = Orchestrator()
    assert hasattr(o, "run_cycle_v2")
    assert callable(getattr(o, "run_cycle_v2"))


def test_timeout_helper_returns_without_waiting_for_hung_worker():
    """Timed fallback must return quickly even if the worker keeps sleeping."""
    import time
    from core.timeout_utils import run_with_timeout

    started = time.time()
    result = run_with_timeout(lambda: time.sleep(2) or "late", timeout_s=0.1, fallback="fallback")
    elapsed = time.time() - started

    assert result == "fallback"
    assert elapsed < 0.8


def test_async_timeout_helper_uses_fresh_executor():
    """Async timeout must not depend on the loop's possibly saturated default executor."""
    import asyncio
    import time
    from core.timeout_utils import run_async_with_timeout

    async def run():
        started = time.time()
        result = await run_async_with_timeout(lambda: time.sleep(2) or "late", timeout_s=0.1, fallback="fallback")
        return result, time.time() - started

    result, elapsed = asyncio.run(run())
    assert result == "fallback"
    assert elapsed < 0.8


def test_decision_audit_json_roundtrip():
    """Decision audit stores compact replay records and can query by id/symbol."""
    import tempfile
    from pathlib import Path
    from core import decision_audit

    old_file = decision_audit.AUDIT_FILE
    old_remote = decision_audit._REMOTE_DISABLED
    with tempfile.TemporaryDirectory() as td:
        decision_audit.AUDIT_FILE = Path(td) / "audit.json"
        decision_audit._REMOTE_DISABLED = True
        rec = decision_audit.record_audit(
            event_type="test_decision",
            symbol="AMZN",
            source="unit_test",
            action="BUY",
            verdict="BUY",
            confidence=0.66,
            inputs={"ticker": "AMZN"},
            agent_outputs={"executioner": "BUY cautiously"},
            market_snapshot={"regime": "Trending Bull"},
            metadata={"reason": "roundtrip"},
        )
        loaded = decision_audit.get_audit(rec["id"])
        by_symbol = decision_audit.get_audits_for_symbol("amzn")

        assert loaded["id"] == rec["id"]
        assert loaded["symbol"] == "AMZN"
        assert loaded["inputs"]["ticker"] == "AMZN"
        assert by_symbol and by_symbol[0]["id"] == rec["id"]

    decision_audit.AUDIT_FILE = old_file
    decision_audit._REMOTE_DISABLED = old_remote


def test_datahub_reuses_cached_topic():
    """DataHub-lite returns cache metadata and avoids duplicate fetches."""
    import tempfile
    from pathlib import Path
    from core import datahub

    calls = {"n": 0}

    def fetcher():
        calls["n"] += 1
        return {"value": calls["n"]}

    with tempfile.TemporaryDirectory() as td:
        datahub._MEMORY.clear()
        cache_path = Path(td) / "topic.json"
        first = datahub.get_topic("unit:datahub", fetcher, 60, cache_path=cache_path)
        second = datahub.get_topic("unit:datahub", fetcher, 60, cache_path=cache_path)

        assert calls["n"] == 1
        assert first["cached"] is False
        assert second["cached"] is True
        assert second["source"] == "memory"
        assert second["data"]["value"] == 1


def test_trading_safety_blocks_global_halt():
    """Safety layer blocks new trades while global halt is active."""
    import tempfile
    from pathlib import Path
    from core import trading_safety

    old_file = trading_safety.SAFETY_FILE
    with tempfile.TemporaryDirectory() as td:
        trading_safety.SAFETY_FILE = Path(td) / "safety.json"
        trading_safety.halt_all("unit test halt")
        check = trading_safety.check_trade_allowed(ticker="NVDA")
        assert check["allowed"] is False
        assert check["code"] == "GLOBAL_HALT"
        trading_safety.resume()
        assert trading_safety.check_trade_allowed(ticker="NVDA")["allowed"] is True

    trading_safety.SAFETY_FILE = old_file


def test_ai_radar_scores_and_persists_findings():
    """AI Radar ranks relevant discoveries and stores an observer-only brief."""
    import tempfile
    from pathlib import Path
    from core import ai_radar

    old_file = ai_radar.RADAR_FILE
    with tempfile.TemporaryDirectory() as td:
        ai_radar.RADAR_FILE = Path(td) / "radar.json"
        finding = ai_radar.make_finding(
            source="unit",
            title="New agent framework for financial research",
            url="https://example.com/agent",
            summary="Adds autonomous agent research workflows for market analysis.",
            tags=["agents", "financial research"],
        )
        assert finding["relevance_score"] >= 70
        assert finding["status"] == "watch"

        brief = ai_radar.save_radar_brief([finding], source="unit")
        recent = ai_radar.load_radar_log(limit=1)

        assert brief["count"] == 1
        assert recent[0]["top_findings"][0]["title"] == finding["title"]
        assert recent[0]["top_findings"][0]["recommended_action"] in ("watch", "test", "adopt", "ignore")

    ai_radar.RADAR_FILE = old_file


def test_market_flow_scores_accumulation_distribution():
    """Market Flow Agent converts existing OHLCV fields into an additive flow signal."""
    from core.market_flow_agent import analyze_flow_snapshot

    accumulation = analyze_flow_snapshot({
        "symbol": "OKTA",
        "vol_ratio": 2.2,
        "vol_direction": "ACCUMULATION",
        "body_pct": 0.62,
        "bull_body": True,
        "tas": "4/4",
        "rsi": 58,
    })
    distribution = analyze_flow_snapshot({
        "symbol": "D",
        "vol_ratio": 2.4,
        "vol_direction": "DISTRIBUTION",
        "body_pct": 0.7,
        "bull_body": False,
        "tas": "1/4",
        "rsi": 42,
    })

    assert accumulation["flow_signal"] == "ACCUMULATION"
    assert accumulation["flow_score"] > distribution["flow_score"]
    assert distribution["flow_signal"] == "DISTRIBUTION"
    assert "market_flow" in accumulation["summary"].lower()


def test_decision_ledger_has_outcome_helpers():
    """Ledger has update_decision_outcomes and get_decisions_pending_outcomes for attribution job."""
    from core.decision_ledger import update_decision_outcomes, get_decisions_pending_outcomes
    assert callable(update_decision_outcomes)
    assert callable(get_decisions_pending_outcomes)
    # Should not raise
    pending = get_decisions_pending_outcomes(7, limit=1)
    assert isinstance(pending, list)


def test_api_root_if_running():
    """If backend is running on 8000, GET / returns status."""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = resp.read().decode()
            assert "status" in data.lower() or "online" in data.lower()
    except (urllib.error.URLError, OSError):
        pass  # Backend not running; skip


if __name__ == "__main__":
    import subprocess
    r = subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(r.returncode)
