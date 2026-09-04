import jwt from "jsonwebtoken";
import { config } from "../config/index.js";

const BASE_URL = "http://localhost:8000/api/v1";

async function runAuthVerificationSuite() {
  console.log("==================================================================");
  console.log("  PART 2: SECURE AUTHENTICATION VERIFICATION SUITE");
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

  // 1. Test Valid Login
  console.log("\n[Scenario 1] Valid Login");
  let validAccessToken = "";
  let validRefreshToken = "";
  try {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "admin@ledgercontrol.com", password: "Password123!" }),
    });
    const data = (await res.json()) as any;
    validAccessToken = data.access_token || data.token;
    validRefreshToken = data.refresh_token;

    assert(res.status === 200, "Valid Login returns 200 OK");
    assert(Boolean(validAccessToken), "Access token returned");
    assert(Boolean(validRefreshToken), "Refresh token returned");
    assert(data.user?.email === "admin@ledgercontrol.com", "Correct user payload returned");
    assert(data.password === undefined && data.passwordHash === undefined, "Password hash NEVER exposed");
  } catch (err: any) {
    assert(false, "Valid Login", err.message);
  }

  // 2. Test Invalid Password
  console.log("\n[Scenario 2] Invalid Password");
  try {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "admin@ledgercontrol.com", password: "WrongPassword999!" }),
    });
    const data = (await res.json()) as any;
    assert(res.status === 401, "Invalid password returns 401 Unauthorized");
    assert(!data.access_token, "No access token issued for invalid password");
  } catch (err: any) {
    assert(false, "Invalid Password", err.message);
  }

  // 3. Test Nonexistent User
  console.log("\n[Scenario 3] Nonexistent User");
  try {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "nonexistent_ghost_user@ledgercontrol.com", password: "Password123!" }),
    });
    assert(res.status === 401, "Nonexistent user returns 401 Unauthorized");
  } catch (err: any) {
    assert(false, "Nonexistent User", err.message);
  }

  // 4. Test Protected Route Access with Valid Token
  console.log("\n[Scenario 4] Protected Route Access with Valid Token");
  try {
    const res = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${validAccessToken}` },
    });
    const data = (await res.json()) as any;
    assert(res.status === 200, "/auth/me returns 200 with valid token");
    assert(data.email === "admin@ledgercontrol.com", "Identity verified");
  } catch (err: any) {
    assert(false, "Protected Route with Valid Token", err.message);
  }

  // 5. Test Missing / Invalid Token
  console.log("\n[Scenario 5] Missing & Invalid Token");
  try {
    const noTokenRes = await fetch(`${BASE_URL}/auth/me`);
    assert(noTokenRes.status === 401, "Missing token returns 401 Unauthorized");

    const badTokenRes = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: "Bearer invalid.malformed.jwt" },
    });
    assert(badTokenRes.status === 401, "Malformed token returns 401 Unauthorized");
  } catch (err: any) {
    assert(false, "Missing & Invalid Token", err.message);
  }

  // 6. Test Expired Access Token
  console.log("\n[Scenario 6] Expired Access Token");
  try {
    const expiredToken = jwt.sign(
      { userId: "fake_id", email: "test@example.com" },
      config.JWT_SECRET,
      { expiresIn: "-10s" }
    );
    const expiredRes = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${expiredToken}` },
    });
    assert(expiredRes.status === 401, "Expired token returns 401 Unauthorized");
  } catch (err: any) {
    assert(false, "Expired Token", err.message);
  }

  // 7. Test Refresh Token Rotation
  console.log("\n[Scenario 7] Refresh Token Rotation");
  let newRefreshToken = "";
  try {
    const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: validRefreshToken }),
    });
    const refreshData = (await refreshRes.json()) as any;
    newRefreshToken = refreshData.refresh_token;

    assert(refreshRes.status === 200, "Refresh returns 200 OK");
    assert(Boolean(refreshData.access_token), "New access token issued");
    assert(Boolean(newRefreshToken), "New refresh token issued");
    assert(newRefreshToken !== validRefreshToken, "Refresh token rotated (new token is distinct)");

    // Attempting to reuse old refresh token MUST fail
    const reuseRes = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: validRefreshToken }),
    });
    assert(reuseRes.status === 401, "Reusing old/revoked refresh token is strictly rejected (401)");
  } catch (err: any) {
    assert(false, "Refresh Token Rotation", err.message);
  }

  // 8. Test Logout & Revocation
  console.log("\n[Scenario 8] Logout & Revocation");
  try {
    const logoutRes = await fetch(`${BASE_URL}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: newRefreshToken }),
    });
    assert(logoutRes.status === 200, "Logout returns 200 OK");

    const refreshAfterLogout = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: newRefreshToken }),
    });
    assert(refreshAfterLogout.status === 401, "Logged-out token cannot be used to refresh (401)");
  } catch (err: any) {
    assert(false, "Logout & Revocation", err.message);
  }

  console.log("\n==================================================================");
  console.log(`  RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runAuthVerificationSuite().catch((err) => {
  console.error("Fatal Test Suite Error:", err);
  process.exit(1);
});
