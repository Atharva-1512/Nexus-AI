'use client';

import React, { useState, useEffect } from 'react';

interface CandleBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export default function CandlestickChart() {
  const [bars, setBars] = useState<CandleBar[]>([]);
  const [hoveredBar, setHoveredBar] = useState<CandleBar | null>(null);

  // Generate real-time updating 5-minute NIFTY 50 OHLC bars
  useEffect(() => {
    const generateInitialData = (): CandleBar[] => {
      const data: CandleBar[] = [];
      let base = 23900.0;
      const now = new Date();

      for (let i = 40; i >= 0; i--) {
        const timeStr = new Date(now.getTime() - i * 5 * 60 * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const change = (Math.random() - 0.47) * 25.0;
        const open = base;
        const close = Math.max(23500, open + change);
        const high = Math.max(open, close) + Math.random() * 12.0;
        const low = Math.min(open, close) - Math.random() * 12.0;
        const volume = Math.floor(Math.random() * 50000) + 15000;
        base = close;

        data.push({ time: timeStr, open, high, low, close, volume });
      }
      return data;
    };

    setBars(generateInitialData());

    // Update real-time 5-second tick
    const interval = setInterval(() => {
      setBars((prevBars) => {
        if (prevBars.length === 0) return prevBars;
        const last = { ...prevBars[prevBars.length - 1] };
        const tickMove = (Math.random() - 0.48) * 8.0;
        last.close = Number((last.close + tickMove).toFixed(2));
        last.high = Number(Math.max(last.high, last.close).toFixed(2));
        last.low = Number(Math.min(last.low, last.close).toFixed(2));

        const updated = [...prevBars];
        updated[updated.length - 1] = last;
        return updated;
      });
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  if (bars.length === 0) return <div className="h-80 flex items-center justify-center text-xs text-gray-500">Loading NIFTY 50 Live Chart...</div>;

  const activeBar = hoveredBar || bars[bars.length - 1];

  // SVG Chart Geometry
  const minPrice = Math.min(...bars.map((b) => b.low)) - 10;
  const maxPrice = Math.max(...bars.map((b) => b.high)) + 10;
  const priceRange = maxPrice - minPrice || 1;

  const svgWidth = 800;
  const svgHeight = 320;
  const paddingBottom = 25;
  const candleWidth = Math.max(4, (svgWidth / bars.length) * 0.65);

  const getY = (price: number) => {
    return svgHeight - paddingBottom - ((price - minPrice) / priceRange) * (svgHeight - paddingBottom - 20);
  };

  return (
    <div className="glass-panel p-5 rounded-2xl space-y-4 border border-blue-500/20 glow-blue">
      {/* Top Chart Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-800 pb-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-emerald-500 animate-ping"></span>
            <h3 className="text-lg font-bold text-white tracking-wide">NIFTY 50 — 5m Interactive Live Chart</h3>
          </div>
          <span className="text-xs font-mono bg-gray-900 border border-gray-700 px-2.5 py-1 rounded-md text-amber-400 font-semibold">
            Real-Time 5s Updates
          </span>
        </div>

        {/* OHLC Bar HUD Display */}
        <div className="flex items-center gap-4 font-mono text-xs bg-gray-900/80 px-3 py-1.5 rounded-lg border border-gray-800">
          <div><span className="text-gray-400">O: </span><span className="text-white font-bold">{activeBar.open.toFixed(2)}</span></div>
          <div><span className="text-gray-400">H: </span><span className="text-emerald-400 font-bold">{activeBar.high.toFixed(2)}</span></div>
          <div><span className="text-gray-400">L: </span><span className="text-rose-400 font-bold">{activeBar.low.toFixed(2)}</span></div>
          <div><span className="text-gray-400">C: </span><span className={`font-bold ${activeBar.close >= activeBar.open ? 'text-emerald-400' : 'text-rose-400'}`}>{activeBar.close.toFixed(2)}</span></div>
        </div>
      </div>

      {/* Candlestick SVG Container */}
      <div className="relative w-full overflow-hidden rounded-xl bg-[#0b101c] p-2 border border-gray-800">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-[340px] overflow-visible">
          {/* Horizontal Grid lines */}
          {[0.2, 0.4, 0.6, 0.8].map((ratio, idx) => {
            const y = (svgHeight - paddingBottom) * ratio;
            const priceVal = (maxPrice - ratio * priceRange).toFixed(1);
            return (
              <g key={idx}>
                <line x1="0" y1={y} x2={svgWidth} y2={y} stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
                <text x={svgWidth - 5} y={y - 4} fill="rgba(255,255,255,0.3)" fontSize="10" textAnchor="end" fontFamily="monospace">
                  {priceVal}
                </text>
              </g>
            );
          })}

          {/* Render Candlesticks */}
          {bars.map((bar, i) => {
            const x = (i / (bars.length - 1)) * (svgWidth - 60) + 20;
            const yOpen = getY(bar.open);
            const yClose = getY(bar.close);
            const yHigh = getY(bar.high);
            const yLow = getY(bar.low);
            const isBullish = bar.close >= bar.open;

            const candleColor = isBullish ? '#22c55e' : '#ef4444';
            const bodyTop = Math.min(yOpen, yClose);
            const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));

            return (
              <g
                key={i}
                onMouseEnter={() => setHoveredBar(bar)}
                onMouseLeave={() => setHoveredBar(null)}
                className="cursor-pointer transition-opacity hover:opacity-80"
              >
                {/* Wick */}
                <line x1={x} y1={yHigh} x2={x} y2={yLow} stroke={candleColor} strokeWidth="1.5" />
                {/* Body */}
                <rect
                  x={x - candleWidth / 2}
                  y={bodyTop}
                  width={candleWidth}
                  height={bodyHeight}
                  fill={candleColor}
                  rx="1"
                />
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
