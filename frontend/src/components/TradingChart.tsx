'use client';

import React, { useEffect, useRef, useState, useImperativeHandle, forwardRef } from 'react';

// ─── Interfaces for Future Overlay Compatibility ──────────────────────────────
export interface ChartOverlayMarker {
  id: string;
  time: number;
  position: 'aboveBar' | 'belowBar' | 'inBar';
  color: string;
  shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square';
  text: string;
}

export interface ChartOverlayLine {
  id: string;
  price: number;
  color: string;
  lineWidth?: number;
  lineStyle?: number;
  label?: string;
}

export interface TradingChartProps {
  symbol?: string;
  interval?: string;
  theme?: 'dark' | 'light';
  timezone?: string;
  containerId?: string;
  markers?: ChartOverlayMarker[];
  lines?: ChartOverlayLine[];
}

export interface TradingChartRef {
  setSymbol: (symbol: string) => void;
  setInterval: (interval: string) => void;
  addMarker: (marker: ChartOverlayMarker) => void;
  clearMarkers: () => void;
  addLine: (line: ChartOverlayLine) => void;
  clearLines: () => void;
}

const INTERVAL_MAP: Record<string, string> = {
  '1m': '1',
  '3m': '3',
  '5m': '5',
  '15m': '15',
  '30m': '30',
  '1h': '60',
  '1d': 'D',
};

const TradingChart = forwardRef<TradingChartRef, TradingChartProps>(({
  symbol = 'NSE:NIFTY',
  interval = '5m',
  theme = 'dark',
  timezone = 'Asia/Kolkata',
  containerId = 'tradingview_advanced_chart',
  markers = [],
  lines = [],
}, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentSymbol, setCurrentSymbol] = useState<string>(symbol);
  const [currentInterval, setCurrentInterval] = useState<string>(interval);
  const [activeMarkers, setActiveMarkers] = useState<ChartOverlayMarker[]>(markers);
  const [activeLines, setActiveLines] = useState<ChartOverlayLine[]>(lines);

  // Imperative handle exposing methods for future AI engine overlays
  useImperativeHandle(ref, () => ({
    setSymbol: (newSymbol: string) => {
      setCurrentSymbol(newSymbol);
    },
    setInterval: (newInterval: string) => {
      setCurrentInterval(newInterval);
    },
    addMarker: (marker: ChartOverlayMarker) => {
      setActiveMarkers((prev) => [...prev.filter((m) => m.id !== marker.id), marker]);
    },
    clearMarkers: () => {
      setActiveMarkers([]);
    },
    addLine: (line: ChartOverlayLine) => {
      setActiveLines((prev) => [...prev.filter((l) => l.id !== line.id), line]);
    },
    clearLines: () => {
      setActiveLines([]);
    },
  }));

  useEffect(() => {
    if (!containerRef.current) return;

    setLoading(true);
    setError(null);
    containerRef.current.innerHTML = '';

    const tvInterval = INTERVAL_MAP[currentInterval] || currentInterval;

    // Create TradingView Embed Widget Container
    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'tradingview-widget-container';
    widgetContainer.style.height = '100%';
    widgetContainer.style.width = '100%';

    const widgetBody = document.createElement('div');
    widgetBody.className = 'tradingview-widget-container__widget';
    widgetBody.style.height = 'calc(100% - 32px)';
    widgetBody.style.width = '100%';

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;

    // TradingView Official Configuration (Supports NSE:NIFTY cleanly without popups)
    const widgetConfig = {
      autosize: true,
      symbol: currentSymbol,
      interval: tvInterval,
      timezone: timezone,
      theme: theme,
      style: '1',
      locale: 'en',
      enable_publishing: false,
      allow_symbol_change: true,
      calendar: false,
      support_host: 'https://www.tradingview.com',
      hide_side_toolbar: false,
      studies: [
        'STD;EMA',
        'STD;Volume',
        'STD;RSI',
        'STD;MACD',
        'STD;Bollinger_Bands',
        'STD;VWAP',
      ],
    };

    script.innerHTML = JSON.stringify(widgetConfig);

    widgetContainer.appendChild(widgetBody);
    widgetContainer.appendChild(script);
    containerRef.current.appendChild(widgetContainer);

    // Fade out loading spinner after script mount
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1200);

    return () => {
      clearTimeout(timer);
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [currentSymbol, currentInterval, timezone, theme]);

  return (
    <div className="w-full flex flex-col glass-panel rounded-2xl border border-blue-500/20 glow-blue overflow-hidden">
      {/* Top Header & Resolution Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-3 bg-[#0f172a]/90 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <h3 className="text-md font-bold text-white font-mono tracking-wide">
              {currentSymbol} — TradingView Advanced Candlestick Chart
            </h3>
          </div>
          <span className="text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/30 px-2.5 py-0.5 rounded-md font-semibold">
            Asia/Kolkata
          </span>
        </div>

        {/* Resolution Buttons (1m, 3m, 5m, 15m, 30m, 1h, 1d) */}
        <div className="flex items-center gap-1 bg-gray-900/90 p-1 rounded-lg border border-gray-800 text-xs">
          {['1m', '3m', '5m', '15m', '30m', '1h', '1d'].map((res) => (
            <button
              key={res}
              onClick={() => setCurrentInterval(res)}
              className={`px-2.5 py-1 rounded font-mono font-bold transition ${
                currentInterval === res
                  ? 'bg-blue-600 text-white shadow shadow-blue-500/40'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              {res.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chart Canvas Area */}
      <div className="relative w-full h-[600px] bg-[#0b101c]">
        {/* Loading Spinner */}
        {loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0b101c]/90 z-20 space-y-3">
            <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-xs font-mono text-gray-300">Loading TradingView Advanced Chart ({currentSymbol})...</p>
          </div>
        )}

        {/* Error Fallback Display */}
        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0b101c] z-20 space-y-3 p-6 text-center">
            <div className="text-rose-400 font-mono text-sm font-bold">⚠️ Chart Loading Error</div>
            <p className="text-xs text-gray-400 max-w-md">{error}</p>
          </div>
        )}

        {/* TradingView Container */}
        <div ref={containerRef} className="w-full h-full" />
      </div>

      {/* Overlay Status Bar */}
      {(activeMarkers.length > 0 || activeLines.length > 0) && (
        <div className="px-6 py-2 bg-gray-900/90 border-t border-gray-800 flex items-center gap-4 text-xs font-mono text-gray-300">
          <span>AI Overlays Active:</span>
          {activeMarkers.length > 0 && <span className="text-emerald-400">{activeMarkers.length} Markers</span>}
          {activeLines.length > 0 && <span className="text-amber-400">{activeLines.length} Target/SL Lines</span>}
        </div>
      )}
    </div>
  );
});

TradingChart.displayName = 'TradingChart';
export default TradingChart;
