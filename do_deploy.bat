@echo off
cd /d C:\Users\asus\Alpha-Omega-System
del .git\index.lock 2>nul
del .git\HEAD.lock 2>nul
git add frontend/src/components/SignalTracker.jsx
git commit -m "fix: legacy signal compatibility - EntryReasonPanel placeholder + visible action log"
git push origin main
echo DONE
