"""
auth.py — Enterprise Authentication Module
==========================================
Supports:
  1. Google OAuth (via streamlit-authenticator + Google Client ID)
  2. Email / Password (hashed, persistent)
  3. Guest Mode (limited features)

Usage:
    from auth import render_auth, get_user_profile
"""

import hashlib
import json
import os
import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple

import streamlit as st

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────
DATA_DIR = Path("user_data")
DATA_DIR.mkdir(exist_ok=True)
CREDS_FILE = DATA_DIR / "credentials.json"

# Default admin credentials (seeded on first run)
DEFAULT_USERS = {
    "admin": {
        "password_hash": hashlib.sha256(b"admin123").hexdigest(),
        "email": "admin@crisprtool.com",
        "role": "admin",
        "created": "2024-01-01T00:00:00",
    }
}


# ─────────────────────────────────────────────────────────────
# Credential Helpers
# ─────────────────────────────────────────────────────────────

def _load_credentials() -> Dict:
    """Load stored user credentials, seeding defaults if empty."""
    if CREDS_FILE.exists():
        with open(CREDS_FILE) as f:
            data = json.load(f)
        # Migrate legacy flat-hash format
        migrated = {}
        for uname, val in data.items():
            if isinstance(val, str):
                migrated[uname] = {
                    "password_hash": val,
                    "email": f"{uname}@unknown.com",
                    "role": "user",
                    "created": datetime.datetime.now().isoformat(),
                }
            else:
                migrated[uname] = val
        if migrated != data:
            _save_credentials(migrated)
        return migrated

    _save_credentials(DEFAULT_USERS)
    return dict(DEFAULT_USERS)


def _save_credentials(creds: Dict):
    with open(CREDS_FILE, "w") as f:
        json.dump(creds, f, indent=2)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# Core Auth Functions
# ─────────────────────────────────────────────────────────────

def login(username: str, password: str) -> Tuple[bool, str]:
    """
    Attempt login with username/password.
    Returns (success, error_message).
    """
    if not username or not password:
        return False, "Please enter both username and password."

    creds = _load_credentials()
    if username not in creds:
        return False, "Username not found."

    user_data = creds[username]
    stored_hash = user_data.get("password_hash", user_data) if isinstance(user_data, dict) else user_data

    if stored_hash == _hash_password(password):
        return True, ""
    return False, "Incorrect password."


def signup(username: str, password: str, email: str = "") -> Tuple[bool, str]:
    """
    Register a new user.
    Returns (success, error_message).
    """
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."
    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Username may only contain letters, numbers, _ and -"

    creds = _load_credentials()
    if username in creds:
        return False, "Username already exists. Please choose another."

    creds[username] = {
        "password_hash": _hash_password(password),
        "email": email or f"{username}@unknown.com",
        "role": "user",
        "created": datetime.datetime.now().isoformat(),
    }
    _save_credentials(creds)
    return True, ""


def get_user_profile(username: str) -> Dict:
    """Return profile dict for a user."""
    creds = _load_credentials()
    if username == "guest":
        return {"username": "guest", "email": "", "role": "guest", "avatar_initials": "GU"}
    data = creds.get(username, {})
    email = data.get("email", "") if isinstance(data, dict) else ""
    role  = data.get("role", "user") if isinstance(data, dict) else "user"
    initials = (username[:2]).upper()
    return {
        "username": username,
        "email": email,
        "role": role,
        "avatar_initials": initials,
    }


# ─────────────────────────────────────────────────────────────
# Google OAuth (optional — requires streamlit-authenticator)
# ─────────────────────────────────────────────────────────────

def try_google_oauth() -> Optional[Dict]:
    """
    Attempt Google OAuth login.
    Returns user dict if successful, None otherwise.

    Prerequisites:
      pip install streamlit-authenticator
      Set in .streamlit/secrets.toml:
        [google_oauth]
        client_id     = "YOUR_CLIENT_ID.apps.googleusercontent.com"
        client_secret = "YOUR_CLIENT_SECRET"
        redirect_uri  = "http://localhost:8501"
    """
    try:
        from streamlit_authenticator import Authenticate  # type: ignore

        if "google_oauth" not in st.secrets:
            return None

        cfg = st.secrets["google_oauth"]

        # Build authenticator config
        auth_config = {
            "credentials": {"usernames": {}},
            "cookie": {"name": "crispr_auth", "key": "crispr_secret_key_xyz", "expiry_days": 7},
            "preauthorized": {"emails": []},
        }
        authenticator = Authenticate(
            auth_config["credentials"],
            auth_config["cookie"]["name"],
            auth_config["cookie"]["key"],
            auth_config["cookie"]["expiry_days"],
        )
        name, auth_status, username = authenticator.login("Login with Google", "main")

        if auth_status:
            return {
                "username": username or name,
                "name": name,
                "email": "",
                "provider": "google",
            }
    except ImportError:
        pass  # streamlit-authenticator not installed
    except Exception:
        pass  # OAuth not configured

    return None


# ─────────────────────────────────────────────────────────────
# Session helpers
# ─────────────────────────────────────────────────────────────

def set_authenticated(username: str, is_guest: bool = False):
    """Mark session as authenticated."""
    profile = get_user_profile(username)
    st.session_state.authenticated = True
    st.session_state.username = username
    st.session_state.user_email = profile.get("email", "")
    st.session_state.is_guest = is_guest
    st.session_state.show_auth = False


def logout():
    """Clear authentication state."""
    for k in ["authenticated", "username", "user_email", "is_guest",
              "results_df", "ot_dict", "sequence_info", "analysis_complete",
              "current_project_id"]:
        if k in st.session_state:
            st.session_state[k] = (
                False if isinstance(st.session_state[k], bool) else
                "" if isinstance(st.session_state[k], str) else
                None
            )
