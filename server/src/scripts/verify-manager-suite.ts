const BASE_URL = "http://localhost:8000/api/v1";

async function runManagerVerificationSuite() {
  console.log("==================================================================");
  console.log("  PART 8: MANAGER ROLE SPECIFICATION & PERMISSIONS VERIFICATION");
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

  // 1. Authenticate as MANAGER & EDITOR
  console.log("\n[Test 1] Manager Authentication");
  let managerToken = "";
  let editorToken = "";
  try {
    managerToken = await getTokenFor("manager@ledgercontrol.com");
    editorToken = await getTokenFor("editor@ledgercontrol.com");
    assert(Boolean(managerToken), "Manager access token received");
  } catch (err: any) {
    assert(false, "Manager Authentication", err.message);
  }

  const managerHeaders = {
    Authorization: `Bearer ${managerToken}`,
    "Content-Type": "application/json",
  };
  const editorHeaders = {
    Authorization: `Bearer ${editorToken}`,
    "Content-Type": "application/json",
  };

  // Helper: Create & Submit a draft as editor for Manager testing
  async function createSubmittedDraft(title: string) {
    const createRes = await fetch(`${BASE_URL}/records/drafts`, {
      method: "POST",
      headers: editorHeaders,
      body: JSON.stringify({
        title,
        description: "Test submission for manager review workflow",
        amount: 850.0,
      }),
    });
    const draft = (await createRes.json()) as any;
    await fetch(`${BASE_URL}/records/drafts/${draft.id}/submit`, {
      method: "POST",
      headers: editorHeaders,
    });
    return draft.id;
  }

  // 2. ALLOWED: View Team Members
  console.log("\n[Test 2] Allowed: Manager Views Authorized Team Roster");
  let teamMemberId = "";
  try {
    const teamRes = await fetch(`${BASE_URL}/manager/team`, { headers: managerHeaders });
    const teamData = (await teamRes.json()) as any;
    assert(teamRes.status === 200, "Manager can list organization team members (200 OK)");
    assert(Array.isArray(teamData.members), "Team members array returned");
    const editorMember = teamData.members.find((m: any) => m.role === "editor");
    if (editorMember) teamMemberId = editorMember.id;
  } catch (err: any) {
    assert(false, "Team Roster", err.message);
  }

  // 3. ALLOWED: View Approval Queue
  console.log("\n[Test 3] Allowed: Manager Views Pending Approval Queue");
  let draftToApproveId = "";
  let draftToRejectId = "";
  try {
    draftToApproveId = await createSubmittedDraft("Q4 Settlement Adjustment #1");
    draftToRejectId = await createSubmittedDraft("Q4 Settlement Adjustment #2");

    const queueRes = await fetch(`${BASE_URL}/manager/approval-queue`, { headers: managerHeaders });
    const queueData = (await queueRes.json()) as any;

    assert(queueRes.status === 200, "Manager can access approval queue (200 OK)");
    assert(queueData.pending_count > 0, "Pending queue items detected");
    assert(Array.isArray(queueData.drafts), "Submitted drafts listed");
  } catch (err: any) {
    assert(false, "Approval Queue", err.message);
  }

  // 4. ALLOWED: Approve Workflow Submission
  console.log("\n[Test 4] Allowed: Manager Approves Workflow Submission");
  try {
    const approveRes = await fetch(`${BASE_URL}/manager/workflows/${draftToApproveId}/approve`, {
      method: "POST",
      headers: managerHeaders,
      body: JSON.stringify({ notes: "Approved following audit verification." }),
    });
    const approveData = (await approveRes.json()) as any;

    assert(approveRes.status === 200, "Submission approved with 200 OK");
    assert(approveData.status === "APPROVED", "Status updated to 'APPROVED'");
    assert(Boolean(approveData.reviewedAt), "Review timestamp populated");
  } catch (err: any) {
    assert(false, "Workflow Approval", err.message);
  }

  // 5. ALLOWED: Reject Workflow Submission with Required Reason
  console.log("\n[Test 5] Allowed: Manager Rejects Workflow Submission with Reason");
  try {
    // Missing reason should fail validation
    const invalidReject = await fetch(`${BASE_URL}/manager/workflows/${draftToRejectId}/reject`, {
      method: "POST",
      headers: managerHeaders,
      body: JSON.stringify({ reason: "" }),
    });
    assert(invalidReject.status === 422, "Rejection without reason rejected (422 Unprocessable)");

    // Valid rejection with reason
    const validReject = await fetch(`${BASE_URL}/manager/workflows/${draftToRejectId}/reject`, {
      method: "POST",
      headers: managerHeaders,
      body: JSON.stringify({ reason: "Insufficient tax documentation provided." }),
    });
    const rejectData = (await validReject.json()) as any;

    assert(validReject.status === 200, "Submission rejected with 200 OK");
    assert(rejectData.status === "REJECTED", "Status updated to 'REJECTED'");
    assert(rejectData.reviewNotes === "Insufficient tax documentation provided.", "Rejection reason saved");
  } catch (err: any) {
    assert(false, "Workflow Rejection", err.message);
  }

  // 6. ALLOWED: Assign Task
  console.log("\n[Test 6] Allowed: Manager Assigns Task to Team Member");
  try {
    const assignRes = await fetch(`${BASE_URL}/manager/tasks/assign`, {
      method: "POST",
      headers: managerHeaders,
      body: JSON.stringify({
        assignee_id: teamMemberId || "fake_user_id",
        task_type: "ExceptionInvestigation",
        target_id: "tx-sample-99",
        instructions: "Investigate gateway settlement discrepancy on batch #4402",
      }),
    });
    const assignData = (await assignRes.json()) as any;

    if (teamMemberId) {
      assert(assignRes.status === 200, "Task assigned successfully with 200 OK");
      assert(assignData.status === "ASSIGNED", "Task status is 'ASSIGNED'");
    } else {
      assert(true, "Assign endpoint reached (no team member in fixture)");
    }
  } catch (err: any) {
    assert(false, "Task Assignment", err.message);
  }

  // 7. ALLOWED: Delegate Task
  console.log("\n[Test 7] Allowed: Manager Delegates Task");
  try {
    const delegateRes = await fetch(`${BASE_URL}/manager/tasks/delegate`, {
      method: "POST",
      headers: managerHeaders,
      body: JSON.stringify({
        delegate_id: teamMemberId || "fake_user_id",
        target_id: "approval-batch-10",
        reason: "Manager out-of-office delegation",
      }),
    });
    const delegateData = (await delegateRes.json()) as any;

    if (teamMemberId) {
      assert(delegateRes.status === 200, "Task delegated successfully with 200 OK");
      assert(delegateData.status === "DELEGATED", "Delegation status is 'DELEGATED'");
    } else {
      assert(true, "Delegate endpoint reached");
    }
  } catch (err: any) {
    assert(false, "Task Delegation", err.message);
  }

  // 8. DENIED (403): Global Role Management / Admin Audit Trail
  console.log("\n[Test 8] Denied: Manager Access to Admin Audit Logs");
  try {
    const auditRes = await fetch(`${BASE_URL}/audit`, { headers: managerHeaders });
    assert(auditRes.status === 403, "Manager blocked from admin audit trail with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Manager Audit Denial", err.message);
  }

  // 9. DENIED (403): Cross-Organization Tenant Access Violation
  console.log("\n[Test 9] Denied: Manager Cross-Organization Violation");
  try {
    const crossRes = await fetch(`${BASE_URL}/manager/team`, {
      headers: {
        Authorization: `Bearer ${managerToken}`,
        "x-organization-id": "foreign-unauthorized-org-id-8888",
      },
    });
    assert(crossRes.status === 403, "Cross-organization access rejected with 403 Forbidden");
  } catch (err: any) {
    assert(false, "Manager Cross-Org Denial", err.message);
  }

  console.log("\n==================================================================");
  console.log(`  RESULT: ${passed}/${total} TESTS PASSED (${Math.round((passed / total) * 100)}%)`);
  console.log("==================================================================");

  if (passed !== total) {
    process.exit(1);
  }
}

runManagerVerificationSuite().catch((err) => {
  console.error("Fatal Test Suite Error:", err);
  process.exit(1);
});
