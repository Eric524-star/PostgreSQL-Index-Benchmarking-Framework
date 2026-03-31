import psycopg2
import time
import psutil
import os
import random
import statistics
from scipy.stats import wilcoxon  

# ==========================================
# DATABASE SETTINGS (UPDATE THESE FOR YOUR ENVIRONMENT)
# ==========================================
DB_HOST = "localhost"
DB_NAME = "database"       # Placeholder: Update with your DB name
DB_USER = "admin"           # Placeholder: Update with your DB username
DB_PASS = "YOUR_PASSWORD_HERE" # Placeholder: Update with your secure password
DB_PORT = "5432"               # Default PostgreSQL port (update if different, e.g., 5433)

TABLE_NAME = "orders"
COLUMN_TO_TEST = "customer_name"   
INDEX_NAME = "idx_fyp_btree"     

TEST_ITERATIONS = 50  

def get_connection():
    try:
        return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)
    except Exception as e:
        print(f"Connection Error: {e}"); return None

def set_high_priority():
    try:
        p = psutil.Process(os.getpid())
        if os.name == 'nt':
            p.nice(psutil.HIGH_PRIORITY_CLASS)
        else:
            p.nice(-10)
    except:
        pass

def get_io_stats(cur):
    cur.execute(f"SELECT coalesce(sum(heap_blks_read),0), coalesce(sum(heap_blks_hit),0) FROM pg_statio_user_tables WHERE relname = '{TABLE_NAME}'")
    return cur.fetchone()

def generate_dummy_data(start_id, count=1000):
    data = []
    for i in range(count):
        row = (start_id + i, '2025-01-01 12:00:00', f"Dummy_User_{i}", 1234567890, 1, 1, 50.00, "Test_Row")
        data.append(row)
    return data

def calculate_percentile(data, percentile):
    data.sort()
    index = (percentile / 100) * len(data)
    return data[int(index)] if index.is_integer() else data[int(index)]

def perform_vacuum(conn, table_name):
    old_autocommit = conn.autocommit
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"VACUUM {table_name}")
    cur.close()
    conn.autocommit = old_autocommit

