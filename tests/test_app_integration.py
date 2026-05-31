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
