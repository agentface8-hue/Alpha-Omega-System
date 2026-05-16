# ALPHA-OMEGA DECISIONS LOG
# Every architectural/integration decision with reasoning and outcome
# Format: DATE | DECISION | WHY | OUTCOME

---

## 2026-05-16

| Decision | Why | Outcome |
|---|---|---|
| Google Sheets REMOVED | OAuth invalid_grant from Render Oregon IP | Replaced with Airtable |
| Airtable ADDED | Permanent API key, no OAuth, no expiry | GREEN - working |
| Alpha Vantage -> Finnhub | AV: 25 calls/day, always failing | Finnhub: 60/min free, real-time |
| Render upgraded $25/month | Remove cold starts, persistent processes | Done |
| trade_log.py: Sheets -> Airtable | Sheets broken, Airtable never called on close | Fixed - raw signal dict passed directly |
| price_feed.py: AV -> Finnhub | AV broken, portfolio prices were stale | Fixed - portfolio_manager gets real prices |
| AI health agent: 24h cooldown | Was re-applying fixes every 30min | Fixed - calibration_params.json stores cooldowns |
| Health alerts: RED only | Telegram was spamming every YELLOW | Fixed |
| Dream Log: /api/dreams/latest | Health check hitting wrong endpoint (404) | Fixed |
| LLM Council skill installed | Need adversarial pressure-testing | Installed at ~/.claude/skills/llm-council |

## PENDING DECISIONS
- Should Signal Tracker and Portfolio be merged? (Council 4/5 said yes)
- Dreaming Agent: fix or remove? (0 dreams ever logged)
- Migrate calibration_params.json to Supabase (survive Render deploys)?
