# EXECUTION_PLAN.md — Credit Card Transactions Lake

**Version:** 2.1  
**Phase:** 3 (Execution Planning)  
**Date:** 2026-03-31  
**Status:** Draft — pending engineer sign-off

---

## Data Expectations (Seed Data Analysis)

### Source Row Counts

| File | Data Rows |
|---|---|
| transaction_codes.csv | 4 |
| transactions_YYYY-MM-DD.csv (each of 7) | 5 |
| accounts_2024-01-01.csv | 2 |
| accounts_2024-01-02 through 07.csv (each of 6) | 3 |

### Per-Day Transaction Outcome (same pattern all 7 days)

Each day has 5 transactions:
- 3 clean, resolvable transactions
- 1 ACC-ORPHAN → Silver with _is_resolvable = false
- 1 DRIVE_THRU → quarantined as INVALID_CHANNEL

Conservation per day: 5 Bronze = 4 Silver + 1 Quarantine

### Totals Across 7 Days

| Layer | Count |
|---|---|
| Bronze transactions | 35 |
| Silver transactions | 28 (21 resolvable + 7 unresolvable) |
| Quarantine | 7 |
| Silver accounts (after all days) | 3 unique |
| Silver transaction codes | 4 |

### Gold Expectations

- Daily summary: 7 rows. Day 1: total_transactions=3, total_signed_amount=-30.00, online=2, instore=1
- Weekly account summary: 3 rows (all dates in ISO week 1, Mon 2024-01-01 to Sun 2024-01-07)
- ACC-001 closing_balance: 1300.00 (day 7)

### Account Availability Timeline

| Date | Silver Accounts (cumulative) |
|---|---|
| 2024-01-01 | ACC-001, ACC-002 |
| 2024-01-02+ | ACC-001, ACC-002, ACC-003 |

ACC-ORPHAN never appears → permanently unresolvable.

---

## Risk Register (reference: RISK_REGISTER.md)

| ID | Risk | Decision |
|---|---|---|
| R1 | ref() returns last partition only | Glob patterns for cross-partition reads |
| R2 | external materialization: no incremental merge | SQL-level merge for accounts |
| R3 | External fails if directory missing | ensure_directories() before dbt |
| R4 | Version mismatch | Pin dbt-core==1.7.19, dbt-duckdb==1.7.5 |
| R5 | Schema tests validate last partition only | Two layers: schema.yml + custom glob tests |

## Technical Decisions (reference: RISK_REGISTER.md)

| ID | Decision |
|---|---|
| TD1 | All models use external materialization |
| TD2 | Shared validation as dbt macro |
| TD3 | ref() for single-file models; glob for cross-partition |
| TD4 | No persistent work tables; DuckDB = processing engine only |

---

## Session Decomposition

| Session | Name | Tasks | Est. Duration | Status |
|---|---|---|---|---|
| S1 | Environment + Foundation | 5 (3 std + 2 inv) | 2h30 – 3h40 | ✅ Under 4h |
| S2 | Bronze + Silver Dimensions | 4 (0 std + 4 inv) | 2h12 – 3h20 | ✅ Under 4h |
| S3 | Silver Transactions + Quarantine | 5 (1 std + 4 inv) | 2h40 – 4h00 | ✅ Under 4h |
| S4 | Silver Verification + Gold Models | 5 (1 std + 4 inv) | 2h40 – 4h00 | ✅ Under 4h |
| S5 | dbt Test Suite + Rejection Coverage | 5 (1 std + 4 inv) | 2h40 – 4h00 | ✅ Under 4h |
| S6 | Pipeline Runners + Docker | 5 (1 std + 4 inv) | 2h40 – 4h00 | ✅ Under 4h |
| S7 | System E2E Verification | 3 (0 std + 3 inv) | 1h39 – 2h30 | ✅ Under 4h |

Total: 32 tasks across 7 sessions. All sessions strictly under 4h limit.

Timing basis: standard task 28–40 min, invariant-touching task 33–50 min (per PBVI reference).

---

## Session 1 — Environment + Foundation

Branch: session/s1_environment_foundation
Integration check: Bronze transaction codes loaded and verified.

### S1.T1 — Environment Verification
Description: Verify toolchain. Python 3.11, dbt-core 1.7.19, dbt-duckdb 1.7.5, DuckDB.
Inputs: Raw container. Outputs: All tools installed.

CC Prompt:
Verify the development environment:
1. Confirm Python 3.11+: python3 --version
2. Install dbt-core==1.7.19 and dbt-duckdb==1.7.5
3. dbt --version (expect 1.7.19 / 1.7.5)
4. python3 -c "import duckdb; print(duckdb.__version__)"
5. DuckDB SELECT 1 test
Report exact versions. Stop on failure.

