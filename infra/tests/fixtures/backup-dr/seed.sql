CREATE SCHEMA IF NOT EXISTS sample_app;

CREATE TABLE IF NOT EXISTS sample_app.widgets (
  id text PRIMARY KEY,
  name text NOT NULL,
  source text NOT NULL
);

INSERT INTO sample_app.widgets (id, name, source)
VALUES ('recovery-drill-widget', 'recovery-drill-widget', 'seed-before-backup')
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    source = EXCLUDED.source;
