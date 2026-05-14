@echo off
cd /d C:\Users\asus\Alpha-Omega-System
if exist .git\index.lock del /f .git\index.lock
git add core\momentum_screener.py core\portfolio_manager.py core\universe_builder.py backend\main.py
git commit -m "feat: momentum pre-screener covers all 377 stocks fairly with sector bias"
git push origin main
git push vercel main
echo DONE