def main():
    set_high_priority()
    conn = get_connection(); cur = conn.cursor()

    cur.execute("SELECT pg_backend_pid()")
    pg_pid = cur.fetchone()[0]
    pg_proc = psutil.Process(pg_pid)

    # 1. PRE-EXPERIMENT INFO
    cur.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    conn.commit()
    
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total_rows = cur.fetchone()[0]
    cur.execute(f"SELECT pg_total_relation_size('{TABLE_NAME}')")
    s_table = cur.fetchone()[0] 

    print("="*60)
    print(f"SYSTEM SETUP")
    print(f"Target Table: {TABLE_NAME} ({total_rows} rows)")
    print(f"Table Size:   {s_table / (1024*1024):.2f} MB")
    print(f"Test Column:  {COLUMN_TO_TEST}")
    print("="*60)

    cur.execute(f"SELECT {COLUMN_TO_TEST} FROM {TABLE_NAME} LIMIT 100 OFFSET 5000")
    test_names = [row[0] for row in cur.fetchall()]

    # ==========================================
    # --- PHASE 1: BASELINE ---
    # ==========================================
    print("\n[PHASE 1] Starting Baseline Tests...")
    cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE {COLUMN_TO_TEST} = %s", (test_names[0],))
    
    lq_baseline_list = []
    cpu_time_start = pg_proc.cpu_times() 

    for i in range(TEST_ITERATIONS):
        target = random.choice(test_names)
        t_start = time.perf_counter() 
        cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE {COLUMN_TO_TEST} = %s", (target,))
        cur.fetchone()
        lq_baseline_list.append((time.perf_counter() - t_start) * 1000)

    cpu_time_end = pg_proc.cpu_times()
    
    base_avg = statistics.mean(lq_baseline_list)
    base_std = statistics.stdev(lq_baseline_list)
    base_p95 = calculate_percentile(lq_baseline_list, 95)
    base_cpu_used = (cpu_time_end.user - cpu_time_start.user) + (cpu_time_end.system - cpu_time_start.system)

    # Baseline Write 
    dummy = generate_dummy_data(9900000, count=1000)
    
    t_start = time.perf_counter()
    cur.executemany(f"INSERT INTO {TABLE_NAME} VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", dummy)
    conn.commit() 
    t_baseline_write = time.perf_counter() - t_start
    
    cur.execute(f"DELETE FROM {TABLE_NAME} WHERE notes = 'Test_Row'")
    conn.commit()
    perform_vacuum(conn, TABLE_NAME)
    
    print(f"  Write Test (Baseline): Inserted & Committed 1000 rows -> {t_baseline_write:.4f} s")

    # ==========================================
    # --- PHASE 2: INDEXED (B-Tree) ---
    # ==========================================
    print("\n[PHASE 2] Applying B-Tree Index...")
    t_start_build = time.perf_counter()
    cur.execute(f"CREATE INDEX {INDEX_NAME} ON {TABLE_NAME} USING btree ({COLUMN_TO_TEST})")
    conn.commit()
    t_build = time.perf_counter() - t_start_build 

    print(f"Testing Indexed Results...")
    cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE {COLUMN_TO_TEST} = %s", (test_names[0],))
    
    lq_indexed_list = []
    cpu_time_start_idx = pg_proc.cpu_times()

    for i in range(TEST_ITERATIONS):
        target = random.choice(test_names)
        t_start = time.perf_counter()
        cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE {COLUMN_TO_TEST} = %s", (target,))
        cur.fetchone()
        lq_indexed_list.append((time.perf_counter() - t_start) * 1000)
    
    cpu_time_end_idx = pg_proc.cpu_times()

    idx_avg = statistics.mean(lq_indexed_list)
    idx_std = statistics.stdev(lq_indexed_list)
    idx_p95 = calculate_percentile(lq_indexed_list, 95)
    idx_cpu_used = (cpu_time_end_idx.user - cpu_time_start_idx.user) + (cpu_time_end_idx.system - cpu_time_start_idx.system)
    
    # Indexed Write
    t_start = time.perf_counter()
    cur.executemany(f"INSERT INTO {TABLE_NAME} VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", dummy)
    conn.commit() 
    t_indexed_write = time.perf_counter() - t_start
    
    cur.execute(f"DELETE FROM {TABLE_NAME} WHERE notes = 'Test_Row'")
    conn.commit()
    perform_vacuum(conn, TABLE_NAME)
    
    print(f"  Write Test (Indexed): Inserted & Committed 1000 rows -> {t_indexed_write:.4f} s")

    # Stats Retrieval
    cur.execute(f"SELECT pg_relation_size('{INDEX_NAME}')")
    s_index = cur.fetchone()[0]
    
    try:
        cur.execute(f"SELECT avg_item_size * tuple_count, index_size FROM pgstatindex('{INDEX_NAME}')")
        s_used, s_allocated = cur.fetchone()
        b_idx = ((s_allocated - s_used) / s_allocated) * 100
    except:
        b_idx = 0.0 

    # ==========================================
    # --- PHASE 3: STATISTICAL SIGNIFICANCE ---
    # ==========================================
    try:
        stat, p_value = wilcoxon(lq_baseline_list, lq_indexed_list)
    except ValueError:
        p_value = 1.0

    # ==========================================
    # --- FINAL COMPREHENSIVE REPORT ---
    # ==========================================
    print("\n" + "="*65)
    print("            FINAL ACADEMIC PERFORMANCE METRICS")
    print("="*65)
    print(f"1. Query Latency Distribution (n={TEST_ITERATIONS}):")
    print(f"      [Baseline] Avg: {base_avg:.2f} ms | StdDev: ±{base_std:.2f} ms | P95: {base_p95:.2f} ms")
    print(f"      [Indexed]  Avg: {idx_avg:.2f} ms  | StdDev: ±{idx_std:.2f} ms  | P95: {idx_p95:.2f} ms")
    print(f"      >> Speedup Ratio: {base_avg/idx_avg:.1f}x Faster (based on average)")
    
    significance = "Statistically Significant" if p_value < 0.05 else "Not Significant"
    p_display = "< 0.001" if p_value < 0.001 else f"{p_value:.4f}"
    print(f"      >> Wilcoxon Test: p-value {p_display} ({significance})")
    
    print(f"\n2. Write Overhead (Wo) - Measured via True COMMIT:")
    print(f"      - Baseline 1k rows: {t_baseline_write:.4f} s")
    print(f"      - Indexed 1k rows:  {t_indexed_write:.4f} s")
    print(f"      >> True Overhead:   {((t_indexed_write - t_baseline_write)/t_baseline_write)*100:.2f}%")
    
    print(f"\n3. System Resource Utilization (Cumulative during queries):")
    print(f"      - Baseline PG CPU Time: {base_cpu_used:.4f} seconds")
    print(f"      - Indexed PG CPU Time:  {idx_cpu_used:.4f} seconds")
    # print(f"      - Cache Hit Ratio:      {hit_ratio:.2f}% (Memory Hits: {idx_hits}, Disk Reads: {idx_reads})")
    
    print(f"\n4. Structural Costs:")
    print(f"      - Build Time (Tbuild): {t_build:.4f} s")
    print(f"      - Storage Ratio (Rs):  {(s_index / s_table)*100:.2f}% of table size ({s_index / (1024*1024):.2f} MB)")
    print(f"      - Index Bloat (Bidx):  {b_idx:.2f}%")
    print("="*65)

    conn.close()

if __name__ == "__main__":
    main()