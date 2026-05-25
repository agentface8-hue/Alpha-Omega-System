"""
seed_signal_history.py
Uploads enriched historical trades to Supabase signal_history table.
Run once after creating the table.

Uses data/enriched_trades.json (already built by _enrich_trades.py).
For the 14 failed (crypto), falls back to trade_log basic data.
"""
import sys, os, json
sys.path.insert(0, r'C:\Users\asus\Alpha-Omega-System')
from dotenv import load_dotenv; load_dotenv()
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "")
SB_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

def sb_post(endpoint, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(
        f"{SB_URL}/rest/v1/{endpoint}",
        data=body,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status

# Load enriched trades
enriched_path = r'C:\Users\asus\Alpha-Omega-System\data\enriched_trades.json'
enriched = json.load(open(enriched_path))
print(f"Loaded {len(enriched)} enriched trades")

# Also load raw trade_log from Supabase for the failed ones
raw_req = urllib.request.Request(
    f"{SB_URL}/rest/v1/trade_log?select=*&limit=200",
    headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
)
with urllib.request.urlopen(raw_req, timeout=15) as r:
    raw_trades = json.loads(r.read())
print(f"Loaded {len(raw_trades)} raw trades from trade_log")

# Check what's already in signal_history
check_req = urllib.request.Request(
    f"{SB_URL}/rest/v1/signal_history?select=count&limit=1",
    headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
             "Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"}
)
with urllib.request.urlopen(check_req, timeout=10) as r:
    existing_count = r.headers.get("Content-Range", "0-0/0").split("/")[-1]
    print(f"Existing rows in signal_history: {existing_count}")
    if int(existing_count) > 0:
        print("Table already has data. Skipping to avoid duplicates.")
        print("To re-seed, manually DELETE FROM signal_history in Supabase.")
        sys.exit(0)

# Map raw trade_log by (ticker, date_closed) for fallback
raw_map = {}
for t in raw_trades:
    key = (str(t.get("ticker","")).upper(), str(t.get("date_closed",""))[:10])
    raw_map[key] = t

uploaded = 0
skipped  = 0
for t in enriched:
    ticker     = str(t.get("ticker","")).upper()
    date_closed= str(t.get("date_closed", t.get("date", "")))[:10]
    pnl        = t.get("pnl", t.get("pnl_pct", 0))
    conv       = t.get("conv", t.get("conviction", 0))
    tas_num    = t.get("tas_num", -1)
    vol_ratio  = t.get("vol_ratio", -1)
    vol_dir    = t.get("vol_dir", t.get("vol_direction", "NEUTRAL"))
    regime     = t.get("regime", "Unknown")
    exit_reason= t.get("exit_reason", "")
    mae        = t.get("mae", t.get("mae_pct", 0))
    mfe        = t.get("mfe", t.get("mfe_pct", 0))
    tf_daily   = t.get("tf_daily", "")
    tf_weekly  = t.get("tf_weekly", "")
    tf_65m     = t.get("tf_65m", "")
    tf_240m    = t.get("tf_240m", "")

    # Try to get entry/exit from raw trade_log
    raw = raw_map.get((ticker, date_closed), {})
    entry_price = float(raw.get("entry_price") or 0)
    exit_price  = float(raw.get("exit_price") or 0)
    asset_type  = str(raw.get("asset_type", "stock"))

    # Skip if TAS failed and it's a crypto (already no vol data)
    if tas_num < 0 and asset_type == "crypto":
        skipped += 1
        continue

    row = {
        "ticker":        ticker,
        "date_closed":   date_closed,
        "entry_price":   entry_price or None,
        "exit_price":    exit_price  or None,
        "pnl_pct":       round(float(pnl), 4) if pnl is not None else None,
        "conviction":    round(float(conv), 1) if conv is not None else None,
        "exit_reason":   exit_reason,
        "regime":        regime,
        "asset_type":    asset_type,
        "mae_pct":       round(float(mae), 4) if mae is not None else None,
        "mfe_pct":       round(float(mfe), 4) if mfe is not None else None,
        "tas_num":       int(tas_num) if tas_num >= 0 else None,
        "vol_ratio":     round(float(vol_ratio), 3) if vol_ratio >= 0 else None,
        "vol_direction": vol_dir if vol_dir != "?" else None,
        "tf_daily":      tf_daily or None,
        "tf_weekly":     tf_weekly or None,
        "tf_65m":        tf_65m  or None,
        "tf_240m":       tf_240m or None,
        "source":        "trade_log_enriched",
    }

    try:
        status = sb_post("signal_history", row)
        print(f"  OK   {ticker:<6} {date_closed}  pnl={pnl:+.2f}%  tas={tas_num}/4  vol={vol_ratio:.2f}x")
        uploaded += 1
    except Exception as e:
        print(f"  FAIL {ticker:<6} {date_closed}: {e}")
        skipped += 1

print(f"\nDone. Uploaded: {uploaded}  Skipped: {skipped}")
