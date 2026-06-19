# Alpha-Omega on Clouding.io

Move the API from Render to a [Clouding](https://clouding.io/) VPS with **persistent JSON storage** — Alpha-Omega only. AI Scout stays on its own Supabase.

## Server spec (recommended)

| Setting | Value |
|---------|-------|
| OS | Ubuntu 24.04 |
| RAM | 2 GB |
| vCPU | 1 |
| Disk | 10 GB SSD |
| Cost | ~€6/mo |
| Hostname | `alpha-omega` |

## Server (live)

| Field | Value |
|-------|-------|
| Public IP | `46.183.113.197` |
| DNS | `289c4c10-4400-4814-b389-cf8b47133fc3.clouding.host` |
| Health | http://46.183.113.197/health |
| Storage | JSON at `/var/lib/alpha-omega` (no Supabase) |

## 1. Create server (Clouding portal)

1. [portal.clouding.io](https://portal.clouding.io/dsb/vmm/create)
2. Name: **Alpha-Omega API** / hostname **alpha-omega**
3. Image: **Ubuntu 24.04**
4. Size: **2 GB RAM, 1 vCore, 10 GB SSD**
5. Generate password → **save it**
6. Submit → note the **public IP**

## 2. Bootstrap (SSH as root)

```bash
ssh root@YOUR_CLOUDING_IP
curl -fsSL https://raw.githubusercontent.com/agentface8-hue/Alpha-Omega-System/main/deploy/clouding-bootstrap.sh | bash
```

Or copy `deploy/clouding-bootstrap.sh` manually if the repo branch isn’t merged yet.

## 3. Environment

```bash
cp /opt/alpha-omega/deploy/clouding.env.example /opt/alpha-omega/.env
nano /opt/alpha-omega/.env   # paste keys from local Alpha-Omega-System/.env
systemctl start alpha-omega
systemctl status alpha-omega
curl -s http://127.0.0.1:8080/health | python3 -m json.tool
```

Required keys: `GOOGLE_API_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_PERSONAL_CHAT_ID`, `OWNER_PASSWORD`.

**Do not set** `SUPABASE_URL` on Clouding — use `STORAGE_MODE=json`.

## 4. Point frontend at Clouding

**Vercel** → Project `alpha-omega-ngfw` → Environment:

```
VITE_API_URL=http://YOUR_CLOUDING_IP
```

Redeploy Vercel. Later add a domain + `certbot --nginx -d api.yourdomain.com`.

## 5. Copy local data (optional)

From your PC:

```powershell
scp -r C:\Users\asus\Alpha-Omega-System\signals\* root@YOUR_IP:/var/lib/alpha-omega/signals/
scp -r C:\Users\asus\Alpha-Omega-System\data\* root@YOUR_IP:/var/lib/alpha-omega/data/
scp C:\Users\asus\Alpha-Omega-System\calibration\calibration_params.json root@YOUR_IP:/var/lib/alpha-omega/calibration/
```

## 6. Verify

```bash
curl http://YOUR_IP/health
curl http://YOUR_IP/api/storage/status
```

Expect `"storage": "json_fallback"` and no Supabase quota errors.

## 7. Retire Render (when stable)

- Pause or delete `alpha-omega-system` on Render
- Update Hermes `alpha-omega-agent` env / skill with new API URL

## Data layout on VPS

```
/var/lib/alpha-omega/
├── signals/active_signals.json
├── signals/closed_signals.json
├── signals/portfolio_*.json
├── calibration/calibration_params.json
└── data/ao_users.json
```

Persistent across reboots and redeploys.
