ALTER TABLE alert_events
    ADD COLUMN IF NOT EXISTS date DATE;

UPDATE alert_events
    SET date = triggered_at::date
    WHERE date IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_events_symbol_type_date
    ON alert_events (symbol, alert_type, date);
