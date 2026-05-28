"""Theme learning API."""
from fastapi import APIRouter, HTTPException
import asyncio
import concurrent.futures

router = APIRouter()


@router.get("/active")
async def themes_active():
    from core.theme_engine import get_active_themes, load_registry
    return {"themes": get_active_themes(), "registry": load_registry()}


@router.post("/refresh")
async def themes_refresh(body: dict = None):
    body = body or {}
    loop = asyncio.get_event_loop()

    def _run():
        from core.theme_engine import refresh_themes
        return refresh_themes(use_llm=bool(body.get("use_llm", False)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        try:
            return await asyncio.wait_for(loop.run_in_executor(ex, _run), timeout=60.0)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Theme refresh timed out")
