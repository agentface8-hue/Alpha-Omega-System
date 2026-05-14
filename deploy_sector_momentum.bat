@echo off
cd /d C:\Users\asus\Alpha-Omega-System
if exist .git\index.lock del /f .git\index.lock
git add backend\main.py
git commit -m "feat: sector tab now loads top 30 by momentum score not market cap"
git push origin main
git push vercel main
echo DONE
