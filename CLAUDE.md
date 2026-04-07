# Claude.md — v1.0 · FROZEN · 2026-03-31

## 1. System Intent

This system is a Medallion data lake (Bronze → Silver → Gold) that ingests daily CSV credit card transaction extracts, enforces quality rules at each layer boundary, and produces trusted Gold aggregations queryable via DuckDB. It does not compute risk, make credit decisions, modify source records, handle schema evolution, provide a serving API, or retain account history (no SCD2). Success: an analyst queries Gold, gets a number, and traces it backward through `_pipeline_run_id` to the exact source CSV — or sees exactly why a record was rejected.

---

## 2. Hard Invariants

**INVARIANT INV-01 (Conservation Equation):** For every processed date, Bronze record count = Silver record count + Quarantine record count, per entity. No record in both. No record in neither. This is never negotiable.

**INVARIANT INV-02 (Source-to-Bronze Completeness):** Bronze partition row count must exactly equal source CSV row count (excluding header). No rows added, removed, or modified beyond audit columns. This is never negotiable.

**INVARIANT INV-03 (Cross-Partition Transaction Uniqueness):** A transaction_id may appear at most once across ALL Silver transaction partitions. Duplicates go to quarantine as DUPLICATE_TRANSACTION_ID. This is never negotiable.

**INVARIANT INV-04 (Sign Amount Integrity):** Every Silver transaction has non-null `_signed_amount` = +amount when debit_credit_indicator=DR, -amount when CR. Transaction Codes dimension is the sole authority for sign — no hardcoded sign mappings anywhere. This is never negotiable.

**INVARIANT INV-05 (Quarantine Reason Validity):** Every quarantine record has non-null `_rejection_reason` from exactly this list: NULL_REQUIRED_FIELD, INVALID_AMOUNT, INVALID_CHANNEL, INVALID_TRANSACTION_CODE, DUPLICATE_TRANSACTION_ID, INVALID_ACCOUNT_STATUS. No other codes. This is never negotiable.

**INVARIANT INV-06 (Validation Order — First Failure Wins):** Transaction validation executes in this exact order, stopping at first failure: (1) NULL_REQUIRED_FIELD, (2) INVALID_AMOUNT, (3) INVALID_CHANNEL, (4) INVALID_TRANSACTION_CODE, (5) DUPLICATE_TRANSACTION_ID. UNRESOLVABLE_ACCOUNT_ID (6) is flag-only on passing records. Account validation: (1) NULL_REQUIRED_FIELD, (2) INVALID_ACCOUNT_STATUS. This is never negotiable.

**INVARIANT INV-07 (Gold Exclusion Boundary):** Gold aggregations include ONLY Silver transactions where `_is_resolvable = true`. This filter must exist in every Gold model reading Silver transactions. This is never negotiable.

**INVARIANT INV-08 (Accounts Dimension Uniqueness):** Silver accounts contains at most one row per account_id at all times. This is never negotiable.

**INVARIANT INV-09 (Silver Transaction Granularity):** Each Bronze transaction passing validation produces exactly one Silver record. No aggregation, splitting, or reshaping. This is never negotiable.

**INVARIANT INV-10 (Quarantine Granularity):** Each rejected record produces exactly one quarantine entry with exactly one rejection reason. This is never negotiable.

**INVARIANT INV-11 (Transaction Code Referential Integrity):** Transaction code validation uses Silver transaction_codes dimension only. No hardcoded lists of valid codes anywhere. This is never negotiable.

**INVARIANT INV-12 (Gold Daily Summary Granularity):** Exactly one row per distinct transaction_date in resolvable Silver transactions. This is never negotiable.

**INVARIANT INV-13 (Gold Weekly Account Summary Granularity):** Exactly one row per account_id per ISO week (Mon–Sun). Only accounts with ≥1 resolvable transaction included. This is never negotiable.

**INVARIANT INV-14 (Gold Layer Boundary):** Gold reads exclusively from Silver. No Gold model references Bronze, source CSVs, run log, or control table. This is never negotiable.

