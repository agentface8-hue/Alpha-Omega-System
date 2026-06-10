"""
thinking_machines_benchmark.py - observer-only Tinker/Thinking Machines benchmark.

This module never opens trades, changes portfolio state, or affects execution gates.
It compares Thinking Machines output against Alpha-Omega's current analysis so we can
decide whether the provider is worth promoting later.
"""
from __future__ import annotations

import datetime
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"
DEFAULT_MODEL = ""
DEFAULT_BASE_MODEL = "moonshotai/Kimi-K2.6"

# Retiring 2026-06-12 per Thinking Machines email — switch before that date.
RETIRING_MODELS = {
    "moonshotai/Kimi-K2-Thinking",
    "Kimi-K2-Thinking",
    "Qwen/Qwen3-4B-Instruct-2507",
    "Qwen/Qwen3-8B-Base",
    "Qwen/Qwen3-30B-A3B",
    "Qwen/Qwen3-30B-A3B-Base",
    "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "Qwen/Qwen3-32B",
    "meta-llama/Llama-3.1-8B",
    "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Llama-3.1-70B",
    "meta-llama/Llama-3.3-70B-Instruct",
}

RECOMMENDED_REPLACEMENTS = {
    "moonshotai/Kimi-K2-Thinking": "moonshotai/Kimi-K2.6",
    "Kimi-K2-Thinking": "moonshotai/Kimi-K2.6",
    "Qwen/Qwen3-4B-Instruct-2507": "Qwen/Qwen3.5-4B",
    "Qwen/Qwen3-8B-Base": "Qwen/Qwen3-8B",
    "Qwen/Qwen3-30B-A3B": "Qwen/Qwen3.5-35B-A3B-Base",
    "Qwen/Qwen3-30B-A3B-Base": "Qwen/Qwen3.5-35B-A3B-Base",
    "Qwen/Qwen3-30B-A3B-Instruct-2507": "Qwen/Qwen3.5-35B-A3B",
    "Qwen/Qwen3-32B": "Qwen/Qwen3.5-27B",
}
MAX_SYMBOLS = 10


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def status() -> Dict[str, Any]:
    """Return adapter readiness without exposing any secret value."""
    key_present = bool(_env("TML_API_KEY") or _env("TINKER_API_KEY"))
    model = _env("TML_MODEL") or _env("TINKER_MODEL") or DEFAULT_MODEL
    base_model = _env("TML_BASE_MODEL") or _env("TINKER_BASE_MODEL") or DEFAULT_BASE_MODEL
    base_url = _env("TML_BASE_URL") or _env("TINKER_BASE_URL") or DEFAULT_BASE_URL
    has_model_target = bool(model or base_model)
    retiring = base_model in RETIRING_MODELS or model in RETIRING_MODELS
    replacement = RECOMMENDED_REPLACEMENTS.get(base_model) or RECOMMENDED_REPLACEMENTS.get(model)
    return {
        "provider": "thinking_machines_tinker",
        "observer_only": True,
        "api_key_present": key_present,
        "model_present": bool(model),
        "base_model_present": bool(base_model),
        "configured": bool(key_present and has_model_target),
        "base_url": base_url,
        "model": model if model else None,
        "base_model": base_model if base_model else None,
        "model_retiring_june_12": retiring,
        "recommended_replacement": replacement,
        "missing": [
            name for name, ok in (
                ("TML_API_KEY", key_present),
                ("TML_MODEL or TML_BASE_MODEL", has_model_target),
            )
            if not ok
        ],
        "model_note": (
            "Use TML_BASE_MODEL for direct SDK sampling. Default benchmark model is moonshotai/Kimi-K2.6. "
            "Several older models retire 2026-06-12 — see model_retiring_june_12 and recommended_replacement. "
            "Use TML_MODEL only for a Tinker sampler checkpoint path such as tinker://.../sampler_weights/..."
        ),
        "allowed_uses": [
            "council challenger",
            "signal quality benchmark",
            "outcome lesson comparison",
            "AI Radar evaluator",
            "vision/chart sandbox if model supports images",
        ],
        "blocked_uses": [
            "live execution",
            "autopilot decisions",
            "portfolio mutation",
            "threshold changes",
        ],
    }


