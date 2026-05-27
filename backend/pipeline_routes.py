"""Unified daily pipeline API."""
from fastapi import APIRouter, HTTPException
import asyncio
import concurrent.futures

router = APIRouter()


@router.get("/status")
async def pipeline_status():
    from pathlib import Path
    import json
    p = Path(__file__).parent.parent / "calibration" / "last_portfolio_scan.json"
    out = {"scan_cache": False, "regime": None}
    if p.exists():
        try:
            c = json.loads(p.read_text())
            out["scan_cache"] = True
            out["regime"] = c.get("regime")
            out["conv_threshold"] = c.get("conv_threshold")
        except Exception:
            pass
    return out


@router.post("/run")
async def pipeline_run(body: dict = None):
    body = body or {}
    loop = asyncio.get_event_loop()

    def _run():
        from core.daily_pipeline import run_daily_pipeline
        return run_daily_pipeline(
            run_dream=bool(body.get("run_dream", True)),
            run_autopilot=bool(body.get("run_autopilot", True)),
            run_learning=bool(body.get("run_learning", True)),
            dream_force=bool(body.get("dream_force", False)),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        try:
            return await asyncio.wait_for(loop.run_in_executor(ex, _run), timeout=300.0)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Pipeline timed out after 300s")
