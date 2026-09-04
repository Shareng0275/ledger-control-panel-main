import os
import csv
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

SAMPLE_DIR = os.path.join(os.getcwd(), "SAMPLE")
os.makedirs(SAMPLE_DIR, exist_ok=True)

# -------------------------------------------------------------
# 1. GENERATE SAMPLE 1: BANK STATEMENT (CASH POSITION)
# -------------------------------------------------------------
sample1_csv_path = os.path.join(SAMPLE_DIR, "Sample1.csv")
sample1_pdf_path = os.path.join(SAMPLE_DIR, "Sample1.pdf")

# Generate 90 days of realistic bank transactions
bank_txs = [
    # (Date, Description, Amount, Reference, Running Balance)
    ("2026-06-02", "OPENING BALANCE FORWARD", 1250450.00, "BAL-0601", 1250450.00),
    ("2026-06-05", "STRIPE PAYOUT SETTLEMENT - BATCH 8841", 45210.50, "STRIPE-8841", 1295660.50),
    ("2026-06-08", "PAYPAL MERCHANT TRANSFER 9920", 18450.25, "PAYPAL-9920", 1314110.75),
    ("2026-06-12", "ADYEN NV NET PAYOUT REF 4410", 32890.00, "ADYEN-4410", 1347000.75),
    ("2026-06-15", "WIRE OUT - AWS CLOUD HOSTING CORP", -14200.00, "WIRE-AWS-06", 1332800.75),
    ("2026-06-18", "SQUARE INC MERCHANT DEPOSIT 7711", 12450.80, "SQ-7711", 1345251.55),
    ("2026-06-22", "STRIPE PAYOUT SETTLEMENT - BATCH 8892", 52140.00, "STRIPE-8892", 1397391.55),
    ("2026-06-26", "PAYROLL DIRECT DEBIT ACH BATCH", -85400.00, "ACH-PAYROLL-06", 1311991.55),
    ("2026-06-30", "COMMERCIAL ACCOUNT MONTHLY INTEREST", 3415.20, "INT-202606", 1315406.75),
    ("2026-07-03", "STRIPE PAYOUT SETTLEMENT - BATCH 8914", 48950.00, "STRIPE-8914", 1364356.75),
    ("2026-07-07", "PAYPAL MERCHANT TRANSFER 9988", 21340.50, "PAYPAL-9988", 1385697.25),
    ("2026-07-10", "ADYEN NV NET PAYOUT REF 4480", 29400.00, "ADYEN-4480", 1415097.25),
    ("2026-07-14", "STRIPE DISPUTE DEBIT HOLD #9102", -2450.00, "DISP-9102", 1412647.25),
    ("2026-07-17", "SQUARE INC MERCHANT DEPOSIT 7750", 15820.40, "SQ-7750", 1428467.65),
    ("2026-07-21", "WIRE OUT - OFFICE LEASE METROPOLIS", -22500.00, "WIRE-LEASE-07", 1405967.65),
    ("2026-07-25", "STRIPE PAYOUT SETTLEMENT - BATCH 8955", 61200.00, "STRIPE-8955", 1467167.65),
    ("2026-07-28", "PAYROLL DIRECT DEBIT ACH BATCH", -86100.00, "ACH-PAYROLL-07", 1381067.65),
    ("2026-07-31", "COMMERCIAL ACCOUNT MONTHLY INTEREST", 3620.10, "INT-202607", 1384687.75),
    ("2026-08-04", "STRIPE PAYOUT SETTLEMENT - BATCH 9012", 54310.00, "STRIPE-9012", 1438997.75),
    ("2026-08-08", "PAYPAL MERCHANT TRANSFER 1004", 19800.00, "PAYPAL-1004", 1458797.75),
    ("2026-08-11", "ADYEN NV NET PAYOUT REF 4520", 34120.00, "ADYEN-4520", 1492917.75),
    ("2026-08-15", "WIRE OUT - HARDWARE & SERVERS LTD", -18900.00, "WIRE-HW-08", 1474017.75),
    ("2026-08-18", "SQUARE INC MERCHANT DEPOSIT 7801", 14230.90, "SQ-7801", 1488248.65),
    ("2026-08-22", "STRIPE PAYOUT SETTLEMENT - BATCH 9066", 58400.00, "STRIPE-9066", 1546648.65),
    ("2026-08-25", "DISCREPANCY UNMATCHED DEPOSIT", 7500.00, "UNMATCH-0825", 1554148.65),
    ("2026-08-28", "PAYROLL DIRECT DEBIT ACH BATCH", -86500.00, "ACH-PAYROLL-08", 1467648.65),
    ("2026-08-31", "CLOSING STATEMENT BALANCE", 0.00, "CLOSE-0831", 1467648.65)
]

