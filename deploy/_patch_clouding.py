#!/usr/bin/env python3
"""Upload jarvis + live_monitor fixes to Clouding."""
import os
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("CLOUDING_HOST", "46.183.113.197")
PASSWORD = os.environ.get("CLOUDING_ROOT_PASS", "")
REPO = Path(__file__).resolve().parent.parent
FILES = [
    REPO / "backend" / "jarvis_routes.py",
    REPO / "core" / "live_monitor.py",
]


def main():
    if not PASSWORD:
        sys.exit("Set CLOUDING_ROOT_PASS")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    for fp in FILES:
        remote = f"/opt/alpha-omega/{fp.relative_to(REPO).as_posix()}"
        sftp.put(str(fp), remote)
        print("uploaded", remote)
    sftp.close()
    _, o, e = c.exec_command(
        "chown alphaomega:alphaomega /opt/alpha-omega/backend/jarvis_routes.py "
        "/opt/alpha-omega/core/live_monitor.py && systemctl restart alpha-omega && "
        "sleep 5 && curl -sf http://127.0.0.1:8080/health",
        timeout=60,
    )
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print(err, file=sys.stderr)
    c.close()


if __name__ == "__main__":
    main()
