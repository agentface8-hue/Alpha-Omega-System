"""
keepalive.py — Self-pinger to prevent any sleep on Render.
Runs as a background thread. Pings /health every 8 minutes.
Imported and started once from main.py startup.
"""
import threading
import time
import urllib.request
import logging
import os

logger = logging.getLogger(__name__)

_INTERVAL  = 480   # 8 minutes
_SERVICE_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    "https://289c4c10-4400-4814-b389-cf8b47133fc3.clouding.host"
)

def _ping_loop():
    time.sleep(60)  # wait 1 min after startup before first ping
    while True:
        try:
            req = urllib.request.Request(
                f"{_SERVICE_URL}/health",
                headers={"User-Agent": "AlphaOmega-Keepalive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                pass
            logger.debug(f"[KEEPALIVE] ping ok")
        except Exception as e:
            logger.warning(f"[KEEPALIVE] ping failed: {e}")
        time.sleep(_INTERVAL)

def start():
    t = threading.Thread(target=_ping_loop, daemon=True, name="keepalive")
    t.start()
    logger.info("[KEEPALIVE] Background pinger started (every 8 min)")
