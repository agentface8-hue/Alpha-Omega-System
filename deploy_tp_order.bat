@echo off
del /f C:\Users\asus\Alpha-Omega-System\.git\HEAD.lock 2>nul
del /f C:\Users\asus\Alpha-Omega-System\.git\index.lock 2>nul
cd /d C:\Users\asus\Alpha-Omega-System
git add core/signal_tracker.py core/portfolio_manager.py
git commit -m "fix: TP ordering guardrail + DTP now pushes TP3 alongside TP1/TP2"
git push origin main
git push vercel main
echo DONE
