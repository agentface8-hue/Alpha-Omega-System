"""
No-cost agent platform adaptation evaluator.

Compares Cursor, LangGraph, Vertex, and other platforms without external calls
or trading authority. Aggregates shadow adapter readiness from sibling modules.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List


PROTECTED_CORE = [
    "portfolio_manager",
    "signal_tracker",
    "trading_safety",
    "order_executor",
    "executor",
    "supabase_state",
]


def _env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _shadow_status(module_path: str, fn_name: str) -> Dict[str, Any]:
    try:
        import importlib

        mod = importlib.import_module(module_path)
        fn = getattr(mod, fn_name)
        return fn()
    except Exception as e:
        return {"enabled": False, "error": str(e)[:120]}


def _platform_profiles() -> List[Dict[str, Any]]:
    langgraph = _shadow_status("core.langgraph_shadow", "status")
    vertex = _shadow_status("core.vertex_research_runtime", "status")
    cursor_enabled = _env_true("CURSOR_AGENT_PLATFORM_ENABLED")

    return [
        {
            "id": "cursor",
            "name": "Cursor SDK / Automations",
            "runtime_enabled": cursor_enabled,
            "cost_guard": "no_extra_platform_cost_by_default",
            "allowed_use": "engineering_ops_only",
            "blocked_use": "direct_market_decisions_or_execution",
            "fit_score": 95,
            "verdict": "keep_as_primary_engineering_operator",
        },
        {
            "id": "langgraph",
            "name": "LangGraph",
            "runtime_enabled": bool(langgraph.get("enabled")),
            "cost_guard": "open_source_local_first",
            "allowed_use": "local_shadow_workflow_eval",
            "blocked_use": "portfolio_signal_or_execution_mutation",
            "fit_score": 90,
            "verdict": "best_first_pilot_for_trading_workflow_control",
            "shadow_status": langgraph,
        },
        {
            "id": "vertex",
            "name": "Google Vertex AI Agent Platform",
            "runtime_enabled": bool(vertex.get("enabled")),
            "cost_guard": "may_cost_money_when_enabled" if vertex.get("enabled") else "disabled_to_avoid_new_cost",
            "allowed_use": "shadow_research_eval_only",
            "blocked_use": "portfolio_signal_or_execution_mutation",
            "fit_score": 82,
            "verdict": "use_later_for_eval_if_budget_approved",
            "shadow_status": vertex,
        },
        {
            "id": "crewai",
            "name": "CrewAI",
            "runtime_enabled": False,
            "cost_guard": "not_enabled",
            "allowed_use": "benchmark_only",
            "blocked_use": "production_trading_control",
            "fit_score": 68,
            "verdict": "watch_not_first_choice",
        },
        {
            "id": "microsoft_agent_framework",
            "name": "Microsoft Agent Framework",
            "runtime_enabled": False,
            "cost_guard": "not_enabled",
            "allowed_use": "future_study_only",
            "blocked_use": "production_trading_control",
            "fit_score": 55,
            "verdict": "ignore_unless_moving_to_azure",
        },
    ]


def compare_agent_platforms() -> Dict[str, Any]:
    """Return a safe recommendation for adapting agent platforms."""
    platforms = _platform_profiles()
    runtime_enabled = [p["id"] for p in platforms if p["runtime_enabled"]]

    return {
        "status": "shadow_adapters_ready",
        "no_cost_default": not any(p["id"] == "vertex" and p["runtime_enabled"] for p in platforms),
        "observer_only": True,
        "trading_mutation_allowed": False,
        "external_calls_made": False,
        "protected_core": PROTECTED_CORE,
        "runtime_enabled": runtime_enabled,
        "recommended_architecture": [
            {
                "platform": "cursor",
                "role": "engineering_operator",
                "reason": "Manages code, tests, docs, and deployment without moving trading logic.",
            },
            {
                "platform": "langgraph",
                "role": "workflow_control_candidate",
                "reason": "Local checkpoints and replay around read-only research flows.",
            },
            {
                "platform": "vertex",
                "role": "model_eval_and_research_runtime",
                "reason": "Optional shadow runtime for AI Radar, Dreaming Agent, and model evals.",
            },
            {
                "platform": "alpha_omega_core",
                "role": "source_of_truth",
                "reason": "Portfolio, safety, execution, and Supabase state remain authoritative.",
            },
        ],
        "pilot_sequence": [
            "Use /api/langgraph-shadow/run for read-only research replay.",
            "Use /api/vertex-research/shadow for dream/radar/eval shadows only.",
            "Compare shadow output against existing modules before any adoption.",
            "Keep portfolio, signals, and execution inside Alpha-Omega core.",
        ],
        "platforms": platforms,
    }


def status() -> Dict[str, Any]:
    """Small status shape for health panels."""
    report = compare_agent_platforms()
    return {
        "status": report["status"],
        "no_cost_default": report["no_cost_default"],
        "observer_only": report["observer_only"],
        "trading_mutation_allowed": report["trading_mutation_allowed"],
        "runtime_enabled": report["runtime_enabled"],
        "next_step": report["pilot_sequence"][0],
        "langgraph_shadow": _shadow_status("core.langgraph_shadow", "status"),
        "vertex_research": _shadow_status("core.vertex_research_runtime", "status"),
    }
