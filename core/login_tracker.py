"""
login_tracker.py — Login event tracking for Alpha-Omega.

Called by POST /api/login-event when a user successfully logs in.
Collects browser fingerprint from frontend + IP geolocation from ipapi.co.
Sends Telegram notification with full details.
Stores event in Supabase login_events table.
"""
import os
import json
import datetime
import urllib.request
import logging

logger = logging.getLogger(__name__)

FLAG_MAP = {
    "CY":"🇨🇾","US":"🇺🇸","GB":"🇬🇧","DE":"🇩🇪","FR":"🇫🇷","IL":"🇮🇱",
    "AU":"🇦🇺","CA":"🇨🇦","NL":"🇳🇱","SG":"🇸🇬","AE":"🇦🇪","IN":"🇮🇳",
    "RU":"🇷🇺","CN":"🇨🇳","JP":"🇯🇵","BR":"🇧🇷","ZA":"🇿🇦","IT":"🇮🇹",
    "ES":"🇪🇸","PL":"🇵🇱","TR":"🇹🇷","SE":"🇸🇪","CH":"🇨🇭","MX":"🇲🇽",
}


def _get_ip_geo(ip: str) -> dict:
    """Get geolocation from ipapi.co — free, no key needed, 1000 req/day."""
    if not ip or ip in ("127.0.0.1", "::1", "testclient"):
        return {"city": "Local", "country_name": "Development", "country_code": "", "timezone": ""}
    try:
        url = f"https://ipapi.co/{ip}/json/"
        req = urllib.request.Request(url, headers={"User-Agent": "alpha-omega/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.warning(f"[LOGIN] IP geo failed for {ip}: {e}")
        return {}


def _parse_browser(user_agent: str) -> str:
    """Extract readable browser + OS from user agent string."""
    ua = user_agent or ""
    browser = "Unknown Browser"
    os_name = "Unknown OS"

    if "Edg/" in ua:       browser = "Edge"
    elif "OPR/" in ua:     browser = "Opera"
    elif "Chrome/" in ua:  browser = "Chrome"
    elif "Firefox/" in ua: browser = "Firefox"
    elif "Safari/" in ua:  browser = "Safari"

    if "Windows NT 10" in ua: os_name = "Windows 10/11"
    elif "Windows NT" in ua:  os_name = "Windows"
    elif "Mac OS X" in ua:    os_name = "macOS"
    elif "Android" in ua:     os_name = "Android"
    elif "iPhone" in ua:      os_name = "iPhone"
    elif "Linux" in ua:       os_name = "Linux"

    return f"{browser} / {os_name}"


def _save_to_supabase(event: dict):
    try:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            return
        from supabase import create_client
        sb = create_client(url, key)
        sb.table("login_events").insert(event).execute()
    except Exception as e:
        logger.warning(f"[LOGIN] Supabase save failed: {e}")


def _send_telegram(msg: str):
    try:
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_PERSONAL_CHAT_ID", "")
        if not token or not chat_id:
            return
        import urllib.parse
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": msg, "parse_mode": "HTML"
        }).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        urllib.request.urlopen(url, data=data, timeout=8)
    except Exception as e:
        logger.warning(f"[LOGIN] Telegram send failed: {e}")


def track_login(
    username: str,
    real_ip: str,
    user_agent: str,
    screen: str,
    timezone: str,
    language: str,
    visitor_id: str,
    visit_count: int,
) -> dict:
    """Main entry point — called by the FastAPI endpoint."""
    now = datetime.datetime.utcnow()
    ts  = now.strftime("%d %b %Y · %H:%M UTC")

    # Geolocation
    geo  = _get_ip_geo(real_ip)
    city = geo.get("city", "")
    country = geo.get("country_name", "")
    country_code = geo.get("country_code", "")
    region  = geo.get("region", "")
    tz_geo  = geo.get("timezone", timezone or "")
    flag    = FLAG_MAP.get(country_code, "🌍")

    location_str = ", ".join(filter(None, [city, region, country]))
    if not location_str:
        location_str = "Unknown"

    # Browser
    browser_str = _parse_browser(user_agent)

    # Visit status
    visit_label = f"#1 — 🆕 FIRST VISIT" if visit_count <= 1 else f"#{visit_count} — RETURNING"

    # Telegram message
    msg = (
        f"🔐 <b>ALPHA-OMEGA LOGIN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {username}\n"
        f"🕐 <b>Time:</b> {ts}\n"
        f"{flag} <b>Location:</b> {location_str}\n"
        f"🌐 <b>IP:</b> <code>{real_ip}</code>\n"
        f"💻 <b>Device:</b> {browser_str}\n"
        f"📱 <b>Screen:</b> {screen or '—'}\n"
        f"🌍 <b>Timezone:</b> {tz_geo or timezone or '—'}\n"
        f"🗣 <b>Language:</b> {language or '—'}\n"
        f"🔢 <b>Visit:</b> {visit_label}"
    )

    _send_telegram(msg)

    # Store in Supabase
    event = {
        "username":    username,
        "ip":          real_ip,
        "location":    location_str,
        "country":     country,
        "country_code":country_code,
        "browser":     browser_str,
        "screen":      screen,
        "timezone":    tz_geo or timezone,
        "language":    language,
        "visitor_id":  visitor_id,
        "visit_count": visit_count,
        "logged_at":   now.isoformat(),
    }
    _save_to_supabase(event)

    return {"ok": True, "location": location_str, "visit_count": visit_count}
