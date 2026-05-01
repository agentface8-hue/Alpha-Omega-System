"""
telegram_agent.py â€” AI-powered Telegram bot for Alpha-Omega.
You message it â†’ Claude interprets â†’ system executes â†’ you get results.

Commands (natural language or slash):
  /status        â€” portfolio + signal tracker summary
  /scan          â€” run dual-direction scan
  /portfolio     â€” portfolio P&L snapshot
  /check         â€” refresh all prices now
  /open AAPL     â€” open long position on AAPL
  /short TSLA    â€” open short position on TSLA
  /close all     â€” close all open positions
  /close AAPL    â€” close specific position
  /signals       â€” active signals summary
  /autopilot     â€” run autopilot on all systems
  /regime        â€” current market regime + strategy mode
  /futures       â€” futures snapshot
  /learn         â€” run self-calibration now
  /help          â€” show all commands

Architecture:
  - Polls Telegram for new messages every 5s
  - Sends message text to Claude claude-sonnet-4-20250514 for intent parsing
  - Claude returns structured JSON: {action, params, reply}
  - Agent executes the action and sends result back to Telegram
"""
import os, json, time, logging, threading, urllib.request, urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

TOKEN       = os.environ.get("TELEGRAM_TOKEN", "8691159247:AAEfGEBQgXBqXvA9RCO67cFCwwtDaFrNRH4")
PERSONAL_ID = os.environ.get("TELEGRAM_PERSONAL_CHAT_ID", "5812682751")
GROUP_ID    = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "-5228475615")
BASE_URL    = f"https://api.telegram.org/bot{TOKEN}"

# Only accept commands from owner
ALLOWED_CHAT_IDS = {PERSONAL_ID, GROUP_ID}

_last_update_id = 0


