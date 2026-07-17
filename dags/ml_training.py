"""Weekly ML training DAG: forecasting, anomaly detection, recommendations.

Each model logs to MLflow; scores are published to gold and picked up by
the next warehouse build.
"""

from datetime import datetime, timedelta

from airflow.datasets import Dataset
from airflow.decorators import dag, task

ML_SCORES = Dataset("lake://gold/ml")

DEFAULTS = {"retries": 1, "retry_delay": timedelta(minutes=10), "owner": "ml-platform"}


@dag(
    dag_id="ml_training_weekly",
    schedule="0 4 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULTS,
    tags=["ml", "mlflow"],
)
def ml_training_weekly():
    @task
    def price_forecast() -> None:
        from techtrend.ml import forecasting

        forecasting.train_and_forecast(target="price")

    @task
    def demand_forecast() -> None:
        from techtrend.ml import forecasting

        forecasting.train_and_forecast(target="sales_velocity")

    @task
    def anomalies() -> None:
        from techtrend.ml import anomaly

        anomaly.detect()

    @task(outlets=[ML_SCORES])
    def recommendations() -> None:
        from techtrend.ml import recommend

        recommend.build()

    [price_forecast(), demand_forecast(), anomalies()] >> recommendations()


ml_training_weekly()
