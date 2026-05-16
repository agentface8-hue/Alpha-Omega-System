# ALPHA-OMEGA ROLLBACK PROCEDURES
# What to do when things break
# Last updated: 2026-05-16

---

## 1. Code change broke Render backend
```bash
git log --oneline -10          # find last working commit
git revert HEAD                # revert last commit
git push origin main           # triggers Render redeploy
curl https://alpha-omega-system.onrender.com/api/health/full
```

## 2. Airtable trade logging broken
1. GET /api/health/full -> check Airtable status
2. Check AIRTABLE_API_KEY in Render env vars
3. Check Render logs for [TradeLog] Airtable failed messages
4. Trades still go to local CSV while broken (ephemeral backup)
5. After fix: manually reload missed trades using bulk load pattern

## 3. Signals lost after Render deploy
- Active signals are in Supabase (persistent) - should survive
- If missing: re-run autopilot to create fresh signals
- calibration_params.json recreated on first close with defaults

## 4. Finnhub API stops working
```bash
curl "https://finnhub.io/api/v1/quote?symbol=SPY&token=YOUR_KEY"
```
- System falls back to yfinance automatically
- If key revoked: get new free key at finnhub.io, update FINNHUB_API_KEY on Render

## 5. IBKR order stuck / wrong position
1. Log in to IBKR TWS mobile app immediately
2. Manually close position in TWS
3. Set EXECUTOR_MODE=paper in Render env vars
4. Do NOT fix via code first - fix manually in TWS

## 6. Frontend (Vercel) broken
1. Vercel dashboard -> Deployments -> Promote previous deployment
2. OR: git revert HEAD && git push origin main

## 7. Full system reset (last resort)
```bash
# Backup first
curl https://alpha-omega-system.onrender.com/api/signals > backup.json
# Reset
curl -X POST https://alpha-omega-system.onrender.com/api/signals/clear
curl -X POST https://alpha-omega-system.onrender.com/api/calibration/reset
# Restart Render from dashboard
```
