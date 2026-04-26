CREATE SCHEMA IF NOT EXISTS sample_app;

CREATE TABLE sample_app.widgets (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
