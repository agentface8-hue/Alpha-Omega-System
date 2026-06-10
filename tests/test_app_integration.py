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
        assert recent[0]["top_findings"][0]["recommended_action"] in ("watch", "test", "benchmark", "study", "adopt", "ignore")

    ai_radar.RADAR_FILE = old_file


def test_ai_radar_compares_financialdata_against_alpha_omega_stack():
    """AI Radar should compare candidates before recommending any adoption."""
    from core import ai_radar

    finding = ai_radar.make_finding(
        source="Hacker News AI",
        title="Show HN: Build AI Trading Agents in Cursor/Claude with an MCP Server",
        url="https://financialdata.net/mcp-server",
        summary=(
            "FinancialData.Net MCP offers real-time stock prices, fundamentals, "
            "institutional trading insights, income statements, ETF data, and MCP tools."
        ),
        tags=["mcp", "financial", "institutional trading"],
    )

    comparison = finding["alpha_omega_comparison"]
    assert comparison["decision"] == "benchmark"
    assert comparison["overlap"] == "partial"
    assert "data breadth" in " ".join(comparison["potential_advantages"]).lower()
    assert "professional" in " ".join(comparison["risks"]).lower()
    assert finding["recommended_action"] == "benchmark"


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


def test_thinking_machines_status_does_not_expose_secret(monkeypatch):
    """Thinking Machines adapter reports readiness without leaking API keys."""
    from core import thinking_machines_benchmark as tml

    monkeypatch.setenv("TML_API_KEY", "secret-value")
    monkeypatch.delenv("TML_MODEL", raising=False)
    monkeypatch.delenv("TML_BASE_MODEL", raising=False)
    status = tml.status()

    assert status["observer_only"] is True
    assert status["api_key_present"] is True
    assert status["model_present"] is False
    assert status["base_model_present"] is True
    assert status["base_model"] == "moonshotai/Kimi-K2.6"
    assert status["configured"] is True
    assert status["base_url"].endswith("/oai/api/v1")
    assert "moonshotai/Kimi-K2.6" in status["model_note"]
    assert "secret-value" not in str(status)


