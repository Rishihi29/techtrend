"""Experiment tracking.

Logs every training run -- params, metrics, model identity -- to MLflow
when a tracking server is configured (the Docker stack runs one backed by
Postgres + MinIO). Without a server, runs are journaled to a local JSON
run-log so training remains fully auditable in the zero-service demo.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from techtrend.common.logging import get_logger
from techtrend.config.settings import get_settings

log = get_logger(__name__)


def log_run(
    experiment: str,
    params: dict[str, Any],
    metrics: dict[str, float],
    tags: dict[str, str] | None = None,
) -> str:
    """Record one training run; returns the run id."""
    settings = get_settings()
    if settings.mlflow_tracking_uri:
        try:
            import mlflow

            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            mlflow.set_experiment(experiment)
            with mlflow.start_run() as run:
                mlflow.log_params(params)
                mlflow.log_metrics(metrics)
                if tags:
                    mlflow.set_tags(tags)
                return run.info.run_id
        except Exception as exc:  # tracking must never fail the pipeline
            log.warning("mlflow_unavailable_falling_back", error=str(exc))

    run_id = uuid.uuid4().hex[:12]
    record = {
        "run_id": run_id,
        "experiment": experiment,
        "logged_at": datetime.now(UTC).isoformat(),
        "params": params,
        "metrics": metrics,
        "tags": tags or {},
    }
    runlog = settings.local_dir("data", "mlruns") / "runs.jsonl"
    with runlog.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    log.info("run_logged", backend="local", **{"experiment": experiment, "run_id": run_id})
    return run_id


def make_regressor(**params: Any):
    """LightGBM when installed (Docker image), otherwise scikit-learn's
    HistGradientBoostingRegressor -- same algorithm family, zero native deps."""
    try:
        from lightgbm import LGBMRegressor

        return LGBMRegressor(random_state=42, verbose=-1, **params), "lightgbm"
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor

        params.pop("n_estimators", None)
        return HistGradientBoostingRegressor(random_state=42, **params), "sklearn_hgb"
