import {
  Scale,
  AlertTriangle,
  TrendingUp,
  MessageSquareText,
  ClipboardList,
  ShieldCheck,
  Sparkles,
  Lock,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import type { RoleGuideConfig, RoleRule, RoleType } from "./guideTypes";

export function normalizeRole(role?: string): RoleType {
  const r = (role || "").toLowerCase().trim();
  if (r === "admin" || r === "administrator") return "admin";
  if (r === "editor") return "editor";
  if (r === "manager" || r === "analyst") return "editor";
  return "viewer";
}

export const ROLE_RULES_CATALOG: Record<RoleType, RoleRule[]> = {
  admin: [
    {
      id: "rule_adm_1",
      category: "reconciliation",
      ruleCode: "RULE-REC-01",
      title: "Reconciliation Engine Execution",
      description: "Full authority to ingest dual streams (Bank & Gateway) and trigger automated matching algorithms.",
      isAllowed: true,
      permissionKey: "reconciliation.execute",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_adm_2",
      category: "exceptions",
      ruleCode: "RULE-EXC-01",
      title: "Discrepancy Resolution & Bulk Overrides",
      description: "Authorized to accept fuzzy matches, reject breaks, and execute administrative bulk reconciliation overrides.",
      isAllowed: true,
      permissionKey: "reconciliation.resolve",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_adm_3",
      category: "governance",
      ruleCode: "RULE-USR-01",
      title: "User Provisioning & Tenant Administration",
      description: "Full access to create, deactivate, and manage tenant members, authentication settings, and credentials.",
      isAllowed: true,
      permissionKey: "users.manage",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_adm_4",
      category: "governance",
      ruleCode: "RULE-ROL-01",
      title: "RBAC Role Assignment & Privilege Elevation",
      description: "Authorized to assign user roles (Admin, Editor, Viewer) and define organization access tiers.",
      isAllowed: true,
      permissionKey: "roles.manage",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_adm_5",
      category: "audit",
      ruleCode: "RULE-AUD-01",
      title: "Immutable Audit Ledger & Forensic Inspection",
      description: "Unrestricted access to cryptographic audit trails, operator fingerprints, and SOC-2 compliance exports.",
      isAllowed: true,
      permissionKey: "audit.read",
      enforcementLevel: "audited",
    },
  ],
  editor: [
    {
      id: "rule_edt_1",
      category: "reconciliation",
      ruleCode: "RULE-REC-01",
      title: "Reconciliation Ingestion & Execution",
      description: "Authorized to upload bank statements, internal gateway settlement CSVs, and trigger matching runs.",
      isAllowed: true,
      permissionKey: "reconciliation.execute",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_edt_2",
      category: "exceptions",
      ruleCode: "RULE-EXC-02",
      title: "Discrepancy Triage & Resolution Notes",
      description: "Permitted to resolve individual exception breaks with mandatory explanatory justification notes.",
      isAllowed: true,
      permissionKey: "reconciliation.resolve",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_edt_3",
      category: "forecast",
      ruleCode: "RULE-FC-01",
      title: "Cash Forecasting & Model Evaluation",
      description: "Full access to evaluate 7d/30d/90d cash trajectories and execute predictive runway calculations.",
      isAllowed: true,
      permissionKey: "analytics.read",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_edt_4",
      category: "governance",
      ruleCode: "RULE-SEC-01",
      title: "User Management & Role Elevation Prohibited",
      description: "Restricted: Editors cannot create new users, reassign roles, or alter organizational security boundaries.",
      isAllowed: false,
      permissionKey: "users.manage",
      enforcementLevel: "restricted",
    },
    {
      id: "rule_edt_5",
      category: "governance",
      ruleCode: "RULE-SEC-02",
      title: "Global System Settings Prohibited",
      description: "Restricted: Editors cannot modify system-wide reconciliation matching tolerances or API keys.",
      isAllowed: false,
      permissionKey: "settings.manage",
      enforcementLevel: "restricted",
    },
  ],
  viewer: [
    {
      id: "rule_viw_1",
      category: "reconciliation",
      ruleCode: "RULE-OBS-01",
      title: "Read-Only Reconciliation Monitoring",
      description: "Authorized to view match rates, confidence distributions, and export reconciled transaction logs.",
      isAllowed: true,
      permissionKey: "reconciliation.read",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_viw_2",
      category: "exceptions",
      ruleCode: "RULE-OBS-02",
      title: "Discrepancy Queue & AI Diagnostic Review",
      description: "Permitted to inspect breaks, side-by-side statement records, and AI root cause explanations.",
      isAllowed: true,
      permissionKey: "records.read",
      enforcementLevel: "enforced",
    },
    {
      id: "rule_viw_3",
      category: "reconciliation",
      ruleCode: "RULE-RES-01",
      title: "Reconciliation Execution Restricted",
      description: "Restricted: Viewers cannot trigger reconciliation runs or upload new statement/settlement files.",
      isAllowed: false,
      permissionKey: "reconciliation.execute",
      enforcementLevel: "restricted",
    },
    {
      id: "rule_viw_4",
      category: "exceptions",
      ruleCode: "RULE-RES-02",
      title: "Discrepancy Resolution Prohibited",
      description: "Restricted: Viewers cannot accept matches, override breaks, or resolve ledger exceptions.",
      isAllowed: false,
      permissionKey: "reconciliation.resolve",
      enforcementLevel: "restricted",
    },
    {
      id: "rule_viw_5",
      category: "governance",
      ruleCode: "RULE-RES-03",
      title: "System Administration Restricted",
      description: "Restricted: Viewers have no access to tenant administration, user configuration, or role modification.",
      isAllowed: false,
      permissionKey: "users.manage",
      enforcementLevel: "restricted",
    },
  ],
  manager: [],
  analyst: [],
};

// Map manager and analyst to editor rules
ROLE_RULES_CATALOG.manager = ROLE_RULES_CATALOG.editor;
ROLE_RULES_CATALOG.analyst = ROLE_RULES_CATALOG.editor;

export const ROLE_CONFIGS: Record<RoleType, RoleGuideConfig> = {
  admin: {
    role: "admin",
    displayName: "Administrator",
    tagline: "Full Platform Authority & Regulatory Governance",
    description:
      "As an Administrator, you possess unrestricted authority across reconciliation engines, manual override queues, predictive models, tenant security, and immutable audit logs.",
    badgeColor: "bg-purple-950/60 border-purple-500/40 text-purple-300",
    rules: ROLE_RULES_CATALOG.admin,
    steps: [
      {
        id: "admin-welcome",
        route: "/",
        title: "Administrator Command Center",
        badge: "Overview · Step 1 of 7",
        Icon: Sparkles,
        description:
          "Welcome to the Ledger Control Platform. As an Administrator, you maintain full operational and supervisory authority over financial data pipelines, reconciliation runs, and access controls.",
        bulletPoints: [
          "Supervisory oversight over dual-stream bank and gateway ingestion pipelines",
          "Authority to configure match thresholds, tolerances, and multi-tenant parameters",
          "Direct access to cryptographic audit streams and compliance verification",
        ],
        roleHighlight: "Role: ADMINISTRATOR — Unrestricted operational & governance rights.",
      },
      {
        id: "admin-reconcile",
        route: "/",
        title: "Reconciliation Terminal & Engine Control",
        badge: "Ingestion · Step 2 of 7",
        Icon: Scale,
        description:
          "Execute automated dual-stream matching between cash bank statements and gateway settlements. Configure confidence tolerances and inspect real-time match rates.",
        bulletPoints: [
          "Stream 01: Bank Statement (Cash Position) ingestion with automatic date/amount normalization",
          "Stream 02: Gateway Ledger (Settlement Records) with merchant fee and payout tracking",
          "Trigger two-pass matching engine (deterministic exact + AI-scored fuzzy thresholding)",
        ],
        roleHighlight: "Permission `reconciliation.execute`: ENABLED. You can initiate runs and re-run pipelines.",
      },
      {
        id: "admin-exceptions",
        route: "/exceptions",
        title: "Master Discrepancy Queue & Bulk Overrides",
        badge: "Triage · Step 3 of 7",
        Icon: AlertTriangle,
        description:
          "Manage breaks and isolated variances. Administrators have exclusive authority to execute bulk overrides, re-assign breaks, or force-match complex multi-fee settlements.",
        bulletPoints: [
          "Inspect side-by-side statement vs. candidate gateway records with confidence scores",
          "Review automated AI root-cause diagnostics detailing fee deductions or timing lags",
          "Execute individual resolutions or bulk approvals with immutable operator signatures",
        ],
        roleHighlight: "Permission `reconciliation.resolve`: ENABLED. Full override and resolution authority.",
      },
      {
        id: "admin-forecast",
        route: "/forecast",
        title: "Predictive Cash Runway & Model Controls",
        badge: "Analytics · Step 4 of 7",
        Icon: TrendingUp,
        description:
          "Evaluate 7-day, 30-day, and 90-day forward cash trajectory simulations derived directly from verified ledger settlements.",
        bulletPoints: [
          "Analyze settled daily run-rates against statistical confidence bands (95% CI)",
          "Inspect daily burn rate estimates and cash runway reserve projections",
          "Cross-reference corporate cash flows against macro market time-series baselines",
        ],
        roleHighlight: "Permission `analytics.read` & `analytics.export`: ENABLED. Export projection datasets.",
      },
      {
        id: "admin-ask",
        route: "/ask",
        title: "Financial AI Copilot (Admin Mode)",
        badge: "AI Copilot · Step 5 of 7",
        Icon: MessageSquareText,
        description:
          "Query enterprise financial data in natural language. The AI assistant constructs grounded answers strictly from active database tables without hallucination.",
        bulletPoints: [
          "Ask complex questions: 'What is our current cash position?' or 'Show Stripe breaks > $500'",
          "View interactive supporting transaction tables alongside explanatory answers",
          "Direct traceability back to raw database IDs and ingestion batch numbers",
        ],
        roleHighlight: "Grounded Query Engine: Unrestricted tenant data querying and deep variance forensics.",
      },
      {
        id: "admin-audit",
        route: "/audit",
        title: "Cryptographic Audit Ledger & Governance",
        badge: "Compliance · Step 6 of 7",
        Icon: ClipboardList,
        description:
          "Inspect immutable audit records capturing every reconciliation run, break resolution, document upload, and user modification.",
        bulletPoints: [
          "Append-only event stream with microsecond timestamps and operator fingerprints",
          "Inspect raw event JSON payloads for forensic auditing and SOC-2 / regulatory review",
          "Filter by specific reconciliation run IDs or global organization tenant history",
        ],
        roleHighlight: "Permission `audit.read`: ENABLED. Full forensic audit visibility.",
      },
      {
        id: "admin-rules",
        route: "/",
        title: "Administrator Rules & Permissions Matrix",
        badge: "Rule Matrix · Step 7 of 7",
        Icon: ShieldCheck,
        description:
          "Summary of all applicable operational rules, security policies, and permission keys enforced for the Administrator role.",
        bulletPoints: [
          "RULE-REC-01: Authority to execute reconciliation and ingest multi-stream datasets",
          "RULE-EXC-01: Authority to resolve breaks and execute bulk manual overrides",
          "RULE-USR-01 & ROL-01: Full user management and role assignment authority",
          "RULE-AUD-01: Mandatory immutable cryptographic logging of all state mutations",
        ],
        roleHighlight: "Security Status: All permission gates unlocked. Operations audited in real time.",
      },
    ],
  },
  editor: {
    role: "editor",
    displayName: "Operational Editor",
    tagline: "Operational Reconciliation & Break Remediation",
    description:
      "As an Editor, you are authorized to ingest statement datasets, execute matching runs, investigate discrepancies, and submit break resolution notes.",
    badgeColor: "bg-blue-950/60 border-blue-500/40 text-blue-300",
    rules: ROLE_RULES_CATALOG.editor,
    steps: [
      {
        id: "editor-welcome",
        route: "/",
        title: "Operational Workspace",
        badge: "Overview · Step 1 of 6",
        Icon: Sparkles,
        description:
          "Welcome to Ledger Control. As an Operational Editor, your role focuses on running daily reconciliation passes, investigating breaks, and ensuring cash-to-ledger parity.",
        bulletPoints: [
          "Dual-stream ingestion for bank statements and gateway settlement CSVs",
          "Direct access to the exception queue for discrepancy triage and resolution",
          "Predictive cash forecasting and natural language financial inquiries",
        ],
        roleHighlight: "Role: OPERATIONAL EDITOR — Authorized for ingestion, execution, and triage.",
      },
      {
        id: "editor-reconcile",
        route: "/",
        title: "Dual-Stream Ingestion & Matching Engine",
        badge: "Ingestion · Step 2 of 6",
        Icon: Scale,
        description:
          "Upload daily bank statements (Stream 01) and gateway settlement reports (Stream 02) to execute matching passes.",
        bulletPoints: [
          "Drag-and-drop CSV uploads for rapid ingestion",
          "Automated fuzzy matching against internal settlement records",
          "Inspect matched pairs and confidence scores in real time",
        ],
        roleHighlight: "Permission `reconciliation.execute`: ENABLED. You can execute daily runs.",
      },
      {
        id: "editor-exceptions",
        route: "/exceptions",
        title: "Discrepancy Triage & Resolution Notes",
        badge: "Resolution · Step 3 of 6",
        Icon: AlertTriangle,
        description:
          "Review transactions where amounts, dates, or reference numbers deviate. Submit resolution decisions with explanatory audit notes.",
        bulletPoints: [
          "Inspect variance breakdowns (timing lags, processing fee deductions, split payouts)",
          "Mark discrepancies as resolved with mandatory operator notes",
          "Automatic escalation of high-value breaks to the compliance queue",
        ],
        roleHighlight: "Permission `reconciliation.resolve`: ENABLED. Manual resolution with audit trail.",
      },
      {
        id: "editor-forecast",
        route: "/forecast",
        title: "Cash Trajectory & Operational Liquidity",
        badge: "Forecasting · Step 4 of 6",
        Icon: TrendingUp,
        description:
          "Monitor expected cash inflows and outflows based on historical settlement velocity across connected gateways.",
        bulletPoints: [
          "View 7d, 30d, and 90d forward projection trajectories",
          "Analyze burn rate and runway reserve estimates",
          "Identify days with expected settlement delays or seasonal dips",
        ],
        roleHighlight: "Permission `analytics.read`: ENABLED. Full access to predictive metrics.",
      },
      {
        id: "editor-ask",
        route: "/ask",
        title: "Financial AI Copilot Assistant",
        badge: "AI Copilot · Step 5 of 6",
        Icon: MessageSquareText,
        description:
          "Ask questions regarding settlement trends, unreconciled volumes, and merchant performance in natural language.",
        bulletPoints: [
          "Grounded answers backed by database transaction queries",
          "Instant breakdown of fee discrepancies and gateway variance",
          "Export supporting data directly for operational reporting",
        ],
        roleHighlight: "Assistant ready: Natural language queries grounded in tenant data.",
      },
      {
        id: "editor-rules",
        route: "/",
        title: "Editor Rules & Security Guardrails",
        badge: "Rule Matrix · Step 6 of 6",
        Icon: ShieldCheck,
        description:
          "Summary of operational permissions and security guardrails enforced for the Editor role.",
        bulletPoints: [
          "RULE-REC-01: Permitted to upload files and execute reconciliation runs",
          "RULE-EXC-02: Permitted to resolve individual exceptions with audit justification",
          "RULE-SEC-01: Restricted from user provisioning or role assignment",
          "RULE-SEC-02: Restricted from modifying global tenant configuration or API credentials",
        ],
        roleHighlight: "Operational Guardrails Active: Financial actions permitted; admin settings locked.",
      },
    ],
  },
  viewer: {
    role: "viewer",
    displayName: "Read-Only Viewer",
    tagline: "Read-Only Oversight & Compliance Inspection",
    description:
      "As a Viewer, you have read-only access to view reconciliation summaries, monitor exception queues, inspect cash runway forecasts, and audit historical logs.",
    badgeColor: "bg-emerald-950/60 border-emerald-500/40 text-emerald-300",
    rules: ROLE_RULES_CATALOG.viewer,
    steps: [
      {
        id: "viewer-welcome",
        route: "/",
        title: "Supervisory Read-Only Portal",
        badge: "Overview · Step 1 of 6",
        Icon: Sparkles,
        description:
          "Welcome to Ledger Control. As a Read-Only Viewer or Auditor, you have supervisory visibility across reconciliation runs, settlement match rates, and compliance records.",
        bulletPoints: [
          "Real-time monitoring of reconciliation match rates and break queues",
          "Inspection of forward cash runway trajectories and liquidity reserves",
          "Full access to the immutable compliance audit ledger and reporting exports",
        ],
        roleHighlight: "Role: READ-ONLY VIEWER — Non-mutating access for audit and oversight.",
      },
      {
        id: "viewer-reconcile",
        route: "/",
        title: "Reconciled Transaction Log Inspection",
        badge: "Monitoring · Step 2 of 6",
        Icon: Scale,
        description:
          "Inspect dual-stream matching summaries, match confidence distributions, and exported transaction logs.",
        bulletPoints: [
          "Review overall match rate percentage and reconciled USD volume",
          "Inspect individual matched pairs across bank statements and internal ledgers",
          "Export verified CSV datasets for external reporting and audit workpapers",
        ],
        roleHighlight: "Permission `reconciliation.read`: ENABLED. Ingestion & execution disabled.",
      },
      {
        id: "viewer-exceptions",
        route: "/exceptions",
        title: "Exception Queue Review & Diagnostics",
        badge: "Audit · Step 3 of 6",
        Icon: AlertTriangle,
        description:
          "Review open discrepancies and AI-generated root-cause diagnostics detailing timing variances or fee breaks.",
        bulletPoints: [
          "Monitor outstanding breaks and unresolved exception values",
          "Inspect AI diagnostic breakdowns explaining variance drivers",
          "Review resolution history and operator audit signatures",
        ],
        roleHighlight: "Permission `reconciliation.resolve`: DISABLED. Exception resolution actions are restricted.",
      },
      {
        id: "viewer-forecast",
        route: "/forecast",
        title: "Liquidity Health & Cash Trajectories",
        badge: "Forecasting · Step 4 of 6",
        Icon: TrendingUp,
        description:
          "Evaluate 7-day, 30-day, and 90-day cash projections and reserve estimates derived from settled activity.",
        bulletPoints: [
          "Inspect daily burn rate and estimated runway buffer",
          "Review upper and lower 95% confidence intervals",
          "Cross-reference corporate cash flows against historical filings",
        ],
        roleHighlight: "Permission `analytics.read`: ENABLED. Read-only projection visibility.",
      },
      {
        id: "viewer-ask",
        route: "/ask",
        title: "Financial AI Copilot (Read-Only Mode)",
        badge: "AI Copilot · Step 5 of 6",
        Icon: MessageSquareText,
        description:
          "Perform natural language queries to inspect historical settlement metrics, cash trends, and reconciliation summaries.",
        bulletPoints: [
          "Inquire: 'What was our total reconciled volume?' or 'List top 5 exception breaks'",
          "Review verified transaction rows supporting each generated response",
          "Non-mutating inquiry mode with zero risk of database alterations",
        ],
        roleHighlight: "Read-Only AI Mode: Instant answers grounded strictly in authorized datasets.",
      },
      {
        id: "viewer-rules",
        route: "/",
        title: "Viewer Rules & Governance Restrictions",
        badge: "Rule Matrix · Step 6 of 6",
        Icon: ShieldCheck,
        description:
          "Summary of operational boundaries and read-only policies enforced for the Viewer role.",
        bulletPoints: [
          "RULE-OBS-01 & 02: Permitted to observe and inspect all reconciliation dashboards",
          "RULE-RES-01: Restricted from uploading files or initiating reconciliation runs",
          "RULE-RES-02: Restricted from accepting or resolving discrepancy breaks",
          "RULE-RES-03: Restricted from modifying users, tenant parameters, or system settings",
        ],
        roleHighlight: "Separation of Duties: Read-only governance enforced across all endpoints.",
      },
    ],
  },
  manager: {
    role: "manager",
    displayName: "Operations Manager",
    tagline: "Reconciliation Management & Break Escalations",
    description: "Operational management authority covering reconciliation and break triage.",
    badgeColor: "bg-indigo-950/60 border-indigo-500/40 text-indigo-300",
    rules: ROLE_RULES_CATALOG.editor,
    steps: [],
  },
  analyst: {
    role: "analyst",
    displayName: "Financial Analyst",
    tagline: "Reconciliation Analysis & Cash Modeling",
    description: "Financial analysis and modeling authority.",
    badgeColor: "bg-cyan-950/60 border-cyan-500/40 text-cyan-300",
    rules: ROLE_RULES_CATALOG.editor,
    steps: [],
  },
};

// Mirror editor steps to manager and analyst
ROLE_CONFIGS.manager.steps = ROLE_CONFIGS.editor.steps;
ROLE_CONFIGS.analyst.steps = ROLE_CONFIGS.editor.steps;