Test Cases:
| Scenario | Expected |
|---|---|
| Python version | 3.11.x |
| dbt --version | 1.7.19 / 1.7.5 |
| DuckDB import | Version string |

Verification Command: python3 --version && dbt --version && python3 -c "import duckdb; print(duckdb.__version__)"
Invariant Flag: None.

### S1.T2 — dbt Project Configuration
Description: Create dbt_project.yml, update profiles.yml for local dev.
Inputs: Scaffold dbt/. Outputs: dbt_project.yml. dbt parse succeeds.

CC Prompt:
Create dbt/dbt_project.yml (name: transactions_lake, profile: transactions_lake, model-paths: ["models"], test-paths: ["tests"]). Update profiles.yml path to data/pipeline/dbt.duckdb (relative). Create data/pipeline/ directory. Run dbt parse.

Test Cases:
| Scenario | Expected |
|---|---|
| dbt parse | No errors |

Verification Command: dbt parse --project-dir dbt/ --profiles-dir dbt/
Invariant Flag: None.

### S1.T3 — Pipeline Utilities — Paths and Run ID
Description: Path constants and run ID generator.
Inputs: None. Outputs: pipeline/lib/paths.py, pipeline/lib/run_id.py, pipeline/lib/__init__.py.

CC Prompt:
Create pipeline/lib/__init__.py (empty), pipeline/lib/paths.py (BASE_DIR, SOURCE_DIR, DATA_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, PIPELINE_DIR, CONTROL_FILE, RUN_LOG_FILE, helpers: bronze_transactions_path, bronze_accounts_path, silver_transactions_path, silver_quarantine_path, ensure_directories), pipeline/lib/run_id.py (generate_run_id → UUID4). All paths relative to BASE_DIR.

Test Cases:
| Scenario | Expected |
|---|---|
| Import paths | No error |
| bronze_transactions_path("2024-01-01") | Correct path |
| generate_run_id() | UUID4 |

Verification Command: python3 -c "from pipeline.lib.paths import *; from pipeline.lib.run_id import generate_run_id; print(bronze_transactions_path('2024-01-01')); print(generate_run_id())"
Invariant Flag: None.

### S1.T4 — Pipeline Utilities — Watermark and Run Log
Description: Watermark read/write and run log append.
Inputs: paths.py. Outputs: pipeline/lib/watermark.py, pipeline/lib/run_log.py.

CC Prompt:
Create watermark.py (read_watermark → date or None, write_watermark → writes control.parquet) and run_log.py (append_run_log → appends row, creates file if absent, APPEND-ONLY per INV-24). DuckDB for Parquet I/O. UTC timestamps.

Test Cases:
| Scenario | Expected |
|---|---|
| read_watermark() no file | None |
| write then read | Returns date |
| append twice | 2 rows, first preserved |

Verification Command: python3 -c "from pipeline.lib.watermark import *; print(read_watermark()); write_watermark('2024-01-01', 'test'); print(read_watermark())"
Invariant Flag: INV-16, INV-24. Code review: run_log never overwrites.

### S1.T5 — Bronze Loader — Transaction Codes
Description: Bronze loader for static reference file.
Inputs: source/transaction_codes.csv. Outputs: pipeline/lib/bronze_loader.py, Bronze Parquet.

CC Prompt:
Create bronze_loader.py with load_transaction_codes(run_id). If exists → SKIPPED. Validate headers. Read CSV via DuckDB. Add audit columns (_source_file, _ingested_at UTC, _pipeline_run_id). Atomic write (.tmp rename). Assert row count (INV-02). Source READ-ONLY (INV-19).

Test Cases:
| Scenario | Expected |
|---|---|
| First run | SUCCESS, 4 rows |
| Second run | SKIPPED |
| Audit columns | All non-null |

Verification Command: python3 -c "import duckdb; print(duckdb.sql(\"SELECT COUNT(*) FROM read_parquet('data/bronze/transaction_codes/data.parquet')\").fetchone())"
Invariant Flag: INV-02, INV-17, INV-19. Code review: atomic write, source read-only.

---

## Session 2 — Bronze + Silver Dimensions

Branch: session/s2_bronze_silver_dims
Integration check: All Bronze loaded. Silver dimensions ready for transaction processing.

### S2.T1 — Bronze Loader — Accounts and Transactions
Description: Date-partitioned loaders.
Inputs: Source CSVs. Outputs: load_accounts(), load_transactions() in bronze_loader.py.

CC Prompt:
Add load_accounts(date_str, run_id) and load_transactions(date_str, run_id) to bronze_loader.py. Same pattern: exists check, source check, header validation, audit columns, atomic write, row assertion, ensure_directories. Accounts headers: account_id, customer_name, account_status, credit_limit, current_balance, open_date, billing_cycle_start, billing_cycle_end. Transactions headers: transaction_id, account_id, transaction_date, amount, transaction_code, merchant_name, channel.

