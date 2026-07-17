# Cloud Deployment Mapping

Every stateful dependency sits behind configuration; nothing in application
code names a vendor.

| Local component | AWS | Azure | GCP | Switch |
|---|---|---|---|---|
| Lake (MinIO / local FS) | S3 | ADLS Gen2 | GCS | `TECHTREND_LAKE_ROOT`, S3 creds env vars |
| Warehouse (Postgres) | RDS / Aurora / Redshift* | Azure Database / Synapse* | Cloud SQL / BigQuery* | `TECHTREND_POSTGRES_DSN` (+ dbt adapter for *) |
| Airflow | MWAA | -- (AKS / Astronomer) | Cloud Composer | mount `dags/`, install the package |
| MLflow | ECS + RDS + S3 | AKS + ADLS | Cloud Run + GCS | `TECHTREND_MLFLOW_TRACKING_URI` |
| API container | ECS Fargate / App Runner | Container Apps | Cloud Run | push `docker/api` image |
| Prometheus/Grafana | AMP + AMG | Azure Monitor | GMP + Grafana | scrape same `/metrics` |
| Secrets (.env) | Secrets Manager | Key Vault | Secret Manager | inject as env at deploy |

*Columnar warehouses need the matching dbt adapter (`dbt-redshift`,
`dbt-bigquery`, …); models are ANSI-leaning and the CI DuckDB target keeps
them honest about portability.

Recommended first cloud increment: S3 + RDS + MWAA using the existing
images -- no code change, only environment.
