# Relational Indexing Benchmarking Framework

This repository contains the source code and data synthesis logic for Phase 1 of a comprehensive database benchmarking framework. It is specifically designed to evaluate the performance trade-offs of PostgreSQL 17 indexing strategies (e.g., B-Tree, Hash, BRIN) under highly controlled, synthetic HTAP (Hybrid Transactional/Analytical Processing) workloads.

## Key Methodological Innovations

- **Distribution-Aware Data Synthesis:** Synthesizes datasets combining Sequential (optimized for BRIN), Uniform Random (optimized for Hash), and Zipfian skewed (optimized for B-Tree cache locality) distributions within a unified schema.
- **Randomized Search Protocol:** Actively defeats OS and RAM caching mechanisms by continuously randomizing target lookup keys, ensuring the measurement reflects *true physical disk I/O* rather than memory cache hits.
- **Strict Garbage Collection Control:** Enforces pure baseline structural environments by executing a strict `VACUUM` protocol post-deletion, accurately capturing physical write overhead.
- **6-Dimensional Metrics Tracking:** Automatically records Query Latency (Mean, StdDev, P95), Write Overhead (via strict `COMMIT`), CPU Utilization Time, Index Build Time, Storage Efficiency Ratio, and Index Bloat.

## Repository Structure

- `generate_dataset.py`: Generates the 1-million record synthetic e-commerce dataset (`orders.csv` and `products.csv`) based on specific statistical distributions.
- `python_script.py`: The core Python probe that connects to PostgreSQL, executes OLTP/OLAP workloads, and records system resource states via `psutil`.
- `requirements.txt`: Python dependencies required to run the framework.

## Setup & Reproduction Steps

### Prerequisites
- Python 3.9+
- PostgreSQL 17 installed and running locally or remotely.

### 1. Install Dependencies
Clone this repository and install the required Python libraries:
```bash
git clone [https://github.com/Eric524-star/PostgreSQL-Index-Benchmarking-Framework.git](https://github.com/Eric524-star/PostgreSQL-Index-Benchmarking-Framework.git)
cd PostgreSQL-Index-Benchmarking-Framework
pip install -r requirements.txt

### 2. Database Preparation
Create an empty database in your PostgreSQL instance (e.g., fyp_database). Run the following SQL to create the target table:

SQL
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    transaction_date TIMESTAMP WITHOUT TIME ZONE,
    customer_name VARCHAR(255),
    transaction_code BIGINT,
    product_id INTEGER,
    quantity INTEGER,
    amount NUMERIC,
    notes TEXT
);

### 3. Generate the Dataset
Execute the data generator to create the 1-million row dataset. This will output CSV files into a /dataset folder.

Bash
python data_generator.py
(Note: Import the generated fyp_experiment_data.csv into your PostgreSQL orders table using the pgAdmin Import tool or the COPY command).

### 4. Run the Benchmark
Open benchmark_runner.py and update the DATABASE SETTINGS section with your actual PostgreSQL credentials. Then execute the framework:

Bash
python benchmark_runner.py

###  Academic Context
This framework was developed as the core software artifact for a Final Year Project evaluating relational indexing degradation and write-amplification penalties.
The framework has been empirically validated to accurately capture the sub-linear retrieval advantages of tree-based structures while exposing their structural maintenance costs.