Test Cases:
| Scenario | Expected |
|---|---|
| accounts 2024-01-01 | 2 rows |
| accounts 2024-01-02 | 3 rows |
| transactions 2024-01-01 | 5 rows |
| Re-run | SKIPPED |
| Missing file (2024-01-08) | SKIPPED |

Verification Command: python3 -c "import duckdb; print(duckdb.sql(\"SELECT COUNT(*) FROM read_parquet('data/bronze/accounts/date=2024-01-01/data.parquet')\").fetchone())"
Invariant Flag: INV-02, INV-17, INV-19.

### S2.T2 — Bronze Full Load + Verification
Description: Load all 7 days, verify totals.
Inputs: All source CSVs. Outputs: All Bronze partitions, pipeline/verify_bronze.py.

CC Prompt:
Write and run verify_bronze.py: load all 7 days (tx_codes + accounts + transactions per day). Verify: tx_codes=4, transactions=35, accounts=20, all audit columns non-null, re-run returns SKIPPED. Print PASS/FAIL, exit code 0/1.

Test Cases:
| Scenario | Expected |
|---|---|
| Bronze tx codes | 4 |
| Bronze transactions | 35 |
| Bronze accounts | 20 |
| Re-run | All SKIPPED |

Verification Command: python3 pipeline/verify_bronze.py
Invariant Flag: INV-02, INV-17, INV-18.

### S2.T3 — silver_transaction_codes Model
Description: dbt model for Silver reference data.
Inputs: Bronze tx_codes. Outputs: dbt/models/silver/silver_transaction_codes.sql.

CC Prompt:
Create silver_transaction_codes.sql: external materialization, location=data/silver/transaction_codes/data.parquet. Read Bronze parquet. All source columns + _source_file, _bronze_ingested_at, _pipeline_run_id (from var). Run with --vars.

Test Cases:
| Scenario | Expected |
|---|---|
| Row count | 4 |
| PURCH01 indicator | DR |
| PAY01 indicator | CR |

Verification Command: python3 -c "import duckdb; print(duckdb.sql(\"SELECT transaction_code, debit_credit_indicator FROM read_parquet('data/silver/transaction_codes/data.parquet')\").fetchall())"
Invariant Flag: INV-11. Code review: no hardcoded code lists.

### S2.T4 — silver_accounts Model
Description: dbt model with SQL-level upsert.
Inputs: Bronze accounts. Outputs: dbt/models/silver/silver_accounts.sql.

CC Prompt:
Create silver_accounts.sql: external materialization, location=data/silver/accounts/data.parquet. Read Bronze for processing_date. Validate NULL_REQUIRED_FIELD and INVALID_ACCOUNT_STATUS. SQL-level upsert: read existing (if exists) + UNION new valid + dedup by account_id keeping newest. Columns: all source + _source_file, _bronze_ingested_at, _pipeline_run_id, _record_valid_from. Run for day 1 then day 2.

Test Cases:
| Scenario | Expected |
|---|---|
| After day 1 | 2 accounts |
| After day 2 | 3 accounts |
| COUNT per account_id | All = 1 |

Verification Command: python3 -c "import duckdb; print(duckdb.sql(\"SELECT account_id, current_balance FROM read_parquet('data/silver/accounts/data.parquet') ORDER BY account_id\").fetchall())"
Invariant Flag: INV-08. Code review: one row per account_id after upsert.

---

## Session 3 — Silver Transactions + Quarantine

Branch: session/s3_silver_transactions
Integration check: Conservation equation holds for day 1.

### S3.T1 — Validation Macro
Description: Shared validation logic as dbt macro.
Inputs: Architecture validation rules. Outputs: dbt/macros/transaction_validation.sql.

CC Prompt:
Create transaction_validation.sql macro. Reads Bronze transactions for processing_date. CASE WHEN chain (INV-06): 1.NULL_REQUIRED_FIELD, 2.INVALID_AMOUNT, 3.INVALID_CHANNEL, 4.INVALID_TRANSACTION_CODE (ref silver_transaction_codes), 5.DUPLICATE_TRANSACTION_ID (glob all Silver partitions, handle first run). Returns all columns + _rejection_reason. Does NOT include UNRESOLVABLE check.

Test Cases:
| Scenario | Expected |
|---|---|
| dbt parse | No errors |
| Day 1 TXN-01-005 | INVALID_CHANNEL |
| Day 1 TXN-01-001 | NULL (passes) |

Verification Command: dbt parse --project-dir dbt/ --profiles-dir dbt/
Invariant Flag: INV-01, INV-06, INV-11. Code review: exact validation order, ref for tx_codes, glob for dedup.

