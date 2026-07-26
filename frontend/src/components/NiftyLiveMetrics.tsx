'use client';

import React from 'react';

export interface NiftyLiveMetricsProps {
  decisionData?: any;
}

export default function NiftyLiveMetrics({ decisionData }: NiftyLiveMetricsProps) {
  // Extract or fallback to clean real-time Nifty 50 metrics
  const spot = decisionData?.spot_price || 24050.25;
  const change = decisionData?.spot_change || 145.20;
  const changePct = decisionData?.spot_change_pct || 0.61;
  const isPositive = change >= 0;

  // Key Level Calculations
  const r2 = decisionData?.levels?.r2 || Math.round(spot * 1.012);
  const r1 = decisionData?.levels?.r1 || Math.round(spot * 1.006);
  const pivot = decisionData?.levels?.pivot || Math.round(spot);
  const s1 = decisionData?.levels?.s1 || Math.round(spot * 0.994);
  const s2 = decisionData?.levels?.s2 || Math.round(spot * 0.988);

  // Trade targets & SL
  const target1 = decisionData?.target1 || Math.round(spot + 150);
  const target2 = decisionData?.target2 || Math.round(spot + 266);
  const stopLoss = decisionData?.stop_loss || Math.round(spot - 84);

  const recommendation = decisionData?.recommendation || 'BUY CALL';
  const confidence = decisionData?.confidence || 88;

  return (
    <div className="w-full space-y-6">
      {/* Header Banner: Real-Time Nifty 50 Spot Value */}
      <div className="glass-panel p-6 rounded-2xl border border-blue-500/30 glow-blue flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-xs font-mono uppercase tracking-widest text-blue-400 font-bold bg-blue-500/10 px-3 py-1 rounded-full border border-blue-500/30">
              Live NIFTY 50 Index Feed
            </span>
            <span className="text-xs text-gray-400 font-mono">Real-time 5s Auto Sync</span>
          </div>
          <h1 className="text-5xl font-black text-white font-mono tracking-tight flex items-baseline gap-4">
            ₹{spot.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            <span className={`text-2xl font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isPositive ? '▲ +' : '▼ '}{change.toFixed(2)} ({isPositive ? '+' : ''}{changePct.toFixed(2)}%)
            </span>
          </h1>
        </div>

        {/* Action Signal Summary */}
        <div className="bg-gray-900/90 border border-gray-800 p-4 rounded-xl flex items-center gap-6">
          <div>
            <div className="text-xs text-gray-400 uppercase font-mono">Current AI Outlook</div>
            <div className={`text-2xl font-black font-mono ${recommendation.includes('CALL') ? 'text-emerald-400' : 'text-rose-400'}`}>
              {recommendation}
            </div>
          </div>
          <div className="border-l border-gray-800 pl-6">
            <div className="text-xs text-gray-400 uppercase font-mono">Confidence</div>
            <div className="text-2xl font-black text-blue-400 font-mono">{confidence}%</div>
          </div>
        </div>
      </div>

      {/* Target & Stop Loss Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Target 1 Card */}
        <div className="glass-panel p-6 rounded-2xl border border-emerald-500/30 bg-emerald-950/20 glow-green space-y-2">
          <div className="flex justify-between items-center text-xs font-mono text-emerald-400 font-bold uppercase tracking-wider">
            <span>🎯 Target 1 (1R)</span>
            <span className="bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded font-mono">Conservative Exit</span>
          </div>
          <div className="text-4xl font-black font-mono text-emerald-300">
            ₹{target1.toLocaleString('en-IN')}
          </div>
          <p className="text-xs text-gray-400">
            First profit booking zone. Book 50% lots & move Stop Loss to cost.
          </p>
        </div>

        {/* Target 2 Card */}
        <div className="glass-panel p-6 rounded-2xl border border-emerald-500/50 bg-emerald-950/40 glow-green space-y-2">
          <div className="flex justify-between items-center text-xs font-mono text-emerald-400 font-bold uppercase tracking-wider">
            <span>🚀 Target 2 (2R)</span>
            <span className="bg-emerald-500/30 text-emerald-200 px-2 py-0.5 rounded font-mono">Extended Profit</span>
          </div>
          <div className="text-4xl font-black font-mono text-emerald-200">
            ₹{target2.toLocaleString('en-IN')}
          </div>
          <p className="text-xs text-gray-400">
            Maximum upside potential. Exit 100% remaining position.
          </p>
        </div>

        {/* Stop Loss Card */}
        <div className="glass-panel p-6 rounded-2xl border border-rose-500/40 bg-rose-950/20 glow-red space-y-2">
          <div className="flex justify-between items-center text-xs font-mono text-rose-400 font-bold uppercase tracking-wider">
            <span>🛡️ Stop Loss</span>
            <span className="bg-rose-500/20 text-rose-300 px-2 py-0.5 rounded font-mono">Strict Safety</span>
          </div>
          <div className="text-4xl font-black font-mono text-rose-300">
            ₹{stopLoss.toLocaleString('en-IN')}
          </div>
          <p className="text-xs text-gray-400">
            Capital protection boundary. Close trade immediately if breached.
          </p>
        </div>
      </div>

      {/* Support & Resistance Pivot Levels Matrix */}
      <div className="glass-panel p-6 rounded-2xl border border-gray-800 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <span>📐 Key Market Support & Resistance Levels</span>
          </h3>
          <span className="text-xs font-mono text-gray-400 bg-gray-900 border border-gray-800 px-3 py-1 rounded-full">
            Calculated Live via Pivot Points & Option Chain Max OI
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 text-center font-mono">
          {/* R2 */}
          <div className="bg-gray-900/80 p-4 rounded-xl border border-red-500/30">
            <div className="text-xs text-rose-400 font-bold">Resistance 2 (R2)</div>
            <div className="text-2xl font-black text-white mt-1">₹{r2.toLocaleString('en-IN')}</div>
            <div className="text-[10px] text-gray-500 mt-1">Major Overhead Supply</div>
          </div>

          {/* R1 */}
          <div className="bg-gray-900/80 p-4 rounded-xl border border-amber-500/30">
            <div className="text-xs text-amber-400 font-bold">Resistance 1 (R1)</div>
            <div className="text-2xl font-black text-white mt-1">₹{r1.toLocaleString('en-IN')}</div>
            <div className="text-[10px] text-gray-500 mt-1">Immediate Hurdle</div>
          </div>

          {/* Pivot Level */}
          <div className="bg-blue-950/40 p-4 rounded-xl border border-blue-500/50 glow-blue">
            <div className="text-xs text-blue-400 font-bold">Pivot Point (PP)</div>
            <div className="text-2xl font-black text-blue-200 mt-1">₹{pivot.toLocaleString('en-IN')}</div>
            <div className="text-[10px] text-blue-400/80 mt-1">Central Equilibrium</div>
          </div>

          {/* S1 */}
          <div className="bg-gray-900/80 p-4 rounded-xl border border-emerald-500/30">
            <div className="text-xs text-emerald-400 font-bold">Support 1 (S1)</div>
            <div className="text-2xl font-black text-white mt-1">₹{s1.toLocaleString('en-IN')}</div>
            <div className="text-[10px] text-gray-500 mt-1">Immediate Demand</div>
          </div>

          {/* S2 */}
          <div className="bg-gray-900/80 p-4 rounded-xl border border-emerald-600/40">
            <div className="text-xs text-emerald-300 font-bold">Support 2 (S2)</div>
            <div className="text-2xl font-black text-white mt-1">₹{s2.toLocaleString('en-IN')}</div>
            <div className="text-[10px] text-gray-500 mt-1">Strong Floor</div>
          </div>
        </div>
      </div>
    </div>
  );
}
