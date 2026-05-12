import React, { useState, useEffect, useRef } from 'react';

// CoinGecko (free, no key) → BTC, ETH, PAXG (PAX Gold ≈ XAU spot, 1 oz peg)
const CG_URL = 'https://api.coingecko.com/api/v3/simple/price' +
    '?ids=bitcoin,ethereum,pax-gold' +
    '&vs_currencies=usd&include_24hr_change=true&precision=2';

// ExchangeRate-API (free, no key) → EUR, GBP, JPY vs USD
const FX_URL = 'https://open.er-api.com/v6/latest/USD';

const ASSET_DEFS = [
    { id: 'bitcoin',  symbol: 'BTC',     icon: '₿',  decimals: 2, source: 'cg' },
    { id: 'ethereum', symbol: 'ETH',     icon: 'Ξ',  decimals: 2, source: 'cg' },
    { id: 'pax-gold', symbol: 'XAU',     icon: '🥇', decimals: 2, source: 'cg' },
    { id: 'eurusd',   symbol: 'EUR/USD', icon: '€',  decimals: 4, source: 'fx' },
    { id: 'gbpusd',   symbol: 'GBP/USD', icon: '£',  decimals: 4, source: 'fx' },
    { id: 'usdjpy',   symbol: 'USD/JPY', icon: '¥',  decimals: 2, source: 'fx' },
];

const LiveTicker = () => {
    const [assets, setAssets] = useState(
        ASSET_DEFS.map(a => ({ ...a, price: null, change: null, flash: null }))
    );
    // Store first-fetch fx prices so we can compute an intra-session change %
    const fxBaseline = useRef({});
    const prevPrices  = useRef({});

    const fetchAll = async () => {
        try {
            const [cgRes, fxRes] = await Promise.allSettled([
                fetch(CG_URL),
                fetch(FX_URL),
            ]);

            let cg = {};
            let fxRates = {};

            if (cgRes.status === 'fulfilled' && cgRes.value.ok) {
                cg = await cgRes.value.json();
            }
            if (fxRes.status === 'fulfilled' && fxRes.value.ok) {
                const fxJson = await fxRes.value.json();
                fxRates = fxJson.rates || {};
            }

            // Derived forex prices (USD as base → invert for EUR and GBP pairs)
            const fxPrices = {
                eurusd: fxRates.EUR ? 1 / fxRates.EUR : null,
                gbpusd: fxRates.GBP ? 1 / fxRates.GBP : null,
                usdjpy: fxRates.JPY || null,
            };

            // Store baseline on first successful fetch
            Object.entries(fxPrices).forEach(([id, price]) => {
                if (price != null && fxBaseline.current[id] == null) {
                    fxBaseline.current[id] = price;
                }
            });

            setAssets(prev => prev.map(asset => {
                let price = null;
                let change = null;
                let flash = null;

                if (asset.source === 'cg') {
                    const d = cg[asset.id];
                    if (d) {
                        price  = d.usd;
                        change = d.usd_24h_change ?? null;
                    }
                } else {
                    price = fxPrices[asset.id];
                    const base = fxBaseline.current[asset.id];
                    if (price != null && base != null) {
                        change = ((price - base) / base) * 100;
                    }
                }

                // Flash direction vs previous price
                const prev = prevPrices.current[asset.id];
                if (price != null && prev != null) {
                    flash = price > prev ? 'flash-green' : price < prev ? 'flash-red' : null;
                }
                if (price != null) prevPrices.current[asset.id] = price;

                return { ...asset, price, change, flash };
            }));

            // Clear flash after animation
            setTimeout(() => {
                setAssets(prev => prev.map(a => ({ ...a, flash: null })));
            }, 600);

        } catch (err) {
            console.warn('[LiveTicker] fetch error:', err);
        }
    };

    useEffect(() => {
        fetchAll();
        const interval = setInterval(fetchAll, 60_000); // refresh every 60 s
        return () => clearInterval(interval);
    }, []);

    const fmt = (asset) => {
        if (asset.price == null) return '···';
        return asset.price.toFixed(asset.decimals);
    };

    return (
        <div className="live-ticker">
            <div className="ticker-track">
                {assets.map(asset => (
                    <div key={asset.id} className={`ticker-item ${asset.flash || ''}`}>
                        <span className="ticker-icon">{asset.icon}</span>
                        <span className="ticker-symbol">{asset.symbol}</span>
                        <span className="ticker-price">{fmt(asset)}</span>
                        <span className={`ticker-change ${(asset.change ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                            {asset.change != null
                                ? `${asset.change >= 0 ? '+' : ''}${asset.change.toFixed(2)}%`
                                : ''}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default LiveTicker;
