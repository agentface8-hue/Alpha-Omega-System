@echo off
echo ===================================
echo  Alpha-Omega: Fix API URL + Deploy
echo ===================================

echo [1/3] Building frontend with correct API URL...
cd /d C:\Users\asus\Alpha-Omega-System\frontend
call npx vite build
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo [2/3] Committing fix...
cd /d C:\Users\asus\Alpha-Omega-System
git add frontend/.env.production frontend/dist/
git commit -m "fix: add .env.production so VITE_API_URL bakes in correctly (was 127.0.0.1:8000)"

echo [3/3] Deploying to Vercel...
git push origin main
git push vercel main

echo.
echo Done! Site will be live in ~30 seconds.
pause
