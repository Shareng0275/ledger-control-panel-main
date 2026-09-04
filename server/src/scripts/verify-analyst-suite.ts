const BASE_URL = "http://localhost:8000/api/v1";

async function runAnalystVerificationSuite() {
  console.log("==================================================================");
  console.log("  PART 6: ANALYST ROLE SPECIFICATION & PERMISSIONS VERIFICATION");
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

  // 1. Authenticate as ANALYST
  console.log("\n[Test 1] Analyst Authentication");
  let analystToken = "";
  try {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "analyst@ledgercontrol.com", password: "Password123!" }),
    });
    const data = (await res.json()) as any;
    analystToken = data.access_token || data.token;
    assert(res.status === 200, "Analyst login succeeded with 200 OK");
    assert(Boolean(analystToken), "Analyst access token received");
  } catch (err: any) {
    assert(false, "Analyst Login", err.message);
  }

  const authHeaders = {
    Authorization: `Bearer ${analystToken}`,
    "Content-Type": "application/json",
  };

  // 2. ALLOWED: Advanced Dashboard & Forecast Queries
  console.log("\n[Test 2] Allowed: Advanced Forecasting & Analytics Queries");
  try {
    const forecastRes = await fetch(`${BASE_URL}/forecast?horizon=90d`, { headers: authHeaders });
    const forecastData = (await forecastRes.json()) as any;
    assert(forecastRes.status === 200, "Analyst can query 90-day cash forecast horizon");
    assert(Array.isArray(forecastData.points), "Forecast returns projection array");
    assert(typeof (forecastData.analytics?.net_daily_drift ?? forecastData.analytics?.netDailyDrift) === "number", "Analytics drift calculation returned");
  } catch (err: any) {
    assert(false, "Forecast Query", err.message);
  }

  // 3. ALLOWED: AI-Assisted Governed Insights Query
  console.log("\n[Test 3] Allowed: AI-Assisted Financial Q&A (Governed Data)");
  try {
    const askRes = await fetch(`${BASE_URL}/ask`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ question: "What is the status of reconciliation exceptions?" }),
    });
    const askData = (await askRes.json()) as any;
    assert(askRes.status === 200, "Analyst can ask governed financial questions");
    assert(Boolean(askData.answer), "AI answer provided");
    assert(Array.isArray(askData.supporting_rows || askData.supporting_records), "Supporting real data rows returned");
  } catch (err: any) {
    assert(false, "AI Ask Query", err.message);
  }

  // 4. ALLOWED: Complex Filtering & Paginated Transaction Exploration
  console.log("\n[Test 4] Allowed: Complex Query Filtering & Sorting");
  try {
    const filterRes = await fetch(`${BASE_URL}/transactions?page=1&page_size=10&sort_by=amount&sort_order=desc`, {
      headers: authHeaders,
    });
    const filterData = (await filterRes.json()) as any;
    assert(filterRes.status === 200, "Analyst can execute complex filtered queries");
    assert(Array.isArray(filterData.items), "Items returned in paginated payload");
    assert(filterData.page_size === 10, "Page size limit applied");
  } catch (err: any) {
    assert(false, "Complex Filtering", err.message);
  }

  // 5. ALLOWED: Authorized Report Export
  console.log("\n[Test 5] Allowed: Authorized CSV Report Export");
  try {
    const exportRes = await fetch(`${BASE_URL}/transactions/export`, {
      headers: { Authorization: `Bearer ${analystToken}` },
    });
    const text = await exportRes.text();
    assert(exportRes.status === 200, "Analyst can export authorized transaction reports");
    assert(text.includes("ID,Date,Description,Amount"), "Valid CSV structure returned");
  } catch (err: any) {
    assert(false, "Analyst Report Export", err.message);
  }

  // 6. DENIED (403): Admin Audit Log Access
  console.log("\n[Test 6] Denied: Analyst Access to Admin Audit Logs");
  try {
    const auditRes = await fetch(`${BASE_URL}/audit`, { headers: authHeaders });
    assert(auditRes.status === 403, "Analyst blocked from admin audit logs with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Analyst Audit Denial", err.message);
  }

  // 7. DENIED (403): Cross-Organization Tenant Access Attempt
  console.log("\n[Test 7] Denied: Cross-Organization Tenant Access Violation");
  try {
    const crossRes = await fetch(`${BASE_URL}/transactions`, {
      headers: {
        Authorization: `Bearer ${analystToken}`,
        "x-organization-id": "fake-foreign-tenant-uuid-4444",
      },
    });
    assert(crossRes.status === 403, "Cross-organization query rejected with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Cross-Organization Denial", err.message);
  }

  console.log("\n==================================================================");
  console.log(`  RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runAnalystVerificationSuite().catch((err) => {
  console.error("Fatal Test Suite Error:", err);
  process.exit(1);
});
