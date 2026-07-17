select * from read_parquet('{{ var("lake_root") }}/gold/quality/quality_report.parquet')
