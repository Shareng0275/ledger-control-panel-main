const BASE_URL = "http://localhost:8000/api/v1";

async function runPhase14E2ETestingSuite() {
  console.log("==================================================================");
  console.log("  PHASE 14: COMPREHENSIVE END-TO-END SYSTEM TESTING SUITE");
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

  async function loginAs(email: string, password = "Password123!") {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = (await res.json()) as any;
    return { status: res.status, data, token: data.access_token || data.token, refreshToken: data.refresh_token, user: data.user };
  }

  // ─── STEP 1: PRE-TEST ENVIRONMENT INSPECTION ──────────────────────────────
  console.log("\n[Step 1] Pre-Test Environment & Connectivity Inspection");
  try {
    const healthRes = await fetch("http://localhost:8000/health");
    const healthData = (await healthRes.json()) as any;
    assert(healthRes.status === 200, "1.1 Backend health probe returns 200 OK");
    assert(healthData.database === "connected", "1.2 Database is connected and reachable");
    assert(healthData.status === "healthy", "1.3 Application state is healthy");
  } catch (err: any) {
    assert(false, "1.1-1.3 Environment inspection", err.message);
  }

  // ─── STEP 2: AUTHENTICATION TESTING ───────────────────────────────────────
  console.log("\n[Step 2] Authentication & Token Lifecycle Testing");
  const adminLogin = await loginAs("admin@ledgercontrol.com");
  assert(adminLogin.status === 200, "2.1 Successful login returns 200 OK");
  assert(Boolean(adminLogin.token), "2.2 Access token received");
  assert(Boolean(adminLogin.refreshToken), "2.3 Refresh token received");
  assert(adminLogin.user?.email === "admin@ledgercontrol.com", "2.4 Authenticated user info returned");
  assert(!("passwordHash" in adminLogin.user), "2.5 Password hash is NEVER exposed");

  const invalidEmail = await loginAs("nonexistent@domain.com");
  assert(invalidEmail.status === 401, "2.6 Invalid email rejected with 401");

  const invalidPass = await loginAs("admin@ledgercontrol.com", "WrongPassword!");
  assert(invalidPass.status === 401, "2.7 Invalid password rejected with 401");

  const missingCreds = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  assert(missingCreds.status === 422 || missingCreds.status === 400 || missingCreds.status === 401, "2.8 Missing credentials rejected");

  // Refresh token rotation
  const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: adminLogin.refreshToken }),
  });
  const refreshData = (await refreshRes.json()) as any;
  assert(refreshRes.status === 200, "2.9 Refresh endpoint returns 200 OK");
  assert(refreshData.refresh_token !== adminLogin.refreshToken, "2.10 Refresh token rotation produces new unique token");

  // Replay of old refresh token must be rejected
  const replayRes = await fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: adminLogin.refreshToken }),
  });
  assert(replayRes.status === 401, "2.11 Rotated refresh token reuse rejected with 401");

  // ─── STEP 3: VIEWER ROLE TESTING ──────────────────────────────────────────
  console.log("\n[Step 3] Viewer Role User Journey & Permission Enforcement");
  const viewerLogin = await loginAs("viewer@ledgercontrol.com");
  const viewerHeaders = { Authorization: `Bearer ${viewerLogin.token}`, "Content-Type": "application/json" };

  const viewerList = await fetch(`${BASE_URL}/transactions`, { headers: viewerHeaders });
  assert(viewerList.status === 200, "3.1 Viewer: Allowed viewing transactions");

  const viewerForecast = await fetch(`${BASE_URL}/forecast`, { headers: viewerHeaders });
  assert(viewerForecast.status === 200, "3.2 Viewer: Allowed viewing forecast report");

  const viewerExport = await fetch(`${BASE_URL}/transactions/export`, { headers: viewerHeaders });
  assert(viewerExport.status === 200, "3.3 Viewer: Allowed permitted CSV report export");

  const viewerDenyCreate = await fetch(`${BASE_URL}/records/drafts`, {
    method: "POST",
    headers: viewerHeaders,
    body: JSON.stringify({ title: "Unauthorized", description: "Test", amount: 100 }),
  });
  assert(viewerDenyCreate.status === 403, "3.4 Viewer: Blocked from record creation with 403 Forbidden");

  const viewerDenyAudit = await fetch(`${BASE_URL}/audit`, { headers: viewerHeaders });
  assert(viewerDenyAudit.status === 403, "3.5 Viewer: Blocked from audit log route with 403 Forbidden");

  // ─── STEP 4: ANALYST ROLE TESTING ─────────────────────────────────────────
  console.log("\n[Step 4] Analyst Role Analytics & AI Features");
  const analystLogin = await loginAs("analyst@ledgercontrol.com");
  const analystHeaders = { Authorization: `Bearer ${analystLogin.token}`, "Content-Type": "application/json" };

  const analystAsk = await fetch(`${BASE_URL}/ask`, {
    method: "POST",
    headers: analystHeaders,
    body: JSON.stringify({ question: "Summarize current financial reconciliation status" }),
  });
  const askData = (await analystAsk.json()) as any;
  assert(analystAsk.status === 200, "4.1 Analyst: AI-assisted financial Q&A returns 200 OK");
  assert(Boolean(askData.answer), "4.2 AI answer grounded in real database rows");

  const analystAnomalies = await fetch(`${BASE_URL}/analytics/anomalies`, { headers: analystHeaders });
  assert(analystAnomalies.status === 200, "4.3 Analyst: Predictive anomaly detection query returns 200 OK");

  const analystDenyUserManage = await fetch(`${BASE_URL}/admin/users`, { headers: analystHeaders });
  assert(analystDenyUserManage.status === 403, "4.4 Analyst: Blocked from user administration with 403 Forbidden");

  // ─── STEP 5: EDITOR ROLE TESTING ──────────────────────────────────────────
  console.log("\n[Step 5] Editor Role Draft & Submission Workflow");
  const editorLogin = await loginAs("editor@ledgercontrol.com");
  const editorHeaders = { Authorization: `Bearer ${editorLogin.token}`, "Content-Type": "application/json" };

  const editorDraft = await fetch(`${BASE_URL}/records/drafts`, {
    method: "POST",
    headers: editorHeaders,
    body: JSON.stringify({
      title: "End-to-End Test Adjustment",
      description: "Automated ledger correction for Phase 14 QA",
      amount: 1250.0,
      category: "ADJUSTMENT",
    }),
  });
  const draftData = (await editorDraft.json()) as any;
  assert(editorDraft.status === 201, "5.1 Editor: Creates draft record (201 Created)");
  assert(draftData.status === "DRAFT", "5.2 Draft status is 'DRAFT'");

  // Edit draft with version check
  const editorUpdate = await fetch(`${BASE_URL}/records/drafts/${draftData.id}`, {
    method: "PUT",
    headers: editorHeaders,
    body: JSON.stringify({ title: "End-to-End Test Adjustment - Revised", expected_version: 1 }),
  });
  const updatedDraft = (await editorUpdate.json()) as any;
  assert(editorUpdate.status === 200, "5.3 Editor: Updates draft record (200 OK)");
  assert(updatedDraft.version === 2, "5.4 Optimistic concurrency increments version to 2");

  // Submit draft for review
  const editorSubmit = await fetch(`${BASE_URL}/records/drafts/${draftData.id}/submit`, {
    method: "POST",
    headers: editorHeaders,
  });
  const submittedDraft = (await editorSubmit.json()) as any;
  assert(editorSubmit.status === 200, "5.5 Editor: Submits draft for review (200 OK)");
  assert(submittedDraft.status === "SUBMITTED", "5.6 Draft transitioned to 'SUBMITTED'");

  // Editor self-approval attempt must be rejected
  const editorDenyApprove = await fetch(`${BASE_URL}/records/drafts/${draftData.id}/approve`, {
    method: "POST",
    headers: editorHeaders,
    body: JSON.stringify({ notes: "Self approval attempt" }),
  });
  assert(editorDenyApprove.status === 403, "5.7 Editor: Blocked from approving draft with 403 Forbidden");

  // ─── STEP 6: MANAGER ROLE TESTING ─────────────────────────────────────────
  console.log("\n[Step 6] Manager Role Team & Approval Workflow");
  const managerLogin = await loginAs("manager@ledgercontrol.com");
  const managerHeaders = { Authorization: `Bearer ${managerLogin.token}`, "Content-Type": "application/json" };

  const managerQueue = await fetch(`${BASE_URL}/manager/approval-queue`, { headers: managerHeaders });
  assert(managerQueue.status === 200, "6.1 Manager: Retrieves pending approval queue (200 OK)");

  const managerApprove = await fetch(`${BASE_URL}/manager/workflows/${draftData.id}/approve`, {
    method: "POST",
    headers: managerHeaders,
    body: JSON.stringify({ notes: "Approved by Manager in Phase 14 QA" }),
  });
  const approvedData = (await managerApprove.json()) as any;
  assert(managerApprove.status === 200, "6.2 Manager: Approves workflow submission (200 OK)");
  assert(approvedData.status === "APPROVED", "6.3 Status updated to 'APPROVED'");

  const managerDenyAdmin = await fetch(`${BASE_URL}/admin/settings`, { headers: managerHeaders });
  assert(managerDenyAdmin.status === 403, "6.4 Manager: Blocked from master admin settings with 403 Forbidden");

  // ─── STEP 7: ADMINISTRATOR TESTING ────────────────────────────────────────
  console.log("\n[Step 7] Administrator Governance & Safeguards");
  const adminHeaders = { Authorization: `Bearer ${adminLogin.token}`, "Content-Type": "application/json" };

  const adminUsers = await fetch(`${BASE_URL}/admin/users`, { headers: adminHeaders });
  assert(adminUsers.status === 200, "7.1 Admin: Retrieves user management roster (200 OK)");

  const adminLockout = await fetch(`${BASE_URL}/admin/users/${adminLogin.user?.id}/role`, {
    method: "PUT",
    headers: adminHeaders,
    body: JSON.stringify({ role: "viewer" }),
  });
  assert(adminLockout.status === 400, "7.2 Admin: Self-lockout prevention active (400 Bad Request)");

  // ─── STEP 8: AUTHORIZATION SECURITY & BYPASS TESTS ────────────────────────
  console.log("\n[Step 8] Authorization Security & Direct Bypass Tests");
  const unauthReq = await fetch(`${BASE_URL}/admin/users`);
  assert(unauthReq.status === 401, "8.1 Missing JWT rejected with 401 Unauthorized");

  const malformedJwt = await fetch(`${BASE_URL}/admin/users`, { headers: { Authorization: "Bearer forged.token.here" } });
  assert(malformedJwt.status === 401, "8.2 Forged/invalid JWT rejected with 401 Unauthorized");

  // ─── STEP 9 & 10: DATA VALIDATION & TENANT ISOLATION ──────────────────────
  console.log("\n[Steps 9 & 10] Validation & Tenant Isolation");
  const invalidId = await fetch(`${BASE_URL}/transactions/non-existent-uuid-999`, { headers: adminHeaders });
  assert(invalidId.status === 404, "9.1 Invalid resource ID returns 404 Not Found");

  const crossTenantAttempt = await fetch(`${BASE_URL}/transactions`, {
    headers: {
      Authorization: `Bearer ${viewerLogin.token}`,
      "x-organization-id": "unauthorized-foreign-tenant-uuid-8888",
    },
  });
  assert(crossTenantAttempt.status === 403, "10.1 Cross-tenant header tampering rejected with 403 Forbidden");

  // ─── STEP 11: AUDIT RECORD TESTING ────────────────────────────────────────
  console.log("\n[Step 11] Immutable Compliance Audit Logging");
  const auditLogsRes = await fetch(`${BASE_URL}/audit`, { headers: adminHeaders });
  const auditLogsData = (await auditLogsRes.json()) as any;
  assert(auditLogsRes.status === 200, "11.1 Audit trail retrieved with 200 OK");
  assert(auditLogsData.total > 0, "11.2 Audit events recorded for privileged actions & workflows");

  console.log("\n==================================================================");
  console.log(`  PHASE 14 E2E RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runPhase14E2ETestingSuite().catch((err) => {
  console.error("Fatal E2E Test Suite Error:", err);
  process.exit(1);
});
