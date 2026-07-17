"""Monitoring DAG: freshness SLA check + audit heartbeat.

Emits metrics Airflow's statsd exporter forwards to Prometheus; Grafana
alerts on staleness.
"""

from datetime import datetime

from airflow.decorators import dag, task

DEFAULTS = {"retries": 0, "owner": "data-platform"}


@dag(
    dag_id="platform_monitoring",
    schedule="0 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULTS,
    tags=["monitoring", "sla"],
)
def platform_monitoring():
    @task
    def freshness_check() -> None:
        import polars as pl

        from techtrend.common.lake_io import read_parquet

        report = read_parquet("gold", "quality", "quality_report.parquet")
        freshness = report.select(pl.col("freshness")).item()
        if freshness < 0.5:
            raise ValueError(f"data freshness degraded: {freshness}")

    freshness_check()


platform_monitoring()