**INVARIANT INV-15 (Unresolvable Flag Permanence):** Once `_is_resolvable = false`, subsequent runs must not retroactively change it to true. This is never negotiable.

**INVARIANT INV-16 (Watermark Integrity):** Watermark advances only after Bronze + Silver + Gold all complete successfully for a date. Partial failure = watermark unchanged. This is never negotiable.

**INVARIANT INV-17 (Bronze Immutability):** Once written, a Bronze partition is never overwritten, modified, or deleted. If partition exists, skip entirely. This is never negotiable.

**INVARIANT INV-18 (Idempotency):** Running the pipeline N times on the same input produces identical row counts at every layer. No new file for next date = no changes, no watermark advance. This is never negotiable.

**INVARIANT INV-19 (Source File Read-Only):** Pipeline never modifies, moves, renames, or deletes any file in source/. This is never negotiable.

**INVARIANT INV-20 (Processing Order):** For any date, accounts must be loaded to Bronze AND promoted to Silver BEFORE transactions for that date are promoted to Silver. Enforced by pipeline orchestrator, not dbt dependency resolution. This is never negotiable.

**INVARIANT INV-21 (Concurrent Run Prevention):** At most one pipeline instance at a time. File-based lock (fcntl.flock). Second invocation fails immediately. This is never negotiable.

**INVARIANT INV-22 (Run ID Traceability):** Every record at every layer has non-null `_pipeline_run_id`. Every run_id in Silver/Quarantine/Gold has a corresponding run_log entry with status=SUCCESS. This is never negotiable.

**INVARIANT INV-23 (Run Log Completeness):** Every pipeline invocation produces one run_log entry per model/loader. All share the same run_id. Status: SUCCESS, FAILED, or SKIPPED. This is never negotiable.

**INVARIANT INV-24 (Run Log Append-Only):** Run log is appended to, never overwritten or truncated. Previous entries preserved across all runs. This is never negotiable.

---

## 3. Scope Boundary

### Files CC May Create or Modify

**Pipeline Python (pipeline/):**
`pipeline/__init__.py`, `pipeline/lib/__init__.py`, `pipeline/lib/paths.py`, `pipeline/lib/run_id.py`, `pipeline/lib/watermark.py`, `pipeline/lib/run_log.py`, `pipeline/lib/bronze_loader.py`, `pipeline/pipeline_historical.py`, `pipeline/pipeline_incremental.py`

**Verification Scripts (pipeline/):**
`pipeline/verify_bronze.py`, `pipeline/verify_silver.py`, `pipeline/verify_idempotency.py`, `pipeline/test_flag_permanence.py`, `pipeline/test_concurrent.py`, `pipeline/test_e2e_docker.sh`

**dbt Models (dbt/models/):**
`dbt/models/silver/silver_transaction_codes.sql`, `dbt/models/silver/silver_accounts.sql`, `dbt/models/silver/silver_transactions.sql`, `dbt/models/silver/silver_quarantine.sql`, `dbt/models/silver/schema.yml`, `dbt/models/gold/gold_daily_summary.sql`, `dbt/models/gold/gold_weekly_account_summary.sql`, `dbt/models/gold/schema.yml`

**dbt Macros (dbt/macros/):**
`dbt/macros/transaction_validation.sql`

**dbt Tests (dbt/tests/):**
`dbt/tests/test_conservation_law.sql` (existing stub — update), `dbt/tests/test_gold_promotion_gate.sql` (existing stub — update), `dbt/tests/test_tx_codes_conservation.sql` (existing stub — update), `dbt/tests/test_gold_daily_matches_silver.sql`, `dbt/tests/test_cross_partition_uniqueness.sql`, `dbt/tests/test_no_unresolvable_in_gold.sql`, `dbt/tests/test_rejection_codes.sql`, `dbt/tests/test_account_rejection.sql`

