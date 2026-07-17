# ADR-001: Dual warehouse target (DuckDB + Postgres) behind one dbt project

**Status:** Accepted

## Context
The platform needs (a) a warehouse a stranger can build in seconds with no
services, for the demo and for CI, and (b) a client-server warehouse with
partitioning, concurrent access, and operational tables for the Docker/cloud
deployment.

## Decision
One dbt project with two profile targets: `duckdb` (default; file-based, used
by `make demo` and CI) and `postgres` (Docker stack; declarative monthly
RANGE partitioning, BRIN + composite indexes, audit/metadata schemas applied
by `postgres_init.sql`). The API reads either backend through a single
repository layer -- DuckDB's `postgres` extension gives one query interface.

## Consequences
- CI proves every model portable across engines on every push.
- Demo-to-production is a two-env-var change, which is the whole point.
- Engine-specific SQL must stay inside adapters/macros; a model that only
  runs on one target is a build failure, caught immediately.
