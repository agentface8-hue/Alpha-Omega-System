"""Telegram reporting for AMA."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _verbose() -> bool:
    return os.environ.get("AMA_TELEGRAM_VERBOSE", "").lower() in ("1", "true", "yes")


def send_alert(text: str):
    try:
        from core.telegram_alerts import _send
        _send(f"⚡ <b>AMA</b> — {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n{text}")
    except Exception as e:
        logger.warning(f"[AMA] alert failed: {e}")


def report_cycle(cycle: int, snapshot: Dict, results: List[Any]):
    if not results and not _verbose():
        return
    lines = [
        f"🤖 <b>AMA Cycle #{cycle}</b> — {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
        f"System: {snapshot.get('health_overall', '?')}",
        f"Portfolio: {len(snapshot.get('open_positions', []))} open",
        f"Actions: {len(results)}",
    ]
    for r in results:
        icon = "✅" if r.success else "❌"
        lines.append(f"  {icon} {r.action} — {r.detail[:80]}")
    try:
        from core.telegram_alerts import _send
        _send("\n".join(lines))
    except Exception as e:
        logger.warning(f"[AMA] cycle report failed: {e}")
