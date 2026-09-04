"""
Ingest Financial Market Data via Yahoo Finance (yfinance).
Extracts daily OHLCV bars for enterprise currencies, treasuries, and equities.
"""

from typing import List, Dict, Any
import sys
import pandas as pd
import yfinance as yf

# Reconfigure console output to handle standard UTF-8 streams
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def fetch_financial_market_data() -> None:
    """Fetch 90-day time-series data for major financial tickers."""
    print("[1/2] Downloading financial market data from Yahoo Finance...")

    tickers: List[str] = ["EURUSD=X", "GBPUSD=X", "AAPL", "MSFT", "^TNX"]
    records: List[Dict[str, Any]] = []

    for ticker in tickers:
        try:
            print(f"  -> Fetching {ticker}...")
            t = yf.Ticker(ticker)
            df = t.history(period="90d", interval="1d", auto_adjust=True)

            if df is None or df.empty:
                print(f"  [Warning] No data returned for {ticker}")
                continue

            df = df.reset_index()

            for _, row in df.iterrows():
                date_val = row["Date"] if "Date" in row else row["Datetime"]
                date_str = (
                    date_val.strftime("%Y-%m-%d")
                    if hasattr(date_val, "strftime")
                    else str(date_val)[:10]
                )

                open_p = round(float(row["Open"]), 4) if pd.notna(row.get("Open")) else 0.0
                close_p = round(float(row["Close"]), 4) if pd.notna(row.get("Close")) else 0.0
                high_p = round(float(row["High"]), 4) if pd.notna(row.get("High")) else 0.0
                low_p = round(float(row["Low"]), 4) if pd.notna(row.get("Low")) else 0.0
                vol = int(row["Volume"]) if pd.notna(row.get("Volume")) else 0

                records.append({
                    "date": date_str,
                    "ticker": ticker,
                    "open_price": open_p,
                    "close_price": close_p,
                    "high_price": high_p,
                    "low_price": low_p,
                    "volume": vol,
                })
        except Exception as e:
            print(f"  [Error] Failed to process {ticker}: {e}")

    output_df = pd.DataFrame(records)

    if output_df.empty:
        print("[Error] No records were downloaded.")
        return

    # Export to CSV
    output_df.to_csv("yahoo_financial_data.csv", index=False)
    print(f"\n[2/2] Successfully extracted {len(output_df)} market records for all {len(tickers)} tickers.")
    print("Saved to 'yahoo_financial_data.csv'.")
    print(output_df.head(10))


if __name__ == "__main__":
    fetch_financial_market_data()
