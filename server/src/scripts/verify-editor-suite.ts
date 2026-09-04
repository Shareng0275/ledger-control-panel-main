const BASE_URL = "http://localhost:8000/api/v1";

async function runEditorVerificationSuite() {
  console.log("==================================================================");
  console.log("  PART 7: EDITOR ROLE SPECIFICATION & PERMISSIONS VERIFICATION");
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

  // 1. Authenticate as EDITOR & VIEWER
  console.log("\n[Test 1] Editor Authentication");
  let editorToken = "";
  let viewerToken = "";
  try {
    editorToken = await getTokenFor("editor@ledgercontrol.com");
    viewerToken = await getTokenFor("viewer@ledgercontrol.com");
    assert(Boolean(editorToken), "Editor access token received");
  } catch (err: any) {
    assert(false, "Editor Authentication", err.message);
  }

  const editorHeaders = {
    Authorization: `Bearer ${editorToken}`,
    "Content-Type": "application/json",
  };

  // 2. ALLOWED: Create Authorized Draft Record
  console.log("\n[Test 2] Allowed: Editor Creates Draft Record");
  let draftId = "";
  try {
    const createRes = await fetch(`${BASE_URL}/records/drafts`, {
      method: "POST",
      headers: editorHeaders,
      body: JSON.stringify({
        title: "Q3 Vendor Adjustment Entry",
        description: "Reclassification of gateway interchange fee under invoice #INV-9821",
        amount: 1450.75,
        category: "ADJUSTMENT",
      }),
    });
    const createData = (await createRes.json()) as any;
    draftId = createData.id;

    assert(createRes.status === 201, "Draft created with 201 Created");
    assert(createData.status === "DRAFT", "Initial status is 'DRAFT'");
    assert(createData.version === 1, "Initial version is 1");
    assert(createData.author?.email === "editor@ledgercontrol.com", "Author attribution preserved");
  } catch (err: any) {
    assert(false, "Create Draft Record", err.message);
  }

  // 3. ALLOWED: Edit & Save Draft (Ownership & Concurrency)
  console.log("\n[Test 3] Allowed: Editor Edits & Saves Draft");
  try {
    const updateRes = await fetch(`${BASE_URL}/records/drafts/${draftId}`, {
      method: "PUT",
      headers: editorHeaders,
      body: JSON.stringify({
        title: "Q3 Vendor Adjustment Entry - Revised",
        amount: 1500.00,
        expected_version: 1,
      }),
    });
    const updateData = (await updateRes.json()) as any;

    assert(updateRes.status === 200, "Draft updated successfully (200 OK)");
    assert(updateData.amount === 1500.00, "Amount modified correctly");
    assert(updateData.version === 2, "Version incremented to 2");
  } catch (err: any) {
    assert(false, "Edit Draft Record", err.message);
  }

  // 4. Concurrency Protection: Stale Version Conflict Check
  console.log("\n[Test 4] Optimistic Concurrency Conflict Rejection");
  try {
    const conflictRes = await fetch(`${BASE_URL}/records/drafts/${draftId}`, {
      method: "PUT",
      headers: editorHeaders,
      body: JSON.stringify({
        title: "Stale Edit Attempt",
        expected_version: 1, // Stale! Current version is 2
      }),
    });
    assert(conflictRes.status === 409, "Stale update rejected with 409 Conflict");
  } catch (err: any) {
    assert(false, "Concurrency Conflict", err.message);
  }

  // 5. DENIED (403): Non-Author/Unauthorized User Edit Attempt
  console.log("\n[Test 5] Denied: Non-Author Edit Attempt");
  try {
    const foreignEditRes = await fetch(`${BASE_URL}/records/drafts/${draftId}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${viewerToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title: "Tampered by Viewer" }),
    });
    assert(foreignEditRes.status === 403, "Non-author edit blocked with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Non-Author Edit Denial", err.message);
  }

  // 6. ALLOWED: Submit Draft for Review
  console.log("\n[Test 6] Allowed: Editor Submits Draft for Manager Review");
  try {
    const submitRes = await fetch(`${BASE_URL}/records/drafts/${draftId}/submit`, {
      method: "POST",
      headers: editorHeaders,
    });
    const submitData = (await submitRes.json()) as any;

    assert(submitRes.status === 200, "Draft submitted successfully (200 OK)");
    assert(submitData.status === "SUBMITTED", "Status transitioned to 'SUBMITTED'");
    assert(submitData.version === 3, "Version incremented to 3");
  } catch (err: any) {
    assert(false, "Submit Draft", err.message);
  }

  // 7. DENIED (403): Editor Cannot Self-Approve Workflow
  console.log("\n[Test 7] Denied: Editor Attempt to Self-Approve Workflow");
  try {
    const approveRes = await fetch(`${BASE_URL}/records/drafts/${draftId}/approve`, {
      method: "POST",
      headers: editorHeaders,
      body: JSON.stringify({ notes: "Editor self-approval attempt" }),
    });
    assert(approveRes.status === 403, "Editor approval attempt rejected with 403 Forbidden (requires workflow.approve)");
  } catch (err: any) {
    assert(false, "Self-Approve Denial", err.message);
  }

  // 8. DENIED (403): Editor Blocked from Admin Audit Trail
  console.log("\n[Test 8] Denied: Editor Attempt to Access Admin Audit Trail");
  try {
    const auditRes = await fetch(`${BASE_URL}/audit`, { headers: editorHeaders });
    assert(auditRes.status === 403, "Editor blocked from /audit with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Editor Audit Denial", err.message);
  }

  console.log("\n==================================================================");
  console.log(`  RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runEditorVerificationSuite().catch((err) => {
  console.error("Fatal Test Suite Error:", err);
  process.exit(1);
});
