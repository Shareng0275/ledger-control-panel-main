# generate_paysim_dataset.py
import sys
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

def generate_paysim_data(num_records=15000):
    print("[1/3] Generating PaySim Financial Transaction Dataset...")
    np.random.seed(42)

    # 1. Simulation Steps (744 hours = 31 days)
    steps = np.random.randint(1, 744, size=num_records)
    steps.sort()

    # 2. Transaction Types & Probability Distribution
    types_list = ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"]
    type_probs = [0.35, 0.25, 0.22, 0.10, 0.08]
    tx_types = np.random.choice(types_list, size=num_records, p=type_probs)

    # 3. Transaction Amounts (Log-normal distribution simulating financial flows)
    amounts = np.round(np.random.lognormal(mean=7.5, sigma=1.6, size=num_records) + 5, 2)

    # 4. Origin Accounts & Balances
    orig_ids = [f"C{np.random.randint(100000000, 999999999)}" for _ in range(num_records)]
    old_balance_orig = np.round(np.random.uniform(500, 350000, size=num_records), 2)
    
    # Calculate new origin balance based on transaction direction
    new_balance_orig = np.zeros(num_records)
    for i, t in enumerate(tx_types):
        if t in ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT"]:
            new_balance_orig[i] = max(0.0, round(old_balance_orig[i] - amounts[i], 2))
        else: # CASH_IN
            new_balance_orig[i] = round(old_balance_orig[i] + amounts[i], 2)

    # 5. Destination Accounts & Balances (Merchants start with 'M', Customers with 'C')
    dest_ids = []
    for t in tx_types:
        if t == "PAYMENT":
            dest_ids.append(f"M{np.random.randint(100000000, 999999999)}")
        else:
            dest_ids.append(f"C{np.random.randint(100000000, 999999999)}")

    old_balance_dest = np.round(np.random.uniform(0, 150000, size=num_records), 2)
    new_balance_dest = np.zeros(num_records)
    for i, t in enumerate(tx_types):
        if t in ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT"]:
            new_balance_dest[i] = round(old_balance_dest[i] + amounts[i], 2)
        else:
            new_balance_dest[i] = max(0.0, round(old_balance_dest[i] - amounts[i], 2))

    # 6. Fraud Labels (PaySim Rule: Fraud mostly occurs on large TRANSFER / CASH_OUT)
    is_fraud = np.zeros(num_records, dtype=int)
    is_flagged_fraud = np.zeros(num_records, dtype=int)

    for i in range(num_records):
        if tx_types[i] in ["TRANSFER", "CASH_OUT"]:
            # Higher chance of exception/fraud on anomalous account drain
            if old_balance_orig[i] > 10000 and new_balance_orig[i] == 0:
                is_fraud[i] = np.random.choice([0, 1], p=[0.75, 0.25])
            elif amounts[i] > 150000:
                is_fraud[i] = np.random.choice([0, 1], p=[0.85, 0.15])

        # PaySim rule: Flagged if transfer > 200,000 in single simulation step
        if amounts[i] >= 200000 and tx_types[i] == "TRANSFER":
            is_flagged_fraud[i] = 1

    # 7. Map step to calendar date timestamp (starting 2026-08-01)
    base_date = datetime(2026, 8, 1, 0, 0, 0)
    timestamps = [base_date + timedelta(hours=int(s)) for s in steps]
    date_strs = [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in timestamps]

    df = pd.DataFrame({
        "step": steps,
        "timestamp": date_strs,
        "type": tx_types,
        "amount": amounts,
        "nameOrig": orig_ids,
        "oldbalanceOrg": old_balance_orig,
        "newbalanceOrig": new_balance_orig,
        "nameDest": dest_ids,
        "oldbalanceDest": old_balance_dest,
        "newbalanceDest": new_balance_dest,
        "isFraud": is_fraud,
        "isFlaggedFraud": is_flagged_fraud,
    })

    # Save to CSV
    csv_file = "paysim_financial_transactions.csv"
    df.to_csv(csv_file, index=False)
    print(f"[2/3] Successfully generated {len(df)} records. Saved to '{csv_file}'.")

    # Ingest into SQLite Database
    print("[3/3] Ingesting into SQLite 'financial_datasets.db'...")
    conn = sqlite3.connect("financial_datasets.db")
    df.to_sql("paysim_transactions", conn, if_exists="replace", index=False)
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(amount), SUM(isFraud), SUM(isFlaggedFraud) FROM paysim_transactions;")
    stats = cursor.fetchone()
    print(f"[Database Summary] Table 'paysim_transactions':")
    print(f"  - Total Transactions: {stats[0]:,}")
    print(f"  - Total Financial Volume: ${stats[1]:,.2f}")
    print(f"  - Fraud / Exception Breaks: {stats[2]:,}")
    print(f"  - System Flagged High-Risk (>= $200k): {stats[3]:,}")

    conn.close()

if __name__ == "__main__":
    generate_paysim_data()
