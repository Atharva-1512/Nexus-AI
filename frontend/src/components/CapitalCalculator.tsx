'use client';

import React, { useState } from 'react';

export interface CapitalCalculatorProps {
  decisionData?: any;
}

export default function CapitalCalculator({ decisionData }: CapitalCalculatorProps) {
  // User Capital State (Default ₹50,000)
  const [capital, setCapital] = useState<number>(50000);
  const [riskPct, setRiskPct] = useState<number>(2); // Risk 2% per trade

  // Extract live decision metrics or smart defaults
  const spot = decisionData?.spot_price || 24050;
  const recommendation = decisionData?.recommendation || 'BUY CALL';
  const confidence = decisionData?.confidence || 88;

  // Strike & Option Premium parameters
  const isCall = recommendation.includes('CALL');
  const strike = isCall ? Math.ceil(spot / 50) * 50 : Math.floor(spot / 50) * 50;
  const optionSymbol = `NIFTY ${strike} ${isCall ? 'CE' : 'PE'}`;

  // Option pricing math
  const lotSize = 75; // NIFTY Lot Size
  const estimatedPremium = decisionData?.suggested_premium || 220; // Premium per share in ₹
  const costPerLot = estimatedPremium * lotSize; // ₹16,500 per lot

  // Risk Management & Position Sizing Calculation
  const maxRiskAmount = (capital * riskPct) / 100; // e.g. 2% of ₹50,000 = ₹1,000
  const maxAffordableLots = Math.max(1, Math.floor(capital / costPerLot));
  const suggestedLots = Math.min(maxAffordableLots, Math.max(1, Math.floor(maxRiskAmount / (costPerLot * 0.3))));
  const totalInvestment = suggestedLots * costPerLot;
  const totalQty = suggestedLots * lotSize;

  // Profit & Exit Scenarios (1R & 2R Targets)
  const target1Premium = estimatedPremium * 1.5; // +50% Gain (150% of entry)
  const target2Premium = estimatedPremium * 2.0; // +100% Gain (200% of entry)
  const stopLossPremium = estimatedPremium * 0.7; // -30% Risk limit

  // Target 1 Financials
  const profitTarget1 = (target1Premium - estimatedPremium) * totalQty;
  const totalCapitalTarget1 = capital + profitTarget1;

  // Target 2 Financials
  const profitTarget2 = (target2Premium - estimatedPremium) * totalQty;
  const totalCapitalTarget2 = capital + profitTarget2;

  // Stop Loss Financials
  const maxLoss = (estimatedPremium - stopLossPremium) * totalQty;

  return (
    <div className="glass-panel p-6 rounded-2xl border border-blue-500/30 glow-blue space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <h3 className="text-xl font-black text-white font-mono tracking-wide">
              💰 AI Capital & Profit Calculator
            </h3>
          </div>
          <p className="text-xs text-gray-400 mt-1 font-mono">
            Enter your available trading capital to receive personalized lot sizing, profit targets & total portfolio growth.
          </p>
        </div>

        {/* Quick Capital Presets */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 font-mono">Presets:</span>
          {[25000, 50000, 100000, 250000].map((amt) => (
            <button
              key={amt}
              onClick={() => setCapital(amt)}
              className={`px-3 py-1 rounded-lg text-xs font-mono font-bold border transition ${
                capital === amt
                  ? 'bg-blue-600 text-white border-blue-400 shadow shadow-blue-500/40'
                  : 'bg-gray-900 text-gray-300 border-gray-800 hover:border-gray-700'
              }`}
            >
              ₹{(amt / 1000).toFixed(0)}k
            </button>
          ))}
        </div>
      </div>

      {/* Input Row: Capital Amount & Risk Percentage */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-gray-900/60 p-4 rounded-xl border border-gray-800">
        {/* Capital Input Box */}
        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-blue-400 font-mono flex items-center justify-between">
            <span>Enter Your Total Capital (₹)</span>
            <span className="text-gray-400 font-normal">Available Funds</span>
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 font-mono text-lg font-bold">₹</span>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Math.max(1000, Number(e.target.value)))}
              step={5000}
              className="w-full pl-9 pr-4 py-3 bg-gray-950 border border-blue-500/40 rounded-xl text-white font-mono text-xl font-bold focus:outline-none focus:border-blue-400 shadow-inner"
              placeholder="e.g. 50000"
            />
          </div>
        </div>

        {/* Risk Allocation Selector */}
        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-blue-400 font-mono flex items-center justify-between">
            <span>Risk Capital Allocation</span>
            <span className="text-emerald-400 font-bold">{riskPct}% Risk Per Trade</span>
          </label>
          <div className="flex items-center gap-2 pt-2">
            {[1, 2, 3, 5].map((pct) => (
              <button
                key={pct}
                onClick={() => setRiskPct(pct)}
                className={`flex-1 py-3 rounded-xl font-mono text-xs font-bold border transition ${
                  riskPct === pct
                    ? 'bg-blue-600 text-white border-blue-400 shadow shadow-blue-500/30'
                    : 'bg-gray-950 text-gray-400 border-gray-800 hover:text-white'
                }`}
              >
                {pct}% ({pct === 1 ? 'Safe' : pct === 2 ? 'Optimal' : pct === 3 ? 'Aggressive' : 'Max'})
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* AI Recommendation Box based on Capital */}
      <div className="bg-blue-950/30 border border-blue-500/40 p-5 rounded-2xl glow-blue flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-1">
          <div className="text-xs text-blue-400 font-mono uppercase tracking-wider font-bold">
            🤖 AI Recommended Option Contract
          </div>
          <div className="text-2xl font-black text-white font-mono flex items-center gap-3">
            <span className={`px-3 py-1 rounded-lg text-sm ${isCall ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'}`}>
              {recommendation}
            </span>
            <span>{optionSymbol}</span>
            <span className="text-xs font-normal text-gray-400">@ ~₹{estimatedPremium}/share</span>
          </div>
          <div className="text-xs text-gray-400 font-mono">
            Suggested Quantity: <strong className="text-white">{suggestedLots} Lot(s) ({totalQty} Qty)</strong> • Investment: <strong className="text-blue-300">₹{totalInvestment.toLocaleString('en-IN')}</strong> ({((totalInvestment / capital) * 100).toFixed(1)}% of capital)
          </div>
        </div>

        <div className="text-right bg-gray-900/90 px-5 py-3 rounded-xl border border-gray-800 min-w-[200px]">
          <div className="text-xs text-gray-400 font-mono">Cost Per Lot</div>
          <div className="text-xl font-bold font-mono text-emerald-400">₹{costPerLot.toLocaleString('en-IN')}</div>
          <div className="text-[10px] text-gray-500 font-mono">1 Lot = 75 Shares</div>
        </div>
      </div>

      {/* Outcome Matrix: Target 1 Profit, Target 2 Profit & Portfolio Growth */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Target 1 Outcome */}
        <div className="bg-emerald-950/20 border border-emerald-500/30 p-5 rounded-2xl space-y-3">
          <div className="flex justify-between items-center text-xs font-mono text-emerald-400 font-bold uppercase">
            <span>🎯 Target 1 Outcome</span>
            <span className="bg-emerald-500/20 px-2 py-0.5 rounded">+50% Premium</span>
          </div>

          <div>
            <div className="text-xs text-gray-400 font-mono">Net Profit</div>
            <div className="text-3xl font-black font-mono text-emerald-400">
              +₹{profitTarget1.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </div>
          </div>

          <div className="pt-2 border-t border-emerald-500/20">
            <div className="text-xs text-gray-400 font-mono">Total Balance After Profit</div>
            <div className="text-xl font-bold font-mono text-emerald-200">
              ₹{totalCapitalTarget1.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </div>
          </div>
        </div>

        {/* Target 2 Outcome */}
        <div className="bg-emerald-950/40 border border-emerald-500/50 p-5 rounded-2xl space-y-3 glow-green">
          <div className="flex justify-between items-center text-xs font-mono text-emerald-300 font-bold uppercase">
            <span>🚀 Target 2 Outcome</span>
            <span className="bg-emerald-500/30 px-2 py-0.5 rounded text-emerald-200">+100% Premium</span>
          </div>

          <div>
            <div className="text-xs text-gray-400 font-mono">Net Profit</div>
            <div className="text-3xl font-black font-mono text-emerald-300">
              +₹{profitTarget2.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </div>
          </div>

          <div className="pt-2 border-t border-emerald-500/30">
            <div className="text-xs text-gray-400 font-mono">Total Balance After Profit</div>
            <div className="text-xl font-bold font-mono text-emerald-100">
              ₹{totalCapitalTarget2.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </div>
          </div>
        </div>

        {/* Stop Loss Max Risk Outcome */}
        <div className="bg-rose-950/20 border border-rose-500/30 p-5 rounded-2xl space-y-3">
          <div className="flex justify-between items-center text-xs font-mono text-rose-400 font-bold uppercase">
            <span>🛡️ Max Risk (Stop Loss)</span>
            <span className="bg-rose-500/20 px-2 py-0.5 rounded text-rose-300">-30% Cut Limit</span>
          </div>

          <div>
            <div className="text-xs text-gray-400 font-mono">Max Loss If SL Hit</div>
            <div className="text-3xl font-black font-mono text-rose-400">
              -₹{maxLoss.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </div>
          </div>

          <div className="pt-2 border-t border-rose-500/20">
            <div className="text-xs text-gray-400 font-mono">Capital Preserved</div>
            <div className="text-xl font-bold font-mono text-rose-200">
              ₹{(capital - maxLoss).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