**dbt Config:** `dbt/dbt_project.yml` (create), `dbt/profiles.yml` (update for local dev)

**Docker:** `Dockerfile`, `docker-compose.yml`

### CC Must Not

- Modify or delete any file in `source/` (INV-19)
- Edit Claude.md (frozen — return to Claude Desktop if change needed)
- Make architectural decisions not covered here
- Expand scope beyond the task being worked on
- Use `{{ ref() }}` for cross-partition reads (see Technical Reference §6.3)
- Create persistent DuckDB tables — DuckDB is processing engine only, all state in Parquet
- Hardcode transaction codes, sign mappings, or validation code lists (INV-04, INV-11)

**If a task prompt conflicts with an invariant: the invariant wins. Flag the conflict — do not resolve it silently.**

---

## 4. Execution Contract

- One task at a time. No scope expansion. No batching.
- If CC encounters a decision not in this document: stop, flag it, wait for engineer resolution.
- If CC deviates from Claude.md: stop, return to Claude Desktop, understand the deviation.
- All dbt vars passed via `--vars '{"pipeline_run_id": "<uuid>", "processing_date": "YYYY-MM-DD"}'`
- All timestamps are UTC. No local timezone conversions.
- Every file write uses atomic pattern: write to `.tmp`, then rename.
- Every Bronze loader asserts `rows_written == rows_in_source` after write.

---

## 5. Fixed Stack

| Concern | Fixed Choice |
|---|---|
| Python | 3.11+ |
| dbt-core | ==1.7.19 (pinned) |
| dbt-duckdb | ==1.7.5 (pinned) |
| DuckDB | As installed by dbt-duckdb 1.7.5 |
| Storage | Parquet files on local filesystem |
| Container | Docker Compose — single `docker compose up` |
| dbt database | `data/pipeline/dbt.duckdb` (local dev: relative path; Docker: `/app/data/pipeline/dbt.duckdb`) |
| dbt profile name | `transactions_lake` |
| Pipeline runner | `pipeline.py` — Python orchestrator |
| Bronze ingestion | Python + DuckDB directly (NOT dbt) |
| Silver/Gold | dbt models exclusively |
| Run log / control | Parquet files (no metadata database) |

No environment variables are required beyond standard Docker Compose context. All paths are relative to project root.

---

## 6. Technical Reference — CC Memory

This section contains every detail CC needs to execute any task without guessing.

### 6.1 Source Schemas

**transaction_codes.csv** (4 rows, loaded once):
`transaction_code, description, debit_credit_indicator, transaction_type, affects_balance`
Codes: PURCH01(DR/PURCHASE), PAY01(CR/PAYMENT), FEE01(DR/FEE), INT01(DR/INTEREST)

**accounts_YYYY-MM-DD.csv** (day 1: 2 rows, days 2–7: 3 rows):
`account_id, customer_name, account_status, credit_limit, current_balance, open_date, billing_cycle_start, billing_cycle_end`
Note: `billing_cycle_start`/`billing_cycle_end` are DATE type in source (e.g., `2024-01-01`), not integers. `customer_name` is an extra column not in requirements brief — carry through all layers as informational passthrough.

**transactions_YYYY-MM-DD.csv** (5 rows per day, all 7 days):
`transaction_id, account_id, transaction_date, amount, transaction_code, merchant_name, channel`
Amounts always positive in source. `merchant_name` nullable.

### 6.2 Parquet Output Paths

| Entity | Path | Partitioned |
|---|---|---|
| Bronze transaction_codes | `data/bronze/transaction_codes/data.parquet` | No |
| Bronze accounts | `data/bronze/accounts/date=YYYY-MM-DD/data.parquet` | Yes |
| Bronze transactions | `data/bronze/transactions/date=YYYY-MM-DD/data.parquet` | Yes |
| Silver transaction_codes | `data/silver/transaction_codes/data.parquet` | No |
| Silver accounts | `data/silver/accounts/data.parquet` | No |
| Silver transactions | `data/silver/transactions/date=YYYY-MM-DD/data.parquet` | Yes |
| Silver quarantine | `data/silver/quarantine/date=YYYY-MM-DD/rejected.parquet` | Yes |
| Gold daily summary | `data/gold/daily_summary/data.parquet` | No |
| Gold weekly account summary | `data/gold/weekly_account_summary/data.parquet` | No |
| Pipeline control | `data/pipeline/control.parquet` | No |
| Pipeline run log | `data/pipeline/run_log.parquet` | No |

