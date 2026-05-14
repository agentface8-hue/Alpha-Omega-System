@echo off
cd /d C:\Users\asus\Alpha-Omega-System
del /f .git\HEAD.lock 2>nul
del /f .git\index.lock 2>nul
git add backend/main.py
git commit -m "fix: numpy encoder for SSE complete event"
git push origin main
git push vercel main
