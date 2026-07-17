#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 -U techtrend << 'SQL'
CREATE USER airflow WITH PASSWORD 'airflow';
CREATE DATABASE airflow OWNER airflow;
SQL
