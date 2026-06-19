#!/usr/bin/env python3
"""Quick patch: upload auth fix + ensure anthropic installed."""
import os
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("CLOUDING_HOST", "46.183.113.197")
PASSWORD = os.environ.get("CLOUDING_ROOT_PASS", "")
REPO = Path(__file__).resolve().parent.parent

FILES = [
    REPO / "backend" / "auth.py",
    REPO / "backend" / "main.py",
]


def run(client, cmd, timeout=600):
    print(f"$ {cmd[:120]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-2500:].encode("ascii", errors="replace").decode())
    if code != 0:
        print(err.strip()[-1000:].encode("ascii", errors="replace").decode(), file=sys.stderr)
        raise SystemExit(code)


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
    run(
        c,
        "chown alphaomega:alphaomega /opt/alpha-omega/backend/auth.py /opt/alpha-omega/backend/main.py && "
        "sudo -u alphaomega /opt/alpha-omega/.venv/bin/pip install -q anthropic && "
        "sudo -u alphaomega /opt/alpha-omega/.venv/bin/python -c \"import anthropic; print('anthropic ok')\" && "
        "systemctl restart alpha-omega && sleep 4 && "
        "curl -sf http://127.0.0.1:8080/health",
    )
    # seed owner if OWNER_PASSWORD set
    run(
        c,
        "grep -q '^OWNER_PASSWORD=' /opt/alpha-omega/.env && "
        "curl -sf -X POST http://127.0.0.1:8080/api/auth/login "
        "-H 'Content-Type: application/json' "
        "-d '{\"username\":\"avi\",\"password\":\"'\"$(grep '^OWNER_PASSWORD=' /opt/alpha-omega/.env | cut -d= -f2-)\"'\"}' "
        "|| echo 'owner login test skipped'",
        timeout=30,
    )
    c.close()
    print("Patch applied.")


if __name__ == "__main__":
    main()
