# Walkthrough - Annapurna Stores Analytics Platform

The **Annapurna Stores Analytics Platform** is fully implemented, verified, and running locally from a single `docker compose up` command without external cloud dependencies.

---

## Architecture Overview

```
+---------------------------------------------------------------------------------------------------+
|                                        DOCKER COMPOSE                                             |
|                                                                                                   |
|  +---------------------------+   +---------------------------+   +-----------------------------+  |
|  |           MinIO           |   |       PostgreSQL 16       |   |       Analytics Engine      |  |
|  |     (Port 9000/9001)      |   |        (Port 5432)        |   |         (Port 8501)         |  |
|  |---------------------------|   |---------------------------|   |-----------------------------|  |
|  | s3://annapurna-sales/     |   | - stores                  |   | - Idempotent Ingestion      |  |
|  |   fact_sales/             |   | - products (SCD2)         |   | - DuckDB Federated Engine   |  |
|  |     store_id=S01/         |   | - product_categories      |   | - Streamlit Dashboard       |  |
|  |       year_month=2024-10/ |   | - price_revisions         |   | - Automated Test Suite      |  |
|  |         data.parquet      |   |                           |   |                             |  |
|  +---------------------------+   +---------------------------+   +-----------------------------+  |
|               ^                               ^                                 |                 |
|               |                               |                                 |                 |
|               +----------- httpfs ------------+----------- postgres ------------+                 |
|                            (S3 Parquet)                    (Remote Scan)                          |
+---------------------------------------------------------------------------------------------------+
```

---

## Summary of Results Across All Tasks

### Task A: Platform Standup & S3 Partitioned Layout
- **Layout**: `s3://annapurna-sales/fact_sales/store_id=<store_id>/year_month=<YYYY-MM>/data.parquet`
- **Pruning Gains (Target: Store S01, October 2024)**:
  - Flat folder: **4,457 files**, **68,706,877 bytes** (65.52 MB).
  - Partitioned layout in S3: **1 file**, **226,450 bytes** (0.22 MB).
  - **Pruning Gain**: **143.8x fewer files** and **>300x fewer bytes** scanned.

---

### Task B: Idempotent Ingestion & 3-Run Proof
- **Deduplication Strategy**: Business primary key `(bill_no, line_no)`.
- **Three Consecutive Runs Results**:
  - Raw lines scanned: **1,137,585**
  - Unique lines retained: **1,120,924** (16,661 duplicates pruned)
  - Deterministic SHA-256: `a27fbd1aa1dad89d8f0dcea9eae894790ee169fb63da0c81f4c3f36f4c5d5f94`
  - All 3 runs are **100% identical**.

---

### Task C: Dimensional Modeling & Revenue Slicing
- **The "October Double Revenue" Warning Solved**:
  - Naive `SUM(qty * unit_price)` over ALL lines: **₹122,501,668.06** (includes `TENDER` and `TAX`).
  - True Filtered Revenue (`SALE` + `RETURN` + `DISCOUNT` + `VOID`): **₹56,359,195.92** (exact signed-off match).
  - `TENDER` (bill total) and `TAX` (GST) are excluded.
- **SCD2 Product Code Reissue Solved**:
  - In June 2024, 22 product codes were reissued (e.g. `P100621` changed from Coriander Powder to Chewing Gum).
  - Joining using `CAST(s.business_date AS DATE) BETWEEN p.valid_from AND p.valid_to` ensures correct product attribution with zero duplicate lines.
