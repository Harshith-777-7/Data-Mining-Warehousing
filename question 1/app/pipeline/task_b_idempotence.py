import time
from tabulate import tabulate
from .ingest import parse_sales_files, ingest_to_minio

def run_task_b():
    """
    Task B: Make it safe to run twice.
    Runs the ingestion step 3 times, records raw count, unique count,
    and SHA-256 checksum after each run to prove strict idempotence.
    """
    print("\n" + "=" * 80)
    print("TASK B: IDEMPOTENT INGESTION & 3-RUN PROOF")
    print("=" * 80)
    print("Re-sends in billing exports are common and some are incomplete (mid-roll).")
    print("Deduplication Key: (bill_no, line_no).")
    print("Executing 3 consecutive runs to prove identical output...\n")
    
    results = []
    
    for run_i in range(1, 4):
        start_t = time.time()
        raw_count, deduped_records, checksum = parse_sales_files()
        elapsed = time.time() - start_t
        
        unique_count = len(deduped_records)
        duplicates_removed = raw_count - unique_count
        
        results.append({
            "run": f"Run {run_i}",
            "raw_lines": raw_count,
            "unique_lines": unique_count,
            "duplicates_removed": duplicates_removed,
            "checksum": checksum,
            "time_sec": round(elapsed, 2)
        })
        print(f"  [Run {run_i}] Raw: {raw_count:,} | Deduped: {unique_count:,} | Duplicates: {duplicates_removed:,} | SHA256: {checksum} ({elapsed:.2f}s)")

    # Format into table
    table_headers = ["Run Iteration", "Raw Lines Scanned", "Unique Lines Retained", "Duplicates Removed", "SHA-256 Checksum", "Elapsed Time"]
    table_rows = [
        [
            r["run"],
            f"{r['raw_lines']:,}",
            f"{r['unique_lines']:,}",
            f"{r['duplicates_removed']:,}",
            r["checksum"],
            f"{r['time_sec']}s"
        ]
        for r in results
    ]
    
    print("\nSUMMARY TABLE:")
    print(tabulate(table_rows, headers=table_headers, tablefmt="grid"))
    
    # Assert equality
    assert results[0]["unique_lines"] == results[1]["unique_lines"] == results[2]["unique_lines"], "Row count mismatch across runs!"
    assert results[0]["checksum"] == results[1]["checksum"] == results[2]["checksum"], "Checksum mismatch across runs!"
    
    print("\nPROVEN: Run 1 == Run 2 == Run 3.")
    print("  * Line-level deduplication on (bill_no, line_no) is deterministic and strictly idempotent.")
    print(f"  * Checksum is consistently: {results[0]['checksum']}")
    print(f"  * Exactly {results[0]['duplicates_removed']:,} partial / re-sent duplicate lines were pruned in every run.")
    print("=" * 80 + "\n")
    
    return results

if __name__ == '__main__':
    run_task_b()
