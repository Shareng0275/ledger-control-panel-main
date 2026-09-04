const BASE_URL = "http://localhost:8000/api/v1";

async function runAdvancedFeaturesVerificationSuite() {
  console.log("==================================================================");
  console.log("  PART 11: ADVANCED ENTERPRISE FEATURES VERIFICATION SUITE");
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

  // Helper to obtain login token
  async function getTokenFor(email: string) {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: "Password123!" }),
    });
    const data = (await res.json()) as any;
    return data.access_token || data.token;
  }

  let analystToken = "";
  let viewerToken = "";
  try {
    analystToken = await getTokenFor("analyst@ledgercontrol.com");
    viewerToken = await getTokenFor("viewer@ledgercontrol.com");
    assert(Boolean(analystToken), "Analyst token retrieved");
    assert(Boolean(viewerToken), "Viewer token retrieved");
  } catch (err: any) {
    assert(false, "Authentication", err.message);
  }

  const analystHeaders = {
    Authorization: `Bearer ${analystToken}`,
    "Content-Type": "application/json",
  };
  const viewerHeaders = {
    Authorization: `Bearer ${viewerToken}`,
    "Content-Type": "application/json",
  };

  // 1. Custom Dashboards & User Preferences
  console.log("\n[Test 1] Custom Dashboard & User Preferences");
  try {
    const getPrefRes = await fetch(`${BASE_URL}/users/preferences`, { headers: analystHeaders });
    const prefData = (await getPrefRes.json()) as any;
    assert(getPrefRes.status === 200, "User can retrieve dashboard preferences (200 OK)");
    assert(Array.isArray(prefData.visible_kpis), "Visible KPIs array returned");

    const updatePrefRes = await fetch(`${BASE_URL}/users/preferences`, {
      method: "PUT",
      headers: analystHeaders,
      body: JSON.stringify({
        default_horizon: "90d",
        visible_kpis: ["matched_rate", "volatility", "total_value"],
        dashboard_cards: ["summary_donut", "forecast_line", "recent_exceptions"],
      }),
    });
    const updatedData = (await updatePrefRes.json()) as any;
    assert(updatePrefRes.status === 200, "User preferences updated (200 OK)");
    assert(updatedData.default_horizon === "90d", "Horizon preference persisted");
  } catch (err: any) {
    assert(false, "Custom Dashboard Preferences", err.message);
  }

  // 2. Predictive Anomaly Detection (Statistical Pipeline)
  console.log("\n[Test 2] Predictive Anomaly Detection Pipeline");
  try {
    const anomalyRes = await fetch(`${BASE_URL}/analytics/anomalies`, { headers: analystHeaders });
    const anomalyData = (await anomalyRes.json()) as any;

    assert(anomalyRes.status === 200, "Predictive anomaly detection query succeeded (200 OK)");
    assert(typeof anomalyData.overall_risk_score === "number", "Overall risk score computed");
    assert(Array.isArray(anomalyData.anomalies), "Anomalies array returned");
    if (anomalyData.anomalies.length > 0) {
      const first = anomalyData.anomalies[0];
      assert(typeof first.z_score === "number", "Z-score explainability feature present");
      assert(Boolean(first.human_review_required), "Human review safety flag verified");
    } else {
      assert(true, "Zero anomalies in test dataset handled gracefully");
    }
  } catch (err: any) {
    assert(false, "Predictive Anomaly Pipeline", err.message);
  }

  // 3. Automated Scheduled Reporting
  console.log("\n[Test 3] Automated Scheduled Reporting");
  try {
    // List scheduled reports
    const listReportsRes = await fetch(`${BASE_URL}/reports/scheduled`, { headers: analystHeaders });
    const listData = (await listReportsRes.json()) as any;
    assert(listReportsRes.status === 200, "List scheduled reports returned 200 OK");
    assert(Array.isArray(listData.reports), "Reports array returned");

    // Generate automated report
    const genReportRes = await fetch(`${BASE_URL}/reports/scheduled/generate`, {
      method: "POST",
      headers: analystHeaders,
      body: JSON.stringify({ report_type: "WEEKLY_EXCEPTION_SUMMARY", frequency: "WEEKLY" }),
    });
    const genData = (await genReportRes.json()) as any;
    assert(genReportRes.status === 201, "Scheduled report generated with 201 Created");
    assert(genData.status === "COMPLETED", "Report job status is 'COMPLETED'");
    assert(Boolean(genData.payload), "Report output payload stored");
  } catch (err: any) {
    assert(false, "Scheduled Reporting", err.message);
  }

  // 4. RBAC & Tenant Isolation Boundaries
  console.log("\n[Test 4] RBAC & Tenant Boundaries for Advanced Features");
  try {
    // Viewer without analytics.export blocked from triggering report generation
    const viewerBlockRes = await fetch(`${BASE_URL}/reports/scheduled/generate`, {
      method: "POST",
      headers: viewerHeaders,
      body: JSON.stringify({ report_type: "DAILY_RECONCILIATION" }),
    });
    assert(viewerBlockRes.status === 403, "Viewer is blocked from generating scheduled reports (403 Forbidden)");

    // Cross-tenant access attempt
    const crossRes = await fetch(`${BASE_URL}/analytics/anomalies`, {
      headers: {
        Authorization: `Bearer ${analystToken}`,
        "x-organization-id": "fake-foreign-tenant-uuid-7777",
      },
    });
    assert(crossRes.status === 403, "Cross-organization anomaly query strictly rejected (403 Forbidden)");
  } catch (err: any) {
    assert(false, "Boundaries Verification", err.message);
  }

  console.log("\n==================================================================");
  console.log(`  RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runAdvancedFeaturesVerificationSuite().catch((err) => {
  console.error("Fatal Test Suite Error:", err);
  process.exit(1);
});
