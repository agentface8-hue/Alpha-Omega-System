"""
chart_generator.py — Generate a Matplotlib price chart for a closed signal.

Entry point: generate_signal_chart(signal) -> Optional[str]
  Returns the public URL (Supabase) or local file path, or None on failure.
  Always non-blocking — caller wraps in try/except.

Chart shows:
  - Close-price line for the hold period
  - Green ▲ at entry price
  - Red ▼ at close price
  - Red dashed horizontal: SL level
  - Green dashed horizontals: TP1, TP2, TP3
  - Orange dots: TSL move timestamps from action_log
  - Title: "{TICKER} — {entry_date} to {close_date} — {P&L%}"
"""

import os
import logging
import datetime
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "signals" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _fetch_ohlc(ticker: str, start: str, end: str, asset_type: str = "stock"):
    """Fetch daily OHLC via yfinance. Returns a pandas DataFrame or None."""
    try:
        import yfinance as yf
        sym = ticker
        if asset_type == "crypto" and not ticker.endswith("-USD"):
            sym = ticker + "-USD"
        # Add 3-day buffer on each side so entry/close markers are visible
        start_dt = (datetime.datetime.fromisoformat(start) - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        end_dt   = (datetime.datetime.fromisoformat(end)   + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        df = yf.download(sym, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        logger.warning(f"[CHART] yfinance fetch failed for {ticker}: {e}")
        return None


def _upload_to_supabase(local_path: Path, filename: str) -> Optional[str]:
    """Upload PNG to Supabase Storage bucket 'signal-charts'. Returns public URL or None."""
    try:
        from core.signal_store import _sb
        sb = _sb()
        if not sb:
            return None
        with open(local_path, "rb") as f:
            data = f.read()
        bucket = "signal-charts"
        # upsert=True so re-runs don't error on duplicate
        sb.storage.from_(bucket).upload(
            path=filename,
            file=data,
            file_options={"content-type": "image/png", "upsert": "true"},
        )
        public_url = sb.storage.from_(bucket).get_public_url(filename)
        return public_url
    except Exception as e:
        logger.warning(f"[CHART] Supabase upload failed ({filename}): {e}")
        return None


def generate_signal_chart(signal: Dict[str, Any]) -> Optional[str]:
    """
    Generate a price chart PNG for a closed signal.

    Returns the chart URL (Supabase public URL or local path string), or None on failure.
    Never raises — all errors are caught internally.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend — safe on servers
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import pandas as pd
    except ImportError as e:
        logger.warning(f"[CHART] matplotlib not available: {e}")
        return None

    ticker   = signal.get("ticker", "UNK")
    sig_id   = signal.get("id", "unknown")
    entry_t  = signal.get("entry_time", "")
    close_t  = signal.get("closed_at", "")
    asset_t  = signal.get("asset_type", "stock")

    if not entry_t or not close_t:
        logger.warning(f"[CHART] {ticker}: missing entry_time or closed_at, skipping chart")
        return None

    # ── Fetch price data ──────────────────────────────────────────────────────
    df = _fetch_ohlc(ticker, entry_t[:10], close_t[:10], asset_t)
    if df is None:
        logger.warning(f"[CHART] {ticker}: no OHLC data returned")
        return None

    # ── Key levels ────────────────────────────────────────────────────────────
    entry_price = float(signal.get("entry_price", 0))
    close_price = float(signal.get("close_price", 0))
    sl          = float(signal.get("sl", 0))
    tp1         = float(signal.get("tp1", 0))
    tp2         = float(signal.get("tp2", 0))
    tp3         = float(signal.get("tp3", 0))
    pnl_pct     = float(signal.get("pnl_pct", 0))

    entry_date_str = entry_t[:10]
    close_date_str = close_t[:10]
    pnl_label      = f"{pnl_pct:+.2f}%"

    # ── Build TSL move dates from action_log ──────────────────────────────────
    tsl_dates  = []
    tsl_prices = []
    for action in signal.get("action_log", []):
        act = action.get("action", "")
        if "SL TIGHTENED" in act or "TRAIL" in act or "SL OVERRIDE" in act:
            ts_str = action.get("ts", "")
            try:
                ts_dt = datetime.datetime.fromisoformat(ts_str)
                # Find closest date in df
                closest_idx = (df.index - ts_dt).abs().argmin()
                row = df.iloc[closest_idx]
                close_val = float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"])
                tsl_dates.append(df.index[closest_idx])
                tsl_prices.append(close_val)
            except Exception:
                pass

    # ── Entry/close date markers (snap to nearest trading day in df) ──────────
    try:
        entry_dt = datetime.datetime.fromisoformat(entry_t)
        close_dt = datetime.datetime.fromisoformat(close_t)
        entry_idx = (df.index - entry_dt).abs().argmin()
        close_idx = (df.index - close_dt).abs().argmin()
    except Exception as e:
        logger.warning(f"[CHART] {ticker}: date parse error: {e}")
        return None

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0a0f18")
    ax.set_facecolor("#050810")

    # Close price line
    try:
        close_series = df["Close"].squeeze()
    except Exception:
        close_series = df["Close"]

    ax.plot(df.index, close_series, color="#00d4ff", linewidth=1.5, zorder=2)

    # SL — red dashed
    if sl > 0:
        ax.axhline(y=sl, color="#ff4466", linestyle="--", linewidth=1.0, alpha=0.8, label=f"SL ${sl:.2f}", zorder=1)

    # TPs — green dashed
    for label, val in [("TP1", tp1), ("TP2", tp2), ("TP3", tp3)]:
        if val > 0:
            ax.axhline(y=val, color="#00ff88", linestyle="--", linewidth=0.8, alpha=0.7, label=f"{label} ${val:.2f}", zorder=1)

    # Entry marker — green triangle up
    if 0 <= entry_idx < len(df):
        ax.scatter(
            [df.index[entry_idx]], [entry_price],
            marker="^", color="#00ff88", s=120, zorder=5, label=f"Entry ${entry_price:.2f}"
        )

    # Close marker — red triangle down
    if 0 <= close_idx < len(df):
        ax.scatter(
            [df.index[close_idx]], [close_price],
            marker="v", color="#ff4466", s=120, zorder=5, label=f"Exit ${close_price:.2f} ({pnl_label})"
        )

    # TSL move dots — orange
    if tsl_dates:
        ax.scatter(tsl_dates, tsl_prices, marker="o", color="#f97316", s=40, zorder=4, label="TSL moved", alpha=0.85)

    # Axes formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30)
    ax.tick_params(colors="#8899aa", labelsize=8)
    ax.spines["bottom"].set_color("#1a2535")
    ax.spines["top"].set_color("#1a2535")
    ax.spines["left"].set_color("#1a2535")
    ax.spines["right"].set_color("#1a2535")
    ax.yaxis.label.set_color("#8899aa")
    ax.xaxis.label.set_color("#8899aa")

    # Title
    title_color = "#00ff88" if pnl_pct >= 0 else "#ff4466"
    ax.set_title(
        f"{ticker}  —  {entry_date_str} to {close_date_str}  —  {pnl_label}",
        color=title_color, fontsize=11, fontweight="bold", pad=10
    )

    # Legend
    legend = ax.legend(
        fontsize=7, loc="upper left",
        facecolor="#0a0f18", edgecolor="#1a2535", labelcolor="#c0c0c0"
    )

    plt.tight_layout(pad=1.0)

    # ── Save locally ──────────────────────────────────────────────────────────
    filename   = f"{ticker}_{sig_id}.png"
    local_path = REPORTS_DIR / filename
    try:
        fig.savefig(str(local_path), dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    except Exception as e:
        logger.warning(f"[CHART] {ticker}: savefig failed: {e}")
        plt.close(fig)
        return None
    finally:
        plt.close(fig)

    logger.info(f"[CHART] {ticker}: saved to {local_path}")

    # ── Upload to Supabase Storage ────────────────────────────────────────────
    public_url = _upload_to_supabase(local_path, filename)
    if public_url:
        logger.info(f"[CHART] {ticker}: uploaded → {public_url}")
        return public_url

    # Fallback: return local path string
    return str(local_path)
