import React, { useState, useEffect } from 'react';
import { API_BASE } from '../utils/api';

const TICKERS = ['NVDA','AAPL','MSFT','GOOGL','AMZN','META','TSLA','PLTR'];

const TopStocks = ({ onSelectTicker, compact = false }) => {
    const [stocks, setStocks] = useState(
        TICKERS.map(s => ({ symbol: s, price: null, change: null, loading: true }))
    );

    useEffect(() => {
        const fetchPrices = async () => {
            try {
                const apiUrl = API_BASE;
                const res = await fetch(`${apiUrl}/api/prices`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbols: TICKERS })
                });
                if (res.ok) {
                    const data = await res.json();
                    setStocks(data.prices || []);
                }
            } catch (e) {
                console.warn('Price fetch failed, using fallback');
            }
        };
        fetchPrices();
        const interval = setInterval(fetchPrices, 60000); // refresh every 60s
        return () => clearInterval(interval);
    }, []);

    return (
        <div className={`top-stocks ${compact ? 'top-stocks-compact' : ''}`}>
            <div className="widget-header">
                <span className="widget-icon">🔥</span>
                <span className="widget-title">TOP MOVERS</span>
            </div>
            <div className="stocks-grid">
                {stocks.map(stock => (
                    <div
                        key={stock.symbol}
                        className="stock-card"
                        onClick={() => onSelectTicker && onSelectTicker(stock.symbol)}
                        title={`Analyze ${stock.symbol}`}
                    >
                        <div className="stock-symbol">{stock.symbol}</div>
                        <div className="stock-price">
                            {stock.price ? `$${stock.price.toFixed(2)}` : '...'}
                        </div>
                        <div className={`stock-change ${stock.change >= 0 ? 'positive' : 'negative'}`}>
                            {stock.change != null
                                ? `${stock.change >= 0 ? '▲' : '▼'} ${Math.abs(stock.change).toFixed(2)}%`
                                : ''}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default TopStocks;
