"""
auth.py — User authentication and role management for Alpha-Omega.

Uses direct HTTP calls to Supabase REST API (not supabase-py client)
to avoid supabase-py v2 WebSocket initialization hanging on Render.
"""
import os
import hashlib
import datetime
import json
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)

OWNER_USERNAMES = {"avi", "aviandjhon"}


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _sb(endpoint: str, method: str = "GET", data: dict = None,
        params: str = "", prefer: str = "") -> list | dict | None:
    """Direct REST call to Supabase PostgREST. No supabase-py client."""
    url_base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key      = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url_base or not key:
        raise RuntimeError("Supabase not configured")

    url = f"{url_base}/rest/v1/{endpoint}"
    if params:
        url += f"?{params}"

    headers = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer

    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"Supabase {e.code}: {err_body[:120]}")


# ── Login ─────────────────────────────────────────────────────────────────────

def login(username: str, password: str) -> dict:
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Username and password required")

    try:
        rows = _sb("ao_users", params=f"username=eq.{username}&select=*")
    except RuntimeError as e:
        raise ValueError(f"Auth error: {e}")

    if not rows:
        raise ValueError("Invalid username or password")

    user = rows[0]
    if user.get("password_hash") != _hash(password):
        raise ValueError("Invalid username or password")

    role = "owner" if username in OWNER_USERNAMES else user.get("role", "visitor")

    # Update last login
    try:
        _sb("ao_users", method="PATCH",
            data={"last_login": datetime.datetime.utcnow().isoformat(),
                  "login_count": (user.get("login_count") or 0) + 1},
            params=f"username=eq.{username}",
            prefer="return=minimal")
    except Exception:
        pass

    return {
        "username":     user["username"],
        "display_name": user.get("display_name") or username.capitalize(),
        "role":         role,
        "email":        user.get("email", ""),
    }


def register(username: str, password: str, display_name: str = "") -> dict:
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Username and password required")
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    if username in OWNER_USERNAMES:
        raise ValueError("Username not available")

    try:
        existing = _sb("ao_users", params=f"username=eq.{username}&select=username")
        if existing:
            raise ValueError("Username already taken")
    except ValueError:
        raise
    except RuntimeError as e:
        raise ValueError(f"Registration failed: {e}")

    new_user = {
        "username":      username,
        "display_name":  display_name or username.capitalize(),
        "password_hash": _hash(password),
        "role":          "visitor",
        "login_count":   0,
        "created_at":    datetime.datetime.utcnow().isoformat(),
    }
    try:
        _sb("ao_users", method="POST", data=new_user, prefer="return=minimal")
    except RuntimeError as e:
        raise ValueError(f"Registration failed: {e}")

    return {"username": username, "display_name": new_user["display_name"], "role": "visitor"}


def ensure_owner_exists(username: str, password: str):
    username = username.lower()
    try:
        existing = _sb("ao_users", params=f"username=eq.{username}&select=username")
        if not existing:
            _sb("ao_users", method="POST", prefer="return=minimal", data={
                "username":      username,
                "display_name":  "Avi",
                "password_hash": _hash(password),
                "role":          "owner",
                "login_count":   0,
                "created_at":    datetime.datetime.utcnow().isoformat(),
            })
            logger.info(f"[AUTH] Owner '{username}' created")
        else:
            logger.info(f"[AUTH] Owner '{username}' already exists")
    except Exception as e:
        logger.warning(f"[AUTH] Could not ensure owner: {e}")


def list_users() -> list:
    try:
        rows = _sb("ao_users",
                   params="select=username,display_name,role,login_count,last_login,created_at&order=created_at")
        return rows or []
    except Exception as e:
        logger.warning(f"[AUTH] list_users error: {e}")
        return []
