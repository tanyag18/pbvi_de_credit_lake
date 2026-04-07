import duckdb
from datetime import datetime, timezone
from pipeline.lib.paths import CONTROL_FILE, PIPELINE_DIR


def read_watermark():
    if not CONTROL_FILE.exists():
        return None
    result = duckdb.sql(
        f"SELECT last_processed_date FROM read_parquet('{CONTROL_FILE}') "
        "ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    if result is None:
        return None
    return result[0]


def write_watermark(date_str, run_id):
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    tmp_file = CONTROL_FILE.with_suffix(".tmp")
    duckdb.sql(
        f"""
        COPY (
            SELECT
                CAST('{date_str}' AS DATE) AS last_processed_date,
                CAST('{now}' AS TIMESTAMP) AS updated_at,
                CAST('{run_id}' AS VARCHAR) AS updated_by_run_id
        ) TO '{tmp_file}' (FORMAT PARQUET)
        """
    )
    tmp_file.replace(CONTROL_FILE)
