# Contributing

## Setup
```bash
make install
pre-commit install
```

## Workflow
1. Branch from `main`; keep changes scoped to one concern.
2. `make lint && make typecheck && make test` must pass locally.
3. If you touch the warehouse, run `make demo` — CI executes the full
   pipeline, so a broken dbt model fails your PR.
4. Architectural changes need an ADR in `docs/adr/` (copy an existing one).

## Conventions
- Business logic lives in `src/techtrend/`; DAGs orchestrate only.
- All SQL is parameterised; all config comes from `Settings`.
- New datasets get a Pandera contract before they get a bronze table.
