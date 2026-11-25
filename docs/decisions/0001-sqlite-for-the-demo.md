# 0001: SQLite for the demo, SQL portable to Postgres

**Status:** accepted, 16 Nov 2026. An earlier plan named Postgres on Supabase.

**Context.** The data is group-bys over events, which is what SQL is for. But this is a public demo that must load for a stranger months from now. A free hosted Postgres can pause when idle, and it adds a key and a network hop to something that only ever reads a seed file.

**Decision.** Load the seed into SQLite at startup and write the lookups as SQL through SQLAlchemy Core, using nothing SQLite-specific. Moving to Postgres is a connection string and a migration, not a rewrite.

**Consequence.** The hosted demo has no database to keep alive and no database key. Postgres is the production choice.