### S3.T2 — silver_transactions Model
Description: Validated transactions with sign and resolvability.
Inputs: Validation macro, Silver dimensions. Outputs: dbt/models/silver/silver_transactions.sql.

CC Prompt:
Create silver_transactions.sql: external, partitioned by date. Call validation macro, WHERE _rejection_reason IS NULL. Join tx_codes for _signed_amount (DR=+, CR=-). Left join accounts for _is_resolvable. Columns: all source + audit + _signed_amount + _is_resolvable + _promoted_at.

Test Cases:
| Scenario | Expected |
|---|---|
| Day 1 count | 4 |
| TXN-01-001 _signed_amount | +50.00 |
| TXN-01-003 _signed_amount | -200.00 |
| TXN-01-004 _is_resolvable | false |

Verification Command: python3 -c "import duckdb; print(duckdb.sql(\"SELECT transaction_id, _signed_amount, _is_resolvable FROM read_parquet('data/silver/transactions/date=2024-01-01/data.parquet') ORDER BY transaction_id\").fetchall())"
Invariant Flag: INV-03, INV-04, INV-07, INV-09. Code review: sign from debit_credit_indicator only.

### S3.T3 — silver_quarantine Model
Description: Rejected records.
Inputs: Validation macro. Outputs: dbt/models/silver/silver_quarantine.sql.

CC Prompt:
Create silver_quarantine.sql: external, partitioned by date. Call SAME validation macro (INV-01). WHERE _rejection_reason IS NOT NULL. Columns: all source + _source_file, _pipeline_run_id, _rejected_at, _rejection_reason. Run day 1, verify conservation.

Test Cases:
| Scenario | Expected |
|---|---|
| Day 1 quarantine | 1 |
| Rejection reason | INVALID_CHANNEL |
| Conservation: 4 + 1 = 5 | PASS |

Verification Command: python3 -c "import duckdb; s=duckdb.sql(\"SELECT COUNT(*) FROM read_parquet('data/silver/transactions/date=2024-01-01/data.parquet')\").fetchone()[0]; q=duckdb.sql(\"SELECT COUNT(*) FROM read_parquet('data/silver/quarantine/date=2024-01-01/rejected.parquet')\").fetchone()[0]; print(f'S={s} Q={q} Total={s+q} Conservation={\"PASS\" if s+q==5 else \"FAIL\"}')"
Invariant Flag: INV-01, INV-05, INV-10. Code review: same macro as silver_transactions.

### S3.T4 — Account Quarantine Integration
Description: Handle rejected accounts in quarantine.
Inputs: silver_accounts validation. Outputs: Updated quarantine + test_account_rejection.sql.

CC Prompt:
Extend silver_quarantine.sql: add account rejection CTE (NULL_REQUIRED_FIELD, INVALID_ACCOUNT_STATUS), UNION with transaction rejects. Create dbt/tests/test_account_rejection.sql with synthetic bad records (null account_id → NULL_REQUIRED_FIELD, status='INVALID' → INVALID_ACCOUNT_STATUS).

Test Cases:
| Scenario | Expected |
|---|---|
| Real data | 0 account rejects |
| Synthetic null id | NULL_REQUIRED_FIELD |
| Synthetic bad status | INVALID_ACCOUNT_STATUS |

Verification Command: dbt test --select test_account_rejection --project-dir dbt/ --profiles-dir dbt/ --vars '{"processing_date": "2024-01-01", "pipeline_run_id": "test"}'
Invariant Flag: INV-01, INV-05, INV-06.

### S3.T5 — Silver schema.yml
Description: Declarative tests for Silver models.
Inputs: Silver models. Outputs: dbt/models/silver/schema.yml.

CC Prompt:
Create schema.yml: silver_transaction_codes (unique/not_null on code, accepted_values on indicator/type), silver_accounts (unique/not_null on id, accepted_values on status), silver_transactions (not_null on id/_signed_amount/_is_resolvable/_pipeline_run_id, accepted_values on channel), silver_quarantine (not_null + accepted_values on _rejection_reason). Run dbt test.

Test Cases:
| Scenario | Expected |
|---|---|
| dbt test Silver | All pass |

Verification Command: dbt test --select silver_transaction_codes silver_accounts silver_transactions silver_quarantine --project-dir dbt/ --profiles-dir dbt/ --vars '{"processing_date": "2024-01-01", "pipeline_run_id": "test"}'
Invariant Flag: None — declarative gate.

---

## Session 4 — Silver Verification + Gold Models

Branch: session/s4_silver_verify_gold
Integration check: All 7 days verified. Gold models correct.

### S4.T1 — Silver Full Load Verification
Description: Promote all 7 days, verify conservation/uniqueness/sign/resolvability.
Inputs: All Bronze, all Silver models. Outputs: pipeline/verify_silver.py, all Silver partitions.

