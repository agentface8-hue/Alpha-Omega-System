#!/usr/bin/env python3
"""One-shot Clouding deploy — run locally."""
import io
import os
import sys
import tarfile
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("CLOUDING_HOST", "46.183.113.197")
USER = "root"
PASSWORD = os.environ.get("CLOUDING_ROOT_PASS", "")
REPO = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "frontend/node_modules", "frontend/dist", ".cursor", "superpowers",
}
SKIP_SUFFIX = {".pyc", ".pyo"}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return True
    if path.name == ".env":
        return True
    return path.suffix in SKIP_SUFFIX


def make_tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".git")]
            for name in files:
                fp = Path(root) / name
                rel = fp.relative_to(REPO)
                if should_skip(fp) or should_skip(rel):
                    continue
                try:
                    tar.add(fp, arcname=str(rel).replace("\\", "/"))
                except OSError as e:
                    print(f"skip {rel}: {e}")
    buf.seek(0)
    return buf.read()


def build_env_content() -> str:
    local_env = REPO / ".env"
    atlas_env = Path(r"D:\hermas\atlas-jarvis\.env.local")
    lines = []
    if local_env.exists():
        for line in local_env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("SUPABASE_"):
                continue
            lines.append(line)
    extra = {
        "STORAGE_MODE": "json",
        "AO_DATA_ROOT": "/var/lib/alpha-omega",
        "PORT": "8080",
    }
    if atlas_env.exists():
        for line in atlas_env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("ALPHA_OMEGA_API_TOKEN="):
                extra["JARVIS_API_TOKEN"] = line.split("=", 1)[1].strip()
                extra["ALPHA_OMEGA_API_TOKEN"] = line.split("=", 1)[1].strip()
    keys = {l.split("=", 1)[0].strip() for l in lines if "=" in l and not l.strip().startswith("#")}
    for k, v in extra.items():
        if k not in keys:
            lines.append(f"{k}={v}")
    return "\n".join(lines) + "\n"


def upload_tree(sftp, local: Path, remote: str):
    for item in local.iterdir():
        r = f"{remote}/{item.name}"
        if item.is_dir():
            try:
                sftp.mkdir(r)
            except OSError:
                pass
            upload_tree(sftp, item, r)
        elif item.is_file():
            sftp.put(str(item), r)


def run(client, cmd: str, timeout=600):
    print(f"$ {cmd[:140]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-2500:].encode("ascii", errors="replace").decode())
    if code != 0:
        print(err.strip()[-1500:].encode("ascii", errors="replace").decode(), file=sys.stderr)
        raise SystemExit(f"Command failed ({code})")
    return out


def main():
    if not PASSWORD:
        sys.exit("Set CLOUDING_ROOT_PASS")

    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    tarball = make_tarball()
    sftp = client.open_sftp()
    with sftp.file("/tmp/alpha-omega.tgz", "wb") as f:
        f.write(tarball)
    with sftp.file("/tmp/alpha-omega.env", "w") as f:
        f.write(build_env_content())
    sftp.close()

    run(client, "export DEBIAN_FRONTEND=noninteractive && apt-get update -qq && apt-get install -y -qq git python3 python3-venv python3-pip nginx ufw", timeout=900)

    run(client, "id -u alphaomega &>/dev/null || useradd -m -s /bin/bash alphaomega")
    run(client, "mkdir -p /var/lib/alpha-omega/{signals/reports,calibration,data,logs} && chown -R alphaomega:alphaomega /var/lib/alpha-omega")

    for sub, remote_sub in [
        (REPO / "signals", "/var/lib/alpha-omega/signals"),
        (REPO / "data", "/var/lib/alpha-omega/data"),
        (REPO / "calibration", "/var/lib/alpha-omega/calibration"),
    ]:
        if sub.exists():
            sftp = client.open_sftp()
            upload_tree(sftp, sub, remote_sub)
            sftp.close()
    run(client, "chown -R alphaomega:alphaomega /var/lib/alpha-omega")

    run(client, "rm -rf /opt/alpha-omega && mkdir -p /opt/alpha-omega && tar -xzf /tmp/alpha-omega.tgz -C /opt/alpha-omega")
    run(client, "cp /tmp/alpha-omega.env /opt/alpha-omega/.env && chown -R alphaomega:alphaomega /opt/alpha-omega && chmod 600 /opt/alpha-omega/.env")

    run(client, "sudo -u alphaomega python3 -m venv /opt/alpha-omega/.venv", timeout=120)
    run(client, "sudo -u alphaomega /opt/alpha-omega/.venv/bin/pip install -r /opt/alpha-omega/requirements.txt", timeout=900)

    unit = """[Unit]
Description=Alpha-Omega FastAPI
After=network.target

[Service]
User=alphaomega
WorkingDirectory=/opt/alpha-omega
Environment=STORAGE_MODE=json
Environment=AO_DATA_ROOT=/var/lib/alpha-omega
Environment=PORT=8080
EnvironmentFile=-/opt/alpha-omega/.env
ExecStart=/opt/alpha-omega/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    sftp = client.open_sftp()
    with sftp.file("/etc/systemd/system/alpha-omega.service", "w") as f:
        f.write(unit)
    nginx = """server {
    listen 80;
    server_name _;
    client_max_body_size 20M;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""
    with sftp.file("/etc/nginx/sites-available/alpha-omega", "w") as f:
        f.write(nginx)
    sftp.close()

    run(client, "ln -sf /etc/nginx/sites-available/alpha-omega /etc/nginx/sites-enabled/alpha-omega && rm -f /etc/nginx/sites-enabled/default")
    run(client, "ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw --force enable || true")
    run(client, "systemctl daemon-reload && systemctl enable alpha-omega nginx && systemctl restart alpha-omega nginx")

    time.sleep(5)
    out = run(client, "curl -sf http://127.0.0.1:8080/health; echo; curl -sf http://127.0.0.1/health")
    print("HEALTH:", out.strip()[:500])
    client.close()
    print(f"Live: http://{HOST}/health")


if __name__ == "__main__":
    main()
