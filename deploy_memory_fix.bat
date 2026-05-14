@echo off
cd /d C:\Users\asus\Alpha-Omega-System
if exist .git\index.lock del /f .git\index.lock
git add core\momentum_screener.py
git commit -m "fix: chunk momentum screener to 50 tickers to prevent OOM on Render"
git push origin main
git push vercel main
echo DONE