def _baseline_alpha_omega(symbol: str) -> Dict[str, Any]:
    """Use the existing local data/scoring stack as a cheap baseline."""
    from core.conviction_engine import score_ticker
    from core.market_data import fetch_market_regime, fetch_ticker_data

    data = fetch_ticker_data(symbol)
    if data.get("error"):
        return {"symbol": symbol, "error": data.get("error"), "analysis": ""}
    regime = fetch_market_regime()
    scored = score_ticker(data, regime)
    return {
        "symbol": symbol.upper(),
        "decision": scored.get("decision") or scored.get("recommendation") or "UNKNOWN",
        "confidence": scored.get("confidence") or scored.get("score") or scored.get("conviction_score"),
        "analysis": str(scored)[:2000],
    }


def _build_prompt(symbol: str, baseline: Dict[str, Any]) -> str:
    return (
        "You are an observer-only benchmark analyst for Alpha-Omega. "
        "Do not recommend trade execution. Compare the existing Alpha-Omega output, "
        "identify missing risks, missing evidence, and whether the thesis quality is strong.\n\n"
        f"Ticker: {symbol.upper()}\n"
        f"Alpha-Omega baseline:\n{baseline}\n\n"
        "Return concise sections: agreement, missing risks, data gaps, verdict_quality, and confidence."
    )


def _call_tinker(symbol: str, baseline: Dict[str, Any], timeout_s: int = 35) -> Dict[str, Any]:
    cfg = status()
    if not cfg["configured"]:
        return {
            "ok": False,
            "error": "Thinking Machines not configured. Set TML_API_KEY and TML_BASE_MODEL or TML_MODEL.",
            "model": cfg.get("model"),
            "text": "",
            "latency_ms": 0,
        }

    if cfg.get("base_model") and not cfg.get("model"):
        return _call_tinker_sdk(symbol, baseline, timeout_s=timeout_s)

    key = _env("TML_API_KEY") or _env("TINKER_API_KEY")
    base_url = str(cfg["base_url"]).rstrip("/")
    model = str(cfg["model"])
    prompt = _build_prompt(symbol, baseline)
    started = time.time()
    response = requests.post(
        f"{base_url}/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "prompt": prompt,
            "max_tokens": 700,
            "temperature": 0.1,
        },
        timeout=timeout_s,
    )
    latency_ms = int((time.time() - started) * 1000)
    if response.status_code >= 400:
        return {
            "ok": False,
            "error": f"HTTP {response.status_code}: {response.text[:180]}",
            "model": model,
            "text": "",
            "latency_ms": latency_ms,
        }
    data = response.json()
    choices = data.get("choices") or []
    text = ""
    if choices:
        text = choices[0].get("text") or choices[0].get("message", {}).get("content") or ""
    return {"ok": True, "error": "", "model": model, "text": text[:4000], "latency_ms": latency_ms}


