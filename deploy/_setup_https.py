#!/usr/bin/env python3
"""Enable HTTPS on Clouding via certbot (Let's Encrypt)."""
import os
import sys

import paramiko

HOST = os.environ.get("CLOUDING_HOST", "46.183.113.197")
PASSWORD = os.environ.get("CLOUDING_ROOT_PASS", "")
DOMAIN = os.environ.get(
    "CLOUDING_DOMAIN",
    "289c4c10-4400-4814-b389-cf8b47133fc3.clouding.host",
)


def run(client, cmd, timeout=600):
    print(f"$ {cmd[:120]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-3000:].encode("ascii", errors="replace").decode())
    if code != 0:
        print(err.strip()[-1500:].encode("ascii", errors="replace").decode(), file=sys.stderr)
        raise SystemExit(code)
    return out


def main():
    if not PASSWORD:
        sys.exit("Set CLOUDING_ROOT_PASS")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=PASSWORD, timeout=30)

    run(
        client,
        "export DEBIAN_FRONTEND=noninteractive && apt-get install -y -qq certbot python3-certbot-nginx",
        timeout=900,
    )

    nginx = f"""server {{
    listen 80;
    server_name {DOMAIN} {HOST};
    client_max_body_size 20M;
    location / {{
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
    sftp = client.open_sftp()
    with sftp.file("/etc/nginx/sites-available/alpha-omega", "w") as f:
        f.write(nginx)
    sftp.close()

    run(client, "nginx -t && systemctl reload nginx")
    run(
        client,
        f"certbot --nginx -d {DOMAIN} --non-interactive --agree-tos --register-unsafely-without-email --redirect",
        timeout=900,
    )
    run(client, f"curl -sf https://{DOMAIN}/health")
    client.close()
    print(f"HTTPS live: https://{DOMAIN}/health")


if __name__ == "__main__":
    main()
