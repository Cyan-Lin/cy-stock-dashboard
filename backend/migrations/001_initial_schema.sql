CREATE TABLE IF NOT EXISTS daily_prices (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(16) NOT NULL,
    date        DATE        NOT NULL,
    open        NUMERIC(12, 2),
    high        NUMERIC(12, 2),
    low         NUMERIC(12, 2),
    close       NUMERIC(12, 2),
    volume      BIGINT,
    UNIQUE (symbol, date)
);

CREATE TABLE IF NOT EXISTS margin_data (
    id                        SERIAL PRIMARY KEY,
    symbol                    VARCHAR(16)    NOT NULL,
    date                      DATE           NOT NULL,
    margin_balance            NUMERIC(18, 2),
    margin_maintenance_ratio  NUMERIC(8, 4),
    short_balance             NUMERIC(18, 2),
    margin_short_ratio        NUMERIC(8, 4),
    UNIQUE (symbol, date)
);

CREATE TABLE IF NOT EXISTS alert_events (
    id           SERIAL PRIMARY KEY,
    symbol       VARCHAR(16)  NOT NULL,
    alert_type   VARCHAR(64)  NOT NULL,
    triggered_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    details      JSONB
);

CREATE TABLE IF NOT EXISTS national_fund_entries (
    id               SERIAL PRIMARY KEY,
    entry_date       DATE        NOT NULL UNIQUE,
    exit_date        DATE,
    background_event TEXT
);

CREATE TABLE IF NOT EXISTS etf_margin_ratio (
    id     SERIAL PRIMARY KEY,
    symbol VARCHAR(16)   NOT NULL UNIQUE,
    ratio  NUMERIC(4, 2) NOT NULL
);
