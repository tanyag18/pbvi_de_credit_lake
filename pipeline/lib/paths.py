from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SOURCE_DIR = BASE_DIR / "source"
DATA_DIR = BASE_DIR / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
PIPELINE_DIR = DATA_DIR / "pipeline"
CONTROL_FILE = PIPELINE_DIR / "control.parquet"
RUN_LOG_FILE = PIPELINE_DIR / "run_log.parquet"


def bronze_transaction_codes_path():
    return BRONZE_DIR / "transaction_codes" / "data.parquet"


def bronze_accounts_path(date_str):
    return BRONZE_DIR / "accounts" / f"date={date_str}" / "data.parquet"


def bronze_transactions_path(date_str):
    return BRONZE_DIR / "transactions" / f"date={date_str}" / "data.parquet"


def silver_transactions_path(date_str):
    return SILVER_DIR / "transactions" / f"date={date_str}" / "data.parquet"


def silver_quarantine_path(date_str):
    return SILVER_DIR / "quarantine" / f"date={date_str}" / "rejected.parquet"


def ensure_directories(date_str):
    dirs = [
        BRONZE_DIR / "transaction_codes",
        BRONZE_DIR / "accounts" / f"date={date_str}",
        BRONZE_DIR / "transactions" / f"date={date_str}",
        SILVER_DIR / "transaction_codes",
        SILVER_DIR / "accounts",
        SILVER_DIR / "transactions" / f"date={date_str}",
        SILVER_DIR / "quarantine" / f"date={date_str}",
        GOLD_DIR / "daily_summary",
        GOLD_DIR / "weekly_account_summary",
        PIPELINE_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
