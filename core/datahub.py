"""
datahub.py - small shared cache layer for expensive Alpha-Omega reads.

This is intentionally simple: in-memory first, optional JSON file fallback,
and response metadata so API consumers can see cache freshness.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

DATAHUB_DIR = Path(__file__).parent.parent / "calibration" / "datahub"
_MEMORY: Dict[str, Dict[str, Any]] = {}


def _cache_file(topic: str, cache_path: Optional[str | Path] = None) -> Path:
    if cache_path:
        return Path(cache_path)
    slug = hashlib.sha1(topic.encode("utf-8")).hexdigest()[:16]
    return DATAHUB_DIR / f"{slug}.json"


def _load_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        if isinstance(payload, dict) and "ts" in payload and "data" in payload:
            return payload
    except Exception:
        return None
    return None


def _save_file(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, default=str))
    except Exception:
        pass


def _meta(payload: Dict[str, Any], *, source: str, cached: bool) -> Dict[str, Any]:
    age = max(0, round(time.time() - float(payload.get("ts") or time.time()), 2))
    return {"cached": cached, "age_seconds": age, "source": source}


def get_topic(
    topic: str,
    fetcher: Callable[[], Any],
    ttl_seconds: int,
    *,
    force: bool = False,
    cache_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    now = time.time()
    ttl_seconds = max(0, int(ttl_seconds or 0))
    path = _cache_file(topic, cache_path)

    if not force:
        mem = _MEMORY.get(topic)
        if mem and now - float(mem.get("ts", 0)) <= ttl_seconds:
            return {"data": mem["data"], **_meta(mem, source="memory", cached=True)}

        file_payload = _load_file(path)
        if file_payload and now - float(file_payload.get("ts", 0)) <= ttl_seconds:
            _MEMORY[topic] = file_payload
            return {"data": file_payload["data"], **_meta(file_payload, source="file", cached=True)}

    data = fetcher()
    payload = {"topic": topic, "ts": now, "data": data}
    _MEMORY[topic] = payload
    _save_file(path, payload)
    return {"data": data, **_meta(payload, source="fetcher", cached=False)}


def invalidate_topic(prefix: str) -> int:
    keys = [k for k in _MEMORY if k.startswith(prefix)]
    for key in keys:
        _MEMORY.pop(key, None)
    return len(keys)