def _call_tinker_sdk(symbol: str, baseline: Dict[str, Any], timeout_s: int = 35) -> Dict[str, Any]:
    """Direct low-throughput SDK sampling from a base model; no training/checkpoint needed."""
    import asyncio

    async def _run() -> Dict[str, Any]:
        import tinker
        from tinker import types

        if _env("TML_API_KEY") and not _env("TINKER_API_KEY"):
            os.environ["TINKER_API_KEY"] = _env("TML_API_KEY")

        cfg = status()
        base_model = str(cfg["base_model"])
        prompt = _build_prompt(symbol, baseline)
        started = time.time()
        service_client = tinker.ServiceClient()
        sampling_client = await service_client.create_sampling_client_async(base_model=base_model)
        tokenizer = sampling_client.get_tokenizer()
        model_input = types.ModelInput.from_ints(tokenizer.encode(prompt))
        result = await sampling_client.sample_async(
            prompt=model_input,
            sampling_params=types.SamplingParams(max_tokens=400, temperature=0.1, stop=["\n\n\n"]),
            num_samples=1,
        )
        latency_ms = int((time.time() - started) * 1000)
        tokens = result.sequences[0].tokens if result.sequences else []
        return {
            "ok": True,
            "error": "",
            "model": base_model,
            "text": tokenizer.decode(tokens)[:4000],
            "latency_ms": latency_ms,
        }

    try:
        return _run_async_tinker(_run, timeout_s=timeout_s)
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)[:220],
            "model": status().get("base_model"),
            "text": "",
            "latency_ms": 0,
        }


def _run_async_tinker(async_fn: Callable[[], Any], timeout_s: int) -> Any:
    """Run Tinker's async SDK from sync code, including inside FastAPI's event loop."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_fn())

    # FastAPI endpoints already run in an event loop; run the SDK coroutine in
    # a short-lived worker thread so asyncio.run owns its own loop.
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(async_fn()))
        return future.result(timeout=timeout_s + 5)


def _score_tml_output(text: str) -> Dict[str, Any]:
    lower = (text or "").lower()
    checks = {
        "mentions_risk": any(word in lower for word in ["risk", "downside", "invalid", "stop"]),
        "mentions_data": any(word in lower for word in ["data", "volume", "earnings", "price", "trend"]),
        "mentions_confidence": "confidence" in lower,
        "mentions_gaps": any(word in lower for word in ["gap", "missing", "unclear", "unknown"]),
    }
    score = sum(25 for ok in checks.values() if ok)
    return {"score": score, "checks": checks}


def run_benchmark(
    symbols: List[str],
    *,
    alpha_runner: Optional[Callable[[str], Dict[str, Any]]] = None,
    tml_runner: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run an observer-only benchmark on up to MAX_SYMBOLS tickers."""
    clean_symbols = []
    for sym in symbols or []:
        s = str(sym or "").strip().upper()
        if s and s not in clean_symbols:
            clean_symbols.append(s)
        if len(clean_symbols) >= MAX_SYMBOLS:
            break

    alpha_runner = alpha_runner or _baseline_alpha_omega
    tml_runner = tml_runner or _call_tinker
    results = []

    for symbol in clean_symbols:
        baseline = alpha_runner(symbol)
        tml = tml_runner(symbol, baseline)
        scoring = _score_tml_output(tml.get("text", ""))
        results.append({
            "symbol": symbol,
            "trade_action": "none",
            "alpha_omega": baseline,
            "tml": {
                "ok": tml.get("ok", True),
                "model": tml.get("model"),
                "latency_ms": tml.get("latency_ms", 0),
                "error": tml.get("error", ""),
                "text": tml.get("text", ""),
            },
            "tml_quality": scoring,
            "verdict": _verdict(scoring["score"], bool(tml.get("ok", True))),
        })

    avg_score = round(sum(r["tml_quality"]["score"] for r in results) / len(results), 1) if results else 0
    return {
        "ts": _now(),
        "observer_only": True,
        "provider": "thinking_machines_tinker",
        "symbols": clean_symbols,
        "summary": {
            "count": len(results),
            "avg_tml_score": avg_score,
            "recommendation": "benchmark_more" if avg_score >= 70 else "keep_sandbox",
        },
        "results": results,
        "safety": {
            "execution": "blocked",
            "portfolio_mutation": "blocked",
            "used_for_decisions": False,
        },
    }


def _verdict(score: int, ok: bool) -> str:
    if not ok:
        return "not_available"
    if score >= 75:
        return "promising_benchmark"
    if score >= 50:
        return "mixed_benchmark"
    return "weak_benchmark"
