import numpy as np
import pandas as pd
from faker import Faker
import random
from datetime import datetime, timedelta
import os

# ==========================================
# CONFIGURATION
# ==========================================
NUM_PRODUCTS = 10000        
NUM_ORDERS = 1000000     
OUTPUT_DIR = "dataset/"

# Set seeds for complete reproducibility across identical runs
Faker.seed(42)
np.random.seed(42)
random.seed(42)
fake = Faker()

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 1. GENERATE PRODUCTS (Dimension Table)
# ==========================================
print("Generating Products table...")

product_categories = ['Electronics', 'Clothing', 'Home', 'Sports', 'Books']
products = []

for i in range(1, NUM_PRODUCTS + 1):
    # Generates synthetic product names 
    p_name = f"{fake.word().capitalize()} {fake.word().capitalize()} {random.randint(1, 99)}"
    
    product = {
        'product_id': i,
        'product_name': p_name,
        'category': random.choice(product_categories),
        'price': round(random.uniform(5.0, 500.0), 2)
    }
    products.append(product)

products_df = pd.DataFrame(products)
products_df.to_csv(OUTPUT_DIR + 'products.csv', index=False)

# Create dictionary for fast price lookup during order generation
product_price_dict = dict(zip(products_df['product_id'], products_df['price']))

print(f"Products generated and saved to {OUTPUT_DIR}products.csv")

# ==========================================
# 2. GENERATE ORDERS (Fact Table for Experiment Workloads)
# ==========================================
print("Generating Orders table (Unified Multi-Distribution Methodology)...")

start_date = datetime(2023, 1, 1)
time_increment = timedelta(seconds=15) 
current_time = start_date

orders = []
batch_size = 100000

for i in range(1, NUM_ORDERS + 1):
    
    # --- DISTRIBUTION 1: Sequential Timestamp (BRIN Target) ---
    # Strictly increasing progression ensures perfect physical correlation on disk.
    current_time += time_increment
    
    # --- DISTRIBUTION 2: Unsorted Variable-Length Text (B-Tree Target) ---
    # Statistically independent of physical insertion order.
    cust_name = fake.name() 
    
    # --- DISTRIBUTION 3: Uniform Random Integer (Hash Target) ---
    # Synthetic 64-bit integer space. Explicitly bounded to avoid PII collision.
    trans_code = random.randint(1_000_000_000_000, 9_999_999_999_999)

    # --- Zipfian Skewed Foreign Keys (Cache Locality Simulation) ---
    # Emulates the 80/20 rule of realistic e-commerce product popularity.
    pid = np.random.zipf(1.2) 
    if pid > NUM_PRODUCTS: pid = random.randint(1, NUM_PRODUCTS)
    
    qty = random.randint(1, 5) 

    # Calculate financial metrics based on product dictionary
    unit_price = product_price_dict.get(pid, 10.0)
    total_amount = round(unit_price * qty, 2)

    order = {
        'order_id': i,
        'transaction_date': current_time.strftime('%Y-%m-%d %H:%M:%S'),
        'customer_name': cust_name,
        'transaction_code': trans_code,
        'product_id': pid,
        'quantity': qty,   
        'amount': total_amount, 
        'notes': fake.text(max_nb_chars=50) # Padding to realistically simulate index bloat
    }
    orders.append(order)

    # Disk I/O: Append batch to CSV
    if i % batch_size == 0:
        mode = 'w' if i == batch_size else 'a'
        header = True if i == batch_size else False
        pd.DataFrame(orders).to_csv(OUTPUT_DIR + 'fyp_experiment_data.csv', mode=mode, header=header, index=False)
        orders = [] # Clear memory buffer
        print(f"  - Processed {i} rows...")

print("Dataset generation complete!")