### 6.3 CRITICAL: Two Read Patterns in dbt

**`{{ ref('model') }}`** — ONLY for single-file models: `silver_transaction_codes`, `silver_accounts`.

**`read_parquet('data/silver/transactions/date=*/data.parquet')`** — For ALL cross-partition reads: Gold models reading Silver transactions, dedup anti-join checking existing Silver partitions, cross-partition tests.

WHY: dbt-duckdb `external` materialization creates a DuckDB view pointing to the LAST partition written. `{{ ref('silver_transactions') }}` returns one day's data, not all. Using `ref()` for cross-partition reads silently breaks INV-03, INV-07, INV-12, INV-13. This was confirmed via live testing.

For dedup anti-join on first run (no existing Silver partitions): handle the case where the glob returns no files.

### 6.4 dbt Materialization Pattern

ALL models use `external` materialization. No `incremental`, no `table`, no `view`.

```sql
{{ config(
    materialized='external',
    location='data/silver/transactions/date=' ~ var('processing_date') ~ '/data.parquet',
    format='parquet'
) }}
```

Silver accounts uses SQL-level merge (external overwrites entire file each run):
1. Read existing Silver accounts Parquet (if file exists)
2. UNION with new validated Bronze accounts for processing_date
3. Deduplicate by account_id keeping newest (_record_valid_from)
4. Write complete result

### 6.5 Shared Validation Macro

`dbt/macros/transaction_validation.sql` — called by BOTH `silver_transactions` and `silver_quarantine`. They split on `_rejection_reason IS NULL` vs `IS NOT NULL`. This structurally enforces INV-01.

Validation CASE WHEN chain (INV-06 order):
```sql
CASE
  WHEN transaction_id IS NULL OR ... THEN 'NULL_REQUIRED_FIELD'
  WHEN amount <= 0 OR TRY_CAST(amount AS DECIMAL) IS NULL THEN 'INVALID_AMOUNT'
  WHEN channel NOT IN ('ONLINE', 'IN_STORE') THEN 'INVALID_CHANNEL'
  WHEN tc.transaction_code IS NULL THEN 'INVALID_TRANSACTION_CODE'
  WHEN existing.transaction_id IS NOT NULL THEN 'DUPLICATE_TRANSACTION_ID'
  ELSE NULL
END AS _rejection_reason
```

UNRESOLVABLE_ACCOUNT_ID is applied AFTER the macro, in silver_transactions only, as a flag (not quarantine).

### 6.6 Audit Columns by Layer

**Bronze:** `_source_file` (STRING), `_ingested_at` (TIMESTAMP, UTC), `_pipeline_run_id` (STRING)

**Silver transactions:** `_source_file`, `_bronze_ingested_at`, `_pipeline_run_id`, `_promoted_at` (TIMESTAMP, UTC), `_is_resolvable` (BOOLEAN), `_signed_amount` (DECIMAL)

**Silver accounts:** `_source_file`, `_bronze_ingested_at`, `_pipeline_run_id`, `_record_valid_from` (TIMESTAMP, UTC)

**Silver transaction_codes:** `_source_file`, `_bronze_ingested_at`, `_pipeline_run_id`

**Quarantine:** `_source_file`, `_pipeline_run_id`, `_rejected_at` (TIMESTAMP, UTC), `_rejection_reason` (STRING)

**Gold (both models):** `_computed_at` (TIMESTAMP, UTC), `_pipeline_run_id` (STRING)

