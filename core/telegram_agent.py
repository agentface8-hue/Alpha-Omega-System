"""
telegram_agent.py — AI-powered Telegram bot for Alpha-Omega.
Bot: @AlphaOmegaCEO_bot

Commands (natural language or slash):
  /status        — portfolio + signal tracker summary
  /scan          — run dual-direction scan
  /portfolio     — portfolio P&L snapshot
  /check         — refresh all prices now
  /open AAPL     — open long position on AAPL
  /short TSLA    — open short position on TSLA
  /close all     — close all open positions
  /close AAPL    — close specific position
  /signals       — active signals summary
  /autopilot     — run autopilot on all systems
  /regime        — current market regime + strategy mode
  /futures       — futures snapshot
  /learn         — run self-calibration now
  /help          — show all commands

Architecture:
  - Polls Telegram for new messages every 5s
  - Sends message text to Gemini for intent parsing
  - Returns structured JSON: {action, params, reply}
  - Agent executes the action and sends result back to Telegram

FIX LOG:
  2026-05-01 — Fixed two bugs causing bot to ignore all messages:
    1. Webhook conflict: deleteWebhook is now called before polling starts.
       If a webhook was previously set, Telegram silently drops getUpdates.
    2. Group command stripping: /status@AlphaOmegaCEO_bot is now
       normalised to /status before intent parsing.
  2026-05-01 — New bot created: @AlphaOmegaCEO_bot (old bot deleted)
"""
import os, json, time, logging, threading, urllib.request, urllib.parse, urllib.error, socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

TOKEN       = os.environ.get("TELEGRAM_TOKEN", "")
PERSONAL_ID = os.environ.get("TELEGRAM_PERSONAL_CHAT_ID", "")
GROUP_ID    = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")
BASE_URL    = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""

# Only accept commands from owner
ALLOWED_CHAT_IDS = {x for x in (PERSONAL_ID, GROUP_ID) if x}

