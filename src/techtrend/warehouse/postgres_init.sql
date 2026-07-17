-- ============================================================================
-- TechTrend warehouse -- PostgreSQL physical design (Docker/cloud target).
-- Applied once by the compose init container. dbt (target: postgres) builds
-- staging/marts on top; the partitioned fact and operational tables below
-- are the physical layer dbt writes into / alongside.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ops;

-- ---------------------------------------------------------------- audit ----
CREATE TABLE IF NOT EXISTS ops.pipeline_audit (
    audit_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline        TEXT        NOT NULL,
    run_id          TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running',
    rows_processed  BIGINT,
    details         JSONB
);
CREATE INDEX IF NOT EXISTS idx_audit_pipeline_time
    ON ops.pipeline_audit (pipeline, started_at DESC);

-- ------------------------------------------------------------- metadata ----
CREATE TABLE IF NOT EXISTS ops.ingestion_state (
    source      TEXT PRIMARY KEY,
    watermark   TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.dataset_registry (
    dataset       TEXT PRIMARY KEY,
    layer         TEXT NOT NULL,
    grain         TEXT NOT NULL,
    owner         TEXT NOT NULL DEFAULT 'data-platform',
    schema_hash   TEXT,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------ partitioned fact (physical) ----
-- Monthly RANGE partitions; date predicates prune, old months detach cheaply.
CREATE TABLE IF NOT EXISTS analytics.fact_price_observation_p (
    product_sk          TEXT      NOT NULL,
    product_nk          INTEGER   NOT NULL,
    date_sk             INTEGER   NOT NULL,
    price               NUMERIC(10,2) NOT NULL CHECK (price > 0),
    original_price      NUMERIC(10,2),
    discount_percentage NUMERIC(5,2) DEFAULT 0,
    availability        TEXT,
    stock_level         INTEGER,
    rating              NUMERIC(3,2),
    review_count        INTEGER,
    sales_velocity      NUMERIC(10,2),
    is_trending         BOOLEAN
) PARTITION BY RANGE (date_sk);

CREATE INDEX IF NOT EXISTS idx_fact_product_date
    ON analytics.fact_price_observation_p (product_sk, date_sk);
CREATE INDEX IF NOT EXISTS idx_fact_date_brin
    ON analytics.fact_price_observation_p USING brin (date_sk);

-- Helper to create a month partition idempotently (called by the load DAG).
CREATE OR REPLACE FUNCTION analytics.ensure_month_partition(p_yyyymm TEXT)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    lo INTEGER := (p_yyyymm || '01')::INTEGER;
    hi INTEGER := to_char((to_date(p_yyyymm || '01', 'YYYYMMDD')
                           + INTERVAL '1 month'), 'YYYYMMDD')::INTEGER;
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS analytics.fact_price_observation_p_%s
         PARTITION OF analytics.fact_price_observation_p
         FOR VALUES FROM (%s) TO (%s)', p_yyyymm, lo, hi);
END $$;

-- ------------------------------------------------- materialised rollup ----
-- Refreshed by the reporting DAG after each warehouse build.
-- (Created lazily because it depends on dbt-built relations.)
CREATE OR REPLACE FUNCTION analytics.refresh_rollups() RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF to_regclass('analytics.mv_category_daily') IS NULL THEN
        EXECUTE 'CREATE MATERIALIZED VIEW analytics.mv_category_daily AS
                 SELECT * FROM analytics.agg_category_daily';
        EXECUTE 'CREATE INDEX ON analytics.mv_category_daily (category, full_date)';
    ELSE
        EXECUTE 'REFRESH MATERIALIZED VIEW analytics.mv_category_daily';
    END IF;
END $$;
