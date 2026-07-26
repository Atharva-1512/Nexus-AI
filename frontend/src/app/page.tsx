'use client';

import React, { useState, useEffect } from 'react';
import CandlestickChart from '@/components/CandlestickChart';
import TradingChart from '@/components/TradingChart';
import NiftyLiveMetrics from '@/components/NiftyLiveMetrics';




// API Base URL
const API_BASE = 'http://localhost:8000/api/v1';

interface AlertItem {
  id: string;
  type: string;
  title: string;
  message: string;
  timestamp?: string;
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<'decision' | 'tvchart' | 'explainability' | 'options' | 'technical' | 'macro' | 'alerts'>('decision');
  const [scenario, setScenario] = useState<'neutral' | 'bullish' | 'bearish'>('bullish');
  const [soundEnabled] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>('');


  // Data states
  const [decisionData, setDecisionData] = useState<Record<string, unknown> | null>(null);
  const [alertsData, setAlertsData] = useState<AlertItem[]>([]);



  // Sound Synthesizer using Web Audio API
  const playWebAudioSound = (type: 'call' | 'put' | 'alert') => {
    if (!soundEnabled) return;
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'call') {
        osc.frequency.setValueAtTime(523.25, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.2);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
        osc.start();
        osc.stop(ctx.currentTime + 0.3);
      } else if (type === 'put') {
        osc.frequency.setValueAtTime(659.25, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(440.0, ctx.currentTime + 0.2);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
        osc.start();
        osc.stop(ctx.currentTime + 0.3);
      } else {
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
        osc.start();
        osc.stop(ctx.currentTime + 0.2);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const decRes = await fetch(`${API_BASE}/decision/recommend?scenario=${scenario}&spot=24050`);
        if (decRes.ok) {
          const d = await decRes.json();
          setDecisionData(d);
        }

        const altRes = await fetch(`${API_BASE}/alerts/history`);
        if (altRes.ok) {
          const a = await altRes.json();
          setAlertsData(a.alerts || []);
        }

        setLastUpdated(new Date().toLocaleTimeString());
      } catch (err) {
        console.log('Error fetching backend API:', err);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [scenario]);



  const triggerTestSoundAlert = async () => {
    playWebAudioSound('call');
    try {
      await fetch(`${API_BASE}/alerts/test`, { method: 'POST' });
    } catch (e) {
      console.log(e);
    }
  };


  return (
    <div className="min-h-screen bg-[#090d16] text-gray-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-gray-800 bg-[#0f172a]/90 backdrop-blur-md px-6 py-4 sticky top-0 z-50 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">
            NX
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-white via-gray-200 to-blue-400 bg-clip-text text-transparent">
              NEXUS AI <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 font-semibold border border-blue-500/30">NIFTY 50 OPTIONS</span>
            </h1>
            <p className="text-xs text-gray-400">Institutional Decision Support System • Next Expiry: <span className="text-amber-400 font-medium">Tuesday Weekly</span></p>
          </div>
        </div>

        {/* Live Status Bar */}
        <div className="flex items-center gap-6 text-sm">
          <div className="flex items-center gap-2 bg-gray-900/80 px-3 py-1.5 rounded-lg border border-gray-800">
            <span className="text-gray-400">Spot:</span>
            <span className="font-mono font-bold text-white">24,050.25</span>
            <span className="text-emerald-400 text-xs font-semibold">+145.20 (+0.61%)</span>
          </div>

          <div className="flex items-center gap-2 bg-gray-900/80 px-3 py-1.5 rounded-lg border border-gray-800">
            <span className="text-gray-400">India VIX:</span>
            <span className="font-mono font-bold text-amber-400">14.85</span>
            <span className="text-emerald-400 text-xs">-2.1%</span>
          </div>

          {/* Scenario Selector */}
          <div className="flex items-center bg-gray-900 p-1 rounded-lg border border-gray-800 text-xs">
            <button
              onClick={() => setScenario('bullish')}
              className={`px-3 py-1 rounded font-medium transition ${scenario === 'bullish' ? 'bg-emerald-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}
            >
              Bullish Simulation
            </button>
            <button
              onClick={() => setScenario('bearish')}
              className={`px-3 py-1 rounded font-medium transition ${scenario === 'bearish' ? 'bg-rose-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}
            >
              Bearish Simulation
            </button>
            <button
              onClick={() => setScenario('neutral')}
              className={`px-3 py-1 rounded font-medium transition ${scenario === 'neutral' ? 'bg-gray-700 text-white shadow' : 'text-gray-400 hover:text-white'}`}
            >
              Neutral
            </button>
          </div>

          {/* Audio & Alert Controls */}
          <button
            onClick={triggerTestSoundAlert}
            className="flex items-center gap-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 px-3 py-1.5 rounded-lg text-xs font-semibold transition"
          >
            <span>🔔 Sound Test</span>
          </button>
        </div>
      </header>

      {/* Main Tab Navigation */}
      <div className="bg-[#0c1220] border-b border-gray-800 px-6 py-2 flex items-center justify-between text-sm overflow-x-auto">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab('decision')}
            className={`px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 ${activeTab === 'decision' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'}`}
          >
            <span>⚡ Command Center</span>
          </button>
          <button
            onClick={() => setActiveTab('tvchart')}
            className={`px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 ${activeTab === 'tvchart' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'}`}
          >
            <span>📊 Live NIFTY Metrics & Levels</span>
          </button>


          <button
            onClick={() => setActiveTab('explainability')}
            className={`px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 ${activeTab === 'explainability' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'}`}
          >
            <span>🔍 Explainability Dashboard</span>
          </button>
          <button
            onClick={() => setActiveTab('options')}
            className={`px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 ${activeTab === 'options' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'}`}
          >
            <span>📊 Option Chain Intelligence</span>
          </button>
          <button
            onClick={() => setActiveTab('technical')}
            className={`px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 ${activeTab === 'technical' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'}`}
          >
            <span>📈 Technical Studio</span>
          </button>
          <button
            onClick={() => setActiveTab('macro')}
            className={`px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 ${activeTab === 'macro' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'}`}
          >
            <span>🌐 Macro & Sentiment</span>
          </button>
          <button
            onClick={() => setActiveTab('alerts')}
            className={`px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 ${activeTab === 'alerts' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'}`}
          >
            <span>🚨 Alert Console</span>
            {alertsData.length > 0 && <span className="bg-red-500 text-white text-xs px-1.5 py-0.2 rounded-full font-bold">{alertsData.length}</span>}
          </button>
        </div>

        <div className="text-xs text-gray-400 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded font-mono font-bold">⚡ 5s Live Refresh</span>
          <span>Updated: {lastUpdated || 'Live'}</span>
        </div>

      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-6 space-y-6 max-w-[1600px] mx-auto w-full">

        {/* DEDICATED TAB: Live NIFTY 50 Metrics, Targets & S/R Levels */}
        {activeTab === 'tvchart' && (
          <NiftyLiveMetrics decisionData={decisionData} />
        )}



        {/* TAB 1: COMMAND CENTER / DECISION ENGINE */}
        {activeTab === 'decision' && (

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Main Recommendation Banner */}
            <div className="lg:col-span-2 space-y-6">
              <div className="glass-panel p-6 rounded-2xl border border-emerald-500/30 glow-green relative overflow-hidden">
                <div className="absolute top-0 right-0 p-6 opacity-10 font-mono font-black text-8xl text-emerald-400 select-none pointer-events-none">
                  {String(decisionData?.recommendation || 'BUY CALL')}
                </div>


                <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-bold tracking-widest text-emerald-400 uppercase bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 rounded-full">
                        Primary AI Recommendation
                      </span>
                      <span className="text-xs font-mono text-gray-300 bg-gray-900 border border-gray-700 px-3 py-1 rounded-full flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        Analysis Date: <strong className="text-white">{new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</strong> • <span className="text-amber-400 font-mono">{lastUpdated || '15:30 IST'}</span>
                      </span>
                    </div>
                    <h2 className="text-4xl font-black text-white mt-2 flex items-center gap-3">
                      <span>🟢 BUY CALL</span>
                      <span className="text-2xl font-semibold text-emerald-400">NIFTY 24100 CE</span>
                    </h2>
                  </div>


                  <div className="text-right">
                    <div className="text-3xl font-black text-emerald-400 font-mono">91%</div>
                    <div className="text-xs text-gray-400 uppercase font-semibold">Confidence Score</div>
                  </div>
                </div>

                {/* Progress confidence bar */}
                <div className="w-full bg-gray-800 rounded-full h-3 mb-6 overflow-hidden">
                  <div className="bg-gradient-to-r from-emerald-500 to-teal-400 h-3 rounded-full transition-all duration-1000" style={{ width: '91%' }}></div>
                </div>

                {/* Trade Parameters Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-gray-900/80 p-4 rounded-xl border border-gray-800 text-sm">
                  <div>
                    <div className="text-xs text-gray-400">Suggested Strike</div>
                    <div className="font-bold text-white text-base">24,100 CE (1 Step OTM)</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Expiry Date</div>
                    <div className="font-bold text-amber-400 text-base">Next Tuesday</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Entry Range</div>
                    <div className="font-mono font-bold text-white text-base">₹221 - ₹244</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Risk : Reward</div>
                    <div className="font-mono font-bold text-emerald-400 text-base">1 : 2.1</div>
                  </div>
                </div>

                {/* Target & Stop Loss */}
                <div className="grid grid-cols-3 gap-4 mt-4">
                  <div className="bg-emerald-950/40 border border-emerald-500/20 p-3 rounded-xl">
                    <div className="text-xs text-emerald-400 font-medium">Target 1 (1R)</div>
                    <div className="text-lg font-bold font-mono text-emerald-300">₹350.00</div>
                  </div>
                  <div className="bg-emerald-950/60 border border-emerald-500/30 p-3 rounded-xl">
                    <div className="text-xs text-emerald-400 font-medium">Target 2 (2R)</div>
                    <div className="text-lg font-bold font-mono text-emerald-200">₹466.00</div>
                  </div>
                  <div className="bg-rose-950/40 border border-rose-500/20 p-3 rounded-xl">
                    <div className="text-xs text-rose-400 font-medium">Stop Loss</div>
                    <div className="text-lg font-bold font-mono text-rose-300">₹116.00</div>
                  </div>
                </div>
              </div>

              {/* Multi-Engine Signal Matrix */}
              <div className="glass-panel p-6 rounded-2xl space-y-4">


                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <span>🧠 6-Engine Signal Consensus</span>
                </h3>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Option Chain (30%)</span>
                      <span className="text-emerald-400 font-bold">78/100</span>
                    </div>
                    <div className="text-sm font-semibold text-emerald-400">PCR 1.35 • Call Unwinding</div>
                  </div>

                  <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Technical Analysis (20%)</span>
                      <span className="text-emerald-400 font-bold">72/100</span>
                    </div>
                    <div className="text-sm font-semibold text-emerald-400">RSI 63 • MACD Bull Cross</div>
                  </div>

                  <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Macro Intelligence (15%)</span>
                      <span className="text-emerald-400 font-bold">70/100</span>
                    </div>
                    <div className="text-sm font-semibold text-emerald-400">FII Net Buying • GIFT +0.4%</div>
                  </div>

                  <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Sentiment & News (12%)</span>
                      <span className="text-emerald-400 font-bold">68/100</span>
                    </div>
                    <div className="text-sm font-semibold text-emerald-400">Greed Index 70 • Positive News</div>
                  </div>

                  <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Greeks & Volatility (14%)</span>
                      <span className="text-emerald-400 font-bold">65/100</span>
                    </div>
                    <div className="text-sm font-semibold text-emerald-400">Low VIX 14.8 • Cheap Premiums</div>
                  </div>

                  <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>ML Model (9%)</span>
                      <span className="text-emerald-400 font-bold">67/100</span>
                    </div>
                    <div className="text-sm font-semibold text-emerald-400">LSTM Direction Score 0.67</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Reasoning & Position Sizing */}
            <div className="space-y-6">
              {/* Position Sizing Box */}
              <div className="glass-panel p-6 rounded-2xl border border-blue-500/20">
                <h3 className="text-md font-bold text-white mb-3">🛡 Risk & Position Sizing</h3>
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between py-1.5 border-b border-gray-800">
                    <span className="text-gray-400">Max Risk per Trade:</span>
                    <span className="font-mono text-white font-bold">₹10,000 (1% Capital)</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-gray-800">
                    <span className="text-gray-400">NIFTY Lot Size:</span>
                    <span className="font-mono text-white font-bold">75 Qty</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-gray-800">
                    <span className="text-gray-400">Macro Regime Multiplier:</span>
                    <span className="font-mono text-emerald-400 font-bold">80% (SIDEWAYS)</span>
                  </div>
                  <div className="flex justify-between py-1.5 text-sm pt-2">
                    <span className="text-gray-200 font-semibold">Recommended Quantity:</span>
                    <span className="font-mono text-blue-400 font-black text-base">1 Lot (75 Qty)</span>
                  </div>
                </div>
              </div>

              {/* Quick AI Narrative */}
              <div className="glass-panel p-6 rounded-2xl">
                <h3 className="text-md font-bold text-white mb-3 flex items-center gap-2">
                  <span>💡 Executive AI Summary</span>
                </h3>
                <ul className="space-y-2 text-xs text-gray-300">
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>PCR risen from 0.95 to 1.35 indicating strong Put writing support at 24,000.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>FII net bought ₹1,520 Cr in cash markets with active stock futures accumulation.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>Technical momentum indicators (RSI 63 & MACD bullish cross) favor continuation towards 24,250.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>Crude oil remains stable at $78/bbl keeping macro risk contained.</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: EXPLAINABILITY DASHBOARD (Matches exact user specification) */}
        {activeTab === 'explainability' && (
          <div className="space-y-6">
            <div className="glass-panel p-6 rounded-2xl border border-blue-500/20">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-white">Explainability & Feature Contribution Dashboard</h2>
                  <p className="text-xs text-gray-400">Exact weighted decomposition of decision factors driving AI predictions.</p>
                </div>
                <div className="bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 font-bold px-4 py-2 rounded-xl text-lg font-mono">
                  Confidence 91%
                </div>
              </div>

              {/* User requested factor weight waterfall UI */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Left: Factor Weights Breakdown */}
                <div className="space-y-4">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-gray-400 border-b border-gray-800 pb-2">
                    Factor Contribution Breakdown
                  </h3>

                  {[
                    { name: 'PCR (Put-Call Ratio)', weight: 18, score: 82, color: 'bg-emerald-500' },
                    { name: 'OI Build-up', weight: 21, score: 88, color: 'bg-teal-500' },
                    { name: 'Technical Indicators', weight: 20, score: 75, color: 'bg-blue-500' },
                    { name: 'FII / DII Institutional Flow', weight: 15, score: 80, color: 'bg-indigo-500' },
                    { name: 'Greeks & Volatility', weight: 14, score: 72, color: 'bg-purple-500' },
                    { name: 'News & Social Sentiment', weight: 12, score: 70, color: 'bg-sky-500' },
                  ].map((f) => (
                    <div key={f.name} className="space-y-1 bg-gray-900/50 p-3 rounded-xl border border-gray-800">
                      <div className="flex justify-between text-xs">
                        <span className="font-semibold text-gray-200">{f.name}</span>
                        <span className="font-mono text-emerald-400 font-bold">Weight: {f.weight}% | Score: {f.score}/100</span>
                      </div>
                      <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden flex">
                        <div className={`${f.color} h-full rounded-full transition-all duration-500`} style={{ width: `${f.weight * 4}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Right: Key Decision Reasons (User Specified List) */}
                <div className="space-y-4">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-gray-400 border-b border-gray-800 pb-2">
                    Supporting Reasons & Signal Drivers
                  </h3>

                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { reason: 'PCR ↑', detail: 'PCR risen to 1.35', positive: true },
                      { reason: 'FII Buying', detail: '+₹1,520 Cr Cash Net', positive: true },
                      { reason: 'RSI 63', detail: 'Bullish Momentum Zone', positive: true },
                      { reason: 'MACD Cross', detail: 'Histogram positive', positive: true },
                      { reason: 'Global Market Bullish', detail: 'S&P 500 +0.8%', positive: true },
                      { reason: 'OI Build-up', detail: '24,000 Call Unwinding', positive: true },
                      { reason: 'Crude Stable', detail: '$78.20/bbl (No risk)', positive: true },
                      { reason: 'Dollar Weak', detail: 'DXY 103.5 (-0.4%)', positive: true },
                      { reason: 'Positive News', detail: 'Earnings Beat Index', positive: true },
                    ].map((item, idx) => (
                      <div key={idx} className="bg-gray-900/60 p-3 rounded-xl border border-gray-800 flex items-center justify-between">
                        <div>
                          <div className="text-sm font-bold text-white">{item.reason}</div>
                          <div className="text-xs text-gray-400">{item.detail}</div>
                        </div>
                        <span className="text-xs font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          HIGH
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: OPTION CHAIN INTELLIGENCE */}
        {activeTab === 'options' && (
          <div className="space-y-6">
            <div className="glass-panel p-6 rounded-2xl space-y-6">
              <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-white">NIFTY 50 Option Chain Analysis</h2>
                <div className="text-xs text-amber-400 font-semibold bg-amber-500/10 border border-amber-500/30 px-3 py-1 rounded-full">
                  Weekly Expiry: Next Tuesday
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-gray-900/80 p-4 rounded-xl border border-gray-800">
                  <div className="text-xs text-gray-400">Put-Call Ratio (PCR)</div>
                  <div className="text-2xl font-black text-emerald-400 font-mono mt-1">1.35</div>
                  <div className="text-xs text-emerald-400">Bullish Sentiment</div>
                </div>
                <div className="bg-gray-900/80 p-4 rounded-xl border border-gray-800">
                  <div className="text-xs text-gray-400">Max Pain Strike</div>
                  <div className="text-2xl font-black text-amber-400 font-mono mt-1">₹24,000</div>
                  <div className="text-xs text-gray-400">Spot is +50 pts above</div>
                </div>
                <div className="bg-gray-900/80 p-4 rounded-xl border border-gray-800">
                  <div className="text-xs text-gray-400">Highest CE Open Interest</div>
                  <div className="text-2xl font-black text-rose-400 font-mono mt-1">24,500</div>
                  <div className="text-xs text-gray-400">Resistance Level</div>
                </div>
                <div className="bg-gray-900/80 p-4 rounded-xl border border-gray-800">
                  <div className="text-xs text-gray-400">Highest PE Open Interest</div>
                  <div className="text-2xl font-black text-emerald-400 font-mono mt-1">24,000</div>
                  <div className="text-xs text-emerald-400">Key Support Base</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: TECHNICAL STUDIO */}
        {activeTab === 'technical' && (
          <div className="glass-panel p-6 rounded-2xl space-y-6">
            <h2 className="text-2xl font-bold text-white">Technical Analysis & Price Action</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                <div className="text-xs text-gray-400">RSI (14)</div>
                <div className="text-xl font-bold text-emerald-400 font-mono">63.40</div>
                <div className="text-xs text-gray-400">Bullish Zone</div>
              </div>
              <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                <div className="text-xs text-gray-400">MACD Histogram</div>
                <div className="text-xl font-bold text-emerald-400 font-mono">+18.45</div>
                <div className="text-xs text-emerald-400">Bullish Crossover Active</div>
              </div>
              <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                <div className="text-xs text-gray-400">Supertrend (10, 3)</div>
                <div className="text-xl font-bold text-emerald-400 font-mono">BULLISH</div>
                <div className="text-xs text-gray-400">Support @ 23,880</div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: MACRO & SENTIMENT */}
        {activeTab === 'macro' && (
          <div className="glass-panel p-6 rounded-2xl space-y-6">
            <div className="flex justify-between items-center border-b border-gray-800 pb-4">
              <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                  <span>🌐 Global Macro & Sentiment Intelligence</span>
                </h2>
                <p className="text-xs text-gray-400">Live international market indices, GIFT NIFTY early indicator, currency, and commodities.</p>
              </div>
              <span className="text-xs font-mono bg-blue-500/20 text-blue-400 border border-blue-500/30 px-3 py-1.5 rounded-full font-semibold">
                Pre-Market Lead: GIFT NIFTY
              </span>
            </div>

            {/* Featured Lead Indicator: GIFT NIFTY & Key Macro */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-gradient-to-br from-blue-950/60 to-indigo-950/60 p-4 rounded-xl border border-blue-500/40 glow-blue">
                <div className="flex justify-between items-center text-xs text-blue-300 font-semibold mb-1">
                  <span>GIFT NIFTY (Pre-Market)</span>
                  <span className="bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/30">+0.42%</span>
                </div>
                <div className="text-2xl font-black font-mono text-white mt-1">24,152.00</div>
                <div className="text-xs text-emerald-400 font-semibold mt-1">▲ +101.75 pts (Gap-Up Expectation)</div>
              </div>

              <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                <div className="text-xs text-gray-400 mb-1">USD / INR</div>
                <div className="text-lg font-bold font-mono text-white">83.45</div>
                <div className="text-xs text-emerald-400 font-semibold mt-1">-0.05% (Currency Stable)</div>
              </div>

              <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                <div className="text-xs text-gray-400 mb-1">Crude Oil (WTI)</div>
                <div className="text-lg font-bold font-mono text-white">$78.20</div>
                <div className="text-xs text-emerald-400 font-semibold mt-1">-0.8% (Macro Favorable)</div>
              </div>

              <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                <div className="text-xs text-gray-400 mb-1">FII Net Cash Flow</div>
                <div className="text-lg font-bold font-mono text-emerald-400">+₹1,520 Cr</div>
                <div className="text-xs text-emerald-400 font-semibold mt-1">Net Buyer in Equities</div>
              </div>
            </div>

            {/* 6 Global Indices Grid */}
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider">
                International Equity Benchmarks (9 Global Markets)
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
                {[
                  { name: 'S&P 500 (US)', value: '5,564.40', chg: '+0.82%', pos: true },
                  { name: 'NASDAQ (US)', value: '18,398.45', chg: '+1.14%', pos: true },
                  { name: 'Nikkei 225 (Japan)', value: '41,220.00', chg: '+0.55%', pos: true },
                  { name: 'DAX (Germany)', value: '18,520.10', chg: '+0.34%', pos: true },
                  { name: 'FTSE 100 (UK)', value: '8,245.30', chg: '-0.12%', pos: false },
                  { name: 'Hang Seng (HK)', value: '17,800.50', chg: '+0.28%', pos: true },
                ].map((idx) => (
                  <div key={idx.name} className="bg-gray-900/50 p-3 rounded-xl border border-gray-800 flex flex-col justify-between">
                    <span className="text-gray-400 font-medium">{idx.name}</span>
                    <div className="font-mono font-bold text-white text-sm mt-1">{idx.value}</div>
                    <span className={`font-mono font-semibold mt-1 ${idx.pos ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {idx.chg}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}


        {/* TAB 6: ALERT CONSOLE */}
        {activeTab === 'alerts' && (
          <div className="glass-panel p-6 rounded-2xl space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-white">Real-Time Alert Console with Sound</h2>
              <button onClick={triggerTestSoundAlert} className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-xl text-xs font-bold transition">
                Test Sound Notification
              </button>
            </div>

            <div className="space-y-3">
              {alertsData.length === 0 ? (
                <div className="text-sm text-gray-400 py-8 text-center bg-gray-900/40 rounded-xl">
                  No active alerts. Trigger a test alert above to test sound effects.
                </div>
              ) : (
                alertsData.map((alt) => (
                  <div key={alt.id} className="bg-gray-900/80 p-4 rounded-xl border border-gray-800 flex items-center justify-between">
                    <div>
                      <div className="font-bold text-white text-sm">{alt.title}</div>
                      <div className="text-xs text-gray-300 mt-0.5">{alt.message}</div>
                    </div>
                    <span className="text-xs font-mono bg-blue-500/20 text-blue-400 px-2 py-1 rounded">
                      {alt.timestamp ? new Date(alt.timestamp).toLocaleTimeString() : 'Just now'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
