import duckdb
from datetime import datetime, timezone
from pipeline.lib.paths import (
    SOURCE_DIR, bronze_transaction_codes_path, bronze_accounts_path,
    bronze_transactions_path,
)

EXPECTED_TX_CODES_HEADER = [
    "transaction_code", "description", "debit_credit_indicator",
    "transaction_type", "affects_balance",
]

EXPECTED_ACCOUNTS_HEADER = [
    "account_id", "customer_name", "account_status", "credit_limit",
    "current_balance", "open_date", "billing_cycle_start", "billing_cycle_end",
]

EXPECTED_TRANSACTIONS_HEADER = [
    "transaction_id", "account_id", "transaction_date", "amount",
    "transaction_code", "merchant_name", "channel",
]


def _validate_header(source_file, expected_header):
    with open(source_file, "r") as f:
        header_line = f.readline().strip()
    actual = [c.strip() for c in header_line.split(",")]
    if actual != expected_header:
        raise ValueError(
            f"Header mismatch in {source_file}. "
            f"Expected: {expected_header}, Got: {actual}"
        )


def _count_data_rows(source_file):
    with open(source_file, "r") as f:
        lines = f.readlines()
    # Exclude header and empty trailing lines
    return sum(1 for line in lines[1:] if line.strip())


def load_transaction_codes(run_id):
    output_path = bronze_transaction_codes_path()

    # INV-17: if exists, skip entirely
    if output_path.exists():
        return "SKIPPED", 0

    source_file = SOURCE_DIR / "transaction_codes.csv"
    _validate_header(source_file, EXPECTED_TX_CODES_HEADER)
    expected_rows = _count_data_rows(source_file)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    tmp_file = output_path.with_suffix(".tmp")

    # INV-19: source read-only — only SELECT/read operations
    duckdb.sql(f"""
        COPY (
            SELECT
                *,
                CAST('{source_file}' AS VARCHAR) AS _source_file,
                CAST('{now}' AS TIMESTAMP) AS _ingested_at,
                CAST('{run_id}' AS VARCHAR) AS _pipeline_run_id
            FROM read_csv_auto('{source_file}')
        ) TO '{tmp_file}' (FORMAT PARQUET)
    """)

    # INV-02: assert row count matches source
    written_rows = duckdb.sql(
        f"SELECT COUNT(*) FROM read_parquet('{tmp_file}')"
    ).fetchone()[0]
    assert written_rows == expected_rows, (
        f"INV-02 violation: expected {expected_rows} rows, wrote {written_rows}"
    )

    tmp_file.replace(output_path)
    return "SUCCESS", written_rows