def test_thinking_machines_status_accepts_base_model(monkeypatch):
    """Tinker can benchmark from a base model without creating a checkpoint."""
    from core import thinking_machines_benchmark as tml

    monkeypatch.setenv("TML_API_KEY", "secret-value")
    monkeypatch.setenv("TML_BASE_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
    monkeypatch.delenv("TML_MODEL", raising=False)
    status = tml.status()

    assert status["configured"] is True
    assert status["base_model_present"] is True
    assert status["base_model"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert "secret-value" not in str(status)


def test_thinking_machines_benchmark_compares_outputs_observer_only():
    """Benchmark runner compares TML output against Alpha-Omega without trade actions."""
    from core.thinking_machines_benchmark import run_benchmark

    def alpha_runner(symbol):
        return {
            "symbol": symbol,
            "decision": "HOLD",
            "analysis": "Risk: earnings soon. Entry needs confirmation. Stop-loss below support.",
            "confidence": 0.55,
        }

    def tml_runner(symbol, baseline):
        return {
            "text": "Risk: earnings soon. Entry needs confirmation. Stop-loss below support. Also watch volume.",
            "model": "unit-tinker",
            "latency_ms": 12,
        }

    result = run_benchmark(["GOOGL"], alpha_runner=alpha_runner, tml_runner=tml_runner)

    assert result["observer_only"] is True
    assert result["symbols"] == ["GOOGL"]
    assert result["summary"]["count"] == 1
    assert result["summary"]["avg_tml_score"] > 0
    assert result["results"][0]["trade_action"] == "none"
    assert result["results"][0]["tml"]["model"] == "unit-tinker"


def test_thinking_machines_async_runner_works_inside_running_loop():
    """SDK coroutine runner works when called from an already-running FastAPI loop."""
    import asyncio

    from core.thinking_machines_benchmark import _run_async_tinker

    async def sample():
        return {"ok": True}

    async def outer():
        return _run_async_tinker(sample, timeout_s=2)

    assert asyncio.run(outer()) == {"ok": True}


def test_agent_platform_evaluator_is_no_cost_and_observer_only(monkeypatch):
    """Agent platform adaptation must not create paid calls or trading authority by default."""
    monkeypatch.delenv("VERTEX_SHADOW_ENABLED", raising=False)
    monkeypatch.delenv("LANGGRAPH_SHADOW_ENABLED", raising=False)
    monkeypatch.delenv("CURSOR_AGENT_PLATFORM_ENABLED", raising=False)

    from core.agent_platform_evaluator import compare_agent_platforms

    report = compare_agent_platforms()

    assert report["no_cost_default"] is True
    assert report["observer_only"] is True
    assert report["trading_mutation_allowed"] is False
    assert report["recommended_architecture"][0]["platform"] == "cursor"
    assert report["recommended_architecture"][1]["platform"] == "langgraph"
    assert report["recommended_architecture"][2]["platform"] == "vertex"
    assert "portfolio_manager" in report["protected_core"]


def test_langgraph_shadow_is_disabled_by_default(monkeypatch):
    """LangGraph shadow must stay off unless explicitly enabled."""
    monkeypatch.delenv("LANGGRAPH_SHADOW_ENABLED", raising=False)

    from core.langgraph_shadow import status

    cfg = status()
    assert cfg["observer_only"] is True
    assert cfg["trading_mutation_allowed"] is False
    assert cfg["enabled"] is False


def test_langgraph_shadow_runs_read_only_research_when_enabled(monkeypatch):
    """LangGraph shadow reuses existing scoring stack without portfolio mutation."""
    monkeypatch.setenv("LANGGRAPH_SHADOW_ENABLED", "true")

    from core.langgraph_shadow import run_shadow_research

    def fake_regime():
        return {"regime": "RISK_ON"}

    def fake_data(symbol):
        return {"symbol": symbol, "close": 100.0}

    def fake_score(data, regime):
        return {"symbol": data["symbol"], "decision": "WATCH", "confidence": 0.61}

    monkeypatch.setattr("core.market_data.fetch_market_regime", fake_regime)
    monkeypatch.setattr("core.market_data.fetch_ticker_data", fake_data)
    monkeypatch.setattr("core.conviction_engine.score_ticker", fake_score)

    result = run_shadow_research("NVDA")

    assert result["observer_only"] is True
    assert result["trade_action"] == "none"
    assert result["symbol"] == "NVDA"
    assert result["checkpoints"]
    assert result["score"]["decision"] == "WATCH"


def test_vertex_research_runtime_is_disabled_by_default(monkeypatch):
    """Vertex research runtime must not call paid APIs unless explicitly enabled."""
    monkeypatch.delenv("VERTEX_SHADOW_ENABLED", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    from core.vertex_research_runtime import status

    cfg = status()
    assert cfg["observer_only"] is True
    assert cfg["trading_mutation_allowed"] is False
    assert cfg["enabled"] is False
    assert cfg["external_calls_made"] is False


def test_vertex_research_shadow_dream_does_not_save_dream(monkeypatch):
    """Vertex dream shadow builds context only; it must not duplicate dream persistence."""
    monkeypatch.setenv("VERTEX_SHADOW_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "alpha-omega-test")

    from core import vertex_research_runtime as vr

    monkeypatch.setattr(vr, "_vertex_generate", lambda prompt: {"text": "shadow-only", "provider": "vertex_stub"})
    monkeypatch.setattr(
        "core.dreaming_agent._quick_scan_top_tickers",
        lambda tickers: [{"ticker": "NVDA", "conviction": 80}],
    )
    monkeypatch.setattr(
        "core.dreaming_agent._build_dream_prompt",
        lambda market_ctx, scan_results: "dream prompt",
    )

    saved = {"called": False}

    def _block_save(_dream):
        saved["called"] = True
        return True

    monkeypatch.setattr("core.dreaming_agent._save_dream", _block_save)

    result = vr.run_shadow_task("dream", force=True)

    assert result["observer_only"] is True
    assert result["trade_action"] == "none"
    assert saved["called"] is False
    assert result["task"] == "dream"


def test_platform_shadow_api_routes_are_read_only():
    """Backend exposes read-only platform/shadow endpoints."""
    from backend.main import app

    routes = {(tuple(sorted(route.methods)), route.path) for route in app.routes if hasattr(route, "methods")}

    assert (("GET",), "/api/agent-platforms/compare") in routes
    assert (("GET",), "/api/agent-platforms/status") in routes
    assert (("GET",), "/api/langgraph-shadow/status") in routes
    assert (("POST",), "/api/langgraph-shadow/run") in routes
    assert (("GET",), "/api/vertex-research/status") in routes
    assert (("POST",), "/api/vertex-research/shadow") in routes


def test_decision_ledger_has_outcome_helpers():
    """Ledger has update_decision_outcomes and get_decisions_pending_outcomes for attribution job."""
    from core.decision_ledger import update_decision_outcomes, get_decisions_pending_outcomes
    assert callable(update_decision_outcomes)
    assert callable(get_decisions_pending_outcomes)
    # Should not raise
    pending = get_decisions_pending_outcomes(7, limit=1)
    assert isinstance(pending, list)


def test_trend_exit_policy_hot_sector_wider_cap(monkeypatch):
    """HOT + Trending Bull allows higher sector concentration."""
    from core import trend_exit_policy as tep

    monkeypatch.setattr(
        tep,
        "_sector_bias",
        lambda sector: "HOT" if sector == "Technology" else "NEUTRAL",
    )
    assert tep.sector_cap_pct("Technology", "Trending Bull") == 40.0
    assert tep.sector_cap_pct("Energy", "Trending Bull") == 25.0
    assert tep.max_sector_slots(25000, 3340, "Technology", "Trending Bull") >= 3


def test_trend_exit_policy_delays_hot_breakeven_until_tp1(monkeypatch):
    """HOT trend should not move SL to breakeven before TP1."""
    from core import trend_exit_policy as tep

    monkeypatch.setattr(tep, "_sector_bias", lambda sector: "HOT")
    sl, note = tep.portfolio_tsl_candidate(
        entry=100.0, atr=10.0, multiple=1.5, current_sl=90.0,
        tp1_hit=False, sector="Technology", regime="Trending Bull",
    )
    assert sl is None
    sl, note = tep.portfolio_tsl_candidate(
        entry=100.0, atr=10.0, multiple=1.5, current_sl=90.0,
        tp1_hit=True, sector="Technology", regime="Trending Bull",
    )
    assert sl == 100.0
    assert "TP1" in (note or "")


def test_tinker_default_model_not_retiring():
    from core.thinking_machines_benchmark import DEFAULT_BASE_MODEL, RETIRING_MODELS, status

    assert DEFAULT_BASE_MODEL not in RETIRING_MODELS
    cfg = status()
    assert cfg["base_model"] == "moonshotai/Kimi-K2.6"
    assert cfg.get("model_retiring_june_12") is False


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
