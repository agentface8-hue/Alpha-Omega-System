@echo off
del /f C:\Users\asus\Alpha-Omega-System\.git\HEAD.lock 2>nul
del /f C:\Users\asus\Alpha-Omega-System\.git\index.lock 2>nul
cd /d C:\Users\asus\Alpha-Omega-System\frontend
call npm run build
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
cd /d C:\Users\asus\Alpha-Omega-System
git add core/universe_builder.py core/sector_ranker.py core/portfolio_manager.py backend/main.py frontend/src/components/ScanDashboard.jsx
git commit -m "feat: >$10B universe builder + sector momentum ranker + smart scan UI"
git push origin main
git push vercel main
echo DONE
