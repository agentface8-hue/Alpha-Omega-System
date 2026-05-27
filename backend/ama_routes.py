"""AMA API routes."""
from fastapi import APIRouter, HTTPException
import asyncio
import concurrent.futures

router = APIRouter()


@router.get("/status")
async def ama_status():
    from core.ama.agent import get_status
    return get_status()


@router.get("/history")
async def ama_history(limit: int = 50):
    from core.ama.memory import get_history
    return {"history": get_history(limit)}


@router.get("/snapshot")
async def ama_snapshot():
    import asyncio
    import concurrent.futures
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as ex:
        from core.ama.observer import collect_snapshot
        snap = await asyncio.wait_for(loop.run_in_executor(ex, collect_snapshot), timeout=25.0)
    return snap


@router.post("/run-now")
async def ama_run_now():
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as ex:
        from core.ama.agent import run_cycle_now
        try:
            return await asyncio.wait_for(loop.run_in_executor(ex, run_cycle_now), timeout=90.0)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="AMA cycle timed out")


@router.post("/pause")
async def ama_pause():
    from core.ama.agent import pause
    pause()
    return {"paused": True}


@router.post("/resume")
async def ama_resume():
    from core.ama.agent import resume
    resume()
    return {"paused": False}


@router.get("/memory")
async def ama_memory_dump():
    mem = __import__("core.ama.memory", fromlist=["get_memory"]).get_memory()
    return {
        "action_cooldowns": mem.action_cooldowns,
        "actions_today": mem.actions_today,
        "recent_actions": mem.recent_actions[-20:],
        "what_worked": mem.what_worked,
        "what_failed": mem.what_failed,
    }


@router.post("/clear-memory")
async def ama_clear_memory():
    from core.ama.memory import clear_memory
    clear_memory()
    return {"cleared": True}
