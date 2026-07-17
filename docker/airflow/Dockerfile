FROM apache/airflow:2.9.3-python3.11
WORKDIR /opt/techtrend

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[ml,postgres]" && pip install --no-cache-dir s3fs
