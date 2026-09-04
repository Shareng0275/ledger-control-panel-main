import sqlite3
import pandas as pd
import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CSV_PATH = r"PS_20174392719_1491204439457_log.csv"
DB_PATH = "financial_datasets.db"
CHUNK_SIZE = 50000
MAX_ROWS = 250000 # Ingest high-performance indexed slice with 100% fraud cases in range

print(f"[*] Starting ingestion of {CSV_PATH} into {DB_PATH}...")
start_time = time.time()

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Ensure table schema with high-performance indexes
cursor.execute("DROP TABLE IF EXISTS paysim_transactions")
cursor.execute("""
CREATE TABLE IF NOT EXISTS paysim_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step INTEGER NOT NULL,
    type TEXT NOT NULL,
    amount REAL NOT NULL,
    nameOrig TEXT NOT NULL,
    oldbalanceOrg REAL NOT NULL,
    newbalanceOrig REAL NOT NULL,
    nameDest TEXT NOT NULL,
    oldbalanceDest REAL NOT NULL,
    newbalanceDest REAL NOT NULL,
    isFraud INTEGER NOT NULL,
    isFlaggedFraud INTEGER NOT NULL
)
""")
conn.commit()

total_inserted = 0
fraud_count = 0

for chunk in pd.read_csv(CSV_PATH, chunksize=CHUNK_SIZE):
    if total_inserted >= MAX_ROWS:
        break
    
    # Clean types
    chunk['step'] = chunk['step'].astype(int)
    chunk['type'] = chunk['type'].astype(str)
    chunk['amount'] = chunk['amount'].astype(float)
    chunk['nameOrig'] = chunk['nameOrig'].astype(str)
    chunk['oldbalanceOrg'] = chunk['oldbalanceOrg'].astype(float)
    chunk['newbalanceOrig'] = chunk['newbalanceOrig'].astype(float)
    chunk['nameDest'] = chunk['nameDest'].astype(str)
    chunk['oldbalanceDest'] = chunk['oldbalanceDest'].astype(float)
    chunk['newbalanceDest'] = chunk['newbalanceDest'].astype(float)
    chunk['isFraud'] = chunk['isFraud'].astype(int)
    chunk['isFlaggedFraud'] = chunk['isFlaggedFraud'].astype(int)
    
    chunk.to_sql("paysim_transactions", conn, if_exists="append", index=False)
    total_inserted += len(chunk)
    fraud_count += int(chunk['isFraud'].sum())
    print(f" -> Inserted {total_inserted:,} rows (Fraud instances detected: {fraud_count:,})...")

print("[*] Creating database indexes for sub-millisecond query performance...")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_paysim_step ON paysim_transactions(step)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_paysim_type ON paysim_transactions(type)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_paysim_fraud ON paysim_transactions(isFraud)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_paysim_amount ON paysim_transactions(amount)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_paysim_orig ON paysim_transactions(nameOrig)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_paysim_dest ON paysim_transactions(nameDest)")
conn.commit()

# Query summary stats
cursor.execute("SELECT COUNT(*), SUM(amount), SUM(isFraud) FROM paysim_transactions")
row = cursor.fetchone()
conn.close()

elapsed = time.time() - start_time
print(f"[+] Ingestion successfully completed in {elapsed:.2f}s!")
print(f"    Total Rows: {row[0]:,}")
print(f"    Total Volume: ${row[1]:,.2f}")
print(f"    Fraud Incidents: {row[2]:,}")
