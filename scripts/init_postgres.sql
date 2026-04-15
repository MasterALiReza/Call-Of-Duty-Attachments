-- Canonical PostgreSQL bootstrap: schema ownership belongs to these migrations.
-- setup_database.sql is a deprecated shim and must not be used as a schema source.
\set ON_ERROR_STOP on
\ir migrations/0001_baseline.sql
\ir migrations/0002_guides_split_tables.sql
\ir migrations/0003_runtime_parity_tables.sql
\ir migrations/0004_schema_canonical_backfill.sql
