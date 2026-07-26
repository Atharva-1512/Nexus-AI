'use client';

import React, { useState } from 'react';

export interface CapitalCalculatorProps {
  decisionData?: any;
}

export default function CapitalCalculator({ decisionData }: CapitalCalculatorProps) {
  // User Inputs
  const [capital, setCapital] = useState<number>(50000);
  const [useCustomLots, setUseCustomLots] = useState<boolean>(false);
  const [customLots, setCustomLots] = useState<number>(2);
  const [selectedStrikeMode, setSelectedStrikeMode] = useState<'AUTO' | 'ATM_ITM' | 'OTM'>('AUTO');

  // Live market metrics
  const spot = decisionData?.spot_price || 24050;
  const recommendation = decisionData?.recommendation || 'BUY PUT'; // e.g. BUY PUT or BUY CALL
  const isCall = recommendation.includes('CALL');
  const lotSize = 75; // NIFTY 1 Lot = 75 Qty

  // Dynamic strike calculation for PE scenarios (e.g., 23950 PE vs 23750 PE)
  const baseAtmStrike = isCall ? Math.floor(spot / 50) * 50 : Math.ceil(spot / 50) * 50; // 24050 / 24000
  
  // Strike 1: ITM / Near ATM (e.g., 23950 PE or 24100 CE)
  const strike1 = isCall ? baseAtmStrike + 50 : baseAtmStrike - 100; // e.g. 23950 PE
  const strike1Premium = 210; // ~₹210 per share
  const strike1Delta = 0.48;
  const strike1Theta = -12;

  // Strike 2: Far OTM (e.g., 23750 PE or 24300 CE)
  const strike2 = isCall ? baseAtmStrike + 250 : baseAtmStrike - 300; // e.g. 23750 PE
  const strike2Premium = 85; // ~₹85 per share
  const strike2Delta = 0.22;
  const strike2Theta = -7;

  // Lot Calculation: Manual vs Auto Risk Sizing
  const costPerLotStrike1 = strike1Premium * lotSize; // ₹15,750
  const costPerLotStrike2 = strike2Premium * lotSize; // ₹6,375

  const autoLotsStrike1 = Math.max(1, Math.floor((capital * 0.4) / costPerLotStrike1));
  const autoLotsStrike2 = Math.max(1, Math.floor((capital * 0.4) / costPerLotStrike2));

  const activeLotsStrike1 = useCustomLots ? customLots : autoLotsStrike1;
  const activeLotsStrike2 = useCustomLots ? customLots : autoLotsStrike2;

  const investmentStrike1 = activeLotsStrike1 * costPerLotStrike1;
  const investmentStrike2 = activeLotsStrike2 * costPerLotStrike2;

  // Targets & Profit Logic for Strike 1 (23950 PE)
  const strike1Target1Prem = strike1Premium * 1.5; // +50%
  const strike1Target2Prem = strike1Premium * 2.0; // +100%
  const strike1ProfitT1 = (strike1Target1Prem - strike1Premium) * (activeLotsStrike1 * lotSize);
  const strike1ProfitT2 = (strike1Target2Prem - strike1Premium) * (activeLotsStrike1 * lotSize);

  // Targets & Profit Logic for Strike 2 (23750 PE)
  const strike2Target1Prem = strike2Premium * 1.5; // +50%
  const strike2Target2Prem = strike2Premium * 2.0; // +100%
  const strike2ProfitT1 = (strike2Target1Prem - strike2Premium) * (activeLotsStrike2 * lotSize);
  const strike2ProfitT2 = (strike2Target2Prem - strike2Premium) * (activeLotsStrike2 * lotSize);

  // AI Decision Logic: Should user buy 23950 PE or 23750 PE?
  const bestStrikeRecommendation =
    investmentStrike1 <= capital
      ? {
          suggestedStrike: `NIFTY ${strike1} ${isCall ? 'CE' : 'PE'}`,
          type: 'ATM / ITM (High Delta)',
          reason: `Recommended! Delta ${strike1Delta} captures 48% of spot movement with strong liquidity. Higher probability of hitting Target 1 before time decay.`,
          strikeNum: strike1,
          lots: activeLotsStrike1,
          investment: investmentStrike1,
          profitT1: strike1ProfitT1,
          profitT2: strike1ProfitT2,
          totalAfterT1: capital + strike1ProfitT1,
          totalAfterT2: capital + strike1ProfitT2,
        }
      : {
          suggestedStrike: `NIFTY ${strike2} ${isCall ? 'CE' : 'PE'}`,
          type: 'OTM (Budget Friendly)',
          reason: `Lower capital requirement. Delta ${strike2Delta} requires a larger spot move to double, but total risk amount is strictly capped at ₹${investmentStrike2.toLocaleString('en-IN')}.`,
          strikeNum: strike2,
          lots: activeLotsStrike2,
          investment: investmentStrike2,
          profitT1: strike2ProfitT1,
          profitT2: strike2ProfitT2,
          totalAfterT1: capital + strike2ProfitT1,
          totalAfterT2: capital + strike2ProfitT2,
        };

  return (
    <div className="glass-panel p-6 rounded-2xl border border-blue-500/30 glow-blue space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <h3 className="text-xl font-black text-white font-mono tracking-wide">
              💰 AI Capital & Lot Sizing Strike Evaluator
            </h3>
          </div>
          <p className="text-xs text-gray-400 mt-1 font-mono">
            Enter your capital & lot quantity to compare contracts (e.g. NIFTY {strike1} {isCall ? 'CE' : 'PE'} vs NIFTY {strike2} {isCall ? 'CE' : 'PE'}) and get exact profit projections.
          </p>
        </div>

        {/* Quick Capital Presets */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 font-mono">Capital Presets:</span>
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

      {/* Input Controls Row: Capital & Lot Quantity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-gray-900/60 p-4 rounded-xl border border-gray-800">
        {/* Total Capital Input */}
        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-blue-400 font-mono flex items-center justify-between">
            <span>Enter Your Total Capital (₹)</span>
            <span className="text-gray-400 font-normal">Trading Balance</span>
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

        {/* Lot Selector Input */}
        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-blue-400 font-mono flex items-center justify-between">
            <span>Number of Lots to Buy</span>
            <span className="text-emerald-400 font-bold">
              {useCustomLots ? `${customLots} Lot(s) (${customLots * lotSize} Qty)` : 'Auto Sized by Risk'}
            </span>
          </label>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setUseCustomLots(false)}
              className={`px-3 py-3 rounded-xl font-mono text-xs font-bold border transition ${
                !useCustomLots
                  ? 'bg-blue-600 text-white border-blue-400'
                  : 'bg-gray-950 text-gray-400 border-gray-800 hover:text-white'
              }`}
            >
              🤖 Auto AI Sizing
            </button>

            {[1, 2, 3, 5, 10].map((num) => (
              <button
                key={num}
                onClick={() => {
                  setUseCustomLots(true);
                  setCustomLots(num);
                }}
                className={`flex-1 py-3 rounded-xl font-mono text-xs font-bold border transition ${
                  useCustomLots && customLots === num
                    ? 'bg-emerald-600 text-white border-emerald-400 shadow shadow-emerald-500/30'
                    : 'bg-gray-950 text-gray-400 border-gray-800 hover:text-white'
                }`}
              >
                {num} Lot{num > 1 ? 's' : ''}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Primary AI Recommendation Box */}
      <div className="bg-blue-950/40 border border-blue-500/50 p-5 rounded-2xl glow-blue flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="bg-blue-500/20 text-blue-300 border border-blue-500/40 px-3 py-0.5 rounded-full text-xs font-mono font-bold uppercase">
              AI Primary Strike Suggestion
            </span>
            <span className="text-xs text-gray-400 font-mono">Spot: ₹{spot}</span>
          </div>
          <h2 className="text-3xl font-black text-white font-mono flex items-center gap-3">
            <span className="text-emerald-400">{bestStrikeRecommendation.suggestedStrike}</span>
            <span className="text-xs font-normal text-gray-400 bg-gray-900 border border-gray-800 px-3 py-1 rounded-md">
              {bestStrikeRecommendation.type}
            </span>
          </h2>
          <p className="text-xs text-gray-300 font-mono max-w-2xl leading-relaxed">
            {bestStrikeRecommendation.reason}
          </p>
        </div>

        <div className="bg-gray-900/90 p-4 rounded-xl border border-gray-800 text-right min-w-[220px]">
          <div className="text-xs text-gray-400 font-mono">Trade Capital Required</div>
          <div className="text-2xl font-black font-mono text-emerald-400">
            ₹{bestStrikeRecommendation.investment.toLocaleString('en-IN')}
          </div>
          <div className="text-[10px] text-gray-400 font-mono mt-1">
            {bestStrikeRecommendation.lots} Lot(s) ({bestStrikeRecommendation.lots * lotSize} Qty)
          </div>
        </div>
      </div>

      {/* Side-by-Side Strike Comparison: 23950 PE vs 23750 PE */}
      <div className="space-y-3">
        <h4 className="text-sm font-bold text-white font-mono flex items-center gap-2">
          <span>⚖️ Detailed Strike Analysis & Comparison: NIFTY {strike1} {isCall ? 'CE' : 'PE'} vs NIFTY {strike2} {isCall ? 'CE' : 'PE'}</span>
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Card 1: NIFTY 23950 PE (ATM / Near ITM) */}
          <div className={`glass-panel p-6 rounded-2xl border transition space-y-4 ${
            bestStrikeRecommendation.strikeNum === strike1
              ? 'border-emerald-500/50 bg-emerald-950/20 glow-green'
              : 'border-gray-800 bg-gray-900/40'
          }`}>
            <div className="flex justify-between items-center pb-3 border-b border-gray-800">
              <div>
                <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded border border-emerald-500/30">
                  RECOMMENDED (ITM / Near ATM)
                </span>
                <h3 className="text-2xl font-black text-white font-mono mt-1">
                  NIFTY {strike1} {isCall ? 'CE' : 'PE'}
                </h3>
              </div>
              <div className="text-right font-mono">
                <div className="text-xs text-gray-400">Premium</div>
                <div className="text-xl font-bold text-emerald-300">₹{strike1Premium}/sh</div>
              </div>
            </div>

            {/* Metrics Breakdown */}
            <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono bg-gray-950 p-3 rounded-xl border border-gray-800">
              <div>
                <div className="text-gray-400">Delta</div>
                <div className="font-bold text-emerald-400">{strike1Delta}</div>
              </div>
              <div>
                <div className="text-gray-400">Lots Required</div>
                <div className="font-bold text-white">{activeLotsStrike1} Lot(s)</div>
              </div>
              <div>
                <div className="text-gray-400">Total Investment</div>
                <div className="font-bold text-blue-300">₹{investmentStrike1.toLocaleString('en-IN')}</div>
              </div>
            </div>

            {/* Profit Projections */}
            <div className="space-y-2 pt-2 text-xs font-mono">
              <div className="flex justify-between items-center bg-emerald-950/40 p-2.5 rounded-lg border border-emerald-500/20">
                <span className="text-emerald-400">Target 1 Profit (+50%):</span>
                <strong className="text-emerald-300 text-sm">+₹{strike1ProfitT1.toLocaleString('en-IN')}</strong>
              </div>
              <div className="flex justify-between items-center bg-emerald-950/60 p-2.5 rounded-lg border border-emerald-500/40">
                <span className="text-emerald-300">Target 2 Profit (+100%):</span>
                <strong className="text-emerald-200 text-sm">+₹{strike1ProfitT2.toLocaleString('en-IN')}</strong>
              </div>
              <div className="flex justify-between items-center bg-gray-900 p-2.5 rounded-lg border border-gray-800">
                <span className="text-gray-300">Total Balance After Profit (T2):</span>
                <strong className="text-white text-sm">₹{(capital + strike1ProfitT2).toLocaleString('en-IN')}</strong>
              </div>
            </div>
          </div>

          {/* Card 2: NIFTY 23750 PE (Far OTM) */}
          <div className={`glass-panel p-6 rounded-2xl border transition space-y-4 ${
            bestStrikeRecommendation.strikeNum === strike2
              ? 'border-emerald-500/50 bg-emerald-950/20 glow-green'
              : 'border-gray-800 bg-gray-900/40'
          }`}>
            <div className="flex justify-between items-center pb-3 border-b border-gray-800">
              <div>
                <span className="text-xs font-mono font-bold text-amber-400 bg-amber-500/10 px-2.5 py-0.5 rounded border border-amber-500/30">
                  BUDGET / OTM CONTRACT
                </span>
                <h3 className="text-2xl font-black text-white font-mono mt-1">
                  NIFTY {strike2} {isCall ? 'CE' : 'PE'}
                </h3>
              </div>
              <div className="text-right font-mono">
                <div className="text-xs text-gray-400">Premium</div>
                <div className="text-xl font-bold text-amber-300">₹{strike2Premium}/sh</div>
              </div>
            </div>

            {/* Metrics Breakdown */}
            <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono bg-gray-950 p-3 rounded-xl border border-gray-800">
              <div>
                <div className="text-gray-400">Delta</div>
                <div className="font-bold text-amber-400">{strike2Delta}</div>
              </div>
              <div>
                <div className="text-gray-400">Lots Required</div>
                <div className="font-bold text-white">{activeLotsStrike2} Lot(s)</div>
              </div>
              <div>
                <div className="text-gray-400">Total Investment</div>
                <div className="font-bold text-blue-300">₹{investmentStrike2.toLocaleString('en-IN')}</div>
              </div>
            </div>

            {/* Profit Projections */}
            <div className="space-y-2 pt-2 text-xs font-mono">
              <div className="flex justify-between items-center bg-emerald-950/40 p-2.5 rounded-lg border border-emerald-500/20">
                <span className="text-emerald-400">Target 1 Profit (+50%):</span>
                <strong className="text-emerald-300 text-sm">+₹{strike2ProfitT1.toLocaleString('en-IN')}</strong>
              </div>
              <div className="flex justify-between items-center bg-emerald-950/60 p-2.5 rounded-lg border border-emerald-500/40">
                <span className="text-emerald-300">Target 2 Profit (+100%):</span>
                <strong className="text-emerald-200 text-sm">+₹{strike2ProfitT2.toLocaleString('en-IN')}</strong>
              </div>
              <div className="flex justify-between items-center bg-gray-900 p-2.5 rounded-lg border border-gray-800">
                <span className="text-gray-300">Total Balance After Profit (T2):</span>
                <strong className="text-white text-sm">₹{(capital + strike2ProfitT2).toLocaleString('en-IN')}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
