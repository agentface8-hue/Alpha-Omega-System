@echo off
cd /d C:\Users\asus\Alpha-Omega-System

echo Clearing any git lock files...
del /f .git\index.lock 2>nul
del /f .git\HEAD.lock 2>nul
del /f .git\COMMIT_EDITMSG.lock 2>nul

echo Staging files...
git add core/telegram_alerts.py core/telegram_agent.py

echo Current git status:
git status

echo Committing...
git commit -m "fix: route all Telegram alerts to alphaomega group only"

echo Pushing...
git push origin main

echo Done!
pause
