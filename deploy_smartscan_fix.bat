@echo off
cd /d C:\Users\asus\Alpha-Omega-System
if exist .git\index.lock del /f .git\index.lock
git add frontend\src\components\ScanDashboard.jsx
git commit -m "fix: Smart Scan uses momentum screener"
git push origin main
git push vercel main
echo DONE
