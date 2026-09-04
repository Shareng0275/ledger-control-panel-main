const BASE_URL = "http://localhost:8000/api/v1";

async function runRbacVerificationSuite() {
  console.log("==================================================================");
  console.log("  PART 4: RBAC & PERMISSION ARCHITECTURE VERIFICATION SUITE");
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

  // 1. Unauthenticated Request
  console.log("\n[Test 1] Unauthenticated Request Rejection");
  try {
    const res = await fetch(`${BASE_URL}/transactions`);
    assert(res.status === 401, "Unauthenticated request returns 401 Unauthorized");
  } catch (err: any) {
    assert(false, "Unauthenticated Request", err.message);
  }

  // 2. Direct API Access Bypass with Malformed/Fake Token
  console.log("\n[Test 2] Direct API Bypass Attempt with Fake Token");
  try {
    const res = await fetch(`${BASE_URL}/transactions`, {
      headers: { Authorization: "Bearer forged_fake_token_attempt" },
    });
    assert(res.status === 401, "Forged token rejected with 401 Unauthorized");
  } catch (err: any) {
    assert(false, "Direct API Bypass", err.message);
  }

  // 3. Authenticated User with Allowed Permission
  console.log("\n[Test 3] Authenticated User with Allowed Permission");
  let adminToken = "";
  let viewerToken = "";
  let managerToken = "";
  try {
    adminToken = await getTokenFor("admin@ledgercontrol.com");
    viewerToken = await getTokenFor("viewer@ledgercontrol.com");
    managerToken = await getTokenFor("manager@ledgercontrol.com");

    const adminAuditRes = await fetch(`${BASE_URL}/audit`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    assert(adminAuditRes.status === 200, "Administrator can access /audit (audit.read)");

    const viewerTxRes = await fetch(`${BASE_URL}/transactions`, {
      headers: { Authorization: `Bearer ${viewerToken}` },
    });
    assert(viewerTxRes.status === 200, "Viewer can access /transactions (reconciliation.read)");
  } catch (err: any) {
    assert(false, "Allowed Permission Test", err.message);
  }

  // 4. Authenticated User WITHOUT Permission
  console.log("\n[Test 4] Authenticated User WITHOUT Permission");
  try {
    // Viewer trying to access /audit (requires role 'admin')
    const viewerAuditRes = await fetch(`${BASE_URL}/audit`, {
      headers: { Authorization: `Bearer ${viewerToken}` },
    });
    assert(viewerAuditRes.status === 403, "Viewer is blocked from /audit with 403 Forbidden");

    // Viewer trying to resolve exception (requires 'reconciliation.resolve')
    const viewerResolveRes = await fetch(`${BASE_URL}/exceptions/fake_exc_id/resolve`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${viewerToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ resolution_type: "manual_match" }),
    });
    assert(viewerResolveRes.status === 403, "Viewer is blocked from resolving exceptions with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Denied Permission Test", err.message);
  }

  // 5. Cross-Organization Tenant Isolation Violation Attempt
  console.log("\n[Test 5] Cross-Organization Tenant Tampering Attempt");
  try {
    const crossOrgRes = await fetch(`${BASE_URL}/transactions`, {
      headers: {
        Authorization: `Bearer ${viewerToken}`,
        "x-organization-id": "unauthorized-foreign-tenant-uuid-9999",
      },
    });
    assert(crossOrgRes.status === 403, "Cross-org access attempt strictly blocked with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Cross-Organization Test", err.message);
  }

  console.log("\n==================================================================");
  console.log(`  RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runRbacVerificationSuite().catch((err) => {
  console.error("Fatal Test Suite Error:", err);
  process.exit(1);
});