**Gold daily_summary additionally:** `_source_period_start` (DATE), `_source_period_end` (DATE)

### 6.7 Gold Column Specifications

**gold_daily_summary:** `transaction_date`, `total_transactions`, `total_signed_amount`, `transactions_by_type` (STRUCT), `online_transactions`, `instore_transactions`, `_computed_at`, `_pipeline_run_id`, `_source_period_start`, `_source_period_end`

**gold_weekly_account_summary:** `week_start_date` (Monday), `week_end_date` (Sunday), `account_id`, `total_purchases` (INTEGER count), `avg_purchase_amount` (DECIMAL), `total_payments` (DECIMAL sum), `total_fees` (DECIMAL sum), `total_interest` (DECIMAL sum), `closing_balance` (from Silver accounts current_balance), `_computed_at`, `_pipeline_run_id`

### 6.8 Pipeline Control

**control.parquet:** `last_processed_date` (DATE), `updated_at` (TIMESTAMP), `updated_by_run_id` (STRING)

**run_log.parquet:** `run_id`, `pipeline_type` (HISTORICAL/INCREMENTAL), `model_name`, `layer` (BRONZE/SILVER/GOLD), `started_at`, `completed_at`, `status` (SUCCESS/FAILED/SKIPPED), `records_processed`, `records_written`, `records_rejected`, `error_message` (no paths/credentials)

### 6.9 Expected Data Outcomes (7-day seed)

| Metric | Value |
|---|---|
| Bronze transaction_codes | 4 |
| Bronze transactions (total) | 35 (5 × 7) |
| Bronze accounts (total) | 20 (2 + 3×6) |
| Silver transactions | 28 (4 per day × 7) |
| Silver quarantine | 7 (1 per day × 7) |
| Silver accounts (final) | 3 (ACC-001, ACC-002, ACC-003) |
| Silver unresolvable | 7 (ACC-ORPHAN, 1 per day) |
| Silver resolvable | 21 (3 per day × 7) |
| Gold daily_summary rows | 7 |
| Gold weekly_account_summary rows | 3 |
| Day 1 conservation | 5 = 4 + 1 |
| Day 1 daily summary | total=3, amount=-30.00, online=2, instore=1 |
| ACC-001 closing_balance (day 7) | 1300.00 |
| All dates in ISO week 1 | 2024-01-01 (Mon) to 2024-01-07 (Sun) |

### 6.10 Account Availability Timeline

| Date | Cumulative Silver Accounts |
|---|---|
| 2024-01-01 | ACC-001, ACC-002 |
| 2024-01-02+ | ACC-001, ACC-002, ACC-003 |

ACC-ORPHAN never appears in any accounts file — permanently unresolvable.

### 6.11 Bronze Header Expectations (for schema validation)

**transaction_codes.csv:** `transaction_code,description,debit_credit_indicator,transaction_type,affects_balance`
**accounts:** `account_id,customer_name,account_status,credit_limit,current_balance,open_date,billing_cycle_start,billing_cycle_end`
**transactions:** `transaction_id,account_id,transaction_date,amount,transaction_code,merchant_name,channel`

### 6.12 Directory Pre-Creation

`pipeline.py` must create ALL output directories before invoking dbt. The `external` materialization fails if parent directories don't exist. Use `ensure_directories(date_str)` helper in paths.py.

### 6.13 Existing Scaffold Test Stubs

Three dbt tests exist in scaffold and must be updated (not replaced):
- `dbt/tests/test_conservation_law.sql` — uses `{{ var("processing_date") }}`
- `dbt/tests/test_gold_promotion_gate.sql` — tests run_log
- `dbt/tests/test_tx_codes_conservation.sql`

Update invariant references from scaffold's I-XX to our INV-XX numbering.

---

*End of Claude.md — v1.0 · FROZEN · 2026-03-31*
*Source artifacts: ARCHITECTURE.md v1.0, INVARIANTS.md v1.0, EXECUTION_PLAN.md v2.0, RISK_REGISTER.md v1.0*
