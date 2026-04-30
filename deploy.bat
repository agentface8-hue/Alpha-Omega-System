cd /d C:\Users\asus\Alpha-Omega-System\frontend
npx vite build
cd /d C:\Users\asus\Alpha-Omega-System
git add core/backtester.py frontend/src/components/BacktestDashboard.jsx
git commit -m "feat: buy-hold benchmark, profit factor, per-ticker breakdown in backtester"
git push origin main
git push vercel main