_last_update_id = 0
_POLL_LOCK_ID = "telegram_poll"
_POLL_TTL_S = 90
_on_render = bool(os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL"))


def _poll_enabled() -> bool:
    if not TOKEN:
        return False
    return os.environ.get("TELEGRAM_POLL_ENABLED", "true").lower() not in ("0", "false", "no")


def _instance_id() -> str:
    return (
        os.environ.get("RENDER_INSTANCE_ID")
        or os.environ.get("HOSTNAME")
        or socket.gethostname()
        or "local"
    )


def _sb_client():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def _acquire_poll_lock() -> bool:
    """Supabase lease — only one process may call getUpdates for this bot token."""
    sb = _sb_client()
    if not sb:
        return True
    now = datetime.utcnow()
    inst = _instance_id()
    try:
        r = sb.table("portfolio_state").select("data").eq("id", _POLL_LOCK_ID).execute()
        if r.data:
            lock = r.data[0].get("data") or {}
            holder = lock.get("holder")
            exp_raw = lock.get("expires_at")
            if holder and holder != inst and exp_raw:
                try:
                    exp_dt = datetime.fromisoformat(str(exp_raw).replace("Z", "")[:26])
                    if exp_dt > now:
                        return False
                except Exception:
                    pass
        expires = (now + timedelta(seconds=_POLL_TTL_S)).isoformat()
        sb.table("portfolio_state").upsert({
            "id": _POLL_LOCK_ID,
            "data": {"holder": inst, "expires_at": expires, "updated_at": now.isoformat()},
            "updated_at": now.isoformat(),
        }).execute()
        return True
    except Exception as e:
        logger.warning(f"[AGENT] poll lock skipped: {e}")
        return True


# ------ Telegram helpers -----------------------------------------------

def _tg_request(method: str, data: dict, *, quiet_409: bool = False) -> Optional[dict]:
    if not TOKEN:
        return None
    try:
        url  = f"{BASE_URL}/{method}"
        body = json.dumps(data).encode()
        req  = urllib.request.Request(url, data=body,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 409:
            if not quiet_409:
                logger.warning(f"[AGENT] Telegram 409 on {method} — another poller active")
            raise
        logger.error(f"[TG] {method} HTTP {e.code}: {e.reason}")
        return None
    except Exception as e:
        logger.error(f"[TG] {method} error: {e}")
        return None


def _get_updates(offset: int) -> list:
    result = _tg_request("getUpdates", {
        "offset": offset, "timeout": 5, "allowed_updates": ["message"]
    }, quiet_409=True)
    if result and result.get("ok"):
        return result.get("result", [])
    return []


def _send(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    result = _tg_request("sendMessage", {
        "chat_id": chat_id, "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    })
    return bool(result and result.get("ok"))


def _delete_webhook() -> bool:
    """
    Delete any existing webhook so long-polling works.
    If a webhook is registered, Telegram will NOT deliver updates via
    getUpdates — it silently drops them. This must run before polling starts.
    """
    try:
        result = _tg_request("deleteWebhook", {"drop_pending_updates": False})
        if result and result.get("ok"):
            logger.info("[AGENT] deleteWebhook OK — polling mode active")
            return True
        else:
            logger.warning(f"[AGENT] deleteWebhook unexpected response: {result}")
            return False
    except urllib.error.HTTPError:
        return False
    except Exception as e:
        logger.error(f"[AGENT] deleteWebhook error: {e}")
        return False


# ------ Intent parser --------------------------------------------------

SYSTEM_PROMPT = """You are the AI agent for Alpha-Omega, an AI trading system.
Parse user messages and return ONLY a JSON object with:
{
  "action": one of: status|scan|portfolio|check|open_long|open_short|close|autopilot|regime|futures|learn|help|unknown,
  "ticker": ticker symbol if mentioned (e.g. "AAPL") or null,
  "close_all": true if user says "close all",
  "reply": short conversational reply to send back (max 2 sentences)
}

Examples:
"scan now" → {"action":"scan","ticker":null,"close_all":false,"reply":"Running dual scan now..."}
"open NVDA" → {"action":"open_long","ticker":"NVDA","close_all":false,"reply":"Opening NVDA long position..."}
"short TSLA" → {"action":"open_short","ticker":"TSLA","close_all":false,"reply":"Opening TSLA short..."}
"close all" → {"action":"close","ticker":null,"close_all":true,"reply":"Closing all positions..."}
"close AAPL" → {"action":"close","ticker":"AAPL","close_all":false,"reply":"Closing AAPL..."}
"how is the portfolio" → {"action":"portfolio","ticker":null,"close_all":false,"reply":"Checking portfolio..."}
"what's the market doing" → {"action":"regime","ticker":null,"close_all":false,"reply":"Checking regime..."}
"run autopilot" → {"action":"autopilot","ticker":null,"close_all":false,"reply":"Running autopilot..."}
Return ONLY valid JSON. No markdown, no explanation."""


def _parse_intent(text: str) -> Dict:
    """Parse user intent — Gemini if API key available, else robust keyword fallback."""
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if api_key:
        try:
            import urllib.request as _ur
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            body = json.dumps({"contents": [{"parts": [{"text": SYSTEM_PROMPT + chr(10) + "User: " + text}]}], "generationConfig": {"maxOutputTokens": 200}}).encode()
            req = _ur.Request(url, data=body, headers={"Content-Type": "application/json"})
            with _ur.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read().decode())
            raw = resp["candidates"][0]["content"]["parts"][0]["text"].strip().replace("```json","").replace("```","").strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"[AGENT] Gemini parse failed, using fallback: {e}")

    # ------ Robust keyword fallback -----------------------------------
    t = text.lower().strip().lstrip("/")

    import re
    COMMANDS = {"status","scan","portfolio","check","open","short","close",
                "autopilot","regime","futures","learn","help","start","hi","hello"}
    tickers = [w for w in re.findall(r'\b[A-Z]{1,5}\b', text)
               if w not in COMMANDS and len(w) >= 1]
    ticker = tickers[0] if tickers else None
    close_all = "all" in t

    if any(x in t for x in ["help","command","what can","what do"]):
        return {"action":"help","ticker":None,"close_all":False,"reply":"Here are all commands:"}
    if any(x in t for x in ["status","overview","summary","how is"]):
        return {"action":"status","ticker":None,"close_all":False,"reply":"Getting full system status..."}
    if any(x in t for x in ["scan","find signal","look for","search"]):
        return {"action":"scan","ticker":None,"close_all":False,"reply":"Running dual scan now..."}
    if any(x in t for x in ["portfolio","my positions","positions","pnl","p&l","money","profit"]):
        return {"action":"portfolio","ticker":None,"close_all":False,"reply":"Checking portfolio..."}
    if any(x in t for x in ["check price","refresh","update price","check now"]):
        return {"action":"check","ticker":None,"close_all":False,"reply":"Refreshing prices..."}
    if any(x in t for x in ["open long","buy","go long","long "]) or t.startswith("open"):
        return {"action":"open_long","ticker":ticker,"close_all":False,"reply":f"Opening long on {ticker or '?'}..."}
    if any(x in t for x in ["short","sell short","go short"]):
        return {"action":"open_short","ticker":ticker,"close_all":False,"reply":f"Opening short on {ticker or '?'}..."}
    if any(x in t for x in ["close","exit","sell"]):
        return {"action":"close","ticker":ticker,"close_all":close_all,
                "reply":"Closing all..." if close_all else f"Closing {ticker or 'position'}..."}
    if any(x in t for x in ["autopilot","auto pilot","auto fill","autofill","auto-fill"]):
        return {"action":"autopilot","ticker":None,"close_all":False,"reply":"Running autopilot..."}
    if any(x in t for x in ["regime","market","vix","condition","environment"]):
        return {"action":"regime","ticker":None,"close_all":False,"reply":"Checking market regime..."}
    if any(x in t for x in ["future","es ","nq ","crude","gold","silver","futures"]):
        return {"action":"futures","ticker":None,"close_all":False,"reply":"Fetching futures..."}
    if any(x in t for x in ["learn","calibrat","train","improve","self"]):
        return {"action":"learn","ticker":None,"close_all":False,"reply":"Running self-calibration..."}
    if any(x in t for x in ["hi","hello","hey","start","ping","test","alive","online"]):
        return {"action":"status","ticker":None,"close_all":False,"reply":"Hey! I'm online and monitoring. Here's the current status:"}

    return {"action":"unknown","ticker":None,"close_all":False,
            "reply":"I didn't understand that. Type /help for all commands."}


# ------ Action executor ------------------------------------------------

def _execute(action: str, ticker: Optional[str], close_all: bool) -> str:
    """Execute the parsed action and return a formatted response string."""
    try:

        if action == "status":
            from core.signal_tracker import get_all_signals
            from core.portfolio_manager import get_portfolio
            sigs = get_all_signals()
            pf   = get_portfolio()
            stats   = sigs.get("stats", {})
            pf_stat = pf.get("stats", {})
            return (
                f"🤖 <b>System Status</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>Signal Tracker</b>\n"
                f"  Active: {stats.get('active_count',0)} signals\n"
                f"  Win rate: {stats.get('win_rate',0)}%\n"
                f"  TP1 rate: {stats.get('tp1_rate',0)}%\n"
                f"  Profit factor: {stats.get('profit_factor',0)}\n\n"
                f"<b>Portfolio</b>\n"
                f"  Value: ${pf_stat.get('total_value',25000):,.0f}\n"
                f"  P&L: {'+' if pf_stat.get('total_pnl',0)>=0 else ''}"
                f"${pf_stat.get('total_pnl',0):,.0f} ({pf_stat.get('total_pnl_pct',0):+.2f}%)\n"
                f"  Open: {pf_stat.get('open_count',0)} positions\n"
                f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
            )

        elif action == "scan":
            from core.printing_scanner import run_dual_scan
            scan = run_dual_scan()
            longs  = scan.get("longs", [])[:3]
            shorts = scan.get("shorts", [])[:3]
            mode   = scan.get("mode", {})
            lines  = [f"🔍 <b>Dual Scan Complete</b> — {mode.get('label','')}\n──────────────────"]
            if longs:
                lines.append("📈 <b>TOP LONGS</b>")
                for r in longs:
                    lines.append(f"  {r['ticker']} {r['conviction_pct']}% | TP1 ${r['tp1']:.2f} | SL ${r['sl']:.2f}")
            if shorts:
                lines.append("📉 <b>TOP SHORTS</b>")
                for r in shorts:
                    lines.append(f"  {r['ticker']} {r['conviction_pct']}% | TP1 ${r['tp1']:.2f} | SL ${r['sl']:.2f}")
            if not longs and not shorts:
                lines.append("No qualifying signals right now.")
            lines.append(f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}")
            return "\n".join(lines)

        elif action == "portfolio":
            from core.portfolio_manager import get_portfolio
            pf   = get_portfolio()
            stat = pf.get("stats", {})
            open_pos = pf.get("open_positions", [])
            lines = [
                f"💼 <b>Portfolio</b>\n──────────────────",
                f"Value: <b>${stat.get('total_value',0):,.2f}</b>",
                f"P&L: <b>{'+' if stat.get('total_pnl',0)>=0 else ''}${stat.get('total_pnl',0):,.2f}</b> ({stat.get('total_pnl_pct',0):+.2f}%)",
                f"Cash: ${stat.get('cash',0):,.2f}",
                f"Win rate: {stat.get('win_rate',0)}% ({stat.get('total_closed',0)} closed)\n",
            ]
            if open_pos:
                lines.append("<b>Open Positions:</b>")
                for p in open_pos:
                    upnl = p.get("unrealized_pnl", 0)
                    lines.append(
                        f"  {p['ticker']} @ ${p['entry_price']} — "
                        f"{'+' if upnl>=0 else ''}${upnl:.0f} "
                        f"({p.get('unrealized_pnl_pct',0):+.2f}%)"
                    )
            lines.append(f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}")
            return "\n".join(lines)

        elif action == "check":
            from core.portfolio_manager import check_portfolio
            result = check_portfolio()
            stat   = result.get("portfolio", {}).get("stats", {})
            exits  = [u for u in result.get("updates", []) if u.get("action")]
            lines  = [
                f"🔄 <b>Prices Refreshed</b>\n──────────────────",
                f"Total P&L: {'+' if stat.get('total_pnl',0)>=0 else ''}${stat.get('total_pnl',0):,.0f}",
            ]
            if exits:
                lines.append("\n<b>Exits fired:</b>")
                for ex in exits:
                    lines.append(f"  {ex['ticker']}: {ex['action']}")
            else:
                lines.append("No exits triggered.")
            lines.append(f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}")
            return "\n".join(lines)

        elif action == "open_long" and ticker:
            from core.market_data import fetch_ticker_data, fetch_market_regime
            from core.conviction_engine import score_ticker
            from core.portfolio_manager import open_position
            data    = fetch_ticker_data(ticker.upper())
            regime  = fetch_market_regime()
            scored  = score_ticker(data, regime)
            if scored.get("hard_fail"):
                return f"⛔ <b>{ticker.upper()}</b> hard fail: {scored.get('hard_fail_reason','')}"
            result = open_position(
                ticker=ticker.upper(),
                entry_price=scored.get("entry_high", scored["last_close"]),
                sl=scored["sl"], tp1=scored["tp1"], tp2=scored["tp2"], tp3=scored["tp3"],
                conviction=scored["conviction_pct"],
            )
            if "error" in result:
                return f"❌ Cannot open {ticker.upper()}: {result['error']}"
            return (
                f"✅ <b>LONG OPENED — {ticker.upper()}</b>\n"
                f"Entry: ${result['entry_price']:.2f}\n"
                f"SL: ${result['sl']:.2f} | TP1: ${result['tp1']:.2f}\n"
                f"Shares: {result['shares']} | Risk: ${result['risk_actual']:.0f}\n"
                f"Conviction: {result['conviction']}%"
            )

        elif action == "open_short" and ticker:
            from core.printing_scanner import score_short
            from core.market_data import fetch_ticker_data, fetch_market_regime
            from core.printing_portfolio import open_position as open_print_pos
            data   = fetch_ticker_data(ticker.upper())
            regime = fetch_market_regime()
            scored = score_short(data, regime)
            if scored.get("hard_fail"):
                return f"⛔ <b>{ticker.upper()}</b> short fail: {scored.get('hard_fail_reason','')}"
            result = open_print_pos(
                ticker=ticker.upper(), direction="short",
                entry_price=scored["entry"],
                sl=scored["sl"], tp1=scored["tp1"],
                tp2=scored.get("tp2", scored["tp1"]),
                tp3=scored.get("tp3", scored["tp1"]),
                conviction=scored["conviction_pct"],
            )
            if "error" in result:
                return f"❌ Cannot short {ticker.upper()}: {result['error']}"
            return (
                f"🔻 <b>SHORT OPENED — {ticker.upper()}</b>\n"
                f"Entry: ${result['entry_price']:.2f}\n"
                f"SL: ${result['sl']:.2f} | TP1: ${result['tp1']:.2f}\n"
                f"Shares: {result['shares']} | Risk: ${result['risk_usd']:.0f}\n"
                f"Conviction: {result['conviction']}%"
            )

        elif action == "close":
            from core.portfolio_manager import get_portfolio, close_position
            pf = get_portfolio()
            positions = pf.get("open_positions", [])
            if not positions:
                return "📭 No open positions to close."
            if close_all:
                results = [close_position(p["id"]) for p in positions]
                total_pnl = sum(r.get("pnl", 0) for r in results if "pnl" in r)
                return (
                    f"✅ <b>All positions closed</b>\n"
                    f"Closed: {len(results)} positions\n"
                    f"Total P&L: {'+' if total_pnl>=0 else ''}${total_pnl:.0f}"
                )
            elif ticker:
                pos = next((p for p in positions if p["ticker"] == ticker.upper()), None)
                if not pos:
                    return f"❌ No open position found for {ticker.upper()}"
                r = close_position(pos["id"])
                return f"✅ <b>Closed {ticker.upper()}</b>\nP&L: {'+' if r.get('pnl',0)>=0 else ''}${r.get('pnl',0):.0f}"

        elif action == "autopilot":
            from core.portfolio_manager import autopilot_fill
            result = autopilot_fill()
            opened = result.get("opened", [])
            if not opened:
                return f"🤖 Autopilot: {result.get('message', 'No qualifying signals')}"
            lines = [f"🚀 <b>Autopilot Filled {len(opened)} Slots</b>"]
            for o in opened:
                lines.append(f"  {o['ticker']} @ ${o['entry']:.2f} ({o['conviction']}%)")
            return "\n".join(lines)

        elif action == "regime":
            from core.market_data import fetch_market_regime
            from core.regime_engine import get_strategy_mode
            regime = fetch_market_regime()
            mode   = get_strategy_mode(regime)
            return (
                f"🌍 <b>Market Regime</b>\n──────────────────\n"
                f"Regime: <b>{regime['regime']}</b>\n"
                f"VIX: <b>{regime['vix']}</b>\n"
                f"SPY: ${regime['spy_close']} ({regime['spy_change_pct']:+.2f}%)\n\n"
                f"Strategy Mode: <b>{mode['label']}</b>\n"
                f"{mode['description']}\n"
                f"Longs: {'✅' if mode['long_enabled'] else '❌'}  "
                f"Shorts: {'✅' if mode['short_enabled'] else '❌'}\n"
                f"Edge: {mode['expected_edge']}"
            )

        elif action == "futures":
            from core.futures_data import fetch_all_futures
            data = fetch_all_futures()
            session = data.get("session", {})
            lines = [
                f"📊 <b>Futures</b> — {session.get('et_time','')}\n"
                f"{session.get('label','')}\n──────────────────"
            ]
            for sym, f in data.get("futures", {}).items():
                if f.get("error"): continue
                trend_e = "🟢" if f["trend"]=="BULL" else "🔴"
                lines.append(
                    f"{trend_e} <b>{sym}</b> ${f['price']:,.2f} "
                    f"({f['change_pct']:+.2f}%) {f['trend']}"
                )
            return "\n".join(lines)

        elif action == "learn":
            from core.learning_loop import run_once
            result = run_once()
            if result.get("status") == "insufficient_data":
                return f"📚 {result['message']}"
            return (
                f"🎓 <b>Calibration Complete</b>\n"
                f"Signals analyzed: {result.get('signals_analyzed', 0)}"
            )

        elif action == "help":
            return (
                "🤖 <b>Alpha-Omega AI Agent Commands</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "/status — full system summary\n"
                "/scan — run long + short scan\n"
                "/portfolio — portfolio P&L\n"
                "/check — refresh all prices\n"
                "/open AAPL — open long position\n"
                "/short TSLA — open short position\n"
                "/close AAPL — close position\n"
                "/close all — close everything\n"
                "/autopilot — auto-fill all slots\n"
                "/regime — market regime + strategy\n"
                "/futures — ES/NQ/CL/GC snapshot\n"
                "/learn — run self-calibration\n\n"
                "💬 Or just type naturally — I understand plain English."
            )

        return f"❓ Unknown action: {action}"

    except Exception as e:
        logger.error(f"[AGENT] Execute error: {e}", exc_info=True)
        return f"⚠️ Error executing {action}: {str(e)[:100]}"


# ------ Message handler ------------------------------------------------

def _handle_message(update: dict):
    msg     = update.get("message", {})
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text    = msg.get("text", "").strip()

    if not text or chat_id not in ALLOWED_CHAT_IDS:
        if text and chat_id not in ALLOWED_CHAT_IDS:
            logger.warning(f"[AGENT] Rejected message from unknown chat_id={chat_id!r} (allowed: {ALLOWED_CHAT_IDS})")
        return

    # Strip @botname suffix from group commands: /status@AlphaOmegaCEO_bot → /status
    if text.startswith("/") and "@" in text:
        text = text.split("@")[0]

    logger.info(f"[AGENT] Message from chat_id={chat_id}: {text[:80]}")

    intent    = _parse_intent(text)
    action    = intent.get("action", "unknown")
    ticker    = intent.get("ticker")
    close_all = intent.get("close_all", False)

    _send(chat_id, f"⏳ {intent.get('reply', 'Processing...')}")

    if action != "unknown":
        _send(chat_id, _execute(action, ticker, close_all))
    else:
        _send(chat_id, "❓ I didn't understand that. Type /help for available commands.")


# ------ Polling loop ---------------------------------------------------

# Max 3 concurrent heavy operations (scan, portfolio, autopilot)
# Prevents unbounded thread spawning → OOM on Render
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="tg_agent")

def _poll_loop():
    global _last_update_id
    logger.info("[AGENT] Telegram polling loop started")
    _consecutive_409 = 0
    _standby_logged = False
    while True:
        if not _acquire_poll_lock():
            if not _standby_logged:
                logger.info("[AGENT] Standby — another instance holds Telegram poll lock")
                _standby_logged = True
            time.sleep(20)
            continue
        _standby_logged = False
        try:
            updates = _get_updates(_last_update_id + 1)
            _consecutive_409 = 0
            for update in updates:
                _last_update_id = max(_last_update_id, update.get("update_id", 0))
                _executor.submit(_handle_message, update)
        except urllib.error.HTTPError as e:
            if e.code == 409:
                _consecutive_409 += 1
                wait = min(60, 5 * _consecutive_409)
                if _consecutive_409 <= 3 or _consecutive_409 % 5 == 0:
                    logger.warning(
                        f"[AGENT] 409 Conflict — another getUpdates poller active. "
                        f"Waiting {wait}s (attempt {_consecutive_409})"
                    )
                _delete_webhook()
                time.sleep(wait)
                continue
            logger.error(f"[AGENT] Poll HTTP error: {e}")
        except Exception as e:
            logger.error(f"[AGENT] Poll error: {e}")
        time.sleep(4)


def start():
    if not _poll_enabled():
        logger.info("[AGENT] Telegram polling disabled (no token or TELEGRAM_POLL_ENABLED=false)")
        return
    guard = 45 if _on_render else 10
    logger.info(f"[AGENT] Waiting {guard}s before polling (deploy guard)...")
    time.sleep(guard)
    logger.info("[AGENT] Deleting webhook before polling...")
    _delete_webhook()

    t = threading.Thread(target=_poll_loop, daemon=True, name="telegram_agent")
    t.start()
    logger.info("[AGENT] Telegram AI Agent started — @AlphaOmegaCEO_bot")

    try:
        _send(GROUP_ID,
            "🤖 <b>Alpha-Omega Trading — AI Agent Online</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Bot: @AlphaOmegaCEO_bot ✅\n"
            "Type /help to see what I can do.\n"
            f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
        )
    except Exception:
        pass
