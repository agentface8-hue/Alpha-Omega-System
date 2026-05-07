@echo off
cd /d C:\Users\asus\Alpha-Omega-System
del .git\index.lock 2>nul
git add core/portfolio_manager.py frontend/src/components/PortfolioTab.jsx
git commit -m "Fix Auto-Fill: read max_positions from API, show Portfolio Full when slots=0"
git push origin main
