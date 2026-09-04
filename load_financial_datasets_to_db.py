# load_financial_datasets_to_db.py
import sys
import os
import sqlite3
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

def load_all_to_database():
    db_path = "financial_datasets.db"
    conn = sqlite3.connect(db_path)
    
    print("[Database] Ingesting CSV datasets into SQLite database...")
    
    # 1. Ingest Yahoo Finance Market Data
    if os.path.exists("yahoo_financial_data.csv"):
        df_yf = pd.read_csv("yahoo_financial_data.csv")
        df_yf.to_sql("market_timeseries", conn, if_exists="replace", index=False)
        print(f"[Database Success] Ingested {len(df_yf)} rows into table 'market_timeseries'.")
    else:
        print("[Database Warning] yahoo_financial_data.csv not found.")

    # 2. Ingest SEC EDGAR Corporate Cash Flows
    if os.path.exists("sec_edgar_cash_flows.csv"):
        df_sec = pd.read_csv("sec_edgar_cash_flows.csv")
        df_sec.to_sql("sec_corporate_cash_flows", conn, if_exists="replace", index=False)
        print(f"[Database Success] Ingested {len(df_sec)} rows into table 'sec_corporate_cash_flows'.")
    else:
        print("[Database Warning] sec_edgar_cash_flows.csv not found.")

    # Verification query
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"[Database] Active tables in '{db_path}': {[t[0] for t in tables]}")
    
    conn.close()

if __name__ == "__main__":
    load_all_to_database()
