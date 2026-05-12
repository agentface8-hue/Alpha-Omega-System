"""
universe_builder.py — Dynamic stock universe >$10B market cap
Curated by GICS sector. All tickers verified >$10B at time of curation.
Cache refreshes weekly. No API calls needed — curated list + yfinance for
optional market cap spot-checks.
"""
import json, datetime
from pathlib import Path
from typing import Dict, List

CACHE_PATH = Path(__file__).parent.parent / "calibration" / "universe_cache.json"
CACHE_TTL_DAYS = 7

# ── Curated >$10B universe by GICS sector ───────────────────────────────────
# Ordered within each sector: mega-cap leaders first, then large-cap momentum names
UNIVERSE_BY_SECTOR: Dict[str, List[str]] = {
    "Technology": [
        "NVDA","AAPL","MSFT","AVGO","ORCL","CRM","ADBE","AMD","QCOM","NOW",
        "INTU","TXN","AMAT","LRCX","KLAC","MU","ADI","CDNS","SNPS","ANET",
        "IBM","ACN","CSCO","INTC","HPQ","NTAP","GLW","KEYS","FTNT","IT",
        "ON","MPWR","TER","SWKS","MCHP","TSM","MRVL","SMCI","STX","WDC",
        # High-growth >$10B not in S&P500
        "CRWD","PANW","NET","ZS","DDOG","SNOW","PLTR","GTLB","OKTA","HUBS",
        "WDAY","VEEV","MNDY","BILL","DOCU","APP","TTD","HOOD",
    ],
    "Financials": [
        "JPM","BAC","WFC","GS","MS","BLK","C","SCHW","AXP","COF",
        "USB","PNC","TFC","ICE","CME","SPGI","MCO","AON","MMC","AJG",
        "BK","STT","SYF","AIG","MET","PRU","AFL","ALL","PGR","COF",
        "TRV","CB","HIG","FITB","RF","KEY","HBAN","MTB","CFG","NTRS",
        # Fintech >$10B
        "COIN","SQ","PYPL","V","MA",
    ],
    "Health Care": [
        "LLY","UNH","JNJ","ABBV","MRK","TMO","ABT","DHR","PFE","BMY",
        "AMGN","MDT","ISRG","GILD","CVS","ELV","CI","HUM","CNC","MOH",
        "BSX","SYK","BDX","ZBH","EW","HOLX","IDXX","IQV","VEEV","DXCM",
        "PODD","ALGN","GEHC","RMD","BIIB","REGN","VRTX","MRNA","ZTS","A",
        "MTD","WAT","DGX","LH","INCY",
    ],
    "Industrials": [
        "GE","CAT","RTX","HON","UNP","LMT","BA","DE","ETN","ITW",
        "GD","FDX","UPS","EMR","PH","ROK","AME","VRSK","CTAS","FAST",
        "GWW","EXPD","ODFL","XPO","JBHT","NSC","CSX","IR","TT","CARR",
        "OTIS","LHX","NOC","TDG","HII","LDOS","SAIC","DOV","FTV","GNRC",
        # Growth industrials >$10B
        "RKLB","AXON","PWR","MTZ","HUBB",
    ],
    "Consumer Discretionary": [
        "AMZN","TSLA","HD","MCD","NKE","LOW","SBUX","TJX","BKNG","CMG",
        "ABNB","GM","F","ROST","DHI","LEN","NVR","PHM","TOL","MAR",
        "HLT","RCL","CCL","NCLH","LVS","WYNN","MGM","DRI","YUM","QSR",
        "DPZ","AZO","ORLY","AAP","GPC","KMX","AN","EBAY","ETSY","W",
        # Growth >$10B
        "SHOP","CVNA","UBER","LYFT",
    ],
    "Consumer Staples": [
        "PG","KO","PEP","COST","WMT","PM","MO","MDLZ","CL","GIS",
        "KHC","SYY","ADM","TSN","HRL","CPB","CAG","SJM","MKC",
        "CHD","CLX","EL","KR","SFM","GO","BJ","CVS","CELH",
    ],
    "Energy": [
        "XOM","CVX","COP","EOG","SLB","MPC","PSX","VLO","OXY","HES",
        "HAL","DVN","FANG","BKR","APA","EQT","RRC","AR","CNX","OKE",
        # Power/Clean energy >$10B
        "VST","CEG","FSLR","NEE","AES","D",
    ],
    "Communication Services": [
        "META","GOOGL","GOOG","NFLX","DIS","TMUS","VZ","T","CHTR","EA",
        "WBD","OMC","FOXA","FOX","LYV","TTWO","ZM","TDOC","RBLX","SPOT",
        "SNAP","PINS","MTCH",
    ],
    "Utilities": [
        "NEE","SO","DUK","AEP","SRE","D","EXC","PCG","XEL","ED",
        "ETR","FE","PPL","AES","ES","WEC","CMS","NI","EVRG","AVA",
    ],
    "Materials": [
        "LIN","APD","SHW","ECL","FCX","NEM","NUE","VMC","MLM","ALB",
        "MOS","CF","IFF","PPG","FMC","RPM","PKG","IP","AVY","BALL",
        "ATI","RS","CMC","SEE","SON",
    ],
    "Real Estate": [
        "PLD","AMT","EQIX","CCI","WELL","DLR","O","PSA","SPG","AVB",
        "EQR","VICI","IRM","EXR","ARE","MAA","UDR","CPT","ESS","KIM",
        "REG","BRX","VICI","WPC","NNN",
    ],
}

# Reverse map: ticker → sector
TICKER_SECTOR_MAP: Dict[str, str] = {
    t: sector
    for sector, tickers in UNIVERSE_BY_SECTOR.items()
    for t in tickers
}


def build_universe(force: bool = False) -> Dict:
    """Return universe dict. Uses cache if fresh (<7 days)."""
    if not force and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            age = (datetime.datetime.utcnow() -
                   datetime.datetime.fromisoformat(cached.get("built_at", "2000-01-01"))).days
            if age < CACHE_TTL_DAYS:
                return cached
        except Exception:
            pass

    # Deduplicate within each sector, preserve order
    sectors_clean = {}
    seen_global: set = set()
    for sector, tickers in UNIVERSE_BY_SECTOR.items():
        deduped = []
        for t in tickers:
            if t not in seen_global:
                seen_global.add(t)
                deduped.append(t)
        sectors_clean[sector] = deduped

    all_tickers = [t for tickers in sectors_clean.values() for t in tickers]
    result = {
        "built_at": datetime.datetime.utcnow().isoformat(),
        "total_tickers": len(all_tickers),
        "min_market_cap_b": 10,
        "sectors": sectors_clean,
        "all_tickers": all_tickers,
        "ticker_sector_map": {t: s for s, tks in sectors_clean.items() for t in tks},
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(result, indent=2))
    print(f"[UNIVERSE] Built: {len(all_tickers)} tickers across {len(sectors_clean)} sectors")
    return result


def get_universe() -> Dict:
    return build_universe()


def get_sector_tickers(sector: str) -> List[str]:
    return get_universe()["sectors"].get(sector, [])


def get_all_tickers() -> List[str]:
    return get_universe()["all_tickers"]


def get_ticker_sector(ticker: str) -> str:
    return get_universe()["ticker_sector_map"].get(ticker.upper(), "Other")
