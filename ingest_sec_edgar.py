# ingest_sec_edgar.py
import sys
import requests
import pandas as pd
import json

sys.stdout.reconfigure(encoding='utf-8')

# SEC requires User-Agent header in format: "Name Contact@email.com"
HEADERS = {
    "User-Agent": "LedgerControlFinancePlatform admin@ledgercontrol.io",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

def fetch_sec_company_facts(ciks=[("Apple Inc", "0000320193"), ("Microsoft Corp", "0000789019")]):
    extracted = []
    
    for entity_name_default, cik in ciks:
        print(f"[SEC] Querying SEC EDGAR for CIK: {cik} ({entity_name_default})...")
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                print(f"[SEC Warning] Responded with status {response.status_code} for CIK {cik}")
                continue

            data = response.json()
            entity_name = data.get("entityName", entity_name_default)
            print(f"[SEC] Found records for: {entity_name}")

            # Extract Operating Cash Flow (US-GAAP taxonomy)
            us_gaap = data.get("facts", {}).get("us-gaap", {})
            cash_flow_facts = us_gaap.get("NetCashProvidedByUsedInOperatingActivities", {}).get("units", {}).get("USD", [])

            for item in cash_flow_facts:
                if item.get("form") in ["10-Q", "10-K"]:
                    extracted.append({
                        "entity": entity_name,
                        "form": item.get("form"),
                        "fiscal_year": item.get("fy"),
                        "fiscal_period": item.get("fp"),
                        "start_date": item.get("start"),
                        "end_date": item.get("end"),
                        "filed_date": item.get("filed"),
                        "operating_cash_flow": item.get("val"),
                    })
        except Exception as e:
            print(f"[SEC Error] Querying CIK {cik}: {e}")

    if extracted:
        df = pd.DataFrame(extracted).drop_duplicates(subset=["entity", "end_date", "form"]).sort_values(["entity", "end_date"], ascending=[True, False])
        df.to_csv("sec_edgar_cash_flows.csv", index=False)
        print(f"[SEC Success] Successfully extracted {len(df)} filings. Saved to 'sec_edgar_cash_flows.csv'.")
        print(df.head(10))
    else:
        print("[SEC Error] No records could be extracted from SEC EDGAR.")

if __name__ == "__main__":
    fetch_sec_company_facts()