CC Prompt:
Write and run verify_silver.py: for each date 2024-01-01 to 07 (accounts before transactions per INV-20): ensure_directories, dbt run silver_accounts, dbt run silver_transactions+quarantine, verify conservation. After all: total Silver=28, quarantine=7, accounts=3, no dup transaction_id, no null _signed_amount, unresolvable=7. PASS/FAIL.

Test Cases:
| Scenario | Expected |
|---|---|
| Conservation per date | 5=4+1 each |
| Silver total | 28 |
| Quarantine total | 7 |
| Unique transaction_ids | 28 |

Verification Command: python3 pipeline/verify_silver.py
Invariant Flag: INV-01–INV-11, INV-20. Code review: accounts before transactions.

### S4.T2 — gold_daily_summary Model
Description: One row per transaction_date from resolvable Silver.
Inputs: Silver transactions. Outputs: dbt/models/gold/gold_daily_summary.sql.

CC Prompt:
Create gold_daily_summary.sql: external. Read Silver via glob (R1). WHERE _is_resolvable=true (INV-07). Join tx_codes for type. Group by date. Columns: transaction_date, total_transactions, total_signed_amount, online/instore counts, transactions_by_type, _computed_at, _pipeline_run_id, _source_period_start/end. ONLY reads Silver (INV-14).

Test Cases:
| Scenario | Expected |
|---|---|
| Row count | 7 |
| Day 1: total | 3, -30.00, online=2, instore=1 |

Verification Command: python3 -c "import duckdb; print(duckdb.sql(\"SELECT transaction_date, total_transactions, total_signed_amount FROM read_parquet('data/gold/daily_summary/data.parquet') ORDER BY transaction_date\").fetchall())"
Invariant Flag: INV-07, INV-12, INV-14. Code review: _is_resolvable filter, glob, no Bronze refs.

### S4.T3 — gold_weekly_account_summary Model
Description: One row per account per ISO week.
Inputs: Silver transactions, accounts, tx_codes. Outputs: dbt/models/gold/gold_weekly_account_summary.sql.

CC Prompt:
Create gold_weekly_account_summary.sql: external. Glob Silver transactions, _is_resolvable=true. Join tx_codes for type, accounts for closing_balance. Group by account_id + ISO week. Columns: week_start/end, account_id, total_purchases, avg_purchase_amount, total_payments/fees/interest, closing_balance, _computed_at, _pipeline_run_id. Only accounts with ≥1 resolvable txn.

Test Cases:
| Scenario | Expected |
|---|---|
| Row count | 3 |
| Week | 2024-01-01 to 2024-01-07 |
| ACC-001 closing_balance | 1300.00 |

Verification Command: python3 -c "import duckdb; print(duckdb.sql(\"SELECT account_id, total_purchases, closing_balance FROM read_parquet('data/gold/weekly_account_summary/data.parquet') ORDER BY account_id\").fetchall())"
Invariant Flag: INV-07, INV-13, INV-14.

### S4.T4 — Gold schema.yml
Description: Declarative tests for Gold.
Inputs: Gold models. Outputs: dbt/models/gold/schema.yml.

CC Prompt:
Create schema.yml: gold_daily_summary (transaction_date unique/not_null, totals not_null, _pipeline_run_id not_null), gold_weekly_account_summary (_pipeline_run_id not_null, custom composite uniqueness on account_id+week_start_date).

Test Cases:
| Scenario | Expected |
|---|---|
| dbt test Gold | All pass |

Verification Command: dbt test --select gold_daily_summary gold_weekly_account_summary --project-dir dbt/ --profiles-dir dbt/ --vars '{"pipeline_run_id": "test"}'
Invariant Flag: INV-12, INV-13.

### S4.T5 — Fix Existing Test Stubs
Description: Verify/fix 3 scaffold test stubs.
Inputs: Scaffold tests. Outputs: Fixed tests.

CC Prompt:
Review dbt/tests/: test_conservation_law.sql, test_gold_promotion_gate.sql, test_tx_codes_conservation.sql. Update invariant references to INV-XX numbering. Run and fix failures. Note: gold_promotion_gate tests run_log which isn't populated yet — verify it compiles, defer full test to S6.

Test Cases:
| Scenario | Expected |
|---|---|
| conservation + tx_codes tests | Pass |

Verification Command: dbt test --select test_conservation_law test_tx_codes_conservation --project-dir dbt/ --profiles-dir dbt/ --vars '{"processing_date": "2024-01-01", "pipeline_run_id": "test"}'
Invariant Flag: INV-01, INV-22.

---

## Session 5 — dbt Test Suite + Rejection Coverage

