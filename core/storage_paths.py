"""Persistent data paths — JSON storage on Clouding VPS or local dev."""
import os
from pathlib import Path

_STORAGE_MODE = os.environ.get("STORAGE_MODE", "auto").lower()
_AO_ROOT = os.environ.get("AO_DATA_ROOT", "").strip()
_REPO_ROOT = Path(__file__).resolve().parent.parent


def storage_mode() -> str:
    """auto | json | supabase — json skips Supabase entirely."""
    if _STORAGE_MODE in ("json", "supabase"):
        return _STORAGE_MODE
    if _AO_ROOT:
        return "json"
    return "auto"


def use_json_primary() -> bool:
    return storage_mode() == "json"


def use_supabase() -> bool:
    return storage_mode() != "json"


def data_root() -> Path:
    if _AO_ROOT:
        root = Path(_AO_ROOT)
    else:
        root = _REPO_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def signals_dir() -> Path:
    d = data_root() / "signals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def calibration_dir() -> Path:
    d = data_root() / "calibration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def app_data_dir() -> Path:
    d = data_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d
