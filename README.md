# Data Mining & Warehousing Laboratory

This repository contains lab assignments and laboratory examination projects for **Data Mining & Warehousing**.

---

## Contents

* **[`Data-mining-lab-1/`](./Data-mining-lab-1)**: Laboratory Assignment 1.
* **[`question 1/`](./question%201)**: **Annapurna Stores - Multi-Store Billing Analytics Platform**
  - Complete, containerized lakehouse & dimensional analytics stack built with DuckDB, MinIO S3, and PostgreSQL.
  - Automated evaluation test suite (`Tasks A through F`).
  - Audited output deliverables and executive financial reconciliation memo.
  - Interactive Streamlit Executive Dashboard.
* **[`question 2/`](./question%202)**: **SetuBid - Twelve Thousand Tenders, Wearing Disguises**
  - High-performance, sublinear near-duplicate tender deduplication engine for 12,000 notices across 260 government portals.
  - MinHash signature compression ($K=128$, 512 bytes) and sublinear LSH candidate retrieval ($b=16, r=8$).
  - Relational SQLite database (`setubid_lsh.db`) with B-Tree indexed access path ($1,084.1\times$ faster than sequential scan).
  - Empirical pathology mitigation (mega-bucket resolution from 33.25M to 948k candidates, reducing worst-case latency by $21.3\times$).
  - Strict asymmetric risk settings ($C_{FP} : C_{FN} = 500 : 1$) and monotonic card ID bookmark stability across pipeline executions.
  - Audited deliverables: [`QUESTION_2_REPORT.md`](./question%202/outputs/QUESTION_2_REPORT.md), [`metrics_summary.json`](./question%202/outputs/metrics_summary.json), and publication-grade plots.