# â”€â”€ Telegram helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _tg_request(method: str, data: dict) -> Optional[dict]:
    try:
        url  = f"{BASE_URL}/{method}"
        body = json.dumps(data).encode()
        req  = urllib.request.Request(url, data=body,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.error(f"[TG] {method} error: {e}")
        return None


def _send(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    result = _tg_request("sendMessage", {
        "chat_id": chat_id, "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    })
    return bool(result and result.get("ok"))


def _get_updates(offset: int) -> list:
    result = _tg_request("getUpdates", {
        "offset": offset, "timeout": 5, "allowed_updates": ["message"]
    })
    if result and result.get("ok"):
        return result.get("result", [])
    return []


# â”€â”€ Claude intent parser â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SYSTEM_PROMPT = """You are the AI agent for Alpha-Omega, an AI trading system.
Parse user messages and return ONLY a JSON object with:
{
  "action": one of: status|scan|portfolio|check|open_long|open_short|close|autopilot|regime|futures|learn|help|unknown,
  "ticker": ticker symbol if mentioned (e.g. "AAPL") or null,
  "close_all": true if user says "close all",
  "reply": short conversational reply to send back (max 2 sentences)
}

Examples:
"scan now" â†’ {"action":"scan","ticker":null,"close_all":false,"reply":"Running dual scan now..."}
"open NVDA" â†’ {"action":"open_long","ticker":"NVDA","close_all":false,"reply":"Opening NVDA long position..."}
"short TSLA" â†’ {"action":"open_short","ticker":"TSLA","close_all":false,"reply":"Opening TSLA short..."}
"close all" â†’ {"action":"close","ticker":null,"close_all":true,"reply":"Closing all positions..."}
"close AAPL" â†’ {"action":"close","ticker":"AAPL","close_all":false,"reply":"Closing AAPL..."}
"how is the portfolio" â†’ {"action":"portfolio","ticker":null,"close_all":false,"reply":"Checking portfolio..."}
"what's the market doing" â†’ {"action":"regime","ticker":null,"close_all":false,"reply":"Checking regime..."}
"run autopilot" â†’ {"action":"autopilot","ticker":null,"close_all":false,"reply":"Running autopilot..."}
Return ONLY valid JSON. No markdown, no explanation."""


def _parse_intent(text: str) -> Dict:
    """Parse user intent â€” Claude if API key available, else robust keyword fallback."""
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

    # â”€â”€ Robust keyword fallback (works with no API key) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    t = text.lower().strip().lstrip("/")

    # Extract ticker â€” any ALL-CAPS word 1-5 chars that's not a command word
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


# â”€â”€ Action executor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
                f"ðŸ“Š <b>System Status</b>\n"
                f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
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
                f"ðŸ• {datetime.utcnow().strftime('%H:%M UTC')}"
            )

        elif action == "scan":
            from core.printing_scanner import run_dual_scan
            scan = run_dual_scan()
            longs  = scan.get("longs", [])[:3]
            shorts = scan.get("shorts", [])[:3]
            mode   = scan.get("mode", {})
            lines  = [f"ðŸ” <b>Dual Scan Complete</b> â€” {mode.get('label','')}\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"]
            if longs:
                lines.append("ðŸ“ˆ <b>TOP LONGS</b>")
                for r in longs:
                    lines.append(f"  {r['ticker']} {r['conviction_pct']}% | TP1 ${r['tp1']:.2f} | SL ${r['sl']:.2f}")
            if shorts:
                lines.append("ðŸ“‰ <b>TOP SHORTS</b>")
                for r in shorts:
                    lines.append(f"  {r['ticker']} {r['conviction_pct']}% | TP1 ${r['tp1']:.2f} | SL ${r['sl']:.2f}")
            if not longs and not shorts:
                lines.append("No qualifying signals right now.")
            lines.append(f"ðŸ• {datetime.utcnow().strftime('%H:%M UTC')}")
            return "\n".join(lines)

        elif action == "portfolio":
            from core.portfolio_manager import get_portfolio
            pf   = get_portfolio()
            stat = pf.get("stats", {})
            st   = pf.get("state", {})
            open_pos = pf.get("open_positions", [])
            lines = [
                f"ðŸ’¼ <b>Portfolio</b>\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
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
                        f"  {p['ticker']} @ ${p['entry_price']} â†’ "
                        f"{'+' if upnl>=0 else ''}${upnl:.0f} "
                        f"({p.get('unrealized_pnl_pct',0):+.2f}%)"
                    )
            lines.append(f"ðŸ• {datetime.utcnow().strftime('%H:%M UTC')}")
            return "\n".join(lines)

        elif action == "check":
            from core.portfolio_manager import check_portfolio
            result = check_portfolio()
            stat   = result.get("portfolio", {}).get("stats", {})
            exits  = [u for u in result.get("updates", []) if u.get("action")]
            lines  = [
                f"ðŸ”„ <b>Prices Refreshed</b>\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
                f"Total P&L: {'+' if stat.get('total_pnl',0)>=0 else ''}${stat.get('total_pnl',0):,.0f}",
            ]
            if exits:
                lines.append("\n<b>Exits fired:</b>")
                for ex in exits:
                    lines.append(f"  {ex['ticker']}: {ex['action']}")
            else:
                lines.append("No exits triggered.")
            lines.append(f"ðŸ• {datetime.utcnow().strftime('%H:%M UTC')}")
            return "\n".join(lines)

        elif action == "open_long" and ticker:
            from core.market_data import fetch_ticker_data, fetch_market_regime
            from core.conviction_engine import score_ticker
            from core.portfolio_manager import open_position
            data    = fetch_ticker_data(ticker.upper())
            regime  = fetch_market_regime()
            scored  = score_ticker(data, regime)
            if scored.get("hard_fail"):
                return f"âš ï¸ <b>{ticker.upper()}</b> hard fail: {scored.get('hard_fail_reason','')}"
            result = open_position(
                ticker=ticker.upper(),
                entry_price=scored.get("entry_high", scored["last_close"]),
                sl=scored["sl"], tp1=scored["tp1"], tp2=scored["tp2"], tp3=scored["tp3"],
                conviction=scored["conviction_pct"],
            )
            if "error" in result:
                return f"âŒ Cannot open {ticker.upper()}: {result['error']}"
            return (
                f"âœ… <b>LONG OPENED â€” {ticker.upper()}</b>\n"
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
                return f"âš ï¸ <b>{ticker.upper()}</b> short fail: {scored.get('hard_fail_reason','')}"
            result = open_print_pos(
                ticker=ticker.upper(), direction="short",
                entry_price=scored["entry"],
                sl=scored["sl"], tp1=scored["tp1"],
                tp2=scored.get("tp2", scored["tp1"]),
                tp3=scored.get("tp3", scored["tp1"]),
                conviction=scored["conviction_pct"],
            )
            if "error" in result:
                return f"âŒ Cannot short {ticker.upper()}: {result['error']}"
            return (
                f"ðŸ“‰ <b>SHORT OPENED â€” {ticker.upper()}</b>\n"
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
                return "ðŸ“­ No open positions to close."
            if close_all:
                results = [close_position(p["id"]) for p in positions]
                total_pnl = sum(r.get("pnl", 0) for r in results if "pnl" in r)
                return (
                    f"ðŸ”’ <b>All positions closed</b>\n"
                    f"Closed: {len(results)} positions\n"
                    f"Total P&L: {'+' if total_pnl>=0 else ''}${total_pnl:.0f}"
                )
            elif ticker:
                pos = next((p for p in positions if p["ticker"] == ticker.upper()), None)
                if not pos:
                    return f"âŒ No open position found for {ticker.upper()}"
                r = close_position(pos["id"])
                return f"ðŸ”’ <b>Closed {ticker.upper()}</b>\nP&L: {'+' if r.get('pnl',0)>=0 else ''}${r.get('pnl',0):.0f}"

        elif action == "autopilot":
            from core.portfolio_manager import autopilot_fill
            result = autopilot_fill()
            opened = result.get("opened", [])
            if not opened:
                return f"ðŸ¤– Autopilot: {result.get('message', 'No qualifying signals')}"
            lines = [f"ðŸ¤– <b>Autopilot Filled {len(opened)} Slots</b>"]
            for o in opened:
                lines.append(f"  {o['ticker']} @ ${o['entry']:.2f} ({o['conviction']}%)")
            return "\n".join(lines)

        elif action == "regime":
            from core.market_data import fetch_market_regime
            from core.regime_engine import get_strategy_mode
            regime = fetch_market_regime()
            mode   = get_strategy_mode(regime)
            return (
                f"ðŸŒ¡ <b>Market Regime</b>\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
                f"Regime: <b>{regime['regime']}</b>\n"
                f"VIX: <b>{regime['vix']}</b>\n"
                f"SPY: ${regime['spy_close']} ({regime['spy_change_pct']:+.2f}%)\n\n"
                f"Strategy Mode: <b>{mode['label']}</b>\n"
                f"{mode['description']}\n"
                f"Longs: {'âœ…' if mode['long_enabled'] else 'âŒ'}  "
                f"Shorts: {'âœ…' if mode['short_enabled'] else 'âŒ'}\n"
                f"Edge: {mode['expected_edge']}"
            )

        elif action == "futures":
            from core.futures_data import fetch_all_futures
            data = fetch_all_futures()
            session = data.get("session", {})
            lines = [
                f"ðŸ“Š <b>Futures</b> â€” {session.get('et_time','')}\n"
                f"{session.get('label','')}\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
            ]
            for sym, f in data.get("futures", {}).items():
                if f.get("error"): continue
                trend_e = "ðŸŸ¢" if f["trend"]=="BULL" else "ðŸ”´"
                lines.append(
                    f"{trend_e} <b>{sym}</b> ${f['price']:,.2f} "
                    f"({f['change_pct']:+.2f}%) {f['trend']}"
                )
            return "\n".join(lines)

        elif action == "learn":
            from core.learning_loop import run_once
            result = run_once()
            if result.get("status") == "insufficient_data":
                return f"ðŸ“š {result['message']}"
            return (
                f"ðŸ§  <b>Calibration Complete</b>\n"
                f"Signals analyzed: {result.get('signals_analyzed', 0)}"
            )

        elif action == "help":
            return (
                "ðŸ¤– <b>Alpha-Omega AI Agent Commands</b>\n"
                "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
                "/status â€” full system summary\n"
                "/scan â€” run long + short scan\n"
                "/portfolio â€” portfolio P&L\n"
                "/check â€” refresh all prices\n"
                "/open AAPL â€” open long position\n"
                "/short TSLA â€” open short position\n"
                "/close AAPL â€” close position\n"
                "/close all â€” close everything\n"
                "/autopilot â€” auto-fill all slots\n"
                "/regime â€” market regime + strategy\n"
                "/futures â€” ES/NQ/CL/GC snapshot\n"
                "/learn â€” run self-calibration\n\n"
                "ðŸ’¬ Or just type naturally â€” I understand plain English."
            )

        return f"â“ Unknown action: {action}"

    except Exception as e:
        logger.error(f"[AGENT] Execute error: {e}", exc_info=True)
        return f"âš ï¸ Error executing {action}: {str(e)[:100]}"


# â”€â”€ Message handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _handle_message(update: dict):
    msg     = update.get("message", {})
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text    = msg.get("text", "").strip()

    if not text or chat_id not in ALLOWED_CHAT_IDS:
        return

    logger.info(f"[AGENT] Message from {chat_id}: {text[:80]}")

    # Parse intent with Claude
    intent = _parse_intent(text)
    action = intent.get("action", "unknown")
    ticker = intent.get("ticker")
    close_all = intent.get("close_all", False)

    # Send acknowledgement immediately
    ack = intent.get("reply", "Processing...")
    _send(chat_id, f"âš™ï¸ {ack}")

    # Execute and send result
    if action != "unknown":
        result = _execute(action, ticker, close_all)
        _send(chat_id, result)
    else:
        _send(chat_id, "â“ I didn't understand that. Type /help for available commands.")


# â”€â”€ Polling loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _poll_loop():
    global _last_update_id
    logger.info("[AGENT] Telegram polling started")
    while True:
        try:
            updates = _get_updates(_last_update_id + 1)
            for update in updates:
                _last_update_id = max(_last_update_id, update.get("update_id", 0))
                _handle_message(update)
        except Exception as e:
            logger.error(f"[AGENT] Poll error: {e}")
        time.sleep(4)   # poll every 4 seconds


def start():
    t = threading.Thread(target=_poll_loop, daemon=True, name="telegram_agent")
    t.start()
    logger.info("[AGENT] Telegram AI Agent started")
    # Send startup notification to group only
    try:
        _send(GROUP_ID,
            "ðŸ¤– <b>Alpha-Omega AI Agent Online</b>\n"
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
            "I'm monitoring the system 24/7.\n"
            "Type /help to see what I can do.\n"
            f"ðŸ• {datetime.utcnow().strftime('%H:%M UTC')}"
        )
    except:
        pass

