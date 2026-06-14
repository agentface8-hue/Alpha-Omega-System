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
from pathlib import Path

logger = logging.getLogger(__name__)

OWNER_USERNAMES = {"avi", "aviandjhon"}
_LOCAL_USERS_FILE = Path(__file__).resolve().parent.parent / "data" / "ao_users.json"


def _is_supabase_quota_error(err: Exception) -> bool:
    msg = str(err).lower()
    return "402" in msg or "exceed_egress_quota" in msg or "restricted" in msg


def _load_local_users() -> list:
    if not _LOCAL_USERS_FILE.exists():
        return []
    try:
        return json.loads(_LOCAL_USERS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[AUTH] Local users file unreadable: {e}")
        return []


def _save_local_users(users: list) -> None:
    _LOCAL_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LOCAL_USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _owner_env_login(username: str, password: str) -> dict | None:
    """Emergency owner login when Supabase is unavailable."""
    owner_pass = os.environ.get("OWNER_PASSWORD", "")
    if not owner_pass:
        return None
    if username not in OWNER_USERNAMES:
        return None
    if password != owner_pass:
        return None
    return {
        "username": username,
        "display_name": "Avi",
        "role": "owner",
        "email": "",
    }


def _local_login(username: str, password: str) -> dict | None:
    for user in _load_local_users():
        if user.get("username") == username and user.get("password_hash") == _hash(password):
            role = "owner" if username in OWNER_USERNAMES else user.get("role", "visitor")
            return {
                "username": user["username"],
                "display_name": user.get("display_name") or username.capitalize(),
                "role": role,
                "email": user.get("email", ""),
            }
    return None


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
        if _is_supabase_quota_error(e):
            owner = _owner_env_login(username, password)
            if owner:
                logger.warning("[AUTH] Supabase quota exceeded — owner env login used")
                return owner
            local = _local_login(username, password)
            if local:
                logger.warning("[AUTH] Supabase quota exceeded — local users login used")
                return local
            raise ValueError(
                "Database temporarily unavailable (Supabase egress quota exceeded). "
                "Owner: use your OWNER_PASSWORD, or upgrade/reactivate Supabase at supabase.com/dashboard."
            )
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
        if _is_supabase_quota_error(e):
            raise ValueError(
                "Registration paused: Supabase egress quota exceeded. "
                "Reactivate Supabase or ask the owner to restore the database."
            )
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
        if _is_supabase_quota_error(e):
            users = _load_local_users()
            if any(u.get("username") == username for u in users):
                raise ValueError("Username already taken")
            users.append(new_user)
            _save_local_users(users)
            logger.warning("[AUTH] Supabase quota exceeded — registered user locally")
            return {"username": username, "display_name": new_user["display_name"], "role": "visitor"}
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


def supabase_status() -> dict:
    """Lightweight Supabase probe for /health and dashboards."""
    try:
        _sb("ao_users", params="select=username&limit=1")
        return {"ok": True}
    except RuntimeError as e:
        return {"ok": False, "quota_exceeded": _is_supabase_quota_error(e), "error": str(e)[:200]}
