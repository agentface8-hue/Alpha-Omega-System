"""
setup_sheets_auth.py — One-time Google Sheets OAuth setup.

Run this ONCE to authorize the Alpha-Omega System to write to your Google Sheet.
After running, a token is saved to data/sheets_token.json and all future writes
happen silently in the background.

REQUIREMENTS (do these once before running):
─────────────────────────────────────────────────────────────────────────────
1. Go to: https://console.cloud.google.com/
2. Create a project (or select existing one).
3. Enable "Google Sheets API":
   APIs & Services → Library → search "Google Sheets API" → Enable
4. Create OAuth 2.0 credentials:
   APIs & Services → Credentials → Create Credentials → OAuth client ID
   Application type: Desktop app
   Name: Alpha-Omega Trade Log
5. Click "Download JSON" → save as:
   C:\\Users\\asus\\Alpha-Omega-System\\credentials.json
6. Run this script: python setup_sheets_auth.py
─────────────────────────────────────────────────────────────────────────────
"""

import sys, os, json
sys.path.insert(0, r'C:\Users\asus\Alpha-Omega-System')

SHEET_ID         = "1G5f1AePhWKJEMJKmfHj1genbr18LMdlCWPsoBJC2ZxM"
BASE_DIR         = r'C:\Users\asus\Alpha-Omega-System'
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE       = os.path.join(BASE_DIR, "data", "sheets_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

COLUMNS = ["Date", "Ticker", "Direction", "Entry", "Exit",
           "P&L$", "P&L%", "Conviction%", "Exit Reason", "Regime"]


def install_deps():
    """Install required packages."""
    import subprocess
    pkgs = ["gspread", "google-auth", "google-auth-oauthlib", "google-auth-httplib2"]
    for pkg in pkgs:
        try:
            __import__(pkg.replace("-", "_").split(".")[0])
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])


def run_auth_flow():
    """Run OAuth flow, save token, initialize sheet headers."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    import gspread

    creds = None

    # Try loading existing token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            data = json.load(f)
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", SCOPES),
        )
        if creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            creds.refresh(Request())
        elif creds.valid:
            print("Existing token is still valid.")

    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            print("\n❌  credentials.json not found!")
            print(f"    Expected at: {CREDENTIALS_FILE}")
            print("\n    Follow the setup steps at the top of this script.")
            sys.exit(1)
        print("Opening browser for Google authorization...")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    # Save token
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes) if creds.scopes else SCOPES,
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"✅  Token saved to: {TOKEN_FILE}")

    # Initialize sheet headers
    print(f"\nConnecting to Google Sheet (ID: {SHEET_ID})...")
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1

    existing = ws.row_values(1)
    if existing == COLUMNS:
        print("✅  Headers already set correctly.")
    elif not existing:
        ws.append_row(COLUMNS, value_input_option="USER_ENTERED")
        print(f"✅  Headers written: {COLUMNS}")
        # Format header row bold
        try:
            ws.format("A1:J1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.13, "green": 0.13, "blue": 0.13},
            })
        except Exception:
            pass
    else:
        print(f"⚠  Row 1 already has content: {existing}")
        print("   Skipping header write to avoid overwriting data.")

    print("\n🎉  Setup complete! The Alpha-Omega System will now auto-log trades to:")
    print(f"    https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print(f"\n    CSV backup: C:\\Users\\asus\\Alpha-Omega-System\\data\\trade_log.csv")


if __name__ == "__main__":
    print("=" * 60)
    print("  Alpha-Omega Trade Log — Google Sheets Auth Setup")
    print("=" * 60)
    install_deps()
    run_auth_flow()
