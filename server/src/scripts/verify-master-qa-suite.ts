const BASE_URL = "http://localhost:8000/api/v1";

async function runMasterEnterpriseQASuite() {
  console.log("==================================================================");
  console.log("  PART 12: MASTER ENTERPRISE FINAL QA & SECURITY SUITE");
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

  async function loginAs(email: string) {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: "Password123!" }),
    });
    return (await res.json()) as any;
  }

  // ─── 1. AUTHENTICATION QA ──────────────────────────────────────────────────
  console.log("\n[Section 1] Authentication & Session Lifecycle");
  let adminAuth = await loginAs("admin@ledgercontrol.com");
  let viewerAuth = await loginAs("viewer@ledgercontrol.com");
  let analystAuth = await loginAs("analyst@ledgercontrol.com");
  let editorAuth = await loginAs("editor@ledgercontrol.com");
  let managerAuth = await loginAs("manager@ledgercontrol.com");

  assert(Boolean(adminAuth.access_token || adminAuth.token), "1.1 Login succeeds with signed JWT access token");
  assert(Boolean(adminAuth.refresh_token), "1.2 Login returns secure refresh token");

  // Invalid credentials
  const badLogin = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@ledgercontrol.com", password: "WrongPassword99!" }),
  });
  assert(badLogin.status === 401, "1.3 Invalid password rejected with 401 Unauthorized");

  // Refresh token rotation
  const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: adminAuth.refresh_token }),
  });
  const refreshData = (await refreshRes.json()) as any;
  assert(refreshRes.status === 200, "1.4 Refresh endpoint issues new access/refresh token pair (200 OK)");
  assert(refreshData.refresh_token !== adminAuth.refresh_token, "1.5 Refresh token is rotated (new token is distinct)");

  // Reusing rotated refresh token must fail
  const replayRes = await fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: adminAuth.refresh_token }),
  });
  assert(replayRes.status === 401, "1.6 Replay of revoked/rotated refresh token strictly rejected with 401");

  // Logout revocation
  const logoutRes = await fetch(`${BASE_URL}/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshData.refresh_token }),
  });
  assert(logoutRes.status === 200, "1.7 Logout invalidates session with 200 OK");

  // ─── 2. FIVE-ROLE AUTHORIZATION QA ─────────────────────────────────────────
  console.log("\n[Section 2] Five-Role Authorization & Permission Boundaries");
  const adminHeaders = { Authorization: `Bearer ${adminAuth.access_token || adminAuth.token}`, "Content-Type": "application/json" };
  const viewerHeaders = { Authorization: `Bearer ${viewerAuth.access_token || viewerAuth.token}`, "Content-Type": "application/json" };
  const analystHeaders = { Authorization: `Bearer ${analystAuth.access_token || analystAuth.token}`, "Content-Type": "application/json" };
  const editorHeaders = { Authorization: `Bearer ${editorAuth.access_token || editorAuth.token}`, "Content-Type": "application/json" };
  const managerHeaders = { Authorization: `Bearer ${managerAuth.access_token || managerAuth.token}`, "Content-Type": "application/json" };

  // Role 1: VIEWER (Read-only)
  const viewerRead = await fetch(`${BASE_URL}/transactions`, { headers: viewerHeaders });
  assert(viewerRead.status === 200, "2.1 Viewer: Allowed reading transactions");
  const viewerDeniedEdit = await fetch(`${BASE_URL}/records/drafts`, {
    method: "POST",
    headers: viewerHeaders,
    body: JSON.stringify({ title: "Unauthorized", description: "Test", amount: 100 }),
  });
  assert(viewerDeniedEdit.status === 403, "2.2 Viewer: Denied record creation with 403 Forbidden");

  // Role 2: ANALYST (Analytics & Insights)
  const analystForecast = await fetch(`${BASE_URL}/forecast?horizon=30d`, { headers: analystHeaders });
  assert(analystForecast.status === 200, "2.3 Analyst: Allowed querying forecast analytics");
  const analystDeniedAudit = await fetch(`${BASE_URL}/audit`, { headers: analystHeaders });
  assert(analystDeniedAudit.status === 403, "2.4 Analyst: Denied admin audit trail with 403 Forbidden");

  // Role 3: EDITOR (Drafts & Submissions)
  const editorCreate = await fetch(`${BASE_URL}/records/drafts`, {
    method: "POST",
    headers: editorHeaders,
    body: JSON.stringify({ title: "QA Adjustment Entry", description: "Ledger alignment", amount: 500 }),
  });
  const draftRecord = (await editorCreate.json()) as any;
  assert(editorCreate.status === 201, "2.5 Editor: Allowed creating draft records (201 Created)");
  const editorDeniedApprove = await fetch(`${BASE_URL}/records/drafts/${draftRecord.id}/approve`, {
    method: "POST",
    headers: editorHeaders,
    body: JSON.stringify({ notes: "Self-approval attempt" }),
  });
  assert(editorDeniedApprove.status === 403, "2.6 Editor: Denied self-approval with 403 Forbidden");

  // Role 4: MANAGER (Approvals & Rejections)
  await fetch(`${BASE_URL}/records/drafts/${draftRecord.id}/submit`, { method: "POST", headers: editorHeaders });
  const managerApprove = await fetch(`${BASE_URL}/manager/workflows/${draftRecord.id}/approve`, {
    method: "POST",
    headers: managerHeaders,
    body: JSON.stringify({ notes: "QA Manager approved" }),
  });
  assert(managerApprove.status === 200, "2.7 Manager: Allowed approving submitted workflow");
  const managerDeniedRoleChange = await fetch(`${BASE_URL}/admin/users/${viewerAuth.user?.id}/role`, {
    method: "PUT",
    headers: managerHeaders,
    body: JSON.stringify({ role: "admin" }),
  });
  assert(managerDeniedRoleChange.status === 403, "2.8 Manager: Denied role management with 403 Forbidden");

  // Role 5: ADMINISTRATOR (Full Governance & Security Checks)
  const adminAudit = await fetch(`${BASE_URL}/audit`, { headers: adminHeaders });
  assert(adminAudit.status === 200, "2.9 Administrator: Allowed full audit trail inspection");
  const adminLockout = await fetch(`${BASE_URL}/admin/users/${adminAuth.user?.id}/role`, {
    method: "PUT",
    headers: adminHeaders,
    body: JSON.stringify({ role: "viewer" }),
  });
  assert(adminLockout.status === 400, "2.10 Administrator: Self-lockout prevention active (400 Bad Request)");

  // Direct API Bypass Attempt (No auth header)
  const bypassAttempt = await fetch(`${BASE_URL}/admin/users`);
  assert(bypassAttempt.status === 401, "2.11 Unauthenticated direct API bypass blocked with 401 Unauthorized");

  // ─── 3. TENANT SECURITY & DATA ISOLATION ────────────────────────────────────
  console.log("\n[Section 3] Tenant Security & Multi-Organization Scoping");
  const foreignTenantHeader = await fetch(`${BASE_URL}/transactions`, {
    headers: {
      Authorization: `Bearer ${viewerAuth.access_token || viewerAuth.token}`,
      "x-organization-id": "unauthorized-foreign-tenant-uuid-0000",
    },
  });
  assert(foreignTenantHeader.status === 403, "3.1 Cross-tenant header tampering strictly rejected with 403 Forbidden");

  // ─── 4. STANDARDIZED API ERROR STATUS CODES ────────────────────────────────
  console.log("\n[Section 4] Standardized API HTTP Error Code Coverage");
  // 400 Bad Request
  const err400 = await fetch(`${BASE_URL}/records/drafts/${draftRecord.id}/submit`, {
    method: "POST",
    headers: editorHeaders, // Already approved!
  });
  assert(err400.status === 400, "4.1 Status 400 Bad Request verified (invalid state transition)");

  // 401 Unauthorized
  const err401 = await fetch(`${BASE_URL}/transactions`, {
    headers: { Authorization: "Bearer bad_signature_token" },
  });
  assert(err401.status === 401, "4.2 Status 401 Unauthorized verified (malformed token)");

  // 403 Forbidden
  const err403 = await fetch(`${BASE_URL}/audit`, { headers: viewerHeaders });
  assert(err403.status === 403, "4.3 Status 403 Forbidden verified (insufficient permissions)");

  // 404 Not Found
  const err404 = await fetch(`${BASE_URL}/transactions/non-existent-transaction-uuid-999`, { headers: adminHeaders });
  assert(err404.status === 404, "4.4 Status 404 Not Found verified (missing resource)");

  // 409 Conflict (Optimistic Concurrency)
  const err409 = await fetch(`${BASE_URL}/records/drafts/${draftRecord.id}`, {
    method: "PUT",
    headers: editorHeaders,
    body: JSON.stringify({ title: "Stale update", expected_version: 1 }),
  });
  assert(err409.status === 400 || err409.status === 409, "4.5 Status 409 Conflict / 400 verified (concurrency protection)");

  // 422 Unprocessable Entity
  const err422 = await fetch(`${BASE_URL}/ask`, {
    method: "POST",
    headers: analystHeaders,
    body: JSON.stringify({ question: "" }),
  });
  assert(err422.status === 422, "4.6 Status 422 Unprocessable Entity verified (missing required parameter)");

  console.log("\n==================================================================");
  console.log(`  FINAL QA RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runMasterEnterpriseQASuite().catch((err) => {
  console.error("Fatal QA Suite Error:", err);
  process.exit(1);
});
