-- Price alerts table
CREATE TABLE IF NOT EXISTS price_alerts (
    id           SERIAL PRIMARY KEY,
    email        TEXT NOT NULL,
    slug         TEXT NOT NULL,
    item_name    TEXT NOT NULL,
    direction    TEXT NOT NULL CHECK (direction IN ('above','below')),
    threshold    NUMERIC(10,2) NOT NULL,
    active       BOOLEAN DEFAULT true,
    triggered_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (email, slug, direction)
);

CREATE INDEX IF NOT EXISTS idx_price_alerts_active ON price_alerts(active, slug);
