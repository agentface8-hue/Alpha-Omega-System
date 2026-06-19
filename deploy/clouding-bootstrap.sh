#!/bin/bash
# Alpha-Omega — first-boot setup on Clouding.io Ubuntu 24.04
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip nginx certbot python3-certbot-nginx ufw

APP_USER=alphaomega
APP_DIR=/opt/alpha-omega
DATA_DIR=/var/lib/alpha-omega

id -u "$APP_USER" &>/dev/null || useradd -m -s /bin/bash "$APP_USER"
mkdir -p "$DATA_DIR"/{signals/reports,calibration,data,logs}
chown -R "$APP_USER:$APP_USER" "$DATA_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git clone https://github.com/agentface8-hue/Alpha-Omega-System.git "$APP_DIR"
fi

sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

cat >/etc/systemd/system/alpha-omega.service <<EOF
[Unit]
Description=Alpha-Omega FastAPI
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment=STORAGE_MODE=json
Environment=AO_DATA_ROOT=$DATA_DIR
Environment=PORT=8080
EnvironmentFile=-$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/nginx/sites-available/alpha-omega <<'EOF'
server {
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
EOF

ln -sf /etc/nginx/sites-available/alpha-omega /etc/nginx/sites-enabled/alpha-omega
rm -f /etc/nginx/sites-enabled/default

ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

systemctl daemon-reload
systemctl enable alpha-omega nginx
systemctl restart nginx

echo "Bootstrap done. Copy .env to $APP_DIR/.env then: systemctl start alpha-omega"
