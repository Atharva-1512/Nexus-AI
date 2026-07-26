-- =============================================================
-- NEXUS AI — PostgreSQL / TimescaleDB Initialization Script
-- Run automatically on first container startup
-- =============================================================

-- Enable TimescaleDB extension (for time-series hypertables)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- OHLCV Time-Series Table (Module 1 — Market Data Engine)
-- Converted to TimescaleDB hypertable for fast time-range queries
-- =============================================================

CREATE TABLE IF NOT EXISTS ohlcv (
    id          BIGSERIAL,
    symbol      VARCHAR(50)     NOT NULL,
    interval    VARCHAR(10)     NOT NULL,   -- '1m', '5m', '15m', '1h', '1d'
    timestamp   TIMESTAMPTZ     NOT NULL,
    open        NUMERIC(12, 2)  NOT NULL,
    high        NUMERIC(12, 2)  NOT NULL,
    low         NUMERIC(12, 2)  NOT NULL,
    close       NUMERIC(12, 2)  NOT NULL,
    volume      BIGINT          NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, interval, timestamp)
);

-- Convert to TimescaleDB hypertable (partitioned by time)
SELECT create_hypertable('ohlcv', 'timestamp',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

-- Compression (after 7 days, compress old chunks)
ALTER TABLE ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, interval'
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_interval ON ohlcv (symbol, interval);
CREATE INDEX IF NOT EXISTS idx_ohlcv_timestamp ON ohlcv (timestamp DESC);


-- =============================================================
-- OPTION CHAIN Snapshots (Module 5 — Option Chain Intelligence)
-- =============================================================

CREATE TABLE IF NOT EXISTS option_chain_snapshots (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    underlying      VARCHAR(20)     NOT NULL,   -- 'NIFTY', 'BANKNIFTY'
    expiry_date     DATE            NOT NULL,
    strike          NUMERIC(10, 2)  NOT NULL,
    option_type     VARCHAR(2)      NOT NULL,   -- 'CE', 'PE'
    timestamp       TIMESTAMPTZ     NOT NULL,
    last_price      NUMERIC(10, 2),
    open_interest   BIGINT,
    oi_change       BIGINT,
    volume          BIGINT,
    iv              NUMERIC(8, 4),              -- Implied Volatility (decimal)
    delta           NUMERIC(8, 6),
    gamma           NUMERIC(10, 8),
    theta           NUMERIC(8, 6),
    vega            NUMERIC(8, 6),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('option_chain_snapshots', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_oc_underlying_expiry ON option_chain_snapshots (underlying, expiry_date);
CREATE INDEX IF NOT EXISTS idx_oc_strike_type ON option_chain_snapshots (strike, option_type);


-- =============================================================
-- AI SIGNALS (Module 22 — Decision Engine)
-- =============================================================

CREATE TABLE IF NOT EXISTS ai_signals (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    signal              VARCHAR(10)     NOT NULL,   -- 'BUY_CALL', 'BUY_PUT', 'NO_TRADE'
    confidence          NUMERIC(5, 2)   NOT NULL,   -- 0–100
    regime              VARCHAR(30),
    entry_price         NUMERIC(10, 2),
    stop_loss           NUMERIC(10, 2),
    target_1            NUMERIC(10, 2),
    target_2            NUMERIC(10, 2),
    risk_reward         NUMERIC(6, 2),
    holding_time_min    INTEGER,
    composite_reasoning TEXT,
    model_version       VARCHAR(20),

    -- Outcome tracking (filled after trade closes)
    outcome             VARCHAR(20),    -- 'WIN', 'LOSS', 'SCRATCH', 'OPEN'
    actual_pnl_pct      NUMERIC(8, 4),
    closed_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON ai_signals (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_signal ON ai_signals (signal);


-- =============================================================
-- SIGNAL FACTOR WEIGHTS (Module 21 — Explainability)
-- =============================================================

CREATE TABLE IF NOT EXISTS signal_factor_weights (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    signal_id       UUID            NOT NULL REFERENCES ai_signals(id) ON DELETE CASCADE,
    factor          VARCHAR(50)     NOT NULL,
    value_text      VARCHAR(100),
    weight_pct      NUMERIC(5, 2)   NOT NULL,
    direction       VARCHAR(10)     NOT NULL,   -- 'bullish', 'bearish', 'neutral'
    narrative       TEXT
);

CREATE INDEX IF NOT EXISTS idx_sfw_signal_id ON signal_factor_weights (signal_id);


-- =============================================================
-- ALERTS (Module 24 — Alert Engine)
-- =============================================================

CREATE TABLE IF NOT EXISTS alerts (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    type            VARCHAR(30)     NOT NULL,
    title           VARCHAR(200)    NOT NULL,
    message         TEXT            NOT NULL,
    confidence      NUMERIC(5, 2),
    priority        VARCHAR(10)     NOT NULL DEFAULT 'MEDIUM',
    sound           BOOLEAN         NOT NULL DEFAULT TRUE,
    acknowledged    BOOLEAN         NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    signal_id       UUID            REFERENCES ai_signals(id),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('alerts', 'created_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);


-- =============================================================
-- FII / DII FLOWS (Module 1 — Market Data Engine)
-- =============================================================

CREATE TABLE IF NOT EXISTS fii_dii_flows (
    id          BIGSERIAL       PRIMARY KEY,
    date        DATE            NOT NULL UNIQUE,
    fii_buy     NUMERIC(15, 2),
    fii_sell    NUMERIC(15, 2),
    fii_net     NUMERIC(15, 2),
    dii_buy     NUMERIC(15, 2),
    dii_sell    NUMERIC(15, 2),
    dii_net     NUMERIC(15, 2),
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fii_date ON fii_dii_flows (date DESC);
