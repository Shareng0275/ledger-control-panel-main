import requests
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 1. Authenticate
login = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "admin@ledgercontrol.com", "password": "Password123!"}
).json()

token = login.get("access_token")
if not token:
    print("Authentication failed:", login)
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}

questions = [
    "What's my current cash position?",
    "Why did my settlement drop last Tuesday?",
    "Show me unreconciled transactions from Stripe above $500"
]

for i, q in enumerate(questions, 1):
    res = requests.post(
        "http://localhost:8000/api/v1/ask",
        json={"question": q},
        headers=headers
    ).json()

    print(f"\n{'='*70}")
    print(f"QUERY {i}: \"{q}\"")
    print(f"{'='*70}")
    print(f"Intent Classified : {res.get('intent')}")
    print(f"Confidence        : {res.get('confidence')}")
    print(f"Answer Output     :\n{res.get('answer')}")
    print(f"Supporting Rows   : {len(res.get('supporting_rows', []))} records provided")
    if res.get('supporting_rows'):
        print("Sample Row        :", json.dumps(res['supporting_rows'][0], indent=2))
