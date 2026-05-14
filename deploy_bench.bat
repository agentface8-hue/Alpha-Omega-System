@echo off
cd /d C:\Users\asus\Alpha-Omega-System
if exist .git\index.lock del /f .git\index.lock
git add core\portfolio_manager.py backend\main.py
git commit -m "feat: shared scan cache - autopilot saves results, bench reads same 30-stock scan"
git push origin main
git push vercel main
echo DONE
