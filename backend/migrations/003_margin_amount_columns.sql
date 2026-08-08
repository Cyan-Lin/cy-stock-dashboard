ALTER TABLE margin_data
    ADD COLUMN IF NOT EXISTS margin_balance_amount NUMERIC(20, 0),
    ADD COLUMN IF NOT EXISTS short_balance_amount  NUMERIC(20, 0);
