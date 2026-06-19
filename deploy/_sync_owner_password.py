#!/usr/bin/env python3
"""Sync OWNER_PASSWORD from Render to Clouding and restart."""
import json
import os
import sys
import urllib.request

import paramiko

RENDER_TOKEN = os.environ.get("RENDER_API_TOKEN", "rnd_zlTy0eupf1eyLbnCc3dOqg9N3XWU")
RENDER_SID = os.environ.get("RENDER_SERVICE_ID", "srv-d67sta0gjchc73b6tmlg")
HOST = os.environ.get("CLOUDING_HOST", "46.183.113.197")
PASSWORD = os.environ.get("CLOUDING_ROOT_PASS", "")


def get_render_owner_password() -> str:
    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{RENDER_SID}/env-vars",
        headers={"Authorization": f"Bearer {RENDER_TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        envs = json.load(r)
    for e in envs:
        ev = e.get("envVar", {})
        if ev.get("key") == "OWNER_PASSWORD":
            return ev.get("value", "")
    return ""


def patch_env_line(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    out, seen = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append(f"{key}={value}")
    return "\n".join(out) + "\n"


def main():
    if not PASSWORD:
        sys.exit("Set CLOUDING_ROOT_PASS")
    owner_pass = get_render_owner_password()
    if not owner_pass:
        sys.exit("OWNER_PASSWORD not found on Render")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    with sftp.file("/opt/alpha-omega/.env", "r") as f:
        env_text = f.read().decode(errors="replace")
    env_text = patch_env_line(env_text, "OWNER_PASSWORD", owner_pass)
    with sftp.file("/opt/alpha-omega/.env", "w") as f:
        f.write(env_text)
    sftp.close()

    _, o, e = c.exec_command(
        "chown alphaomega:alphaomega /opt/alpha-omega/.env && chmod 600 /opt/alpha-omega/.env && "
        "systemctl restart alpha-omega && sleep 5 && curl -sf http://127.0.0.1:8080/health",
        timeout=60,
    )
    out = o.read().decode(errors="replace")
    err = e.read().decode(errors="replace")
    if err.strip():
        print(err, file=sys.stderr)
    print(out.strip() or "restarted")
    c.close()
    print("OWNER_PASSWORD synced from Render (value not printed).")


if __name__ == "__main__":
    main()