# Write Sample1.csv
with open(sample1_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "description", "amount", "reference", "balance"])
    for row in bank_txs:
        writer.writerow(row)
print(f"[+] Created {sample1_csv_path}")

# Write Sample1.pdf using ReportLab
def build_sample1_pdf():
    doc = SimpleDocTemplate(sample1_pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#1E293B'), spaceAfter=4)
    sub_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#64748B'), spaceAfter=12)
    meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#334155'))
    table_hdr_style = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)
    table_cell_style = ParagraphStyle('TD', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#1E293B'))
    table_cell_mono = ParagraphStyle('TDM', parent=styles['Normal'], fontName='Courier', fontSize=8, textColor=colors.HexColor('#0F172A'))

    story = []
    story.append(Paragraph("JPMorgan Chase Commercial Banking", title_style))
    story.append(Paragraph("Official Commercial Checking Account Statement — Cash Position Report", sub_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=10))

    meta_data = [
        [Paragraph("<b>Account Holder:</b> Acme Financial Corp", meta_style), Paragraph("<b>Statement Period:</b> 2026-06-01 to 2026-08-31", meta_style)],
        [Paragraph("<b>Account Number:</b> *******8921", meta_style), Paragraph("<b>Currency:</b> USD ($)", meta_style)],
        [Paragraph("<b>Opening Balance:</b> $1,250,450.00", meta_style), Paragraph("<b>Closing Balance:</b> $1,467,648.65", meta_style)],
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    table_data = [[
        Paragraph("Date", table_hdr_style),
        Paragraph("Description / Transaction Detail", table_hdr_style),
        Paragraph("Reference", table_hdr_style),
        Paragraph("Amount (USD)", table_hdr_style),
        Paragraph("Balance (USD)", table_hdr_style),
    ]]

    for date, desc, amt, ref, bal in bank_txs[1:]:
        amt_str = f"${amt:,.2f}" if amt >= 0 else f"-${abs(amt):,.2f}"
        bal_str = f"${bal:,.2f}"
        table_data.append([
            Paragraph(date, table_cell_mono),
            Paragraph(desc, table_cell_style),
            Paragraph(ref, table_cell_mono),
            Paragraph(amt_str, table_cell_mono),
            Paragraph(bal_str, table_cell_mono),
        ])

    tx_table = Table(table_data, colWidths=[65, 230, 85, 80, 80])
    tx_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    story.append(tx_table)
    doc.build(story)
    print(f"[+] Created {sample1_pdf_path}")

build_sample1_pdf()

# -------------------------------------------------------------
# 2. GENERATE SAMPLE 2: MULTI-GATEWAY SETTLEMENT LEDGER
# -------------------------------------------------------------
sample2_csv_path = os.path.join(SAMPLE_DIR, "Sample2.csv")
sample2_pdf_path = os.path.join(SAMPLE_DIR, "Sample2.pdf")

gateway_txs = [
    # (SettlementDate, Processor, GrossVolume, Fee, NetPayout, PayoutReference, Status, DiscrepancyNotes)
    ("2026-06-04", "Stripe", 46560.76, 1350.26, 45210.50, "STRIPE-8841", "PAID", "Exact Match with Bank Statement"),
    ("2026-06-07", "PayPal", 19001.29, 551.04, 18450.25, "PAYPAL-9920", "PAID", "Exact Match with Bank Statement"),
    ("2026-06-11", "Adyen", 33698.77, 808.77, 32890.00, "ADYEN-4410", "PAID", "Exact Match with Bank Statement"),
    ("2026-06-17", "Square", 12822.66, 371.86, 12450.80, "SQ-7711", "PAID", "Exact Match with Bank Statement"),
    ("2026-06-21", "Stripe", 53697.22, 1557.22, 52140.00, "STRIPE-8892", "PAID", "Exact Match with Bank Statement"),
    ("2026-07-02", "Stripe", 50411.95, 1461.95, 48950.00, "STRIPE-8914", "PAID", "Exact Match with Bank Statement"),
    ("2026-07-06", "PayPal", 21977.86, 637.36, 21340.50, "PAYPAL-9988", "PAID", "Exact Match with Bank Statement"),
    ("2026-07-09", "Adyen", 30122.95, 722.95, 29400.00, "ADYEN-4480", "PAID", "Exact Match with Bank Statement"),
    ("2026-07-13", "Stripe", -2450.00, 0.00, -2450.00, "DISP-9102", "DISPUTE_HOLD", "Dispute hold deduction"),
    ("2026-07-16", "Square", 16292.89, 472.49, 15820.40, "SQ-7750", "PAID", "Exact Match with Bank Statement"),
    ("2026-07-24", "Stripe", 63027.81, 1827.81, 61200.00, "STRIPE-8955", "PAID", "Exact Match with Bank Statement"),
    ("2026-08-03", "Stripe", 55932.03, 1622.03, 54310.00, "STRIPE-9012", "PAID", "Exact Match with Bank Statement"),
    ("2026-08-07", "PayPal", 20391.35, 591.35, 19800.00, "PAYPAL-1004", "PAID", "Exact Match with Bank Statement"),
    ("2026-08-10", "Adyen", 34958.97, 838.97, 34120.00, "ADYEN-4520", "PAID", "Exact Match with Bank Statement"),
    ("2026-08-17", "Square", 14655.92, 425.02, 14230.90, "SQ-7801", "PAID", "Exact Match with Bank Statement"),
    ("2026-08-21", "Stripe", 60144.18, 1744.18, 58400.00, "STRIPE-9066", "PAID", "Exact Match with Bank Statement"),
    ("2026-08-24", "Stripe", 5149.33, 149.33, 5000.00, "STRIPE-UNREC-991", "PENDING", "Unreconciled Stripe breakout payout"),
    ("2026-08-27", "PayPal", 12358.42, 358.42, 12000.00, "PAYPAL-UNREC-882", "HOLD", "Merchant audit reserve hold"),
    ("2026-08-30", "Adyen", 18537.64, 444.64, 18093.00, "ADYEN-IN-TRANSIT", "IN_TRANSIT", "In-transit end of month settlement"),
]

# Write Sample2.csv
with open(sample2_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["settlement_date", "processor", "gross_amount", "processing_fee", "net_amount", "reference_id", "status", "notes"])
    for row in gateway_txs:
        writer.writerow(row)
print(f"[+] Created {sample2_csv_path}")

# Write Sample2.pdf using ReportLab
def build_sample2_pdf():
    doc = SimpleDocTemplate(sample2_pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    sub_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#64748B'), spaceAfter=12)
    meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#334155'))
    table_hdr_style = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)
    table_cell_style = ParagraphStyle('TD', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#1E293B'))
    table_cell_mono = ParagraphStyle('TDM', parent=styles['Normal'], fontName='Courier', fontSize=8, textColor=colors.HexColor('#0F172A'))

    story = []
    story.append(Paragraph("Global Merchant Processing Network", title_style))
    story.append(Paragraph("Consolidated Gateway Settlement Ledger — Multi-Processor Audit Report", sub_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=10))

    gross_total = sum(r[2] for r in gateway_txs)
    fee_total = sum(r[3] for r in gateway_txs)
    net_total = sum(r[4] for r in gateway_txs)

    meta_data = [
        [Paragraph("<b>Merchant:</b> Acme Financial Corp", meta_style), Paragraph("<b>Consolidated Gateways:</b> Stripe, PayPal, Adyen, Square", meta_style)],
        [Paragraph(f"<b>Total Gross Volume:</b> ${gross_total:,.2f}", meta_style), Paragraph("<b>Audit Status:</b> Verified Multi-Stream Log", meta_style)],
        [Paragraph(f"<b>Total Processor Fees:</b> ${fee_total:,.2f}", meta_style), Paragraph(f"<b>Net Settled Volume:</b> ${net_total:,.2f}", meta_style)],
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    table_data = [[
        Paragraph("Date", table_hdr_style),
        Paragraph("Gateway", table_hdr_style),
        Paragraph("Gross Vol", table_hdr_style),
        Paragraph("Fees", table_hdr_style),
        Paragraph("Net Payout", table_hdr_style),
        Paragraph("Reference ID", table_hdr_style),
        Paragraph("Status", table_hdr_style),
    ]]

    for date, proc, gross, fee, net, ref, status, notes in gateway_txs:
        table_data.append([
            Paragraph(date, table_cell_mono),
            Paragraph(proc, table_cell_style),
            Paragraph(f"${gross:,.2f}", table_cell_mono),
            Paragraph(f"${fee:,.2f}", table_cell_mono),
            Paragraph(f"${net:,.2f}", table_cell_mono),
            Paragraph(ref, table_cell_mono),
            Paragraph(status, table_cell_style),
        ])

    tx_table = Table(table_data, colWidths=[65, 60, 75, 65, 80, 115, 80])
    tx_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    story.append(tx_table)
    doc.build(story)
    print(f"[+] Created {sample2_pdf_path}")

build_sample2_pdf()
print("\n[SUCCESS] Sample1 and Sample2 generated in both PDF and CSV formats!")