Branch: session/s5_test_suite
Integration check: Full dbt test suite passes. All rejection codes verified.

### S5.T1 — Gold-Silver Amount Reconciliation Test
Description: Gold totals match Silver sums.
Inputs: Gold/Silver data. Outputs: dbt/tests/test_gold_daily_matches_silver.sql.

CC Prompt:
Compare Gold total_signed_amount per date vs SUM(_signed_amount) from Silver (glob) WHERE _is_resolvable=true. Also check total_transactions count. Return mismatches (0=pass). Tolerance ABS(diff) > 0.01.

Test Cases:
| Scenario | Expected |
|---|---|
| All 7 days match | 0 rows |

Verification Command: dbt test --select test_gold_daily_matches_silver --project-dir dbt/ --profiles-dir dbt/ --vars '{"pipeline_run_id": "test"}'
Invariant Flag: INV-07, INV-12.

### S5.T2 — Cross-Partition Uniqueness Test
Description: No duplicate transaction_id across all Silver partitions.
Inputs: Silver transactions. Outputs: dbt/tests/test_cross_partition_uniqueness.sql.

CC Prompt:
Read all Silver partitions via glob. GROUP BY transaction_id HAVING COUNT(*)>1. Return duplicates (0=pass). Tests INV-03 across ALL partitions.

Test Cases:
| Scenario | Expected |
|---|---|
| 28 records, 0 duplicates | 0 rows |

Verification Command: dbt test --select test_cross_partition_uniqueness --project-dir dbt/ --profiles-dir dbt/ --vars '{"pipeline_run_id": "test"}'
Invariant Flag: INV-03.

### S5.T3 — No-Unresolvable-in-Gold Test
Description: Gold only includes resolvable transactions.
Inputs: Gold/Silver data. Outputs: dbt/tests/test_no_unresolvable_in_gold.sql.

CC Prompt:
Compare Gold total_transactions per date vs COUNT from Silver WHERE _is_resolvable=true. If Gold exceeds → leak. Return mismatches (0=pass).

Test Cases:
| Scenario | Expected |
|---|---|
| Counts match | 0 rows |

Verification Command: dbt test --select test_no_unresolvable_in_gold --project-dir dbt/ --profiles-dir dbt/ --vars '{"pipeline_run_id": "test"}'
Invariant Flag: INV-07.

### S5.T4 — Rejection Code Coverage Tests
Description: All 6 transaction + 2 account rejection codes verified with synthetic data.
Inputs: Validation logic. Outputs: dbt/tests/test_rejection_codes.sql.

CC Prompt:
CTE with synthetic records: null txn_id → NULL_REQUIRED_FIELD, amount=0 → INVALID_AMOUNT, amount=-5 → INVALID_AMOUNT, channel='PHONE' → INVALID_CHANNEL, code='INVALID99' → INVALID_TRANSACTION_CODE, null amount + invalid channel → NULL_REQUIRED_FIELD (first wins, INV-06), status='DELETED' → INVALID_ACCOUNT_STATUS, null account_id → NULL_REQUIRED_FIELD. Apply validation logic, compare actual vs expected. Return mismatches (0=pass).

Test Cases:
| Scenario | Expected |
|---|---|
| Each synthetic record | Correct rejection code |
| Validation order | First failure wins |

Verification Command: dbt test --select test_rejection_codes --project-dir dbt/ --profiles-dir dbt/ --vars '{"pipeline_run_id": "test"}'
Invariant Flag: INV-05, INV-06, INV-10.

### S5.T5 — Full Test Suite Run
Description: Run complete suite, fix failures.
Inputs: All models/tests. Outputs: Clean test run.

CC Prompt:
Run full dbt test suite. Report pass/fail/error. Fix failures. Run conservation for all 7 dates. Final summary.

Test Cases:
| Scenario | Expected |
|---|---|
| Full suite | All pass |

Verification Command: dbt test --project-dir dbt/ --profiles-dir dbt/ --vars '{"processing_date": "2024-01-07", "pipeline_run_id": "test"}'
Invariant Flag: None — session integration check.

---

## Session 6 — Pipeline Runners + Docker

Branch: session/s6_pipeline_docker
Integration check: Historical + incremental pipelines work locally. Docker builds.

### S6.T1 — Historical Pipeline — Core Loop + Bronze Orchestration
Description: Core pipeline structure: CLI args, file lock, date loop, Bronze loading calls.
Inputs: All Bronze loaders, paths module. Outputs: pipeline/pipeline_historical.py (partial — Bronze orchestration only).

CC Prompt:
Create pipeline_historical.py with: CLI args start_date/end_date, file lock via fcntl.flock (INV-21 — fail immediately if locked), generate run_id, load_transaction_codes, for each date in range: ensure_directories, load_accounts, load_transactions. Accounts before transactions (INV-20). Error handling: any Bronze failure → log, stop. Do NOT add dbt invocation yet — next task. Verify by running Bronze load for 2024-01-01 to 2024-01-07.

