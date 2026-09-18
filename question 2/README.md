# SetuBid Deduplication Engine (Question 2)

Aggregating public procurement notices across 260 government portals with sublinear LSH retrieval, relational database storage in SQLite, and asymmetric loss pricing.

## Directory Structure

```
data_2/
├── notices/                     # 12,000 procurement notices across 8 CSV partitions
├── _truth/                      # Ground truth clusters & cluster distributions
├── labelled_pairs.csv           # 900 manually adjudicated pairs (279 same, 621 different)
├── portal_profiles.md           # Scraping team notes on portal boilerplates
├── setubid_lsh.db               # Working SQLite relational database with B-Tree LSH index
│
├── outputs/                     # Final Deliverables & Visualizations
│   ├── QUESTION_2_REPORT.md     # Complete technical writeup answering all parts (A through E)
│   ├── metrics_summary.json     # Machine-readable benchmarks and metrics
│   ├── lsh_s_curves.png         # S-curve plot with operating point (Part C)
│   ├── work_distribution.png    # Work distribution per notice before vs after mitigation (Part E)
│   └── setubid_lsh.db           # Exported relational database
│
├── eda.py                       # Initial exploratory data analysis
├── compare_text_repr.py         # Empirical comparison of text representations (Part A)
├── run_eval_a.py                # Full evaluation of shingle choices on labelled pairs (Part A)
├── eval_minhash.py              # MinHash signature size evaluation (Part B)
├── bench_db_access.py           # Relational schema and B-Tree vs table scan benchmark (Part D)
├── debug_band25.py              # Pathology diagnostic of mega-bucket winning shingles (Part E)
├── test_mitigations.py          # Benchmark of all mitigation strategies on full corpus (Part E)
└── generate_plots.py            # Generates publication-grade plots for Parts C & E
```

## How to Reproduce All Results

Run the scripts using Python 3:

```bash
# 1. Evaluate text decomposition and boilerplate stripping (Part A)
py run_eval_a.py

# 2. Evaluate MinHash sizing accuracy vs theoretical bounds (Part B)
py eval_minhash.py

# 3. Benchmark relational database access plans (B-Tree vs Scan) (Part D)
py bench_db_access.py

# 4. Diagnose mega-bucket pathology and winning boilerplate shingles (Part E)
py debug_band25.py

# 5. Run full mitigation test suite on all 12,000 notices (Part E)
py test_mitigations.py

# 6. Generate high-resolution plots (Parts C & E)
py generate_plots.py
```
