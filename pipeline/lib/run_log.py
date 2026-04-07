import duckdb
from datetime import datetime, timezone
from pipeline.lib.paths import RUN_LOG_FILE, PIPELINE_DIR


def append_run_log(run_id, pipeline_type, model_name, layer,
                   status, records_processed=0, records_written=0,
                   records_rejected=0, error_message=None):
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    err = f"'{error_message}'" if error_message else "NULL"
    new_row_sql = f"""
        SELECT
            CAST('{run_id}' AS VARCHAR) AS run_id,
            CAST('{pipeline_type}' AS VARCHAR) AS pipeline_type,
            CAST('{model_name}' AS VARCHAR) AS model_name,
            CAST('{layer}' AS VARCHAR) AS layer,
            CAST('{now}' AS TIMESTAMP) AS started_at,
            CAST('{now}' AS TIMESTAMP) AS completed_at,
            CAST('{status}' AS VARCHAR) AS status,
            CAST({records_processed} AS INTEGER) AS records_processed,
            CAST({records_written} AS INTEGER) AS records_written,
            CAST({records_rejected} AS INTEGER) AS records_rejected,
            CAST({err} AS VARCHAR) AS error_message
    """

    tmp_file = RUN_LOG_FILE.with_suffix(".tmp")

    if RUN_LOG_FILE.exists():
        # Append-only: read existing + union new row (INV-24)
        duckdb.sql(
            f"""
            COPY (
                SELECT * FROM read_parquet('{RUN_LOG_FILE}')
                UNION ALL
                {new_row_sql}
            ) TO '{tmp_file}' (FORMAT PARQUET)
            """
        )
    else:
        duckdb.sql(
            f"COPY ({new_row_sql}) TO '{tmp_file}' (FORMAT PARQUET)"
        )

    tmp_file.replace(RUN_LOG_FILE)
