@echo off
cd /d C:\Users\asus\Alpha-Omega-System
if exist .git\index.lock del /f .git\index.lock
git add core\sector_ranker.py frontend\src\components\ScanDashboard.jsx
git commit -m "feat: 3-ETF sector ranking SPDR iShares Vanguard averaged"
git push origin main
git push vercel main
echo DONE
