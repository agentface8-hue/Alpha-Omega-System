"""
auth.py — User authentication and role management for Alpha-Omega.

Users stored in Supabase 'users' table.
Roles: 'owner' | 'visitor'
Owner usernames are hardcoded — only Avi can be owner.
Visitors self-register and get read-only access.
"""
import os
import hashlib
import datetime
import logging

logger = logging.getLogger(__name__)

# These usernames are always owners regardless of DB
OWNER_USERNAMES = {"avi", "aviandjhon"}


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _get_sb():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase not configured")
    from supabase import create_client
    return create_client(url, key)


# ── Login ─────────────────────────────────────────────────────────────────────

def login(username: str, password: str) -> dict:
    """
    Validate credentials. Returns user dict with role, or raises ValueError.
    """
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Username and password required")

    pw_hash = _hash(password)

    try:
        sb = _get_sb()
        res = sb.table("ao_users") \
                .select("*") \
                .eq("username", username) \
                .single() \
                .execute()
        user = res.data
    except Exception as e:
        raise ValueError("Invalid username or password")

    if not user:
        raise ValueError("Invalid username or password")

    if user.get("password_hash") != pw_hash:
        raise ValueError("Invalid username or password")

    # Determine role — owner usernames always get owner role
    role = "owner" if username in OWNER_USERNAMES else user.get("role", "visitor")

    # Update last login + count
    try:
        sb.table("ao_users").update({
            "last_login":  datetime.datetime.utcnow().isoformat(),
            "login_count": (user.get("login_count") or 0) + 1,
        }).eq("username", username).execute()
    except Exception:
        pass

    return {
        "username":     user["username"],
        "display_name": user.get("display_name") or username.capitalize(),
        "role":         role,
        "email":        user.get("email", ""),
    }


# ── Register ──────────────────────────────────────────────────────────────────

def register(username: str, password: str, display_name: str = "") -> dict:
    """
    Create a new visitor account. Returns user dict or raises ValueError.
    """
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Username and password required")
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    if username in OWNER_USERNAMES:
        raise ValueError("Username not available")

    # Check username taken
    try:
        sb = _get_sb()
        existing = sb.table("ao_users") \
                     .select("username") \
                     .eq("username", username) \
                     .execute()
        if existing.data:
            raise ValueError("Username already taken")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Registration failed: {str(e)[:60]}")

    # Create user
    new_user = {
        "username":      username,
        "display_name":  display_name or username.capitalize(),
        "password_hash": _hash(password),
        "role":          "visitor",
        "login_count":   0,
        "created_at":    datetime.datetime.utcnow().isoformat(),
    }

    try:
        sb.table("ao_users").insert(new_user).execute()
    except Exception as e:
        raise ValueError(f"Registration failed: {str(e)[:60]}")

    return {
        "username":     username,
        "display_name": new_user["display_name"],
        "role":         "visitor",
    }


# ── Seed owner ────────────────────────────────────────────────────────────────

def ensure_owner_exists(username: str, password: str):
    """
    Called on backend startup — creates owner account if not exists.
    """
    username = username.lower()
    try:
        sb = _get_sb()
        existing = sb.table("ao_users") \
                     .select("username") \
                     .eq("username", username) \
                     .execute()
        if not existing.data:
            sb.table("ao_users").insert({
                "username":      username,
                "display_name":  "Avi",
                "password_hash": _hash(password),
                "role":          "owner",
                "login_count":   0,
                "created_at":    datetime.datetime.utcnow().isoformat(),
            }).execute()
            logger.info(f"[AUTH] Owner account '{username}' created")
    except Exception as e:
        logger.warning(f"[AUTH] Could not ensure owner exists: {e}")


# ── List users (owner only) ────────────────────────────────────────────────────

def list_users() -> list:
    try:
        sb = _get_sb()
        res = sb.table("ao_users") \
                .select("username, display_name, role, login_count, last_login, created_at") \
                .order("created_at") \
                .execute()
        return res.data or []
    except Exception as e:
        return []
