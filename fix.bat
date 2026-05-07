cd /d C:\Users\asus\Alpha-Omega-System\frontend
npx vite build
cd /d C:\Users\asus\Alpha-Omega-System
git add core/backtester.py core/conviction_engine.py frontend/src/components/BacktestDashboard.jsx frontend/src/components/ScanDashboard.jsx
git commit -m "profit-density-rotation-benchmark-ema-slope-exit"
git push origin main
git push vercel main
