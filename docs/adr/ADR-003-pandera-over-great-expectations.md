# ADR-003: Pandera + dbt tests instead of Great Expectations

**Status:** Accepted

## Context
Data quality is enforced at two boundaries: raw -> bronze (Python/Polars)
and inside the warehouse (SQL models).

## Decision
- **Pandera** `DataFrameModel` contracts at raw -> bronze: typed, versioned
  with the code, able to split a batch into valid/quarantined rows.
- **dbt tests** (built-in + a custom grain test) inside the warehouse:
  uniqueness, referential integrity, not-null, grain.
- A separate 5-dimension scoring module produces the composite DQ score
  that gates the medallion DAG.

## Rationale
Great Expectations duplicates both layers with a parallel YAML/JSON config
universe, its own docs site, and heavyweight context objects. For this
surface area it adds maintenance without adding checks. Two focused tools,
each living where the data lives, are easier to review and to reason about.
