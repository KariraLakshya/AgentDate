CREATE TABLE IF NOT EXISTS person (
  id TEXT PRIMARY KEY, linkedin_url TEXT, instagram_url TEXT, display_name TEXT,
  status TEXT NOT NULL DEFAULT 'pending', synthetic BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS consent (
  id SERIAL PRIMARY KEY, person_id TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  statement TEXT NOT NULL, ip_hash TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
-- payload_json is set to NULL after analysis (data handling)
CREATE TABLE IF NOT EXISTS raw_source (
  id SERIAL PRIMARY KEY, person_id TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  source TEXT NOT NULL, url TEXT, payload_json JSONB, readable BOOLEAN NOT NULL DEFAULT TRUE,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS profile (
  id SERIAL PRIMARY KEY, person_id TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  json JSONB NOT NULL, linkedin_persona TEXT, instagram_persona TEXT,
  gap_score REAL, identity_match_score REAL, version INT NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS date (
  id TEXT PRIMARY KEY, person_a TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  person_b TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  kind TEXT NOT NULL DEFAULT 'standard', status TEXT NOT NULL DEFAULT 'pending',
  faithfulness_a REAL, faithfulness_b REAL);
CREATE TABLE IF NOT EXISTS date_turn (
  id SERIAL PRIMARY KEY, date_id TEXT NOT NULL REFERENCES date(id) ON DELETE CASCADE,
  idx INT NOT NULL, speaker TEXT NOT NULL, stage TEXT, public_text TEXT, private_note TEXT,
  chemistry REAL, flags_json JSONB NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS match_score (
  id SERIAL PRIMARY KEY, date_id TEXT NOT NULL REFERENCES date(id) ON DELETE CASCADE,
  rater_person TEXT NOT NULL, dimension_scores_json JSONB NOT NULL,
  would_meet_again BOOLEAN, verdict TEXT);
CREATE TABLE IF NOT EXISTS briefing (
  id SERIAL PRIMARY KEY, person_id TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE, json JSONB NOT NULL);