- **Dimensional Slicing Available**:
  - By Store (`Annapurna T Nagar` #1 at ₹61.86M)
  - By Product Category (`Staples & Grains` #1 at ₹98.68M)
  - By Day of Week (Saturday & Sunday peak traffic)
  - By Month (All 12 months)

---

### Task D: Historical Price Consistency (March vs Latest Prices)
- **Parameterized Query**: Joining `price_revisions` using `product_sk` and `CAST(s.business_date AS DATE) BETWEEN pr.effective_from AND pr.effective_to`.
- **Results for Britannia Cream Biscuit 60g (`P100049`)**:
  - March 2024 (`2024-03`): **₹66.95** (Revision 500029, valid 2022-01-01 to 2024-06-19)
  - December 2024 (`2024-12`): **₹68.93** (Revision 500032, valid 2024-08-08 to 9999-12-31)
  - **Zero query code change** between the two runs.

---

### Task E: Zero-Copy Cross-System Federated Query
- **Federated Query**:
  ```sql
  SELECT st.region, st.city, st.store_name, c.category_name, ROUND(SUM(s.line_revenue), 2) AS category_revenue
  FROM read_parquet('s3://annapurna-sales/fact_sales/*/*/*.parquet', hive_partitioning=true) s
  JOIN pg.stores st ON s.store_id = st.store_id
  JOIN pg.products p ON s.product_code = p.product_code AND CAST(s.business_date AS DATE) BETWEEN p.valid_from AND p.valid_to
  JOIN pg.product_categories c ON p.category_id = c.category_id
  WHERE s.year_month = '2024-10' AND st.region = 'South'
  GROUP BY 1, 2, 3, 4;
  ```
- **Physical Plan Evidence (`EXPLAIN`)**:
  - `POSTGRES_SCAN`: Executed in PostgreSQL with pushed filter `region = 'South'`.
  - `PARQUET_SCAN`: Executed in MinIO S3 via HTTP GET with partition pruning on `year_month = '2024-10'`.
  - `HASH_JOIN`: Executed in-memory inside DuckDB's vectorized query engine. Zero data copying between PostgreSQL and S3.

---

### Task F: 12-Month Financial Reconciliation

| Month | Pipeline Revenue (₹) | Finance Signed-Off (₹) | Discrepancy (₹) | Root Cause Category | Explanation |
|---|---|---|---|---|---|
| **2024-01** | 38,446,071.33 | 38,446,071.33 | ₹0.00 | Match | Exact match to the paisa. |
| **2024-02** | 34,887,085.55 | 34,887,085.55 | ₹0.00 | Match | Exact match to the paisa. |
| **2024-03** | 41,971,649.09 | 42,457,899.09 | **-₹486,250.00** | **Revenue Definition (Scope)** | Off-till institutional order billed outside POS. |
| **2024-04** | 37,958,457.37 | 37,958,457.37 | ₹0.00 | Match | Exact match to the paisa. |
| **2024-05** | 41,764,716.40 | 41,764,716.40 | ₹0.00 | Match | Exact match to the paisa. |
| **2024-06** | 38,987,082.82 | 38,987,082.82 | ₹0.00 | Match | Exact match to the paisa. |
| **2024-07** | 40,295,160.11 | 40,527,291.81 | **-₹232,131.70** | **Source Data Gap** | Pune S07 offline 3 days (phoned in to finance). |
| **2024-08** | 45,252,181.75 | 45,252,181.75 | ₹0.00 | Match | Exact match to the paisa. |
| **2024-09** | 44,615,037.46 | 44,615,037.46 | ₹0.00 | Match | Exact match to the paisa. |
| **2024-10** | 56,359,195.92 | 56,359,195.92 | ₹0.00 | Match | Exact match to the paisa (non-doubled). |
| **2024-11** | 51,583,838.47 | 51,583,838.47 | ₹0.00 | Match | Exact match to the paisa. |
| **2024-12** | 50,745,259.48 | 50,745,209.00 | **+₹50.48** | **Revenue Definition (Rounding)** | Finance rounded bills to rupee; pipeline sums paise. |

- **Conclusion**: 9 of 12 months match to the exact paisa. Zero pipeline bugs. All 3 variances are fully documented and audited.

---

## Live Dashboard Access

The executive dashboard is live at:
```
http://localhost:8501
```
All tabs (Monthly Trends, Store Breakdown, Product Categories, Day of Week, Historical Price Inspector, Financial Reconciliation, System & Engine Proofs) are fully interactive.
