const BASE_URL = "http://localhost:8000/api/v1";

async function runAdminVerificationSuite() {
  console.log("==================================================================");
  console.log("  PART 9: MASTER ADMINISTRATOR VERIFICATION SUITE");
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
    return { token: data.access_token || data.token, userId: data.user?.id };
  }

  // 1. Authenticate as ADMIN & MANAGER
  console.log("\n[Test 1] Administrator & Non-Admin Authentication");
  let adminToken = "";
  let adminUserId = "";
  let managerToken = "";
  try {
    const adminAuth = await getTokenFor("admin@ledgercontrol.com");
    adminToken = adminAuth.token;
    adminUserId = adminAuth.userId;

    const managerAuth = await getTokenFor("manager@ledgercontrol.com");
    managerToken = managerAuth.token;

    assert(Boolean(adminToken), "Admin access token received");
  } catch (err: any) {
    assert(false, "Authentication", err.message);
  }

  const adminHeaders = {
    Authorization: `Bearer ${adminToken}`,
    "Content-Type": "application/json",
  };
  const managerHeaders = {
    Authorization: `Bearer ${managerToken}`,
    "Content-Type": "application/json",
  };

  // 2. ALLOWED: List Users
  console.log("\n[Test 2] Allowed: Administrator Lists All Users");
  try {
    const listRes = await fetch(`${BASE_URL}/admin/users`, { headers: adminHeaders });
    const listData = (await listRes.json()) as any;
    assert(listRes.status === 200, "Admin can list organization users (200 OK)");
    assert(Array.isArray(listData.users), "User list array returned");
  } catch (err: any) {
    assert(false, "List Users", err.message);
  }

  // 3. ALLOWED: Provision New User
  console.log("\n[Test 3] Allowed: Administrator Provisions New User");
  let testUserId = "";
  const testEmail = `operator-${Date.now()}@ledgercontrol.com`;
  try {
    const createRes = await fetch(`${BASE_URL}/admin/users`, {
      method: "POST",
      headers: adminHeaders,
      body: JSON.stringify({
        email: testEmail,
        full_name: "Audit Test Operator",
        role: "editor",
      }),
    });
    const createData = (await createRes.json()) as any;
    testUserId = createData.id;

    assert(createRes.status === 201, "User provisioned with 201 Created");
    assert(createData.email === testEmail, "Email preserved");
    assert(createData.role === "editor", "Role assigned as 'editor'");
  } catch (err: any) {
    assert(false, "Create User", err.message);
  }

  // 4. ALLOWED: Modify User Role
  console.log("\n[Test 4] Allowed: Modify User Role & Audit");
  try {
    const roleRes = await fetch(`${BASE_URL}/admin/users/${testUserId}/role`, {
      method: "PUT",
      headers: adminHeaders,
      body: JSON.stringify({ role: "analyst" }),
    });
    const roleData = (await roleRes.json()) as any;

    assert(roleRes.status === 200, "Role updated with 200 OK");
    assert(roleData.new_role === "analyst", "Role successfully promoted to 'analyst'");
  } catch (err: any) {
    assert(false, "Modify Role", err.message);
  }

  // 5. SECURITY: Prevent Accidental Self-Lockout (Role Demotion)
  console.log("\n[Test 5] Security: Self-Lockout Prevention on Role Demotion");
  try {
    const demoteRes = await fetch(`${BASE_URL}/admin/users/${adminUserId}/role`, {
      method: "PUT",
      headers: adminHeaders,
      body: JSON.stringify({ role: "viewer" }),
    });
    assert(demoteRes.status === 400, "Admin self-demotion blocked with 400 Bad Request");
  } catch (err: any) {
    assert(false, "Self-Lockout Role Check", err.message);
  }

  // 6. SECURITY: Prevent Self-Deactivation
  console.log("\n[Test 6] Security: Self-Lockout Prevention on Account Deactivation");
  try {
    const deactRes = await fetch(`${BASE_URL}/admin/users/${adminUserId}/status`, {
      method: "PUT",
      headers: adminHeaders,
      body: JSON.stringify({ is_active: false, confirm: true }),
    });
    assert(deactRes.status === 400, "Admin self-deactivation blocked with 400 Bad Request");
  } catch (err: any) {
    assert(false, "Self-Deactivation Check", err.message);
  }

  // 7. SECURITY: Destructive Action Confirmation Requirement
  console.log("\n[Test 7] Security: Destructive Action Confirmation Enforcement");
  try {
    const unconfirmedRes = await fetch(`${BASE_URL}/admin/users/${testUserId}/status`, {
      method: "PUT",
      headers: adminHeaders,
      body: JSON.stringify({ is_active: false }), // Missing confirm: true
    });
    assert(unconfirmedRes.status === 422, "Unconfirmed deactivation rejected with 422 Unprocessable");

    // Confirmed deactivation
    const confirmedRes = await fetch(`${BASE_URL}/admin/users/${testUserId}/status`, {
      method: "PUT",
      headers: adminHeaders,
      body: JSON.stringify({ is_active: false, confirm: true }),
    });
    const statusData = (await confirmedRes.json()) as any;
    assert(confirmedRes.status === 200, "Confirmed deactivation succeeded with 200 OK");
    assert(statusData.is_active === false, "User is_active updated to false");
  } catch (err: any) {
    assert(false, "Destructive Confirmation Check", err.message);
  }

  // 8. ALLOWED: Permission Matrix & Security Metrics
  console.log("\n[Test 8] Allowed: Permission Matrix & Security Dashboard Metrics");
  try {
    const permRes = await fetch(`${BASE_URL}/admin/permissions`, { headers: adminHeaders });
    const permData = (await permRes.json()) as any;
    assert(permRes.status === 200, "Admin can inspect permission matrix");
    assert(Boolean(permData.matrix?.admin), "Admin role mapping present");

    const secRes = await fetch(`${BASE_URL}/admin/security/metrics`, { headers: adminHeaders });
    const secData = (await secRes.json()) as any;
    assert(secRes.status === 200, "Admin can view security dashboard metrics");
    assert(typeof secData.total_users === "number", "User count returned in metrics");
  } catch (err: any) {
    assert(false, "Permissions & Metrics", err.message);
  }

  // 9. ALLOWED: System Settings
  console.log("\n[Test 9] Allowed: System Settings Inspection & Update");
  try {
    const settingsRes = await fetch(`${BASE_URL}/admin/settings`, { headers: adminHeaders });
    const settingsData = (await settingsRes.json()) as any;
    assert(settingsRes.status === 200, "Admin can inspect organization settings");
    assert(settingsData.data_isolation === "ROW_LEVEL_ORGANIZATION", "Tenant isolation verified");
  } catch (err: any) {
    assert(false, "Settings Inspection", err.message);
  }

  // 10. ALLOWED: Full Audit Log Inspection
  console.log("\n[Test 10] Allowed: Full Compliance Audit Log Inspection");
  try {
    const auditRes = await fetch(`${BASE_URL}/audit`, { headers: adminHeaders });
    const auditData = (await auditRes.json()) as any;
    assert(auditRes.status === 200, "Admin can query full audit log trail");
    assert(Array.isArray(auditData.items), "Audit logs array returned");
    assert(auditData.total > 0, "Audit trail contains recorded events");
  } catch (err: any) {
    assert(false, "Audit Log Inspection", err.message);
  }

  // 11. DENIED (403): Non-Admin Blocked from /admin/*
  console.log("\n[Test 11] Denied: Non-Admin Access to /admin/* Rejection");
  try {
    const nonAdminRes = await fetch(`${BASE_URL}/admin/users`, { headers: managerHeaders });
    assert(nonAdminRes.status === 403, "Non-admin blocked from /admin/users with 403 Forbidden");

    const nonAdminAudit = await fetch(`${BASE_URL}/audit`, { headers: managerHeaders });
    assert(nonAdminAudit.status === 403, "Non-admin blocked from /audit with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Non-Admin Denial Check", err.message);
  }

  console.log("\n==================================================================");
  console.log(`  RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runAdminVerificationSuite().catch((err) => {
  console.error("Fatal Test Suite Error:", err);
  process.exit(1);
});
