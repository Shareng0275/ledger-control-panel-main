const BASE_URL = "http://localhost:8000/api/v1";

async function runViewerVerificationSuite() {
  console.log("==================================================================");
  console.log("  PART 5: VIEWER ROLE SPECIFICATION & PERMISSIONS VERIFICATION");
  console.log("==================================================================");

  let passed = 0;
  let total = 0;

  function assert(condition: boolean, testName: string, detail?: string) {
    total++;
    if (condition) {
      console.log(`✅ [PASS] ${testName}`);
      passed++;
    } else {
      console.error(`❌ [FAIL] ${testName} - ${detail || ""}`);
    }
  }

  // 1. Authenticate as VIEWER
  console.log("\n[Test 1] Viewer Authentication");
  let viewerToken = "";
  try {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "viewer@ledgercontrol.com", password: "Password123!" }),
    });
    const data = (await res.json()) as any;
    viewerToken = data.access_token || data.token;
    assert(res.status === 200, "Viewer login succeeded with 200 OK");
    assert(Boolean(viewerToken), "Viewer access token received");
  } catch (err: any) {
    assert(false, "Viewer Login", err.message);
  }

  const authHeaders = {
    Authorization: `Bearer ${viewerToken}`,
    "Content-Type": "application/json",
  };

  // 2. ALLOWED: View Authorized Dashboard / Reports / Transactions
  console.log("\n[Test 2] Allowed: Viewer Access to Authorized Records & Forecast");
  try {
    const txRes = await fetch(`${BASE_URL}/transactions`, { headers: authHeaders });
    assert(txRes.status === 200, "Viewer can list authorized transactions (reconciliation.read)");

    const forecastRes = await fetch(`${BASE_URL}/forecast`, { headers: authHeaders });
    assert(forecastRes.status === 200, "Viewer can view forecast analytics (analytics.read)");
  } catch (err: any) {
    assert(false, "Viewer Allowed Operations", err.message);
  }

  // 3. ALLOWED: Download Permitted Exports
  console.log("\n[Test 3] Allowed: Viewer Permitted CSV Export");
  try {
    const exportRes = await fetch(`${BASE_URL}/transactions/export`, {
      headers: { Authorization: `Bearer ${viewerToken}` },
    });
    const contentType = exportRes.headers.get("content-type");
    const text = await exportRes.text();
    assert(exportRes.status === 200, "Viewer can download permitted CSV export");
    assert(Boolean(contentType?.includes("text/csv")), "Export returns text/csv Content-Type");
    assert(text.includes("ID,Date,Description,Amount"), "Export includes standard CSV headers");
  } catch (err: any) {
    assert(false, "Viewer Permitted Export", err.message);
  }

  // 4. DENIED (403): Create / Upload Statements or Documents
  console.log("\n[Test 4] Denied: Viewer Attempt to Upload Statement (Create)");
  try {
    const uploadRes = await fetch(`${BASE_URL}/uploads/statement`, {
      method: "POST",
      headers: { Authorization: `Bearer ${viewerToken}` },
    });
    assert(uploadRes.status === 403, "Viewer upload attempt rejected with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Viewer Upload Denial", err.message);
  }

  // 5. DENIED (403): Trigger Reconciliation Run
  console.log("\n[Test 5] Denied: Viewer Attempt to Trigger Reconciliation Run");
  try {
    const runRes = await fetch(`${BASE_URL}/reconcile/run`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ statement_id: "fake_id", ledger_id: "fake_id" }),
    });
    assert(runRes.status === 403, "Viewer run trigger rejected with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Viewer Reconcile Run Denial", err.message);
  }

  // 6. DENIED (403): Resolve / Update Exception
  console.log("\n[Test 6] Denied: Viewer Attempt to Resolve Exception (Update)");
  try {
    const resolveRes = await fetch(`${BASE_URL}/exceptions/any_exc_id/resolve`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ resolution_type: "manual_match" }),
    });
    assert(resolveRes.status === 403, "Viewer exception resolve rejected with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Viewer Exception Resolve Denial", err.message);
  }

  // 7. DENIED (403): Direct Admin Route / Audit Logs Attempt
  console.log("\n[Test 7] Denied: Viewer Attempt to Access Admin Audit Log");
  try {
    const auditRes = await fetch(`${BASE_URL}/audit`, { headers: authHeaders });
    assert(auditRes.status === 403, "Viewer audit access rejected with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Viewer Audit Log Denial", err.message);
  }

  console.log("\n==================================================================");
  console.log(`  RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runViewerVerificationSuite().catch((err) => {
  console.error("Fatal Test Suite Error:", err);
  process.exit(1);
});