Test Cases:
| Scenario | Expected |
|---|---|
| Bronze loads all 7 days | 35 txns, 20 accts, 4 codes |
| Lock acquired | File lock exists |
| Accounts before transactions | Ordering enforced |

Verification Command: rm -rf data/ && python3 pipeline/pipeline_historical.py 2024-01-01 2024-01-07 && python3 -c "import duckdb; print(duckdb.sql(\"SELECT COUNT(*) FROM read_parquet('data/bronze/transactions/date=*/data.parquet')\").fetchone())"
Invariant Flag: INV-20, INV-21. Code review: lock acquisition, date ordering, accounts-before-transactions.

### S6.T2 — Historical Pipeline — dbt Invocation + Run Log + Watermark
Description: Add Silver/Gold dbt invocation, conservation gating, run log, watermark advance.
Inputs: S6.T1 pipeline_historical.py. Outputs: Complete pipeline_historical.py.

CC Prompt:
Extend pipeline_historical.py: after Bronze per date → dbt run silver_accounts, dbt run silver_transactions+quarantine, dbt test conservation (fail → STOP per INV-01). After all dates: dbt run Gold models. Parse target/run_results.json for per-model metadata. Watermark on full success only (INV-16). Append run_log entries (INV-23). Error: no watermark advance, no downstream. dbt invocation via subprocess with --vars for pipeline_run_id and processing_date.

Test Cases:
| Scenario | Expected |
|---|---|
| Full run 01-01 to 01-07 | All layers complete |
| Watermark | 2024-01-07 |
| Run log | Entries for every model, same run_id |
| Conservation per date | 5 = 4 + 1 all 7 days |

Verification Command: rm -rf data/ && python3 pipeline/pipeline_historical.py 2024-01-01 2024-01-07 && python3 -c "from pipeline.lib.watermark import read_watermark; print(read_watermark())"
Invariant Flag: INV-01, INV-16, INV-22, INV-23. Code review: watermark only on full success, conservation as gate.

### S6.T3 — Incremental Pipeline Runner
Description: Process next unprocessed date.
Inputs: Watermark, loaders, models. Outputs: pipeline/pipeline_incremental.py.

CC Prompt:
Create pipeline_incremental.py: lock, read watermark (None → error), next_date = wm+1, check source files (absent → SKIPPED, no advance), Bronze → Silver → Gold, conservation test, advance watermark on success, run log, freshness warning if wm >2 days behind.

Test Cases:
| Scenario | Expected |
|---|---|
| After historical, no 01-08 | SKIPPED, wm unchanged |
| Run again | SKIPPED again |

Verification Command: python3 pipeline/pipeline_incremental.py && python3 -c "from pipeline.lib.watermark import read_watermark; print(read_watermark())"
Invariant Flag: INV-16, INV-18, INV-20, INV-21.

### S6.T4 — Dockerfile + docker-compose.yml
Description: Docker config for single-command startup.
Inputs: All code. Outputs: Dockerfile, docker-compose.yml.

CC Prompt:
Dockerfile: python:3.11-slim, install dbt-core==1.7.19 dbt-duckdb==1.7.5, WORKDIR /app, copy pipeline/ dbt/ source/. docker-compose.yml: service pipeline, volumes source:ro + data:rw. Update profiles.yml for Docker path. Build and verify.

Test Cases:
| Scenario | Expected |
|---|---|
| docker compose build | Success |
| Container dbt version | 1.7.19/1.7.5 |

Verification Command: docker compose build && docker compose run pipeline dbt --version
Invariant Flag: INV-19. Code review: source read-only mount.

### S6.T5 — Concurrent Run Prevention Test
Description: Verify two simultaneous pipeline instances cannot run.
Inputs: pipeline_historical.py. Outputs: pipeline/test_concurrent.py.

CC Prompt:
Create test_concurrent.py: spawn historical in subprocess, wait 1s, attempt incremental, verify second fails with lock error, wait for first to complete. PASS if second rejected.

Test Cases:
| Scenario | Expected |
|---|---|
| Two simultaneous runs | Second fails immediately |

Verification Command: python3 pipeline/test_concurrent.py
Invariant Flag: INV-21.

---

## Session 7 — System E2E Verification

Branch: session/s7_system_verification
Integration check: Full system verified in Docker. All 24 invariants pass.

### S7.T1 — Docker E2E Test
Description: Clean-slate Docker run — wipe data, run historical, verify all layers.
Inputs: Docker config. Outputs: pipeline/test_e2e_docker.sh.

