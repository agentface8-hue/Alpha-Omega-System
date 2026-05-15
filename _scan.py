f = open('C:/Users/asus/Alpha-Omega-System/core/printing_portfolio.py', 'rb').read().decode('utf-8', errors='replace')
lines = f.split('\n')
keywords = ['yf.', 'yfinance', 'live_price', 'Ticker(', 'history(']
for i, l in enumerate(lines):
    if any(k in l for k in keywords):
        print(i+1, l[:120])
