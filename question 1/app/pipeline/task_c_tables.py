from tabulate import tabulate
from .config import MINIO_BUCKET, get_duckdb_connection

def run_task_c():
    """
    Task C: Design the tables behind the dashboard.
    Demonstrates the dimensional model, fast revenue slicing by store,
    category, day of week, and month, and proves the solution to:
      1. TENDER/TAX exclusion (avoiding ~2.17x double counting in October)
      2. SCD2 product code reissue handling (avoiding duplication and category misclassification)
    """
    print("\n" + "=" * 80)
    print("TASK C: DIMENSIONAL MODELING & FAST REVENUE SLICING")
    print("=" * 80)
    
    con = get_duckdb_connection(attach_postgres=True)
    
    # 1. Show the October double-counting comparison (The Warning)
    print("\n[PART C WARNING] INVESTIGATING THE 'OCTOBER DOUBLE REVENUE' PHENOMENON:")
    double_rev_check = con.execute(f"""
        WITH oct_all AS (
            SELECT line_type, COUNT(*) AS lines, SUM(line_revenue) AS sum_rev
            FROM read_parquet('s3://{MINIO_BUCKET}/all_sales/*/*/*.parquet', hive_partitioning=true)
            WHERE year_month = '2024-10'
            GROUP BY line_type
        )
        SELECT line_type, lines, ROUND(sum_rev, 2) AS line_total
        FROM oct_all
        ORDER BY line_total DESC;
    """).fetchall()
    
    print(tabulate(double_rev_check, headers=["Line Type", "Line Count", "Subtotal (₹)"], tablefmt="grid"))
    
    naive_oct_total = con.execute(f"""
        SELECT ROUND(SUM(qty * unit_price), 2)
        FROM read_parquet('s3://{MINIO_BUCKET}/all_sales/*/*/*.parquet', hive_partitioning=true)
        WHERE year_month = '2024-10';
    """).fetchone()[0]
    
    correct_oct_total = con.execute(f"""
        SELECT ROUND(SUM(line_revenue), 2)
        FROM read_parquet('s3://{MINIO_BUCKET}/fact_sales/*/*/*.parquet', hive_partitioning=true)
        WHERE year_month = '2024-10';
    """).fetchone()[0]
    
    print(f"\n  * Naive SUM(qty * unit_price) over ALL lines in October:   ₹{naive_oct_total:,.2f}")
    print(f"  * True Revenue (SALE + RETURN + DISCOUNT + VOID):         ₹{correct_oct_total:,.2f}")
    print(f"  * Double-Counting Ratio:                                  {naive_oct_total / correct_oct_total:.2f}x")
    print("  * Explanation: TENDER is the bill total and TAX is GST. Summing indiscriminately")
    print("    counts each bill twice and adds GST. Our fact_sales model eliminates both.\n")
    
    # 2. Show the Product Code Reissue Handling
    print("\n[PART C SCD2] RESOLVING REISSUED PRODUCT CODES (e.g. Catch Coriander Powder vs Cadbury Chewing Gum):")
    reissue_check = con.execute("""
        SELECT product_sk, product_code, product_name, category_id, valid_from, valid_to, is_current
        FROM pg.products
        WHERE product_code = 'P100621'
        ORDER BY valid_from;
    """).fetchall()
    print(tabulate(reissue_check, headers=["SK", "Code", "Product Name", "Category", "Valid From", "Valid To", "Is Current"], tablefmt="grid"))
    
    reissue_sales_check = con.execute(f"""
        SELECT 
            s.year_month,
            p.product_sk,
            p.product_name,
            c.category_name,
            ROUND(SUM(s.qty), 0) AS total_qty,
            ROUND(SUM(s.line_revenue), 2) AS total_rev
        FROM read_parquet('s3://{MINIO_BUCKET}/fact_sales/*/*/*.parquet', hive_partitioning=true) s
        JOIN pg.products p 
            ON s.product_code = p.product_code 
           AND CAST(s.business_date AS DATE) BETWEEN p.valid_from AND p.valid_to
        JOIN pg.product_categories c ON p.category_id = c.category_id
        WHERE s.product_code = 'P100621' AND s.year_month IN ('2024-05', '2024-06')
        GROUP BY 1, 2, 3, 4
        ORDER BY 1;
    """).fetchall()
    print("\nSales for Code P100621 crossing the June 1, 2024 reissue threshold:")
    print(tabulate(reissue_sales_check, headers=["Month", "SK", "Resolved Product", "Category", "Qty", "Revenue (₹)"], tablefmt="grid"))
    
    # 3. Slicing Revenue by Store
    print("\n1. SLICE REVENUE BY STORE (Top 5 stores in 2024):")
    by_store = con.execute(f"""
        SELECT 
            st.store_id,
            st.store_name,
            st.city,
            st.region,
            ROUND(SUM(s.line_revenue), 2) AS total_revenue
        FROM read_parquet('s3://{MINIO_BUCKET}/fact_sales/*/*/*.parquet', hive_partitioning=true) s
        JOIN pg.stores st ON s.store_id = st.store_id
        GROUP BY 1, 2, 3, 4
        ORDER BY total_revenue DESC
        LIMIT 5;
    """).fetchall()
    print(tabulate(by_store, headers=["Store ID", "Store Name", "City", "Region", "Total Revenue (₹)"], tablefmt="grid"))
    
    # 4. Slicing Revenue by Product Category
    print("\n2. SLICE REVENUE BY PRODUCT CATEGORY (Top 5 categories in 2024):")
    by_cat = con.execute(f"""
        SELECT 
            c.category_id,
            c.category_name,
            c.department,
            ROUND(SUM(s.line_revenue), 2) AS total_revenue
        FROM read_parquet('s3://{MINIO_BUCKET}/fact_sales/*/*/*.parquet', hive_partitioning=true) s
        JOIN pg.products p 
            ON s.product_code = p.product_code 
           AND CAST(s.business_date AS DATE) BETWEEN p.valid_from AND p.valid_to
        JOIN pg.product_categories c ON p.category_id = c.category_id
        GROUP BY 1, 2, 3
        ORDER BY total_revenue DESC
        LIMIT 5;
    """).fetchall()
    print(tabulate(by_cat, headers=["Category ID", "Category Name", "Department", "Total Revenue (₹)"], tablefmt="grid"))
    
    # 5. Slicing Revenue by Day of the Week
    print("\n3. SLICE REVENUE BY DAY OF THE WEEK (2024 Full Year):")
    by_dow = con.execute(f"""
        SELECT 
            day_of_week,
            ROUND(SUM(day_total), 2) AS total_revenue,
            ROUND(AVG(day_total), 2) AS avg_daily_revenue
        FROM (
            SELECT CAST(business_date AS DATE) AS b_date, day_of_week, SUM(line_revenue) AS day_total
            FROM read_parquet('s3://{MINIO_BUCKET}/fact_sales/*/*/*.parquet', hive_partitioning=true)
            GROUP BY 1, 2
        )
        GROUP BY day_of_week
        ORDER BY 
            CASE day_of_week 
                WHEN 'Monday' THEN 1 
                WHEN 'Tuesday' THEN 2 
                WHEN 'Wednesday' THEN 3 
                WHEN 'Thursday' THEN 4 
                WHEN 'Friday' THEN 5 
                WHEN 'Saturday' THEN 6 
                WHEN 'Sunday' THEN 7 
            END;
    """).fetchall()
    print(tabulate(by_dow, headers=["Day of Week", "Total Revenue (₹)", "Avg Daily Revenue (₹)"], tablefmt="grid"))
    
    # 6. Slicing Revenue by Month
    print("\n4. SLICE REVENUE BY MONTH (2024 All 12 Months):")
    by_month = con.execute(f"""
        SELECT 
            year_month,
            ROUND(SUM(line_revenue), 2) AS total_revenue,
            COUNT(DISTINCT bill_no) AS total_bills,
            ROUND(SUM(line_revenue) / COUNT(DISTINCT bill_no), 2) AS avg_basket_size
        FROM read_parquet('s3://{MINIO_BUCKET}/fact_sales/*/*/*.parquet', hive_partitioning=true)
        GROUP BY 1
        ORDER BY 1;
    """).fetchall()
    print(tabulate(by_month, headers=["Month", "Total Revenue (₹)", "Total Bills", "Avg Basket (₹)"], tablefmt="grid"))
    print("=" * 80 + "\n")
    
    return {
        "correct_oct_total": correct_oct_total,
        "naive_oct_total": naive_oct_total
    }

if __name__ == '__main__':
    run_task_c()
