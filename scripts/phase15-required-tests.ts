import fs from "fs";
import path from "path";

async function runPhase15Tests() {
  console.log("==================================================================");
  console.log("  LEDGER CONTROL — PHASE 15 AUTOMATED TEST SUITE");
  console.log("==================================================================");

  let passed = 0;
  let failed = 0;

  function assert(condition: boolean, testName: string, detail?: string) {
    if (condition) {
      console.log(`  ✓ PASSED: ${testName}`);
      passed++;
    } else {
      console.error(`  ❌ FAILED: ${testName} - ${detail || "Assertion failed"}`);
      failed++;
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // CATEGORY 1: AUTHENTICATION SCENARIOS
  // ───────────────────────────────────────────────────────────────────────────
  console.log("\n[Category 1] Authentication Tests");

  // Test 1.1: Valid Login
  const loginRes = await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@ledgercontrol.com", password: "Password123!" }),
  });
  const loginData = await loginRes.json();
  assert(loginRes.status === 200 && !!loginData.access_token, "Valid Login Returns 200 & JWT Token");

  const adminToken = loginData.access_token;

  // Test 1.2: Invalid Password
  const badPassRes = await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@ledgercontrol.com", password: "WrongPassword999!" }),
  });
  assert(badPassRes.status === 401, "Invalid Password Returns 401 Unauthorized");

  // Test 1.3: Missing Credentials
  const missingCredsRes = await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  assert(missingCredsRes.status === 422 || missingCredsRes.status === 400, "Missing Credentials Returns 400/422 Error");

  // Test 1.4: Invalid Token
  const invalidTokRes = await fetch("http://localhost:8000/api/v1/audit", {
    headers: { Authorization: "Bearer invalid_garbage_token_string" },
  });
  assert(invalidTokRes.status === 401, "Invalid Token Returns 401 Unauthorized");

  // Test 1.5: Unauthorized Access (No Bearer Header)
  const noAuthRes = await fetch("http://localhost:8000/api/v1/audit");
  assert(noAuthRes.status === 401, "Unauthorized Access Returns 401 Unauthorized");


  // ───────────────────────────────────────────────────────────────────────────
  // CATEGORY 2: UPLOAD & EXTRACTION SCENARIOS
  // ───────────────────────────────────────────────────────────────────────────
  console.log("\n[Category 2] Upload & Document Extraction Tests");

  // Test 2.1: Valid PDF Upload
  const pdfForm = new FormData();
  pdfForm.append("file", new Blob([fs.readFileSync("SAMPLE/SAMPLE_BANK_STATEMENT.pdf")]), "SAMPLE_BANK_STATEMENT.pdf");
  const validPdfRes = await fetch("http://localhost:8000/api/v1/uploads/documents", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: pdfForm,
  });
  const validPdfData = await validPdfRes.json();
  assert(validPdfRes.status === 201 && validPdfData.success === true, "Valid PDF Upload Returns 201 Created & Extracted Data");

  // Test 2.2: Valid DOCX Upload
  const docxPath = path.resolve("SAMPLE/SAMPLE_COMPLIANCE_AGREEMENT.docx");
  const docxForm = new FormData();
  docxForm.append("file", new Blob([fs.readFileSync(docxPath)]), "SAMPLE_COMPLIANCE_AGREEMENT.docx");
  const validDocxRes = await fetch("http://localhost:8000/api/v1/uploads/documents", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: docxForm,
  });
  const validDocxData = await validDocxRes.json();
  assert(validDocxRes.status === 201 && validDocxData.success === true, "Valid DOCX Upload Returns 201 Created & Extracted Data");

  // Test 2.3: Unsupported File Extension (.exe)
  const exeForm = new FormData();
  exeForm.append("file", new Blob(["binary data"]), "malicious.exe");
  const exeRes = await fetch("http://localhost:8000/api/v1/uploads/documents", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: exeForm,
  });
  const exeData = await exeRes.json();
  assert(exeRes.status === 422 && exeData.error?.code === "UNSUPPORTED_FORMAT", "Unsupported .exe File Returns 422 UNSUPPORTED_FORMAT");

  // Test 2.4: Empty File (0 Bytes)
  const emptyForm = new FormData();
  emptyForm.append("file", new Blob([]), "empty.pdf");
  const emptyRes = await fetch("http://localhost:8000/api/v1/uploads/documents", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: emptyForm,
  });
  const emptyData = await emptyRes.json();
  assert(emptyRes.status === 422 && emptyData.error?.code === "EMPTY_FILE", "Empty 0-Byte File Returns 422 EMPTY_FILE");


  // ───────────────────────────────────────────────────────────────────────────
  // CATEGORY 3: RBAC ROLE PERMISSION GUARDS
  // ───────────────────────────────────────────────────────────────────────────
  console.log("\n[Category 3] RBAC Role Permission Tests");

  // Test 3.1: ADMIN Access on Restricted /audit Endpoint
  const adminAuditRes = await fetch("http://localhost:8000/api/v1/audit", {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  assert(adminAuditRes.status === 200, "ADMIN Role Allowed on Restricted /audit Endpoint (200 OK)");


  // ───────────────────────────────────────────────────────────────────────────
  // CATEGORY 4: SYSTEM HEALTH & CONNECTIVITY
  // ───────────────────────────────────────────────────────────────────────────
  console.log("\n[Category 4] System Health & Connectivity Tests");

  const healthRes = await fetch("http://localhost:8000/health");
  const healthData = await healthRes.json();
  assert(healthRes.status === 200 && healthData.database === "connected", "Backend & DB Connection Probe (200 OK)");

  const frontRes = await fetch("http://localhost:5173");
  assert(frontRes.status === 200, "Frontend Dev Server Probe (200 OK)");

  console.log("\n==================================================================");
  console.log(`  PHASE 15 TEST RESULTS: ${passed} PASSED | ${failed} FAILED`);
  console.log("==================================================================");

  if (failed > 0) {
    process.exit(1);
  }
}

runPhase15Tests().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
