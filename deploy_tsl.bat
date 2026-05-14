@echo off
del /f C:\Users\asus\Alpha-Omega-System\.git\HEAD.lock 2>nul
del /f C:\Users\asus\Alpha-Omega-System\.git\index.lock 2>nul
cd /d C:\Users\asus\Alpha-Omega-System\frontend
call npm run build
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
cd /d C:\Users\asus\Alpha-Omega-System
git add core/portfolio_manager.py frontend/src/components/PortfolioTab.jsx
git commit -m "fix: ATR refresh + TSL ratchet in check_portfolio — SL now moves up with real ATR"
git push origin main
git push vercel main
echo DONE
