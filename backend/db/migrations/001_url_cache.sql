-- 24h URL cache of minimised, normalised source data (not raw scrape). Rows for a person's URLs are
-- removed by delete-my-data; expired rows are removed on read.
CREATE TABLE IF NOT EXISTS url_cache (
  url TEXT PRIMARY KEY, payload_json JSONB NOT NULL, fetched_at TIMESTAMPTZ NOT NULL DEFAULT now());