CC Prompt:
Create and run test_e2e_docker.sh: rm -rf data/, docker compose run historical 01-01 to 01-07, verify inside container: Bronze (35+20+4), Silver (28+7+3+4), Gold (7+3), watermark (01-07), run_log (all SUCCESS), docker compose run incremental → SKIPPED, watermark unchanged. PASS/FAIL summary.

Test Cases:
| Scenario | Expected |
|---|---|
| Docker E2E all counts | All match expectations |
| Incremental after historical | SKIPPED |

Verification Command: bash pipeline/test_e2e_docker.sh
Invariant Flag: ALL (system-level integration test).

### S7.T2 — Idempotency Verification
Description: Re-run full pipeline, verify identical outputs.
Inputs: Fully loaded system. Outputs: pipeline/verify_idempotency.py.

CC Prompt:
Create and run verify_idempotency.py: record counts at every layer, re-run historical 01-01 to 01-07, compare all counts (identical), watermark unchanged, run_log previous entries preserved (INV-24), new entries appended.

Test Cases:
| Scenario | Expected |
|---|---|
| Bronze counts after re-run | Identical |
| Silver counts | Identical |
| Gold counts | Identical |
| Run log previous preserved | PASS |

Verification Command: python3 pipeline/verify_idempotency.py
Invariant Flag: INV-17, INV-18, INV-24.

### S7.T3 — Unresolvable Flag Permanence Test
Description: Verify _is_resolvable = false is permanent.
Inputs: Silver transactions. Outputs: pipeline/test_flag_permanence.py.

CC Prompt:
Create and run test_flag_permanence.py: query Silver for ACC-ORPHAN transactions, confirm all 7 have _is_resolvable=false, confirm unchanged after re-run. Document: flag reflects state at promotion time, not current state.

Test Cases:
| Scenario | Expected |
|---|---|
| ACC-ORPHAN all false | 7 records, all false |
| After re-run | Still false |

Verification Command: python3 pipeline/test_flag_permanence.py
Invariant Flag: INV-15.

---

## Invariant Coverage Matrix

| Invariant | Tasks |
|---|---|
| INV-01 Conservation | S3.T1, S3.T3, S3.T4, S4.T1, S4.T5, S5.T1, S6.T2 |
| INV-02 Source-to-Bronze | S1.T5, S2.T1, S2.T2 |
| INV-03 Cross-Partition Uniqueness | S3.T2, S4.T1, S5.T2 |
| INV-04 Sign Integrity | S3.T2, S3.T5, S4.T1 |
| INV-05 Quarantine Reason Validity | S3.T3, S3.T4, S3.T5, S4.T1, S5.T4 |
| INV-06 Validation Order | S3.T1, S3.T4, S5.T4 |
| INV-07 Gold Exclusion | S3.T2, S4.T2, S4.T3, S5.T1, S5.T3 |
| INV-08 Accounts Uniqueness | S2.T4, S4.T1 |
| INV-09 Silver Txn Granularity | S3.T2, S4.T1 |
| INV-10 Quarantine Granularity | S3.T3, S5.T4 |
| INV-11 Txn Code Referential | S2.T3, S3.T1 |
| INV-12 Gold Daily Granularity | S4.T2, S4.T4, S5.T1 |
| INV-13 Gold Weekly Granularity | S4.T3, S4.T4 |
| INV-14 Gold Layer Boundary | S4.T2, S4.T3 (code review) |
| INV-15 Flag Permanence | S7.T3 |
| INV-16 Watermark Integrity | S1.T4, S6.T2, S6.T3 |
| INV-17 Bronze Immutability | S1.T5, S2.T1, S7.T2 |
| INV-18 Idempotency | S2.T2, S6.T3, S7.T2 |
| INV-19 Source Read-Only | S1.T5, S2.T1, S6.T4 |
| INV-20 Processing Order | S4.T1, S6.T1, S6.T3 |
| INV-21 Concurrent Prevention | S6.T1, S6.T3, S6.T5 |
| INV-22 Run ID Traceability | S4.T5, S6.T2 |
| INV-23 Run Log Completeness | S6.T2 |
| INV-24 Run Log Append-Only | S1.T4, S7.T2 |

Coverage: 24/24 invariants verified.

---

## Open Questions — RESOLVED

1. dbt-duckdb Parquet output: external materialization with location config. Confirmed 1.7.5.
2. Shared validation: dbt macro in macros/transaction_validation.sql.
3. Conservation test scoping: per-date with --vars + cross-date with glob.

---

*End of EXECUTION_PLAN.md v2.1 — Phase 3 output.*
*7 sessions, 32 tasks, 24 invariants covered.*
*All sessions strictly under 4-hour limit.*
*Pending: Engineer sign-off before Phase 5 (Claude.md).*
