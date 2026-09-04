import csv
from datetime import datetime, timedelta

# Generate 90 days of rich financial transactions (2026-06-01 to 2026-08-31)
start_date = datetime(2026, 6, 1)

statement_rows = []
ledger_rows = []

gateways = ["Stripe", "PayPal", "Adyen", "Square", "Razorpay"]
merchants = [
    ("Acme E-Commerce SaaS", "STRIPE", 4500.00, 130.50),
    ("Nova Cloud Services", "STRIPE", 12500.00, 362.50),
    ("Apex Global Subscriptions", "PAYPAL", 6800.00, 197.20),
    ("Quantum Retail Checkout", "ADYEN", 28400.00, 681.60),
    ("Vertex Point of Sale", "SQUARE", 9200.00, 266.80),
    ("Helios Enterprise API", "STRIPE", 34100.00, 988.90),
    ("Zenith Digital Marketplace", "RAZORPAY", 18200.00, 455.00),
    ("Horizon Mobile In-App", "ADYEN", 14900.00, 357.60),
    ("Omni Corp Enterprise Wire", "WIRE", 52000.00, 25.00),
    ("Strata Systems Billing", "STRIPE", 21800.00, 632.20),
]

recurring_debits = [
    ("AWS Cloud Infrastructure Compute", -14250.00, "INV-AWS-US"),
    ("Google Workspace Enterprise Seats", -840.00, "INV-GSUITE"),
    ("Datadog Infrastructure Monitoring", -3200.00, "INV-DDOG"),
    ("Office Lease Global HQ", -18500.00, "LEASE-HQ"),
    ("Bi-Weekly Payroll Direct Deposit ACH", -42500.00, "PAYROLL-ACH"),
    ("GitHub Enterprise Cloud Plan", -520.00, "INV-GHUB"),
    ("Slack Enterprise Grid Communications", -1200.00, "INV-SLACK"),
    ("Stripe Chargeback Dispute Hold", -1500.00, "DISP-HOLD"),
]

seq = 1000

for day in range(92):
    current_date = start_date + timedelta(days=day)
    date_str = current_date.strftime("%Y-%m-%d")
    weekday = current_date.weekday() # 0-6

    # 1. Gateways settle payouts every weekday
    if weekday < 5:
        # Pick 2-3 merchant gateway batches per weekday
        m1 = merchants[day % len(merchants)]
        m2 = merchants[(day + 3) % len(merchants)]

        for merchant_name, gw, gross, fee in [m1, m2]:
            seq += 1
            net = gross - fee
            ref = f"{gw}-BATCH-{seq}"
            
            # Statement credit (Net Payout deposited into bank)
            statement_rows.append([
                date_str,
                f"{gw} Payout Settlement - {merchant_name}",
                f"{net:.2f}",
                "USD",
                ref,
                "credit"
            ])

            # Ledger row (Gateway internal settlement record)
            # Create exact match for most, and slight fee timing break on some
            has_fee_break = (day % 11 == 0)
            ledger_amt = net - 45.00 if has_fee_break else net
            status = "PENDING_REVIEW" if has_fee_break else "SETTLED"

            ledger_rows.append([
                date_str,
                f"{gw} Gateway Payout - {merchant_name}",
                f"{ledger_amt:.2f}",
                "USD",
                ref,
                gw.lower(),
                status
            ])

    # 2. Operating Debits / Invoices
    if day in [4, 18, 34, 48, 64, 78]: # Payroll
        p = recurring_debits[4]
        ref = f"{p[2]}-{day}"
        statement_rows.append([date_str, p[0], f"{p[1]:.2f}", "USD", ref, "debit"])
    elif day in [1, 31, 61]: # Lease
        l = recurring_debits[3]
        ref = f"{l[2]}-{day}"
        statement_rows.append([date_str, l[0], f"{l[1]:.2f}", "USD", ref, "debit"])
    elif day % 7 == 2: # Tech vendors
        v = recurring_debits[(day % 4)]
        ref = f"{v[2]}-{day}"
        statement_rows.append([date_str, v[0], f"{v[1]:.2f}", "USD", ref, "debit"])

    # 3. Deliberate un-reconciled breaks & exceptions for audit testing
    if day in [15, 42, 73]:
        seq += 1
        # High-value unmatched Stripe transaction > $500
        unrec_amt = 850.00 + (day * 15)
        ref = f"STRIPE-UNREC-{seq}"
        ledger_rows.append([
            date_str,
            f"Stripe Direct Checkout - Uncaptured Break #{seq}",
            f"{unrec_amt:.2f}",
            "USD",
            ref,
            "stripe",
            "EXCEPTION"
        ])

# Write statement CSV
stmt_file = "data/raw/statement_data.csv"
with open(stmt_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "description", "amount", "currency", "reference", "transaction_type"])
    for r in statement_rows:
        writer.writerow(r)
print(f"[+] Wrote {len(statement_rows)} 90-day records to {stmt_file}")

# Write ledger CSV
ledger_file = "data/raw/ledger_data.csv"
with open(ledger_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "description", "amount", "currency", "reference", "source", "status"])
    for r in ledger_rows:
        writer.writerow(r)
print(f"[+] Wrote {len(ledger_rows)} 90-day records to {ledger_file}")
