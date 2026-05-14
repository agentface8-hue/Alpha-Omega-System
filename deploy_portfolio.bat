@echo off
del /f C:\Users\asus\Alpha-Omega-System\.git\HEAD.lock 2>nul
del /f C:\Users\asus\Alpha-Omega-System\.git\index.lock 2>nul
cd /d C:\Users\asus\Alpha-Omega-System\frontend
call npm run build
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
cd /d C:\Users\asus\Alpha-Omega-System
git add frontend/src/components/PortfolioTab.jsx frontend/dist
git commit -m "feat: show current price and D delay badge next to ticker name"
git push origin main
git push vercel main
echo DONE
