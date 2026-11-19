import { ChangeEvent, FormEvent, useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";

const DEFAULT_TEMPLATE_LAYOUT = {
  show_username: true, show_password: true, show_serial_number: true, show_plan: true, show_price: true,
  show_limits: true, show_border: true, font_family: "Arial", font_size: "12", border_width: "1",
  border_color: "#667085", columns: "2", rows: "5", header_text: "الأسطورة نت", footer_text: "بطاقة إنترنت",
  page_gap_mm: "4", card_padding_mm: "3",
  username_x: "50", username_y: "48", password_x: "50", password_y: "65",
  serial_x: "8", serial_y: "90", price_x: "92", price_y: "90",
  plan_x: "50", plan_y: "25", limits_x: "50", limits_y: "82",
};

type PermissionOverride = { permission_code: string; allowed: boolean };
type CardVisibility = "all" | "assigned" | "search_any";
type CurrentUser = {
  id: number;
  username: string;
  display_name: string;
  roles: string[];
  permissions: string[];
  permission_overrides: PermissionOverride[];
  point_of_sale_ids: number[];
  card_visibility: CardVisibility;
};
type AdminRole = { code: string; name: string; description: string | null };
type AdminPermission = { code: string; name: string; module: string; description: string | null };
type AdminAccount = { id: number; username: string; display_name: string; is_active: boolean; roles: string[]; point_of_sale_ids: number[]; card_visibility: CardVisibility; permission_overrides: PermissionOverride[]; last_login_at: string | null; created_at: string };
type AuditLogRecord = { id: number; actor_username: string; action: string; entity_type: string; entity_id: string | null; summary: string; details: Record<string, unknown>; ip_address: string | null; created_at: string };

type Plan = {
  id: number;
  code: string;
  name: string;
  price: number;
  commission_type: "none" | "fixed" | "percentage";
  commission_value: number;
  data_limit_bytes: number | null;
  session_time_limit_seconds: number | null;
  validity_period_seconds: number | null;
  speed_profile: string | null;
  settings: Record<string, unknown>;
  is_active: boolean;
};

type CardTemplate = { id: number; code: string; name: string; width_mm: number; height_mm: number; background_color: string; text_color: string; layout: Record<string, unknown>; plan_id: number | null; is_default: boolean; };

type Card = {
  id: string;
  serial_number: string;
  username: string;
  card_type: string;
  status: string;
  is_free: boolean;
  plan_id: number;
  batch_id: string | null;
  price_snapshot: number;
  assigned_pos_id: number | null;
  first_used_at: string | null;
  expires_at: string | null;
  used_seconds: number;
  upload_bytes: number;
  download_bytes: number;
  plan_snapshot: Record<string, unknown>;
  active_sessions_count: number;
  remaining_time_seconds: number | null;
  remaining_data_bytes: number | null;
  shared_users_limit: number | null;
  speed_limit: string | null;
};

type CardBatchRecord = {
  batch_id: string;
  batch_number: string;
  plan_id: number;
  plan_name: string;
  template_code: string | null;
  point_of_sale_id: number | null;
  point_of_sale_name: string | null;
  quantity: number;
  card_type: string;
  generation_mode: string;
  username_length: number;
  password_length: number;
  prefix: string;
  created_at: string;
  printed_count: number;
  is_online_sale: boolean;
  note: string | null;
};

type RadiusOverview = {
  database_status: string;
  cards_total: number;
  cards_by_status: Record<string, number>;
  active_sessions: number;
  active_users: number;
  sessions_total: number;
  routers_total: number;
  routers_enabled: number;
  plans_total: number;
  plans_enabled: number;
};

type RadiusSessionRecord = {
  id: number;
  username: string;
  serial_number: string;
  card_status: string;
  router_name: string;
  nas_identifier: string;
  acct_session_id: string;
  framed_ip_address: string | null;
  calling_station_id: string | null;
  started_at: string;
  last_update_at: string | null;
  session_time_seconds: number;
  upload_bytes: number;
  download_bytes: number;
};

type RadiusSessionsResponse = {
  active_count: number;
  active_users_count: number;
  total_count: number;
  items: RadiusSessionRecord[];
};

type CardSessionHistory = {
  card_id: string;
  username: string;
  serial_number: string;
  total_sessions: number;
  active_sessions: number;
  items: Array<{
    id: number;
    router_name: string;
    nas_identifier: string;
    acct_session_id: string;
    framed_ip_address: string | null;
    calling_station_id: string | null;
    started_at: string;
    last_update_at: string | null;
    stopped_at: string | null;
    session_time_seconds: number;
    upload_bytes: number;
    download_bytes: number;
  }>;
};

type GeneratedCard = {
  id: string;
  serial_number: string;
  username: string;
  password: string | null;
};

type RouterRecord = {
  id: number;
  name: string;
  nas_identifier: string;
  management_host: string;
  radius_client_address: string | null;
  api_port: number;
  api_username: string | null;
  routeros_version: string | null;
  is_active: boolean;
  last_seen_at: string | null;
};

type RouterConnectionProbe = {
  router_id: number;
  router_name: string;
  identity: string | null;
  version: string | null;
  board_name: string | null;
  architecture_name: string | null;
  uptime: string | null;
  cpu_load: string | null;
  connected: boolean;
  secure: boolean;
  warnings: string[];
  read_only: boolean;
};

type UserManagerProbe = {
  connected: boolean;
  router_id: number;
  router_name: string;
  identity: string | null;
  routeros_version: string | null;
  board_name: string | null;
  architecture_name: string | null;
  uptime: string | null;
  user_manager_available: boolean;
  resources: Record<string, { available: boolean; count: number | null }>;
  warnings: string[];
  read_only: boolean;
};

type UserManagerPreviewItem = {
  id: number;
  external_user_id: string;
  username: string | null;
  source_profile_id: string | null;
  classification: string;
  credential_mode: string;
  credential_state: string;
  matched_card_id: string | null;
  safe_snapshot: Record<string, unknown>;
  issues: string[];
};

type UserManagerPreviewList = {
  run: { id: string; status: string; discovered_users: number; created_at: string | null } | null;
  items: UserManagerPreviewItem[];
  total: number;
  classification_counts: Record<string, number>;
  offset: number;
  limit: number;
  read_only: boolean;
  imported: boolean;
  credentials_read: boolean;
};

type UserManagerPreviewRun = {
  id: string;
  status: string;
  discovered_users: number;
  preview_count: number;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
};

type UserManagerUserInspect = {
  router_id: number;
  found: boolean;
  user: {
    external_id: string | null;
    username: string;
    customer: string | null;
    disabled: string | null;
    actual_profile: string | null;
    shared_users: string | null;
    usage: {
      uptime_used: string | null;
      download_used_bytes: string | null;
      upload_used_bytes: string | null;
      last_seen: string | null;
      active_sessions: string | null;
      missing_fields_are_unknown: boolean;
    };
    profile: {
      name: string;
      validity: string | null;
      "starts-when": string | null;
      price: string | null;
      "override-shared-users": string | null;
      comment: string | null;
    } | null;
    limitations: {
      name: string;
      "uptime-limit": string | null;
      "download-limit": string | null;
      "upload-limit": string | null;
      "transfer-limit": string | null;
      "rate-limit-rx": string | null;
      "rate-limit-tx": string | null;
      group: string | null;
    }[];
    warnings: string[];
  } | null;
  read_only: boolean;
  credentials_read: boolean;
  imported: boolean;
};

type PointOfSale = {
  id: number;
  code: string;
  name: string;
  contact_name: string | null;
  phone: string | null;
  is_active: boolean;
  debt_limit: number | null;
  allow_card_creation: boolean;
  allow_printing: boolean;
};

type PosInventory = {
  point_of_sale_id: number;
  point_of_sale_name: string;
  allocated_cards: number;
  used_cards: number;
  suspended_cards: number;
  commercial_printed_value: number;
  free_cards_printed: number;
};


type PosAccountSummary = {
  point_of_sale_id: number;
  point_of_sale_name: string;
  total_debit: number;
  total_credit: number;
  balance_due: number;
};
type PosAccountEntry = {
  id: number;
  point_of_sale_id: number;
  entry_type: string;
  direction: "debit" | "credit";
  amount: number;
  description: string | null;
  reference: string | null;
  idempotency_key: string;
  created_by: string | null;
  created_at: string;
};

type CardsReportData = { total_cards: number; total_value: number; used_seconds: number; upload_bytes: number; download_bytes: number; by_status: { status: string; count: number }[]; by_plan: { plan_name: string; count: number }[] };
type SessionsReportData = { total_sessions: number; unique_users: number; session_seconds: number; upload_bytes: number; download_bytes: number; active_sessions: number; by_router: { router_name: string; sessions: number }[] };
type BatchesReportData = { total_batches: number; total_cards: number; items: { batch_id: string; batch_number: string; created_at: string; plan_name: string; point_of_sale_name: string | null; quantity: number; generated_cards: number; is_online_sale: boolean; note: string | null }[] };
type PrintingReportData = { total_jobs: number; total_cards_printed: number; reprint_jobs: number; items: { id: string; created_at: string; point_of_sale_name: string; card_count: number; is_reprint: boolean; template_code: string | null }[] };

type PosReportRow = {
  point_of_sale_id: number;
  point_of_sale_name: string;
  opening_balance: number;
  delivered_value: number;
  other_debits: number;
  commissions: number;
  payments: number;
  returns: number;
  other_credits: number;
  period_debit: number;
  period_credit: number;
  closing_balance: number;
};
type PosReport = {
  date_from: string;
  date_to: string;
  point_count: number;
  totals: Omit<PosReportRow, "point_of_sale_id" | "point_of_sale_name">;
  points: PosReportRow[];
};
type PosStatementEntry = {
  id: number;
  created_at: string;
  entry_type: string;
  direction: "debit" | "credit";
  amount: number;
  description: string | null;
  reference: string | null;
  created_by: string | null;
  debit: number;
  credit: number;
  running_balance: number;
};
type PosStatement = {
  point_of_sale_id: number;
  point_of_sale_name: string;
  date_from: string;
  date_to: string;
  opening_balance: number;
  total_debit: number;
  total_credit: number;
  closing_balance: number;
  entries: PosStatementEntry[];
};

type PrintOptions = {
  show_username: boolean;
  show_password: boolean;
  show_serial_number: boolean;
  show_plan: boolean;
  show_price: boolean;
  show_limits: boolean;
  sequential: boolean;
};

type PrintJobHistory = {
  id: string;
  template_code: string | null;
  card_count: number;
  is_reprint: boolean;
  print_options: PrintOptions;
  created_at: string;
  cards: { card_id: string; serial_number: string; username: string; is_free: boolean }[];
};

type CardPrintSelectionResolveResponse = {
  total_requested: number;
  matched_count: number;
  items: { id: string; username: string; serial_number: string; plan_id: number; is_free: boolean }[];
  unmatched: string[];
};
type PrintJobResult = {
  id: string;
  template_code: string | null;
  card_count: number;
  commercial_card_count: number;
  free_card_count: number;
  total_amount: number;
  is_reprint: boolean;
  print_options: PrintOptions;
  items: { card_id: string; serial_number: string; username: string; password: string; is_free: boolean; price_snapshot: number; plan_name: string; data_limit_bytes: number | null; session_time_limit_seconds: number | null; validity_period_seconds: number | null }[];
};

async function apiRequest<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = "تعذر تنفيذ الطلب";
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : message;
    } catch {
      // Keep the generic message if the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

const modules = [
  { title: "الكروت", detail: "إنشاء وإدارة كروت الإنترنت", icon: "▤", page: "cards" as const, permission: "cards.view" },
  { title: "الباقات والسرعات", detail: "إعداد حدود الوقت والحجم والسرعة", icon: "◷", page: "plans" as const, permission: "plans.view" },
  { title: "أجهزة MikroTik", detail: "تسجيل الراوترات وإعداد بيانات الاتصال", icon: "⌁", page: "routers" as const, permission: "routers.view" },
  { title: "نقاط البيع", detail: "إدارة المنافذ والمخزون", icon: "▣", page: "pos-management" as const, permission: "pos.view" },
  { title: "جلسات RADIUS", detail: "المستخدمون المتصلون وسجل الجلسات", icon: "◉", page: "cards" as const, permission: "sessions.view" },
  { title: "التقارير", detail: "تقارير الكروت والاستخدام والدفعات", icon: "▥", page: "reports" as const, permission: "reports.view" },
];

function LoginScreen({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onLogin(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تسجيل الدخول");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="login-brand">
          <div className="brand-mark">أ</div>
          <div><strong>الأسطورة RADIUS</strong><span>إدارة الشبكة والكروت</span></div>
        </div>
        <span className="eyebrow">مرحباً بعودتك</span>
        <h1>تسجيل دخول المشرف</h1>
        <p className="login-description">أدخل بيانات حساب الإدارة للوصول إلى لوحة التحكم.</p>
        <form onSubmit={submit} className="login-form">
          <label htmlFor="username">اسم المستخدم</label>
          <input id="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
          <label htmlFor="password">كلمة المرور</label>
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {error && <div className="login-error" role="alert">{error}</div>}
          <button type="submit" disabled={busy}>{busy ? "جارٍ التحقق..." : "دخول إلى النظام"}</button>
        </form>
        <div className="login-foot">نظام إدارة شبكة الأسطورة نت</div>
      </section>
    </main>
  );
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0 بايت";
  const units = ["بايت", "KB", "MB", "GB", "TB"];
  const unitIndex = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const amount = value / (1024 ** unitIndex);
  return amount.toLocaleString("ar", { maximumFractionDigits: 2 }) + " " + units[unitIndex];
}

function formatDuration(value: number): string {
  const seconds = Math.max(0, Math.floor(Number(value) || 0));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return days + " يوم و" + hours + " ساعة";
  if (hours) return hours + " ساعة و" + minutes + " دقيقة";
  return minutes + " دقيقة";
}

function Dashboard({ user, token, onLogout }: { user: CurrentUser; token: string; onLogout: () => void }) {
  const can = (permission: string) => {
    if (user.roles.includes("owner")) return true;
    const direct = user.permission_overrides.find((item) => item.permission_code === permission);
    if (direct) return direct.allowed;
    if (user.permissions.includes(permission)) return true;
    const [module, action] = permission.split(".");
    if (action === "view") {
      return user.permissions.includes(module + ".manage") ||
        (module === "sessions" && user.permissions.includes("sessions.disconnect"));
    }
    if (["create", "update", "delete", "reprint"].includes(action)) {
      const manageOverride = user.permission_overrides.find((item) => item.permission_code === module + ".manage");
      if (manageOverride) return manageOverride.allowed;
      return user.permissions.includes(module + ".manage");
    }
    // Credential disclosure is never implied by a broad manage permission.
    return false;
  };
  const [page, setPage] = useState<"overview" | "plans" | "card-create" | "cards" | "pos" | "pos-management" | "batches" | "routers" | "reports" | "templates" | "admins" | "audit" | "settings">("overview");
  const [openNavGroup, setOpenNavGroup] = useState<"system" | "cards" | "printing" | null>(null);
  useEffect(() => {
    if (["card-create", "cards", "batches", "templates"].includes(page)) setOpenNavGroup("cards");
    else if (["plans", "routers", "reports"].includes(page)) setOpenNavGroup("system");
    else if (page === "pos") setOpenNavGroup("printing");
  }, [page]);
  const [systemStatus, setSystemStatus] = useState<{ api: string; database: string; version: string; checkedAt: string } | null>(null);
  const [systemStatusLoading, setSystemStatusLoading] = useState(false);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [adminAccounts, setAdminAccounts] = useState<AdminAccount[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditOffset, setAuditOffset] = useState(0);
  const [adminRoles, setAdminRoles] = useState<AdminRole[]>([]);
  const [adminPermissions, setAdminPermissions] = useState<AdminPermission[]>([]);
  const [selectedPermissionRole, setSelectedPermissionRole] = useState("manager");
  const [rolePermissionCodes, setRolePermissionCodes] = useState<string[]>([]);
  const managedPermissionActions: Record<string, string[]> = {
    cards: ["create", "update", "delete"],
    plans: ["create", "update", "delete"],
    routers: ["create", "update", "delete"],
    pos: ["create", "update", "delete"],
    finance: ["create", "update", "delete"],
    printing: ["create", "reprint"],
  };
  const isRolePermissionChecked = (permissionCode: string) => {
    if (rolePermissionCodes.includes(permissionCode)) return true;
    const [module, action] = permissionCode.split(".");
    if (action === "view") {
      return rolePermissionCodes.includes(module + ".manage") ||
        (module === "sessions" && rolePermissionCodes.includes("sessions.disconnect"));
    }
    return managedPermissionActions[module]?.includes(action) === true &&
      rolePermissionCodes.includes(module + ".manage");
  };
  const toggleRolePermission = (permissionCode: string, checked: boolean) => {
    const [module, action] = permissionCode.split(".");
    const actions = managedPermissionActions[module] ?? [];
    setRolePermissionCodes((current) => {
      let next = [...current];
      const manageCode = module + ".manage";
      if (action === "manage") {
        if (checked) {
          next = next.filter((code) => code !== module + ".view" && !actions.some((item) => code === module + "." + item));
          next.push(permissionCode);
        } else {
          next = next.filter((code) => code !== permissionCode);
        }
      } else {
        if (current.includes(manageCode) && (action === "view" || actions.includes(action))) {
          next = next.filter((code) => code !== manageCode);
          next.push(module + ".view", ...actions.map((item) => module + "." + item));
        }
        if (module === "sessions" && action === "view" && !checked) {
          next = next.filter((code) => code !== "sessions.disconnect");
        }
        if (checked) next.push(permissionCode);
        else next = next.filter((code) => code !== permissionCode);
      }
      return Array.from(new Set(next));
    });
  };
  const [adminDraft, setAdminDraft] = useState({ username: "", displayName: "", password: "", roleCode: "operator", pointOfSaleIds: [] as number[], cardVisibility: "search_any" as CardVisibility });
  const [selectedAdminId, setSelectedAdminId] = useState<number | null>(null);
  const [adminOverrideDraft, setAdminOverrideDraft] = useState<Record<string, "inherit" | "allow" | "deny">>({});
  const [adminVisibilityDraft, setAdminVisibilityDraft] = useState<CardVisibility>("search_any");
  const [roleDraft, setRoleDraft] = useState({ code: "", name: "", description: "" });

  const [routers, setRouters] = useState<RouterRecord[]>([]);
  const [userManagerProbe, setUserManagerProbe] = useState<UserManagerProbe | null>(null);
  const [routerConnectionProbe, setRouterConnectionProbe] = useState<RouterConnectionProbe | null>(null);
  const [testingRouterConnectionId, setTestingRouterConnectionId] = useState<number | null>(null);
  const [probingRouterId, setProbingRouterId] = useState<number | null>(null);
  const [inspectRouterId, setInspectRouterId] = useState("");
  const [inspectUsername, setInspectUsername] = useState("");
  const [userManagerUserInspect, setUserManagerUserInspect] = useState<UserManagerUserInspect | null>(null);
  const [userManagerPreviews, setUserManagerPreviews] = useState<UserManagerPreviewList | null>(null);
  const [userManagerPreviewRuns, setUserManagerPreviewRuns] = useState<UserManagerPreviewRun[]>([]);
  const [selectedPreviewRunId, setSelectedPreviewRunId] = useState("");
  const [loadingPreviewRuns, setLoadingPreviewRuns] = useState(false);
  const [savingUserPreview, setSavingUserPreview] = useState(false);
  const [inspectingUser, setInspectingUser] = useState(false);
  const [routerDraft, setRouterDraft] = useState({ name: "", nasIdentifier: "", managementHost: "", radiusClientAddress: "", apiPort: "8729", apiUsername: "", apiSecret: "", radiusSecret: "", routerosVersion: "" });
  const [editingRouterId, setEditingRouterId] = useState<number | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [cardBatches, setCardBatches] = useState<CardBatchRecord[]>([]);
  const [radiusSessions, setRadiusSessions] = useState<RadiusSessionsResponse>({ active_count: 0, active_users_count: 0, total_count: 0, items: [] });
  const [cardSessionHistory, setCardSessionHistory] = useState<CardSessionHistory | null>(null);
  const [radiusOverview, setRadiusOverview] = useState<RadiusOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [cardBatchFilter, setCardBatchFilter] = useState("");
  const [cardTemplates, setCardTemplates] = useState<CardTemplate[]>([]);
  const [selectedCardIds, setSelectedCardIds] = useState<string[]>([]);
  const [templateDraft, setTemplateDraft] = useState({ code: "", name: "", width_mm: "90", height_mm: "50", background_color: "#e9f6ef", text_color: "#174c37", plan_id: "" });
  const [editingTemplateId, setEditingTemplateId] = useState<number | null>(null);
  const [templateLayoutDraft, setTemplateLayoutDraft] = useState<Record<string, string | boolean>>({ ...DEFAULT_TEMPLATE_LAYOUT });
  const [generatedCards, setGeneratedCards] = useState<GeneratedCard[]>([]);
  const [generatedBatchNumber, setGeneratedBatchNumber] = useState("");
  const [editingPlanId, setEditingPlanId] = useState<number | null>(null);
  const [planEditorOpen, setPlanEditorOpen] = useState(false);
  const [cardSearch, setCardSearch] = useState("");
  const [cardStatusFilter, setCardStatusFilter] = useState("");
  const [cardManagementTab, setCardManagementTab] = useState<"all" | "expired" | "batches" | "sessions">("all");
  const [cardPlanFilter, setCardPlanFilter] = useState("");
  const [cardFreeFilter, setCardFreeFilter] = useState("");
  const [cardOffset, setCardOffset] = useState(0);
  const [hasMoreCards, setHasMoreCards] = useState(false);
  const [points, setPoints] = useState<PointOfSale[]>([]);
  const [posSearch, setPosSearch] = useState("");
  const [posStatusFilter, setPosStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [selectedPosId, setSelectedPosId] = useState("");
  const [posInventory, setPosInventory] = useState<PosInventory | null>(null);
  const [posAccount, setPosAccount] = useState<PosAccountSummary | null>(null);
  const [posEntries, setPosEntries] = useState<PosAccountEntry[]>([]);
  const [posReport, setPosReport] = useState<PosReport | null>(null);
  const [cardsReport, setCardsReport] = useState<CardsReportData | null>(null);
  const [sessionsReport, setSessionsReport] = useState<SessionsReportData | null>(null);
  const [batchesReport, setBatchesReport] = useState<BatchesReportData | null>(null);
  const [printingReport, setPrintingReport] = useState<PrintingReportData | null>(null);
  const [reportTab, setReportTab] = useState<"cards" | "usage" | "batches" | "printing" | "finance">(can("cards.view") ? "cards" : can("sessions.view") ? "usage" : can("printing.view") ? "printing" : "finance");
  const [statementPointId, setStatementPointId] = useState("");
  const [posStatement, setPosStatement] = useState<PosStatement | null>(null);
  const [reportFrom, setReportFrom] = useState(() => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10));
  const [reportTo, setReportTo] = useState(() => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10));
  const [accountDraft, setAccountDraft] = useState({ amount: "", entryType: "payment", direction: "credit" as "debit" | "credit", description: "", reference: "" });
  const [printHistory, setPrintHistory] = useState<PrintJobHistory[]>([]);
  const [posDraft, setPosDraft] = useState({ code: "", name: "", contactName: "", phone: "", debtLimit: "", allowCardCreation: true, allowPrinting: true });
  const [editingPosId, setEditingPosId] = useState<number | null>(null);
  const [selectedPrintCardIds, setSelectedPrintCardIds] = useState<string[]>([]);
  const [printPreviewCards, setPrintPreviewCards] = useState<PrintJobResult["items"]>([]);
  const [printTemplate, setPrintTemplate] = useState("classic-green");
  const [printOptions, setPrintOptions] = useState<PrintOptions>({ show_username: true, show_password: true, show_serial_number: true, show_plan: true, show_price: true, show_limits: true, sequential: false });
  const [printMode, setPrintMode] = useState<"default" | "sequential" | "file" | "single">("default");
  const [printImportSummary, setPrintImportSummary] = useState("");
  const [cardMode, setCardMode] = useState<"batch" | "single">("batch");
  const [singleDraft, setSingleDraft] = useState({ planId: "", username: "", cardType: "username_only", password: "", isFree: false });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [planDraft, setPlanDraft] = useState({
    code: "", name: "", price: "", commissionType: "none" as "none" | "fixed" | "percentage", commissionValue: "", dataAmount: "", dataUnit: "GB" as "MB" | "GB", timeHours: "", validityDays: "", speedProfile: "", sharedUsers: "", groupName: "", rateRx: "", rateTx: "", rateUnit: "Kbps" as "Kbps" | "Mbps", scheduleEnabled: false, scheduleDays: ["0","1","2","3","4","5","6"], scheduleFrom: "00:00", scheduleTo: "23:59", notificationsEnabled: false, notifyRemaining: "70", notifyExhausted: "95",
  });
  const [batchDraft, setBatchDraft] = useState({
    planId: "", quantity: "100", cardType: "username_only",
    generationMode: "digits", usernameLength: "8", passwordLength: "10", prefix: "",
    batchMode: "new" as "new" | "existing", existingBatchNumber: "",
    isOnlineSale: false, note: "",
  });

  useEffect(() => {
    const activeTemplates = cardTemplates.filter((item) => item.plan_id !== null && plans.some((plan) => plan.id === item.plan_id && plan.is_active));
    const current = activeTemplates.find((item) => item.code === printTemplate);
    const preferred = current ?? activeTemplates.find((item) => item.is_default) ?? activeTemplates[0];
    if (preferred && preferred.code !== printTemplate) {
      setPrintTemplate(preferred.code);
      const planId = String(preferred.plan_id);
      setSingleDraft((draft) => ({ ...draft, planId }));
      setBatchDraft((draft) => ({ ...draft, planId }));
    }
  }, [cardTemplates, plans, printTemplate]);

  async function loadPlans() {
    const result = await apiRequest<Plan[]>(token, "/api/v1/plans?include_inactive=true");
    setPlans(result);
    const firstActive = result.find((plan) => plan.is_active);
    if (firstActive) {
      if (!batchDraft.planId) setBatchDraft((current) => ({ ...current, planId: String(firstActive.id) }));
      if (!singleDraft.planId) setSingleDraft((current) => ({ ...current, planId: String(firstActive.id) }));
    }
  }

  async function loadAuditLogs(offset = 0) {
    const result = await apiRequest<{ total: number; items: AuditLogRecord[] }>(
      token, `/api/v1/audit-logs?offset=${offset}&limit=50`
    );
    setAuditLogs(result.items);
    setAuditTotal(result.total);
    setAuditOffset(offset);
  }

  async function loadSystemStatus() {
    setSystemStatusLoading(true);
    const checkedAt = new Date().toISOString();
    try {
      const [apiResult, databaseResult] = await Promise.allSettled([
        fetch(`${API_BASE}/health`, { cache: "no-store" }),
        fetch(`${API_BASE}/health/ready`, { cache: "no-store" }),
      ]);
      let api = "unavailable";
      let version = "غير متاح";
      if (apiResult.status === "fulfilled" && apiResult.value.ok) {
        const data = await apiResult.value.json();
        api = "connected";
        version = typeof data.version === "string" ? data.version : "غير محدد";
      }
      let database = "unknown";
      if (databaseResult.status === "fulfilled") {
        try {
          const data = await databaseResult.value.json();
          database = databaseResult.value.ok && data.database === "connected" ? "connected" : "unavailable";
        } catch {
          database = "unavailable";
        }
      }
      setSystemStatus({ api, database, version, checkedAt });
    } finally {
      setSystemStatusLoading(false);
    }
  }

  function renderSystemSettings() {
    const statusLabel = (value: string) => value === "connected" ? "متصل" : value === "unavailable" ? "غير متاح" : "لم يتم الفحص";
    return (
      <>
        <div className="section-heading system-settings-heading">
          <div><span className="eyebrow">إدارة النظام</span><h2>الإعدادات والصيانة</h2><p>مركز متابعة سلامة خدمات النظام والوصول إلى إعداداته الحالية.</p></div>
          <button type="button" className="secondary-button" disabled={systemStatusLoading} onClick={() => loadSystemStatus().catch(() => setError("تعذر فحص حالة النظام."))}>{systemStatusLoading ? "جارٍ الفحص..." : "فحص الحالة الآن"}</button>
        </div>
        <div className="system-status-grid">
          <article className="system-status-card"><span>واجهة API</span><strong className={systemStatus?.api === "connected" ? "status-ok" : "status-unknown"}>{statusLabel(systemStatus?.api ?? "unknown")}</strong><small>فحص استجابة خدمة التطبيق</small></article>
          <article className="system-status-card"><span>قاعدة البيانات</span><strong className={systemStatus?.database === "connected" ? "status-ok" : "status-unknown"}>{statusLabel(systemStatus?.database ?? "unknown")}</strong><small>فحص اتصال PostgreSQL واستعلام جاهزية</small></article>
          <article className="system-status-card"><span>إصدار API</span><strong>{systemStatus?.version ?? "لم يتم الفحص"}</strong><small>الإصدار المعلن من خدمة التطبيق</small></article>
        </div>
        <section className="panel system-maintenance-panel">
          <div className="section-heading"><div><h3>حالة الفحص</h3><p>آخر نتيجة فحص محفوظة في هذه الجلسة.</p></div></div>
          <div className="system-status-row"><span>آخر فحص</span><strong>{systemStatus?.checkedAt ? new Date(systemStatus.checkedAt).toLocaleString("ar") : "لم يتم الفحص بعد"}</strong></div>
          <p className="overview-disclaimer">فحص الجاهزية يؤكد اتصال قاعدة البيانات فقط، ولا يثبت تشغيل FreeRADIUS أو اتصال أجهزة MikroTik فعلياً.</p>
        </section>
        <section className="panel system-maintenance-panel">
          <div className="section-heading"><div><h3>الوصول إلى إعدادات النظام</h3><p>تُدار الإعدادات من صفحاتها الأصلية حتى لا تتكرر القيم أو تتعارض.</p></div></div>
          <div className="system-shortcuts">
            <button type="button" onClick={() => setPage("admins")}>حسابات الإدارة والصلاحيات<span>إدارة الحسابات والأدوار</span></button>
            <button type="button" onClick={() => setPage("routers")}>إعدادات أجهزة الشبكة<span>الراوترات ومعرّفات NAS</span></button>
            <button type="button" onClick={() => setPage("plans")}>إعدادات الباقات والسرعات<span>حدود الوقت والحجم والسرعة</span></button>
            <button type="button" onClick={() => setPage("templates")}>إعدادات تصاميم الكروت<span>القوالب ومقاسات الطباعة</span></button>
          </div>
        </section>
        <section className="panel system-maintenance-panel">
          <div className="section-heading"><div><h3>أدوات الصيانة</h3><p>لن تظهر إجراءات تنفيذية قبل توفير حماية واختبار مناسبين لها.</p></div></div>
          <div className="maintenance-item"><div><strong>النسخ الاحتياطي والاستعادة</strong><small>غير مفعّل بعد؛ يحتاج آلية نسخ مشفرة، والتحقق من سلامة الملف، وخطة استعادة آمنة.</small></div><span className="maintenance-unavailable">غير متاح حالياً</span></div>
          <div className="maintenance-item"><div><strong>تنظيف البيانات والسجلات</strong><small>غير مفعّل بعد؛ لن نحذف سجلات أو جلسات تلقائياً قبل تحديد سياسة الاحتفاظ.</small></div><span className="maintenance-unavailable">غير متاح حالياً</span></div>
          <div className="maintenance-item"><div><strong>إعادة تشغيل الخدمات</strong><small>غير مفعّل من لوحة التحكم؛ لتجنب قطع الخدمة دون تحكم وتأكيد واضح.</small></div><span className="maintenance-unavailable">غير متاح حالياً</span></div>
        </section>
      </>
    );
  }

  function renderAuditLogs() {
    const actionNames: Record<string, string> = {
      "auth.login": "تسجيل دخول",
      "admin.created": "إنشاء حساب إداري",
      "admin.updated": "تعديل حساب إداري",
      "role.permissions_updated": "تعديل صلاحيات دور",
      "role.created": "إنشاء دور إداري",
      "card.created": "إنشاء كرت",
      "card.suspended": "إيقاف كرت",
      "card.reactivated": "إعادة تفعيل كرت",
      "card.cancelled": "إلغاء كرت",
      "cards.batch_created": "إنشاء دفعة كروت",
      "cards.batch_extended": "إضافة كروت إلى دفعة",
      "card_template.created": "إنشاء قالب كروت",
      "card_template.updated": "تعديل قالب كروت",
      "card_template.deleted": "حذف قالب كروت",
      "session.disconnect_requested": "طلب فصل جلسة",
      "print.job_created": "تنفيذ طباعة",
      "print.reprint_created": "إعادة طباعة",
      "finance.entry_created": "تسجيل حركة مالية",
      "plan.created": "إنشاء باقة",
      "plan.updated": "تعديل باقة",
      "pos.created": "إنشاء نقطة بيع",
      "pos.updated": "تعديل نقطة بيع",
      "router.created": "إضافة راوتر",
      "router.updated": "تعديل راوتر",
      "router.connection_tested": "فحص اتصال الراوتر",
    };
    return (
      <section className="panel audit-log-panel">
        <div className="section-heading">
          <div><h2>سجل عمليات النظام</h2><p>سجل زمني للعمليات الإدارية والتشغيلية المسجلة داخل النظام.</p></div>
          <div className="audit-toolbar"><span className="count-tag">{auditTotal.toLocaleString("ar")} عملية</span><button type="button" className="secondary-button" onClick={() => loadAuditLogs(0)}>تحديث السجل</button></div>
        </div>
        <div className="audit-summary-grid">
          <article><span>العمليات في الصفحة</span><strong>{auditLogs.length.toLocaleString("ar")}</strong><small>من أصل {auditTotal.toLocaleString("ar")} عملية</small></article>
          <article><span>المستخدمون الظاهرون</span><strong>{new Set(auditLogs.map((item) => item.actor_username)).size.toLocaleString("ar")}</strong><small>حسابات نفذت عمليات في النتائج الحالية</small></article>
          <article><span>عمليات بعنوان IP</span><strong>{auditLogs.filter((item) => Boolean(item.ip_address)).length.toLocaleString("ar")}</strong><small>سجلات تتضمن عنوان مصدر</small></article>
        </div>
        <div className="table-wrap">
          <table className="data-table audit-log-table">
            <thead><tr><th>التاريخ والوقت</th><th>المستخدم الإداري</th><th>العملية</th><th>القسم</th><th>المعرف</th><th>التفاصيل</th><th>عنوان IP</th></tr></thead>
            <tbody>
              {auditLogs.map((item) => (
                <tr key={item.id}>
                  <td>{new Date(item.created_at).toLocaleString("ar", { dateStyle: "short", timeStyle: "short" })}</td>
                  <td>{item.actor_username}</td>
                  <td><strong>{actionNames[item.action] ?? item.action}</strong></td>
                  <td>{item.entity_type}</td>
                  <td>{item.entity_id ?? "—"}</td>
                  <td>{item.summary}</td>
                  <td>{item.ip_address ?? "—"}</td>
                </tr>
              ))}
              {auditLogs.length === 0 && <tr><td colSpan={7} className="empty-state">لا توجد عمليات مسجلة في هذه الصفحة.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="audit-pagination"><span>عرض {(auditTotal === 0 ? 0 : auditOffset + 1).toLocaleString("ar")}–{Math.min(auditOffset + auditLogs.length, auditTotal).toLocaleString("ar")} من {auditTotal.toLocaleString("ar")}</span><div><button type="button" className="secondary-button" disabled={auditOffset === 0} onClick={() => loadAuditLogs(Math.max(0, auditOffset - 50))}>السابق</button><button type="button" className="secondary-button" disabled={auditOffset + 50 >= auditTotal} onClick={() => loadAuditLogs(auditOffset + 50)}>التالي</button></div></div>
      </section>
    );
  }

  async function loadAdminAccounts() {
    const [accounts, roles, permissions, pointOptions] = await Promise.all([
      apiRequest<AdminAccount[]>(token, "/api/v1/admins"),
      apiRequest<AdminRole[]>(token, "/api/v1/admins/roles"),
      apiRequest<AdminPermission[]>(token, "/api/v1/admins/permissions"),
      apiRequest<PointOfSale[]>(token, "/api/v1/points-of-sale?include_inactive=true"),
    ]);
    setPoints(pointOptions);
    setAdminAccounts(accounts);
    setAdminRoles(roles);
    setAdminPermissions(permissions);
    const assignableRoles = roles.filter((role) => role.code !== "owner");
    if (assignableRoles.length && !assignableRoles.some((role) => role.code === adminDraft.roleCode)) {
      setAdminDraft((draft) => ({ ...draft, roleCode: assignableRoles[0].code }));
    }
    const permissionRole = roles.some((role) => role.code === selectedPermissionRole && role.code !== "owner")
      ? selectedPermissionRole
      : (assignableRoles[0]?.code ?? "manager");
    setSelectedPermissionRole(permissionRole);
    const permissionsForRole = await apiRequest<{ role_code: string; permission_codes: string[] }>(
      token, `/api/v1/admins/roles/${permissionRole}/permissions`
    );
    setRolePermissionCodes(permissionsForRole.permission_codes);
  }

  async function selectPermissionRole(roleCode: string) {
    setSelectedPermissionRole(roleCode);
    try {
      const result = await apiRequest<{ role_code: string; permission_codes: string[] }>(
        token, `/api/v1/admins/roles/${roleCode}/permissions`
      );
      setRolePermissionCodes(result.permission_codes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تحميل صلاحيات الدور");
    }
  }

  async function saveRolePermissions() {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<{ role_code: string; permission_codes: string[] }>(
        token, `/api/v1/admins/roles/${selectedPermissionRole}/permissions`,
        { method: "PUT", body: JSON.stringify({ permission_codes: rolePermissionCodes }) }
      );
      setRolePermissionCodes(result.permission_codes);
      setNotice("تم حفظ مصفوفة الصلاحيات بنجاح.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر حفظ الصلاحيات");
    } finally { setBusy(false); }
  }

  async function createAdminRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const created = await apiRequest<AdminRole>(token, "/api/v1/admins/roles", {
        method: "POST",
        body: JSON.stringify({
          code: roleDraft.code.trim().toLowerCase(),
          name: roleDraft.name.trim(),
          description: roleDraft.description.trim() || null,
        }),
      });
      setRoleDraft({ code: "", name: "", description: "" });
      await loadAdminAccounts();
      await selectPermissionRole(created.code);
      setNotice("تم إنشاء الدور. اختر صلاحياته ثم احفظها قبل إسناده للموظفين.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء الدور الإداري");
    } finally { setBusy(false); }
  }

  async function createAdminAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<AdminAccount>(token, "/api/v1/admins", {
        method: "POST",
        body: JSON.stringify({
          username: adminDraft.username.trim(),
          display_name: adminDraft.displayName.trim(),
          password: adminDraft.password,
          role_codes: [adminDraft.roleCode],
          point_of_sale_ids: adminDraft.pointOfSaleIds,
          card_visibility: adminDraft.cardVisibility,
        }),
      });
      setAdminDraft((draft) => ({ ...draft, username: "", displayName: "", password: "", pointOfSaleIds: [], cardVisibility: "search_any" }));
      await loadAdminAccounts();
      setNotice("تم إنشاء حساب الإدارة بنجاح.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء حساب الإدارة");
    } finally { setBusy(false); }
  }

  async function updateAdminAccount(account: AdminAccount, changes: { role_codes?: string[]; is_active?: boolean; point_of_sale_ids?: number[]; card_visibility?: CardVisibility; permission_overrides?: PermissionOverride[] }) {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<AdminAccount>(token, `/api/v1/admins/${account.id}`, {
        method: "PATCH",
        body: JSON.stringify(changes),
      });
      await loadAdminAccounts();
      setNotice("تم تحديث حساب الإدارة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تحديث حساب الإدارة");
    } finally { setBusy(false); }
  }

  function selectAdminForIndividualSettings(account: AdminAccount) {
    setSelectedAdminId(account.id);
    setAdminVisibilityDraft(account.card_visibility);
    setAdminOverrideDraft(Object.fromEntries(
      account.permission_overrides.map((item) => [item.permission_code, item.allowed ? "allow" : "deny"]),
    ));
  }

  async function saveAdminIndividualSettings() {
    const account = adminAccounts.find((item) => item.id === selectedAdminId);
    if (!account) return;
    const permission_overrides = Object.entries(adminOverrideDraft)
      .filter(([, value]) => value !== "inherit")
      .map(([permission_code, value]) => ({ permission_code, allowed: value === "allow" }));
    await updateAdminAccount(account, {
      permission_overrides,
      card_visibility: adminVisibilityDraft,
    });
  }

  async function loadCardBatches() {
    const result = await apiRequest<CardBatchRecord[]>(token, "/api/v1/cards/batches?limit=200");
    setCardBatches(result);
  }

  async function loadRadiusOverview() {
    setOverviewLoading(true);
    try {
      const result = await apiRequest<RadiusOverview>(token, "/api/v1/cards/overview");
      setRadiusOverview(result);
    } finally {
      setOverviewLoading(false);
    }
  }

  async function disconnectRadiusSession(sessionId: number) {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<{ session_id: number; disconnect_acknowledged: boolean }>(
        token, `/api/v1/cards/sessions/${sessionId}/disconnect`, { method: "POST" }
      );
      setNotice("أكد الراوتر استلام طلب فصل الجلسة. سيظهر انتهاء الجلسة بعد وصول سجل المحاسبة.");
      await loadRadiusSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر فصل الجلسة");
    } finally { setBusy(false); }
  }

  async function loadRadiusSessions() {
    const result = await apiRequest<RadiusSessionsResponse>(token, "/api/v1/cards/sessions?limit=200");
    setRadiusSessions(result);
  }

  async function loadCardSessionHistory(card: Card) {
    try {
      const result = await apiRequest<CardSessionHistory>(
        token,
        `/api/v1/cards/${card.id}/sessions?search=${encodeURIComponent(card.username)}`,
      );
      setCardSessionHistory(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تحميل جلسات الكرت");
    }
  }

  async function loadRouters() {
    const result = await apiRequest<RouterRecord[]>(token, "/api/v1/routers?include_inactive=true");
    setRouters(result);
  }

  function resetRouterDraft() {
    setEditingRouterId(null);
    setRouterDraft({ name: "", nasIdentifier: "", managementHost: "", radiusClientAddress: "", apiPort: "8729", apiUsername: "", apiSecret: "", radiusSecret: "", routerosVersion: "" });
  }

  function beginEditRouter(item: RouterRecord) {
    setEditingRouterId(item.id);
    setRouterDraft({ name: item.name, nasIdentifier: item.nas_identifier, managementHost: item.management_host, radiusClientAddress: item.radius_client_address || "", apiPort: String(item.api_port), apiUsername: "", apiSecret: "", radiusSecret: "", routerosVersion: item.routeros_version || "" });
    setError("");
    setNotice("تعديل بيانات الراوتر: " + item.name);
  }

  async function createRouter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingRouterId !== null ? !can("routers.update") : !can("routers.create")) { setError("ليست لديك صلاحية هذه العملية على الراوترات."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      if (editingRouterId !== null) {
        await apiRequest<RouterRecord>(token, `/api/v1/routers/${editingRouterId}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: routerDraft.name,
            management_host: routerDraft.managementHost,
            radius_client_address: routerDraft.radiusClientAddress || null,
            api_port: Number(routerDraft.apiPort),
            routeros_version: routerDraft.routerosVersion || null,
          }),
        });
        resetRouterDraft();
        await loadRouters();
        setNotice("تم تحديث بيانات الراوتر. لم يتم تغيير بيانات الدخول السرية.");
        return;
      }
      await apiRequest<RouterRecord>(token, "/api/v1/routers", {
        method: "POST",
        body: JSON.stringify({
          name: routerDraft.name,
          nas_identifier: routerDraft.nasIdentifier,
          management_host: routerDraft.managementHost,
          radius_client_address: routerDraft.radiusClientAddress || null,
          api_port: Number(routerDraft.apiPort),
          api_username: routerDraft.apiUsername || null,
          api_secret: routerDraft.apiSecret || null,
          radius_secret: routerDraft.radiusSecret,
          routeros_version: routerDraft.routerosVersion || null,
        }),
      });
      resetRouterDraft();
      await loadRouters();
      setNotice("تم تسجيل الراوتر وحفظ أسراره مشفرة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تسجيل الراوتر");
    } finally { setBusy(false); }
  }

  async function testRouterConnection(item: RouterRecord) {
    if (!can("routers.update")) { setError("فحص اتصال الراوتر يتطلب صلاحية إدارة الراوترات."); return; }
    setTestingRouterConnectionId(item.id);
    setRouterConnectionProbe(null);
    setError("");
    setNotice("");
    try {
      const result = await apiRequest<RouterConnectionProbe>(
        token,
        `/api/v1/routers/${item.id}/test-connection`,
        { method: "POST" },
      );
      setRouterConnectionProbe(result);
      await loadRouters();
      setNotice(`نجح اتصال RouterOS API مع ${item.name}؛ الفحص قراءة فقط.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر فحص اتصال RouterOS API");
    } finally {
      setTestingRouterConnectionId(null);
    }
  }

  async function testRouterUserManager(item: RouterRecord) {
    setProbingRouterId(item.id);
    setUserManagerProbe(null);
    setError("");
    setNotice("");
    try {
      const result = await apiRequest<UserManagerProbe>(
        token,
        `/api/v1/routers/${item.id}/user-manager/test-connection`,
        { method: "POST" },
      );
      setUserManagerProbe(result);
      setNotice(`تم الاتصال بـ User Manager على ${item.name} وفحص الموارد بوضع القراءة فقط.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر فحص اتصال User Manager");
    } finally {
      setProbingRouterId(null);
    }
  }

  async function inspectRouterUser() {
    const routerId = Number(inspectRouterId);
    const targetUsername = inspectUsername.trim();
    if (!routerId || !targetUsername) return;
    setInspectingUser(true);
    setUserManagerUserInspect(null);
    setError("");
    setNotice("");
    try {
      const result = await apiRequest<UserManagerUserInspect>(
        token,
        `/api/v1/routers/${routerId}/user-manager/inspect-user`,
        {
          method: "POST",
          body: JSON.stringify({ username: targetUsername }),
        },
      );
      setUserManagerUserInspect(result);
      setNotice(result.found ? "تم العثور على الكرت في User Manager؛ لم يتم استيراده." : "لم يتم العثور على هذا الاسم في User Manager.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر فحص الكرت");
    } finally {
      setInspectingUser(false);
    }
  }

  async function loadUserManagerPreviewRuns(routerId: number, preferredRunId?: string) {
    setLoadingPreviewRuns(true);
    try {
      const result = await apiRequest<{ items: UserManagerPreviewRun[]; read_only: boolean; imported: boolean; credentials_read: boolean }>(
        token,
        `/api/v1/routers/${routerId}/user-manager/previews/runs?limit=50`,
      );
      setUserManagerPreviewRuns(result.items);
      const nextRunId = preferredRunId && result.items.some((run) => run.id === preferredRunId)
        ? preferredRunId
        : result.items[0]?.id || "";
      setSelectedPreviewRunId(nextRunId);
      if (nextRunId) {
        const previews = await apiRequest<UserManagerPreviewList>(
          token,
          `/api/v1/routers/${routerId}/user-manager/previews?run_id=${encodeURIComponent(nextRunId)}&offset=0&limit=50`,
        );
        setUserManagerPreviews(previews);
      } else {
        setUserManagerPreviews(null);
      }
    } finally {
      setLoadingPreviewRuns(false);
    }
  }

  async function selectUserManagerPreviewRun(runId: string) {
    setSelectedPreviewRunId(runId);
    if (!runId || !inspectRouterId) {
      setUserManagerPreviews(null);
      return;
    }
    try {
      const result = await apiRequest<UserManagerPreviewList>(
        token,
        `/api/v1/routers/${Number(inspectRouterId)}/user-manager/previews?run_id=${encodeURIComponent(runId)}&offset=0&limit=50`,
      );
      setUserManagerPreviews(result);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تحميل المعاينة المختارة");
    }
  }

  async function changeUserManagerPreviewPage(nextOffset: number) {
    if (!inspectRouterId || !selectedPreviewRunId || !userManagerPreviews) return;
    setLoadingPreviewRuns(true);
    try {
      const result = await apiRequest<UserManagerPreviewList>(
        token,
        `/api/v1/routers/${Number(inspectRouterId)}/user-manager/previews?run_id=${encodeURIComponent(selectedPreviewRunId)}&offset=${Math.max(0, nextOffset)}&limit=${userManagerPreviews.limit || 50}`,
      );
      setUserManagerPreviews(result);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تحميل صفحة المعاينة");
    } finally {
      setLoadingPreviewRuns(false);
    }
  }

  async function saveUserManagerPreview() {
    const routerId = Number(inspectRouterId);
    const targetUsername = inspectUsername.trim();
    if (!routerId || !targetUsername) return;
    setSavingUserPreview(true);
    setError("");
    setNotice("");
    try {
      const created = await apiRequest<{ sync_run_id: string; read_only: boolean; imported: boolean; credentials_read: boolean }>(
        token,
        `/api/v1/routers/${routerId}/user-manager/preview-user`,
        { method: "POST", body: JSON.stringify({ username: targetUsername }) },
      );
      await loadUserManagerPreviewRuns(routerId, created.sync_run_id);
      setNotice("حُفظت معاينة الكرت بنجاح. لم يتم استيراده ولم تُقرأ كلمة المرور.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر حفظ معاينة الكرت");
    } finally {
      setSavingUserPreview(false);
    }
  }

  async function toggleRouter(item: RouterRecord) {
    if (!can("routers.update")) { setError("ليست لديك صلاحية تعديل الراوترات."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<RouterRecord>(token, `/api/v1/routers/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      await loadRouters();
      setNotice(item.is_active ? "تم إيقاف الراوتر في سجل الإدارة." : "تم تفعيل الراوتر في سجل الإدارة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تغيير حالة الراوتر");
    } finally { setBusy(false); }
  }

  async function deleteRouter(item: RouterRecord) {
    if (!can("routers.delete")) { setError("ليست لديك صلاحية حذف الراوترات."); return; }
    if (item.is_active) { setError("أوقف الراوتر أولاً قبل حذفه."); return; }
    if (!window.confirm(`حذف الراوتر ${item.name}؟ لا يمكن حذف راوتر مرتبط بجلسات أو سجلات محفوظة.`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<void>(token, `/api/v1/routers/${item.id}`, { method: "DELETE" });
      if (editingRouterId === item.id) resetRouterDraft();
      if (inspectRouterId === String(item.id)) {
        setInspectRouterId("");
        setInspectUsername("");
        setUserManagerUserInspect(null);
        setUserManagerPreviews(null);
        setUserManagerPreviewRuns([]);
        setSelectedPreviewRunId("");
      }
      setRouterConnectionProbe(null);
      setUserManagerProbe(null);
      await loadRouters();
      setNotice("تم حذف الراوتر بعد التحقق من عدم ارتباطه بسجلات محفوظة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر حذف الراوتر");
    } finally { setBusy(false); }
  }

  async function loadCardTemplates() {
    const result = await apiRequest<CardTemplate[]>(token, "/api/v1/card-templates");
    setCardTemplates(result);
    if (result.length) {
      const selected = result.find((item) => item.code === printTemplate)
        ?? result.find((item) => item.is_default)
        ?? result[0];
      setPrintTemplate(selected.code);
      if (selected.plan_id) {
        setBatchDraft((current) => ({ ...current, planId: String(selected.plan_id) }));
        setSingleDraft((current) => ({ ...current, planId: String(selected.plan_id) }));
      }
    }
  }

  async function loadCards(search = cardSearch, offset = cardOffset, batchId = cardBatchFilter, statusFilter = cardStatusFilter, planFilter = cardPlanFilter, freeFilter = cardFreeFilter) {
    if (user.card_visibility === "search_any" && !search.trim()) {
      setCards([]);
      setHasMoreCards(false);
      return;
    }
    const params = new URLSearchParams({ offset: String(offset), limit: "200" });
    if (search.trim()) params.set("search", search.trim());
    if (batchId) params.set("batch_id", batchId);
    if (statusFilter) params.set("status", statusFilter);
    if (planFilter) params.set("plan_id", planFilter);
    if (freeFilter) params.set("is_free", freeFilter === "free" ? "true" : "false");
    const result = await apiRequest<Card[]>(token, `/api/v1/cards?${params.toString()}`);
    setCards(result);
    setHasMoreCards(result.length === 200);
  }

  function applyCardSearch() {
    setCardOffset(0);
    setSelectedCardIds([]);
    setCardSessionHistory(null);
    loadCards(cardSearch, 0, user.card_visibility !== "search_any" ? cardBatchFilter : "", cardStatusFilter, cardPlanFilter, cardFreeFilter)
      .catch((err) => setError(err instanceof Error ? err.message : "تعذر البحث عن الكروت"));
  }

  function toggleSelectedCard(cardId: string) {
    setSelectedCardIds((current) => current.includes(cardId) ? current.filter((id) => id !== cardId) : [...current, cardId]);
  }

  function prepareSelectedCardsForPrinting() {
    const eligible = cards.filter((card) => selectedCardIds.includes(card.id) && card.status === "generated" && card.assigned_pos_id === null);
    if (!eligible.length) { setError("حدد كروتاً منشأة وغير مخصصة للطباعة الأصلية."); return; }
    if (eligible.length !== selectedCardIds.length) { setError("تغيّرت نتائج التحديد؛ أعد تحديد الكروت المؤهلة في الصفحة الحالية."); return; }
    setSelectedPrintCardIds(eligible.map((card) => card.id));
    setPage("pos");
    setNotice("تم تجهيز الكروت المحددة. اختر نقطة البيع لمتابعة الطباعة.");
  }

  function changeCardPage(nextOffset: number) {
    const safeOffset = Math.max(0, nextOffset);
    setCardOffset(safeOffset);
    setSelectedCardIds([]);
    loadCards(cardSearch, safeOffset, cardBatchFilter, cardStatusFilter, cardPlanFilter, cardFreeFilter).catch((err) =>
      setError(err instanceof Error ? err.message : "تعذر تحميل صفحة الكروت")
    );
  }

  async function loadPosInventory(pointId: string) {
    if (!pointId) { setPosInventory(null); return; }
    const result = await apiRequest<PosInventory>(token, `/api/v1/points-of-sale/${pointId}/inventory`);
    setPosInventory(result);
  }

  async function loadPosReport(from = reportFrom, to = reportTo) {
    const result = await apiRequest<PosReport>(
      token,
      `/api/v1/reports/points-of-sale?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}`,
    );
    setPosReport(result);
  }

  async function loadPosStatement(pointId = statementPointId, from = reportFrom, to = reportTo) {
    if (!pointId) { setPosStatement(null); return; }
    const result = await apiRequest<PosStatement>(
      token,
      `/api/v1/reports/points-of-sale/${pointId}/statement?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}`,
    );
    setPosStatement(result);
  }

  async function loadReportData(from = reportFrom, to = reportTo) {
    const query = "date_from=" + encodeURIComponent(from) + "&date_to=" + encodeURIComponent(to);
    const requests: Promise<unknown>[] = [];
    const keys: string[] = [];
    if (can("cards.view")) { keys.push("cards"); requests.push(apiRequest<CardsReportData>(token, "/api/v1/reports/cards?" + query)); }
    if (can("sessions.view")) { keys.push("sessions"); requests.push(apiRequest<SessionsReportData>(token, "/api/v1/reports/sessions?" + query)); }
    if (can("cards.view")) {
      keys.push("batches"); requests.push(apiRequest<BatchesReportData>(token, "/api/v1/reports/batches?" + query));
    }
    if (can("printing.view")) {
      keys.push("printing"); requests.push(apiRequest<PrintingReportData>(token, "/api/v1/reports/printing?" + query));
    }
    if (can("finance.view")) {
      keys.push("finance"); requests.push(apiRequest<PosReport>(token, "/api/v1/reports/points-of-sale?" + query));
    }
    const results = await Promise.all(requests);
    const data = Object.fromEntries(keys.map((key, index) => [key, results[index]]));
    if (data.cards) setCardsReport(data.cards as CardsReportData);
    if (data.sessions) setSessionsReport(data.sessions as SessionsReportData);
    if (data.batches) setBatchesReport(data.batches as BatchesReportData);
    if (data.printing) setPrintingReport(data.printing as PrintingReportData);
    if (data.finance) {
      const financeData = data.finance as PosReport;
      setPosReport(financeData);
      const currentPoint = statementPointId && financeData.points.some((point) => String(point.point_of_sale_id) === statementPointId)
        ? statementPointId
        : String(financeData.points[0]?.point_of_sale_id ?? "");
      setStatementPointId(currentPoint);
      if (currentPoint) await loadPosStatement(currentPoint, from, to);
      else setPosStatement(null);
    }
  }

  async function downloadProtectedFile(path: string, filename: string) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      let message = "تعذر تنزيل الملف";
      try { const data = await response.json(); if (typeof data.detail === "string") message = data.detail; } catch { /* ignore non-JSON error */ }
      throw new Error(message);
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
  }

  async function loadPosAccount(pointId: string) {
    if (!pointId) { setPosAccount(null); setPosEntries([]); return; }
    const [summary, entries] = await Promise.all([
      apiRequest<PosAccountSummary>(token, `/api/v1/points-of-sale/${pointId}/account`),
      apiRequest<PosAccountEntry[]>(token, `/api/v1/points-of-sale/${pointId}/account/entries?limit=100`),
    ]);
    setPosAccount(summary);
    setPosEntries(entries);
  }

  async function createAccountEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!can("finance.create")) { setError("ليست لديك صلاحية تسجيل الحركات المالية."); return; }
    if (!selectedPosId || Number(accountDraft.amount) <= 0) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<PosAccountEntry>(token, `/api/v1/points-of-sale/${selectedPosId}/account/entries`, {
        method: "POST",
        body: JSON.stringify({
          idempotency_key: `pos-entry-${crypto.randomUUID()}`,
          entry_type: accountDraft.entryType,
          direction: accountDraft.direction,
          amount: accountDraft.amount,
          description: accountDraft.description || null,
          reference: accountDraft.reference || null,
        }),
      });
      setAccountDraft({ amount: "", entryType: "payment", direction: "credit", description: "", reference: "" });
      await loadPosAccount(selectedPosId);
      setNotice("تم تسجيل الحركة المالية وتحديث كشف الحساب.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تسجيل الحركة المالية");
    } finally { setBusy(false); }
  }

  async function loadPrintHistory(pointId: string) {
    if (!pointId) { setPrintHistory([]); return; }
    const result = await apiRequest<PrintJobHistory[]>(token, `/api/v1/print-jobs?point_of_sale_id=${pointId}&limit=30`);
    setPrintHistory(result);
  }

  async function loadPointsOfSale() {
    const result = await apiRequest<PointOfSale[]>(token, "/api/v1/points-of-sale?include_inactive=true");
    setPoints(result);
    const current = selectedPosId && result.some((point) => String(point.id) === selectedPosId)
      ? selectedPosId
      : (result.find((point) => point.is_active)?.id ?? result[0]?.id)?.toString() ?? "";
    setSelectedPosId(current);
    const requests: Promise<unknown>[] = [];
    if (can("pos.view")) requests.push(loadPosInventory(current));
    if (can("printing.view")) requests.push(loadPrintHistory(current));
    if (can("finance.view")) requests.push(loadPosAccount(current));
    await Promise.all(requests);
  }

  async function createPointOfSale(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingPosId !== null ? !can("pos.update") : !can("pos.create")) { setError("ليست لديك صلاحية هذه العملية على نقاط البيع."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const pointSettings = user.roles.includes("owner") ? {
        debt_limit: posDraft.debtLimit.trim() ? Number(posDraft.debtLimit) : null,
        allow_card_creation: posDraft.allowCardCreation,
        allow_printing: posDraft.allowPrinting,
      } : {};
      const point = editingPosId
        ? await apiRequest<PointOfSale>(token, `/api/v1/points-of-sale/${editingPosId}`, {
            method: "PATCH",
            body: JSON.stringify({ name: posDraft.name, contact_name: posDraft.contactName || null, phone: posDraft.phone || null, ...pointSettings }),
          })
        : await apiRequest<PointOfSale>(token, "/api/v1/points-of-sale", {
            method: "POST",
            body: JSON.stringify({ code: posDraft.code, name: posDraft.name, contact_name: posDraft.contactName || null, phone: posDraft.phone || null, ...pointSettings }),
          });
      setPosDraft({ code: "", name: "", contactName: "", phone: "", debtLimit: "", allowCardCreation: true, allowPrinting: true });
      setEditingPosId(null);
      await loadPointsOfSale();
      setSelectedPosId(String(point.id));
      const refreshes: Promise<unknown>[] = [loadPosInventory(String(point.id))];
      if (can("printing.view")) refreshes.push(loadPrintHistory(String(point.id)));
      if (can("finance.view")) refreshes.push(loadPosAccount(String(point.id)));
      await Promise.all(refreshes);
      setNotice(editingPosId ? "تم تحديث نقطة البيع." : "تم إنشاء نقطة البيع بنجاح.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء نقطة البيع");
    } finally { setBusy(false); }
  }

  async function togglePointOfSale(point: PointOfSale) {
    if (!user.roles.includes("owner")) { setError("إيقاف نقاط البيع متاح لمدير النظام فقط."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<PointOfSale>(token, `/api/v1/points-of-sale/${point.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !point.is_active }),
      });
      await loadPointsOfSale();
      setNotice(point.is_active ? "تم إيقاف نقطة البيع." : "تم تفعيل نقطة البيع.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تغيير حالة نقطة البيع");
    } finally { setBusy(false); }
  }

  async function togglePointOperation(point: PointOfSale, field: "allow_card_creation" | "allow_printing") {
    if (!user.roles.includes("owner")) { setError("تغيير إعدادات تشغيل نقطة البيع متاح لمدير النظام فقط."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<PointOfSale>(token, `/api/v1/points-of-sale/${point.id}`, {
        method: "PATCH",
        body: JSON.stringify({ [field]: !point[field] }),
      });
      await loadPointsOfSale();
      setNotice(field === "allow_card_creation"
        ? (!point.allow_card_creation ? "تم السماح بإنشاء الكروت لهذه النقطة." : "تم إيقاف إنشاء الكروت لهذه النقطة.")
        : (!point.allow_printing ? "تم السماح بالطباعة لهذه النقطة." : "تم إيقاف الطباعة لهذه النقطة."));
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تحديث صلاحية نقطة البيع");
    } finally { setBusy(false); }
  }

  function togglePrintCard(cardId: string) {
    setSelectedPrintCardIds((current) => {
      if (current.includes(cardId)) return current.filter((id) => id !== cardId);
      if (printMode === "single") return [cardId];
      if (current.length >= 5000) {
        setError("الحد الأقصى لعملية الطباعة الواحدة هو 5000 كرت.");
        return current;
      }
      return [...current, cardId];
    });
  }

  async function importPrintSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(""); setNotice(""); setPrintImportSummary("");
    try {
      if (!selectedPosId) throw new Error("اختر نقطة البيع قبل استيراد ملف الكروت.");
      const content = await file.text();
      const values = Array.from(new Set(content.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
        .map((line) => line.split(/[;,\t]/)[0].trim().replace(/^["']|["']$/g, ""))
        .filter((value) => value && !["username", "user", "serial", "serial_number", "اسم المستخدم", "الرقم التسلسلي"].includes(value.toLowerCase())))).slice(0, 5000);
      if (values.length === 0) throw new Error("الملف لا يحتوي أسماء مستخدمين أو أرقاماً تسلسلية صالحة.");
      const result = await apiRequest<CardPrintSelectionResolveResponse>(token, "/api/v1/cards/print-selection/resolve", {
        method: "POST",
        body: JSON.stringify({ identifiers: values, point_of_sale_id: Number(selectedPosId) }),
      });
      const matched = result.items.map((item) => item.id);
      setSelectedPrintCardIds(matched);
      const unmatchedPreview = result.unmatched.slice(0, 10).join("، ");
      setPrintImportSummary(`تم العثور على ${result.matched_count} كرت من أصل ${result.total_requested} قيمة بعد البحث في قاعدة البيانات كاملة. غير المطابق أو غير المؤهل للطباعة: ${result.unmatched.length}.${unmatchedPreview ? ` أول القيم غير المطابقة: ${unmatchedPreview}` : ""}`);
      setPrintMode("file");
      if (matched.length === 0) setError("لم يتم العثور على كروت مؤهلة للطباعة في نقطة البيع المحددة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر قراءة الملف. استخدم CSV أو TXT يحتوي اسم مستخدم أو رقماً تسلسلياً في العمود الأول.");
    } finally {
      event.target.value = "";
    }
  }

  async function reprintJob(job: PrintJobHistory) {
    if (!can("printing.reprint") || !can("printing.credentials")) { setError("تتطلب إعادة الطباعة صلاحية إعادة الطباعة وعرض بيانات الدخول."); return; }
    if (!selectedPosId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<PrintJobResult>(token, "/api/v1/print-jobs", {
        method: "POST",
        body: JSON.stringify({
          idempotency_key: `reprint-${crypto.randomUUID()}`,
          point_of_sale_id: Number(selectedPosId),
          card_ids: job.cards.map((card) => card.card_id),
          template_code: job.template_code ?? "classic-green",
          is_reprint: true,
          print_options: job.print_options,
        }),
      });
      setPrintTemplate(job.template_code ?? "classic-green");
      setPrintOptions(Object.assign({ show_username: true, show_password: true, show_serial_number: true, show_plan: true, show_price: true, show_limits: true, sequential: false }, job.print_options));
      setPrintPreviewCards(result.items);
      await loadPrintHistory(selectedPosId);
      setNotice(`تم تسجيل إعادة طباعة ${result.card_count} كرت دون إضافة قيمة تجارية جديدة.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذرت إعادة الطباعة");
    } finally { setBusy(false); }
  }

  async function printSelectedCards() {
    if (!can("printing.create") || !can("printing.credentials")) { setError("تتطلب الطباعة صلاحية تنفيذ الطباعة وعرض بيانات دخول الكروت."); return; }
    if (!selectedPosId || selectedPrintCardIds.length === 0) {
      setError("اختر نقطة البيع وكرتاً واحداً على الأقل.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<PrintJobResult>(token, "/api/v1/print-jobs", {
        method: "POST",
        body: JSON.stringify({
          idempotency_key: `print-${crypto.randomUUID()}`,
          point_of_sale_id: Number(selectedPosId),
          card_ids: selectedPrintCardIds,
          template_code: printTemplate,
          is_reprint: false,
          print_options: printOptions,
        }),
      });
      setSelectedPrintCardIds([]);
      setPrintTemplate(result.template_code || printTemplate);
      setPrintOptions(Object.assign({ show_username: true, show_password: true, show_serial_number: true, show_plan: true, show_price: true, show_limits: true, sequential: false }, result.print_options));
      setPrintPreviewCards(result.items);
      await Promise.all([loadCards(), loadPosInventory(selectedPosId), loadPrintHistory(selectedPosId), loadPosAccount(selectedPosId)]);
      setNotice(`تم تسجيل طباعة ${result.card_count} كرت: ${result.commercial_card_count} تجاري و${result.free_card_count} مجاني. القيمة التجارية: ${Number(result.total_amount).toFixed(2)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تنفيذ الطباعة");
    } finally { setBusy(false); }
  }

  useEffect(() => {
    if (page !== "pos") setPrintPreviewCards([]);
    if (page === "audit" && can("audit.view")) {
      setError("");
      loadAuditLogs(0).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل سجل العمليات"));
    }
    if (page === "settings" && user.roles.includes("owner")) {
      setError("");
      loadSystemStatus().catch(() => setError("تعذر فحص حالة النظام."));
    }
    if (page === "admins" && user.roles.includes("owner")) {
      setError("");
      loadAdminAccounts().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل حسابات الإدارة"));
    }
    if (page === "overview" && can("cards.view")) {
      setError("");
      loadRadiusOverview().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل لوحة المعلومات"));
    }
    if ((page === "pos" || page === "templates" || page === "card-create") && can("templates.view")) {
      loadCardTemplates().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل قوالب الطباعة"));
    }
    if (page === "templates") setError("");
    if (page === "batches" && can("cards.view")) {
      setError("");
      loadCardBatches().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل دفعات الكروت"));
    }
    if (page === "card-create" && can("cards.view")) {
      loadCardBatches().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل الدفعات السابقة"));
    }
    if (page === "reports" && (can("reports.view") || can("finance.view"))) {
      setError("");
      loadReportData().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل التقارير"));
    }
    const requests: Promise<unknown>[] = [];
    if ((page === "plans" || page === "templates" || page === "card-create" || page === "pos") && can("plans.view")) requests.push(loadPlans());
    if (page === "cards" && can("cards.view")) requests.push(loadCards());
    if ((page === "pos" || page === "pos-management" || page === "card-create") && can("pos.view")) requests.push(loadPointsOfSale());
    if (page === "routers" && can("routers.view")) requests.push(loadRouters());
    if (requests.length) {
      setError("");
      Promise.all(requests).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل البيانات"));
    }
    // Data is refreshed when the selected section changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, token]);

  async function createPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingPlanId !== null ? !can("plans.update") : !can("plans.create")) { setError("ليست لديك صلاحية هذه العملية على الباقات."); return; }
    setBusy(true); setError(""); setNotice("");
    const numberOrNull = (value: string, multiplier: number) =>
      value.trim() === "" ? null : Math.round(Number(value) * multiplier);
    try {
      const payload = {
        code: planDraft.code,
        name: planDraft.name,
        price: Number(planDraft.price),
        commission_type: planDraft.commissionType,
        commission_value: planDraft.commissionType === "none" ? 0 : Number(planDraft.commissionValue),
        data_limit_bytes: numberOrNull(planDraft.dataAmount, planDraft.dataUnit === "MB" ? 1024 ** 2 : 1024 ** 3),
        session_time_limit_seconds: numberOrNull(planDraft.timeHours, 3600),
        validity_period_seconds: numberOrNull(planDraft.validityDays, 86400),
        speed_profile: planDraft.speedProfile || null,
        settings: {
          shared_users: planDraft.sharedUsers.trim() === "" ? null : Number(planDraft.sharedUsers),
          group: planDraft.groupName || null,
          rate_limit_rx: planDraft.rateRx || null,
          rate_limit_tx: planDraft.rateTx || null,
          rate_limit_unit: planDraft.rateUnit,
          schedule: { enabled: planDraft.scheduleEnabled, days: planDraft.scheduleDays, from: planDraft.scheduleFrom, to: planDraft.scheduleTo },
          notifications: { enabled: planDraft.notificationsEnabled, remaining_percent: Number(planDraft.notifyRemaining), exhausted_percent: Number(planDraft.notifyExhausted) },
        },
      };
      await apiRequest<Plan>(token, editingPlanId ? `/api/v1/plans/${editingPlanId}` : "/api/v1/plans", {
        method: editingPlanId ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      setPlanDraft({ code: "", name: "", price: "", commissionType: "none", commissionValue: "", dataAmount: "", dataUnit: "GB", timeHours: "", validityDays: "", speedProfile: "", sharedUsers: "", groupName: "", rateRx: "", rateTx: "", rateUnit: "Kbps", scheduleEnabled: false, scheduleDays: ["0","1","2","3","4","5","6"], scheduleFrom: "00:00", scheduleTo: "23:59", notificationsEnabled: false, notifyRemaining: "70", notifyExhausted: "95" });
      const wasEditing = editingPlanId !== null;
      setEditingPlanId(null);
      setPlanEditorOpen(false);
      await loadPlans();
      setNotice(wasEditing ? "تم تحديث الباقة بنجاح." : "تم إنشاء الباقة بنجاح.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر حفظ الباقة");
    } finally {
      setBusy(false);
    }
  }

  function editPlan(plan: Plan) {
    setEditingPlanId(plan.id);
    setPlanEditorOpen(true);
    setPlanDraft({
      code: plan.code,
      name: plan.name,
      price: String(plan.price),
      commissionType: plan.commission_type,
      commissionValue: plan.commission_type === "none" ? "" : String(plan.commission_value),
      dataAmount: plan.data_limit_bytes === null ? "" : String(plan.data_limit_bytes / (plan.data_limit_bytes % (1024 ** 3) === 0 ? 1024 ** 3 : 1024 ** 2)),
      dataUnit: plan.data_limit_bytes !== null && plan.data_limit_bytes % (1024 ** 3) !== 0 ? "MB" : "GB",
      timeHours: plan.session_time_limit_seconds === null ? "" : String(plan.session_time_limit_seconds / 3600),
      validityDays: plan.validity_period_seconds === null ? "" : String(plan.validity_period_seconds / 86400),
      speedProfile: plan.speed_profile ?? "",
      sharedUsers: plan.settings?.shared_users == null ? "" : String(plan.settings.shared_users),
      groupName: String(plan.settings?.group ?? ""),
      rateRx: String(plan.settings?.rate_limit_rx ?? ""),
      rateTx: String(plan.settings?.rate_limit_tx ?? ""),
      rateUnit: plan.settings?.rate_limit_unit === "Mbps" ? "Mbps" : "Kbps",
      scheduleEnabled: Boolean((plan.settings?.schedule as Record<string, unknown> | undefined)?.enabled),
      scheduleDays: Array.isArray((plan.settings?.schedule as Record<string, unknown> | undefined)?.days) ? (plan.settings?.schedule as { days: string[] }).days : ["0","1","2","3","4","5","6"],
      scheduleFrom: String((plan.settings?.schedule as Record<string, unknown> | undefined)?.from ?? "00:00"),
      scheduleTo: String((plan.settings?.schedule as Record<string, unknown> | undefined)?.to ?? "23:59"),
      notificationsEnabled: Boolean((plan.settings?.notifications as Record<string, unknown> | undefined)?.enabled),
      notifyRemaining: String((plan.settings?.notifications as Record<string, unknown> | undefined)?.remaining_percent ?? 70),
      notifyExhausted: String((plan.settings?.notifications as Record<string, unknown> | undefined)?.exhausted_percent ?? 95),
    });
    setError("");
    setNotice("أنت تعدّل بيانات الباقة المحددة.");
  }

  async function togglePlan(plan: Plan) {
    if (!can("plans.update")) { setError("ليست لديك صلاحية تعديل الباقات."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<Plan>(token, `/api/v1/plans/${plan.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !plan.is_active }),
      });
      await loadPlans();
      setNotice(plan.is_active ? "تم إيقاف الباقة. لن تظهر عند إنشاء كروت جديدة." : "تم تفعيل الباقة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تغيير حالة الباقة");
    } finally {
      setBusy(false);
    }
  }

  async function deletePlan(plan: Plan) {
    if (!can("plans.delete")) { setError("ليست لديك صلاحية حذف الباقات."); return; }
    if (plan.is_active) { setError("أوقف الباقة أولاً قبل حذفها."); return; }
    if (!window.confirm(`حذف الباقة ${plan.name}؟ لا يمكن حذف باقة مرتبطة بكروت أو دفعات أو قوالب محفوظة.`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<void>(token, `/api/v1/plans/${plan.id}`, { method: "DELETE" });
      await loadPlans();
      setNotice("تم حذف الباقة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر حذف الباقة");
    } finally {
      setBusy(false);
    }
  }

  async function changeCardStatus(card: Card, action: "suspend" | "reactivate" | "cancel") {
    if (!can("cards.update")) { setError("ليست لديك صلاحية تعديل الكروت."); return; }
    const labels = { suspend: "إيقاف", reactivate: "إعادة تفعيل", cancel: "إلغاء" };
    if (action === "cancel" && !window.confirm("هل تريد إلغاء هذا الكرت نهائياً؟")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<Card>(token, `/api/v1/cards/${card.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ action }),
      });
      await loadCards();
      setNotice(`تم ${labels[action]} الكرت ${card.username}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تغيير حالة الكرت");
    } finally {
      setBusy(false);
    }
  }

  async function createSingle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!can("cards.create")) { setError("ليست لديك صلاحية إنشاء الكروت."); return; }
    const selectedTemplate = cardTemplates.find((item) => item.code === printTemplate);
    const linkedPlan = selectedTemplate?.plan_id ? plans.find((plan) => plan.id === selectedTemplate.plan_id && plan.is_active) : undefined;
    if (!selectedTemplate || !linkedPlan) { setError("اختر قالباً مرتبطاً بباقة مفعّلة قبل إنشاء الكرت."); return; }
    setBusy(true); setError(""); setNotice(""); setGeneratedCards([]);
    try {
      const result = await apiRequest<{ id: string; batch_id: string; batch_number: string; serial_number: string; username: string; password: string | null }> (token, "/api/v1/cards/single", {
        method: "POST",
        body: JSON.stringify({
          plan_id: linkedPlan.id,
          username: singleDraft.username,
          card_type: singleDraft.cardType,
          password: singleDraft.cardType === "separate_credentials" ? singleDraft.password : null,
          is_free: singleDraft.isFree,
          template_code: printTemplate,
          point_of_sale_id: selectedPosId ? Number(selectedPosId) : null,
        }),
      });
      setGeneratedCards([{ id: result.id, serial_number: result.serial_number, username: result.username, password: result.password }]);
      setGeneratedBatchNumber(result.batch_number);
      setSelectedPrintCardIds([result.id]);
      if (can("cards.view")) await loadCards();
      setNotice(can("cards.credentials") ? "تم إنشاء الكرت. احفظ بيانات الدخول الآن؛ لن تظهر كلمة المرور مرة أخرى." : "تم إنشاء الكرت. لم تُعرض كلمة المرور لأن حسابك لا يملك صلاحية بيانات الدخول.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء الكرت");
    } finally {
      setBusy(false);
    }
  }

  async function createBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!can("cards.create")) { setError("ليست لديك صلاحية إنشاء دفعات الكروت."); return; }
    const selectedTemplate = cardTemplates.find((item) => item.code === printTemplate);
    const linkedPlan = selectedTemplate?.plan_id ? plans.find((plan) => plan.id === selectedTemplate.plan_id && plan.is_active) : undefined;
    if (!selectedTemplate || !linkedPlan) { setError("اختر قالباً مرتبطاً بباقة مفعّلة قبل إنشاء الدفعة."); return; }
    setBusy(true); setError(""); setNotice(""); setGeneratedCards([]);
    try {
      const result = await apiRequest<{ batch_id: string; batch_number: string; plan_id: number; template_code: string | null; point_of_sale_id: number | null; created_count: number; cards: GeneratedCard[] }>(token, "/api/v1/cards/batch", {
        method: "POST",
        body: JSON.stringify({
          plan_id: linkedPlan.id,
          quantity: Number(batchDraft.quantity),
          card_type: batchDraft.cardType,
          generation_mode: batchDraft.generationMode,
          username_length: Number(batchDraft.usernameLength),
          password_length: Number(batchDraft.passwordLength),
          prefix: batchDraft.prefix,
          template_code: printTemplate,
          point_of_sale_id: selectedPosId ? Number(selectedPosId) : null,
          existing_batch_number: batchDraft.batchMode === "existing" ? batchDraft.existingBatchNumber.trim() : null,
          is_online_sale: batchDraft.isOnlineSale,
          note: batchDraft.note.trim() || null,
        }),
      });
      setGeneratedCards(result.cards);
      setGeneratedBatchNumber(result.batch_number);
      setSelectedPrintCardIds(result.cards.map((card) => card.id));
      if (can("cards.view")) await Promise.all([loadCards(), loadCardBatches()]);
      setNotice(can("cards.credentials") ? `تم إنشاء ${result.created_count} كرت ${batchDraft.batchMode === "existing" ? "وربطها بالدفعة السابقة" : "في دفعة جديدة"}. احفظ بيانات الدخول الآن؛ لن تظهر كلمات المرور مرة أخرى.` : `تم إنشاء ${result.created_count} كرت. لم تُعرض كلمات المرور لأن حسابك لا يملك صلاحية بيانات الدخول.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء الدفعة");
    } finally {
      setBusy(false);
    }
  }

  function renderAdmins() {
    return (
      <div className="admin-management-workspace">
        <div className="section-heading">
          <div><h2>حسابات الإدارة والموظفين</h2><p>إنشاء حسابات دخول مستقلة وتحديد الدور الإداري لكل حساب.</p></div>
          <span className="count-tag">{adminAccounts.length.toLocaleString("ar")} حساب</span>
        </div>
        <div className="notice">يمكنك إنشاء أدوار وظيفية، ثم تخصيص صلاحيات كل موظف على حدة: السماح أو المنع أو اتباع صلاحيات الدور، مع تحديد نطاق ظهور الكروت ونقاط البيع.</div>
        <div className="admin-summary-grid">
          <article><span>إجمالي الحسابات</span><strong>{adminAccounts.length.toLocaleString("ar")}</strong><small>حسابات الإدارة المسجلة</small></article>
          <article><span>حسابات مفعّلة</span><strong>{adminAccounts.filter((account) => account.is_active).length.toLocaleString("ar")}</strong><small>يمكنها تسجيل الدخول</small></article>
          <article><span>حسابات متوقفة</span><strong>{adminAccounts.filter((account) => !account.is_active).length.toLocaleString("ar")}</strong><small>لا يمكنها تسجيل الدخول</small></article>
          <article><span>الأدوار الوظيفية</span><strong>{adminRoles.length.toLocaleString("ar")}</strong><small>الأدوار المعرفة في النظام</small></article>
        </div>
        <form className="panel form-grid admin-create-form" onSubmit={createAdminRole}>
          <div className="section-heading"><div><h3>إنشاء دور وظيفي جديد</h3><p>مثال: موظف نقاط البيع، محاسب، مسؤول طباعة.</p></div></div>
          <label>رمز الدور بالإنجليزية<input value={roleDraft.code} onChange={(event) => setRoleDraft({ ...roleDraft, code: event.target.value })} minLength={3} maxLength={60} pattern="[a-z][a-z0-9_]+" placeholder="pos_staff" required /></label>
          <label>اسم الدور بالعربية<input value={roleDraft.name} onChange={(event) => setRoleDraft({ ...roleDraft, name: event.target.value })} minLength={2} maxLength={120} required /></label>
          <label>وصف العمل<input value={roleDraft.description} onChange={(event) => setRoleDraft({ ...roleDraft, description: event.target.value })} maxLength={500} placeholder="المهام المسموحة لهذا الدور" /></label>
          <div className="form-actions"><button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ..." : "إنشاء الدور"}</button></div>
        </form>
        <form className="panel form-grid admin-create-form" onSubmit={createAdminAccount}>
          <div className="section-heading"><div><h3>إضافة حساب جديد</h3><p>كلمة المرور يجب ألا تقل عن 12 حرفاً.</p></div></div>
          <label>اسم المستخدم<input value={adminDraft.username} onChange={(event) => setAdminDraft({ ...adminDraft, username: event.target.value })} minLength={3} maxLength={80} pattern="[A-Za-z0-9_.-]+" autoComplete="off" required /></label>
          <label>اسم الموظف<input value={adminDraft.displayName} onChange={(event) => setAdminDraft({ ...adminDraft, displayName: event.target.value })} minLength={2} maxLength={150} required /></label>
          <label>كلمة المرور<input type="password" value={adminDraft.password} onChange={(event) => setAdminDraft({ ...adminDraft, password: event.target.value })} minLength={12} maxLength={256} autoComplete="new-password" required /></label>
          <label>الدور الإداري<select value={adminDraft.roleCode} onChange={(event) => setAdminDraft({ ...adminDraft, roleCode: event.target.value })} required>{adminRoles.filter((role) => role.code !== "owner").map((role) => <option key={role.code} value={role.code}>{role.name}</option>)}</select></label>
          <label>نقاط البيع المسموح بها <small>يمكن اختيار أكثر من نقطة، والموظف يرى كروتها فقط.</small><select multiple value={adminDraft.pointOfSaleIds.map(String)} onChange={(event) => {
            const pointOfSaleIds = Array.from(event.target.selectedOptions, (option) => Number(option.value));
            setAdminDraft({
              ...adminDraft,
              pointOfSaleIds,
              cardVisibility: pointOfSaleIds.length > 0 && adminDraft.cardVisibility === "search_any"
                ? "assigned"
                : pointOfSaleIds.length === 0 && adminDraft.cardVisibility === "assigned"
                  ? "search_any"
                  : adminDraft.cardVisibility,
            });
          }} size={Math.min(5, Math.max(2, points.length))}>{points.map((point) => <option key={point.id} value={point.id} disabled={!point.is_active}>{point.name}{point.is_active ? "" : " (متوقفة)"}</option>)}</select></label>
          <label>نطاق ظهور الكروت
            <select value={adminDraft.cardVisibility} onChange={(event) => setAdminDraft({ ...adminDraft, cardVisibility: event.target.value as CardVisibility })}>
              <option value="search_any">البحث عن كرت محدد من أي نقطة بيع</option>
              <option value="assigned">كروت نقاط البيع المرتبطة فقط</option>
              <option value="all">جميع كروت النظام</option>
            </select>
          </label>
          <div className="form-actions"><button type="submit" disabled={busy || adminRoles.length === 0}>{busy ? "جارٍ الحفظ..." : "إنشاء حساب"}</button></div>
        </form>
        <section className="panel admin-permission-matrix">
          <div className="section-heading"><div><h3>مصفوفة صلاحيات الأدوار</h3><p>حدد العرض والإضافة والتعديل والحذف حيث تدعمها الواجهة. صلاحية إدارة القسم تشمل عملياته المتاحة؛ وعند تعديل عملية مفردة تتحول إلى صلاحيات تفصيلية. لا يمكن تعديل دور مدير النظام.</p></div></div>
          <label className="permission-role-picker">الدور الإداري
            <select value={selectedPermissionRole} onChange={(event) => selectPermissionRole(event.target.value)}>
              {adminRoles.filter((role) => role.code !== "owner").map((role) => <option key={role.code} value={role.code}>{role.name}</option>)}
            </select>
          </label>
          <div className="permission-groups">
            {Object.entries(adminPermissions.reduce<Record<string, AdminPermission[]>>((groups, permission) => {
              (groups[permission.module] ??= []).push(permission); return groups;
            }, {})).map(([module, permissions]) => (
              <div className="permission-group" key={module}>
                <h4>{{cards:"الكروت",templates:"تصاميم الكروت",audit:"سجل العمليات",sessions:"الجلسات",plans:"الباقات",routers:"الراوترات",pos:"نقاط البيع",finance:"الحسابات المالية",reports:"التقارير",printing:"الطباعة"}[module] ?? module}</h4>
                {permissions.map((permission) => (
                  <label className="permission-option" key={permission.code}>
                    <input type="checkbox" checked={isRolePermissionChecked(permission.code)} disabled={busy}
                      onChange={(event) => toggleRolePermission(permission.code, event.target.checked)} />
                    <span><strong>{permission.name}</strong><small>{permission.description}</small></span>
                  </label>
                ))}
              </div>
            ))}
          </div>
          <div className="form-actions"><button type="button" onClick={saveRolePermissions} disabled={busy || !selectedPermissionRole}>{busy ? "جارٍ الحفظ..." : "حفظ صلاحيات الدور"}</button></div>
        </section>
        <section className="panel admin-directory">
          <div className="section-heading"><div><h3>الحسابات المسجلة</h3><p>يمكن تغيير دور الحساب أو إيقافه دون حذف سجله.</p></div><button type="button" className="table-action" onClick={() => loadAdminAccounts().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحديث الحسابات"))}>تحديث</button></div>
          <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>المستخدم</th><th>اسم الموظف</th><th>الدور الحالي</th><th>نطاق الكروت</th><th>نقاط البيع المسموحة</th><th>آخر دخول</th><th>الحالة</th><th>الإجراءات</th></tr></thead>
            <tbody>{adminAccounts.map((account) => <tr key={account.id}>
              <td><strong dir="ltr">{account.username}</strong></td><td>{account.display_name}</td>
              <td><select aria-label={`دور ${account.username}`} value={account.roles[0] ?? "viewer"} onChange={(event) => updateAdminAccount(account, { role_codes: [event.target.value] })} disabled={busy || account.id === user.id}>
                {adminRoles.filter((role) => role.code !== "owner" || account.roles.includes("owner")).map((role) => <option key={role.code} value={role.code}>{role.name}</option>)}
              </select></td>
              <td>{account.card_visibility === "all" ? "جميع الكروت" : account.card_visibility === "assigned" ? "نقاطه فقط" : "بحث عن كرت محدد"}</td>
              <td><select aria-label={`نقاط البيع المسموحة لـ ${account.username}`} multiple size={Math.min(4, Math.max(2, points.length))} value={account.point_of_sale_ids.map(String)} onChange={(event) => updateAdminAccount(account, { point_of_sale_ids: Array.from(event.target.selectedOptions, (option) => Number(option.value)) })} disabled={busy || account.id === user.id}>{points.map((point) => <option key={point.id} value={point.id}>{point.name}</option>)}</select></td>
              <td>{account.last_login_at ? new Date(account.last_login_at).toLocaleString("ar") : "لم يسجل الدخول"}</td>
              <td><span className={account.is_active ? "admin-status active" : "admin-status inactive"}>{account.is_active ? "نشط" : "متوقف"}</span></td>
              <td className="actions-cell">
                <button type="button" className="table-action" disabled={busy || account.roles.includes("owner")} onClick={() => selectAdminForIndividualSettings(account)}>تخصيص الصلاحيات</button>
                <button type="button" className="table-action" disabled={busy || account.id === user.id} onClick={() => updateAdminAccount(account, { is_active: !account.is_active })}>{account.is_active ? "إيقاف الحساب" : "تفعيل الحساب"}</button>
              </td>
            </tr>)}</tbody></table></div>
          {adminAccounts.length === 0 && <div className="empty-state">لا توجد حسابات إدارة مسجلة.</div>}
        </section>
        {selectedAdminId !== null && (() => {
          const selectedAccount = adminAccounts.find((item) => item.id === selectedAdminId);
          if (!selectedAccount || selectedAccount.roles.includes("owner")) return null;
          return (
            <section className="panel admin-individual-permissions">
              <div className="section-heading">
                <div><h3>تخصيص صلاحيات الموظف: {selectedAccount.display_name}</h3><p>كل صلاحية يمكن أن تتبع الدور أو تسمح بها لهذا الموظف أو تمنعها عنه بشكل مستقل.</p></div>
                <button type="button" className="table-action" onClick={() => setSelectedAdminId(null)}>إغلاق</button>
              </div>
              <label>نطاق ظهور الكروت
                <select value={adminVisibilityDraft} onChange={(event) => setAdminVisibilityDraft(event.target.value as CardVisibility)}>
                  <option value="search_any">البحث عن كرت محدد من أي نقطة بيع</option>
                  <option value="assigned">كروت نقاط البيع المرتبطة فقط</option>
                  <option value="all">جميع كروت النظام</option>
                </select>
              </label>
              <div className="notice">نطاق الكروت لا يمنح الموظف صلاحية الطباعة أو إنشاء الكروت تلقائياً؛ يجب فتح صلاحية كل عملية بصورة مستقلة وربط نقطة البيع المناسبة. الطباعة تحتاج صلاحيات عرض الكروت ونقاط البيع مع صلاحية الطباعة.</div>
              <div className="permission-groups">
                {Object.entries(adminPermissions.reduce<Record<string, AdminPermission[]>>((groups, permission) => {
                  (groups[permission.module] ??= []).push(permission); return groups;
                }, {})).map(([module, permissions]) => (
                  <div className="permission-group" key={module}>
                    <h4>{{cards:"الكروت",templates:"تصاميم الكروت",audit:"سجل العمليات",sessions:"الجلسات",plans:"الباقات",routers:"الراوترات",pos:"نقاط البيع",finance:"الحسابات المالية",reports:"التقارير",printing:"الطباعة"}[module] ?? module}</h4>
                    {permissions.map((permission) => (
                      <label className="permission-option" key={permission.code}>
                        <span><strong>{permission.name}</strong><small>{permission.description}</small></span>
                        <select aria-label={`صلاحية ${permission.name} للموظف ${selectedAccount.username}`} value={adminOverrideDraft[permission.code] ?? "inherit"} disabled={busy}
                          onChange={(event) => setAdminOverrideDraft((current) => ({ ...current, [permission.code]: event.target.value as "inherit" | "allow" | "deny" }))}>
                          <option value="inherit">اتباع الدور</option>
                          <option value="allow">سماح لهذا الموظف</option>
                          <option value="deny">منع هذا الموظف</option>
                        </select>
                      </label>
                    ))}
                  </div>
                ))}
              </div>
              <div className="form-actions">
                <button type="button" onClick={saveAdminIndividualSettings} disabled={busy}>{busy ? "جارٍ الحفظ..." : "حفظ إعدادات الموظف"}</button>
                <button type="button" className="secondary-button" disabled={busy} onClick={() => { setAdminOverrideDraft({}); setAdminVisibilityDraft(selectedAccount.point_of_sale_ids.length > 0 ? "assigned" : "search_any"); }}>إعادة إلى الافتراضي</button>
              </div>
            </section>
          );
        })()}
      </div>
    );
  }

  function renderOverview() {
    const statusCount = (status: string) => radiusOverview?.cards_by_status[status] ?? 0;
    return (
      <>
        <section className="welcome-card" id="overview">
          <div>
            <span className="welcome-kicker">مرحباً بك، {user.display_name}</span>
            <h2>نظام الأسطورة لإدارة RADIUS</h2>
            <p>ملخص مباشر للمستخدمين والجلسات والكروت وأجهزة الشبكة.</p>
          </div>
          <div className="welcome-symbol">A</div>
        </section>
        <div className="overview-toolbar">
          <div><span className="overview-live-dot" /> {radiusOverview ? "تم جلب الإحصائيات من قاعدة البيانات" : "بانتظار تحميل الإحصائيات"}</div>
          <button type="button" className="table-action" disabled={overviewLoading} onClick={() => loadRadiusOverview().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحديث لوحة المعلومات"))}>{overviewLoading ? "جارٍ التحديث..." : "تحديث الإحصائيات"}</button>
        </div>
        <div className="section-heading"><div><h2>ملخص الشبكة والنظام</h2><p>الأعداد الفعلية المسجلة في قاعدة بيانات RADIUS.</p></div><span className="phase-tag">لوحة معلومات مباشرة</span></div>
        <div className="overview-stat-grid">
          {can("cards.view") && user.card_visibility !== "search_any" && <article><span>إجمالي المستخدمين / الكروت</span><strong>{(radiusOverview?.cards_total ?? 0).toLocaleString("ar")}</strong><small>{user.card_visibility === "all" ? "كل سجلات الكروت في النظام" : "كروت نقاط البيع المرتبطة بحسابك"}</small></article>}
          {can("sessions.view") && user.card_visibility !== "search_any" && <>
            <article><span>المستخدمون المتصلون (اكتف)</span><strong>{(radiusOverview?.active_users ?? 0).toLocaleString("ar")}</strong><small>مستخدمون فريدون ضمن نطاقك لديهم جلسة نشطة</small></article>
            <article><span>جلسات الاتصال النشطة</span><strong>{(radiusOverview?.active_sessions ?? 0).toLocaleString("ar")}</strong><small>جلسات ضمن نطاق الصلاحيات لم يصلها حدث إيقاف</small></article>
            <article><span>إجمالي الجلسات المسجلة</span><strong>{(radiusOverview?.sessions_total ?? 0).toLocaleString("ar")}</strong><small>سجل الجلسات ضمن نطاقك</small></article>
          </>}
          {can("routers.view") && <article><span>أجهزة الراوتر المسجلة</span><strong>{(radiusOverview?.routers_total ?? 0).toLocaleString("ar")}</strong><small>{(radiusOverview?.routers_enabled ?? 0).toLocaleString("ar")} مفعّلة إدارياً</small></article>}
          {can("plans.view") && <article><span>الباقات</span><strong>{(radiusOverview?.plans_total ?? 0).toLocaleString("ar")}</strong><small>{(radiusOverview?.plans_enabled ?? 0).toLocaleString("ar")} باقات مفعّلة</small></article>}
        </div>
        <div className="overview-lower-grid">
          <section className="panel overview-status-panel">
            <h3>حالة خدمات النظام</h3>
            <div className="overview-status-row"><span>واجهة API</span><strong className="status-ok">تستجيب للطلب</strong></div>
            <div className="overview-status-row"><span>قاعدة البيانات</span><strong className={radiusOverview?.database_status === "connected" ? "status-ok" : "status-unknown"}>{radiusOverview?.database_status === "connected" ? "متصلة" : radiusOverview ? "غير متاحة" : "لم يتم الفحص"}</strong></div>
            <p className="overview-disclaimer">هذه الحالة تؤكد استجابة API واتصال قاعدة البيانات وقت جلب الملخص، ولا تعني أن جميع أجهزة الراوتر متصلة فعلياً أو أن خدمة FreeRADIUS تم فحصها تشغيلياً.</p>
          </section>
          {can("cards.view") && user.card_visibility !== "search_any" && <section className="panel overview-status-panel">
            <h3>حالة الكروت</h3>
            <div className="overview-status-row"><span>منشأة</span><strong>{statusCount("generated").toLocaleString("ar")}</strong></div>
            <div className="overview-status-row"><span>نشطة</span><strong>{statusCount("active").toLocaleString("ar")}</strong></div>
            <div className="overview-status-row"><span>منتهية</span><strong>{statusCount("expired").toLocaleString("ar")}</strong></div>
            <div className="overview-status-row"><span>موقوفة</span><strong>{statusCount("suspended").toLocaleString("ar")}</strong></div>
          </section>}
        </div>
        <div className="section-heading"><div><h2>الوصول السريع</h2><p>انتقل مباشرة إلى أقسام إدارة النظام.</p></div></div>
        <div className="module-grid">
          {modules.filter((item) => can(item.permission) && (item.permission !== "sessions.view" || user.card_visibility !== "search_any")).map((item) => (
            <button className="module-card module-card-button" key={item.title} onClick={() => { if (item.permission === "sessions.view") setCardManagementTab("sessions"); setPage(item.page); }}>
              <div className="module-icon">{item.icon}</div><h3>{item.title}</h3><p>{item.detail}</p>
              <span className="module-state active-state">متاح الآن</span>
            </button>
          ))}
        </div>
      </>
    );
  }

  function renderPlans() {
    const activePlans = plans.filter((plan) => plan.is_active).length;
    const inactivePlans = plans.length - activePlans;
    const resetPlanDraft = () => {
      setEditingPlanId(null);
      setPlanDraft({ code: "", name: "", price: "", commissionType: "none", commissionValue: "", dataAmount: "", dataUnit: "GB", timeHours: "", validityDays: "", speedProfile: "", sharedUsers: "", groupName: "", rateRx: "", rateTx: "", rateUnit: "Kbps", scheduleEnabled: false, scheduleDays: ["0","1","2","3","4","5","6"], scheduleFrom: "00:00", scheduleTo: "23:59", notificationsEnabled: false, notifyRemaining: "70", notifyExhausted: "95" });
      setNotice("");
      setPlanEditorOpen(false);
    };
    return (
      <section className="plans-workspace">
        <div className="section-heading plans-page-heading">
          <div><span className="eyebrow">إعدادات الاشتراكات والخدمات</span><h2>إدارة الباقات</h2><p>أنشئ باقات الإنترنت وحدد أسعارها وحدود الاستخدام والسرعة والعمولات والإضافات المرتبطة بها.</p></div>
          <div className="plans-heading-actions">
            <span className="count-tag">{plans.length.toLocaleString("ar")} باقة</span>
            {!planEditorOpen && can("plans.create") && <button type="button" className="plans-add-button" onClick={() => { resetPlanDraft(); setPlanEditorOpen(true); setError(""); }}>إضافة باقة جديدة</button>}
          </div>
        </div>

        {!planEditorOpen && <>
        <div className="plans-summary">
          <article><span>إجمالي الباقات</span><strong>{plans.length.toLocaleString("ar")}</strong><small>الباقات المحفوظة في النظام</small></article>
          <article><span>باقات مفعّلة</span><strong>{activePlans.toLocaleString("ar")}</strong><small>متاحة لإنشاء الكروت</small></article>
          <article><span>باقات متوقفة</span><strong>{inactivePlans.toLocaleString("ar")}</strong><small>محفوظة ويمكن إعادة تفعيلها</small></article>
        </div>
        </>}

        {planEditorOpen && (can("plans.create") || (editingPlanId !== null && can("plans.update"))) && (
<form className="panel plan-editor plans-editor-panel" onSubmit={createPlan}>
          <div className="plans-editor-title">
            <div><span className="eyebrow">{editingPlanId !== null ? "تحديث باقة محفوظة" : "إعداد باقة جديدة"}</span><h3>{editingPlanId !== null ? "تعديل بيانات الباقة" : "إضافة باقة جديدة"}</h3><p>الحقول الاختيارية التي تتركها فارغة تعني أن الحد مفتوح.</p></div>
            <span className="plans-editor-symbol">◷</span>
          </div>

          <div className="plan-form-section"><div className="plan-section-title"><span>01</span><div><h3>البيانات الأساسية والسعر</h3><p>اسم الباقة ورمزها والسعر والحدود الرئيسية</p></div></div><div className="form-grid">
            <label>رمز الباقة<input value={planDraft.code} onChange={(e) => setPlanDraft({ ...planDraft, code: e.target.value })} required placeholder="مثال: BASIC-100" /></label>
            <label>اسم الباقة<input value={planDraft.name} onChange={(e) => setPlanDraft({ ...planDraft, name: e.target.value })} required placeholder="اسم يظهر في الكروت والقوائم" /></label>
            <label>السعر (ريال)<input type="number" min="0" step="0.01" value={planDraft.price} onChange={(e) => setPlanDraft({ ...planDraft, price: e.target.value })} required /></label>
            <label>الصلاحية بالأيام <span className="field-hint">تبدأ من أول دخول</span><input type="number" min="0.01" step="0.01" value={planDraft.validityDays} onChange={(e) => setPlanDraft({ ...planDraft, validityDays: e.target.value })} placeholder="فارغ = مفتوح" /></label>
            <label>وقت الاستخدام بالساعات<input type="number" min="0.01" step="0.01" value={planDraft.timeHours} onChange={(e) => setPlanDraft({ ...planDraft, timeHours: e.target.value })} placeholder="فارغ = مفتوح" /></label>
            <label>كمية التحميل<input type="number" min="0.001" step="0.001" value={planDraft.dataAmount} onChange={(e) => setPlanDraft({ ...planDraft, dataAmount: e.target.value })} placeholder="فارغ = مفتوح" /></label>
            <label>وحدة الحجم<select value={planDraft.dataUnit} onChange={(e) => setPlanDraft({ ...planDraft, dataUnit: e.target.value as "MB" | "GB" })}><option>MB</option><option>GB</option></select></label>
          </div></div>

          <div className="plan-form-section"><div className="plan-section-title"><span>02</span><div><h3>السعر والعمولات</h3><p>تحديد عمولة نقطة البيع لكل كرت</p></div></div><div className="form-grid">
            <label>نوع العمولة<select value={planDraft.commissionType} onChange={(e) => setPlanDraft({ ...planDraft, commissionType: e.target.value as "none" | "fixed" | "percentage", commissionValue: e.target.value === "none" ? "" : planDraft.commissionValue })}><option value="none">بدون عمولة</option><option value="percentage">نسبة مئوية</option><option value="fixed">مبلغ ثابت لكل كرت</option></select></label>
            {planDraft.commissionType !== "none" && <label>{planDraft.commissionType === "percentage" ? "نسبة العمولة (%)" : "العمولة لكل كرت (ريال)"}<input type="number" min="0" max={planDraft.commissionType === "percentage" ? "100" : planDraft.price || undefined} step="0.01" value={planDraft.commissionValue} onChange={(e) => setPlanDraft({ ...planDraft, commissionValue: e.target.value })} required /></label>}
          </div></div>

          <div className="plan-form-section"><div className="plan-section-title"><span>03</span><div><h3>المستخدمون والمجموعة والسرعة</h3><p>حدود الاتصال وإعدادات السرعة المرتبطة بالباقة</p></div></div><div className="form-grid">
            <label>عدد المستخدمين المتزامنين <span className="field-hint">فارغ = غير محدود</span><input type="number" min="1" value={planDraft.sharedUsers} onChange={(e) => setPlanDraft({ ...planDraft, sharedUsers: e.target.value })} placeholder="غير محدود" /></label>
            <label>المجموعة<input value={planDraft.groupName} onChange={(e) => setPlanDraft({ ...planDraft, groupName: e.target.value })} placeholder="اسم المجموعة" /></label>
            <label>ملف السرعة<input value={planDraft.speedProfile} onChange={(e) => setPlanDraft({ ...planDraft, speedProfile: e.target.value })} placeholder="مثال: 2M" /></label>
            <label>سرعة التنزيل<input value={planDraft.rateRx} onChange={(e) => setPlanDraft({ ...planDraft, rateRx: e.target.value })} placeholder="مثال: 2" /></label>
            <label>سرعة الرفع<input value={planDraft.rateTx} onChange={(e) => setPlanDraft({ ...planDraft, rateTx: e.target.value })} placeholder="مثال: 1" /></label>
            <label>وحدة السرعة<select value={planDraft.rateUnit} onChange={(e) => setPlanDraft({ ...planDraft, rateUnit: e.target.value as "Kbps" | "Mbps" })}><option>Kbps</option><option>Mbps</option></select></label>
          </div></div>

          <div className="plan-form-section"><div className="plan-section-title"><span>04</span><div><h3>جدولة استخدام الباقة</h3><p>تحديد الأيام والساعات التي يسمح فيها باستخدام الباقة</p></div></div>
            <label className="checkbox-label plan-feature-toggle"><input type="checkbox" checked={planDraft.scheduleEnabled} onChange={(e) => setPlanDraft({ ...planDraft, scheduleEnabled: e.target.checked })} /> تفعيل أيام وساعات محددة</label>
            {planDraft.scheduleEnabled && <><div className="day-selector">{["الأحد","الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت"].map((day,i)=><label key={day}><input type="checkbox" checked={planDraft.scheduleDays.includes(String(i))} onChange={(e)=>setPlanDraft({...planDraft,scheduleDays:e.target.checked?[...planDraft.scheduleDays,String(i)]:planDraft.scheduleDays.filter(x=>x!==String(i))})}/>{day}</label>)}</div><div className="form-grid"><label>من الساعة<input type="time" value={planDraft.scheduleFrom} onChange={(e)=>setPlanDraft({...planDraft,scheduleFrom:e.target.value})}/></label><label>إلى الساعة<input type="time" value={planDraft.scheduleTo} onChange={(e)=>setPlanDraft({...planDraft,scheduleTo:e.target.value})}/></label></div></>}
          </div>

          <div className="plan-form-section"><div className="plan-section-title"><span>05</span><div><h3>التنبيهات</h3><p>إعداد نسب التنبيه عند قرب انتهاء الصلاحية أو الرصيد</p></div></div>
            <label className="checkbox-label plan-feature-toggle"><input type="checkbox" checked={planDraft.notificationsEnabled} onChange={(e)=>setPlanDraft({...planDraft,notificationsEnabled:e.target.checked})}/> تفعيل نظام الإشعارات لهذه الباقة</label>
            {planDraft.notificationsEnabled && <div className="form-grid"><label>تنبيه عند اقتراب انتهاء الصلاحية (%)<input type="number" min="1" max="99" value={planDraft.notifyRemaining} onChange={(e)=>setPlanDraft({...planDraft,notifyRemaining:e.target.value})}/></label><label>تنبيه عند استهلاك الرصيد (%)<input type="number" min="1" max="100" value={planDraft.notifyExhausted} onChange={(e)=>setPlanDraft({...planDraft,notifyExhausted:e.target.value})}/></label></div>}
          </div>

          <div className="notice">تُحفظ إعدادات الإضافات والجدولة ضمن الباقة. تفعيلها فعلياً على الراوتر وإرسال الإشعارات يحتاج ربط محرك التنفيذ لاحقاً.</div>
          <div className="form-actions plans-form-actions"><button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ..." : editingPlanId ? "حفظ التعديلات" : "إنشاء الباقة"}</button><button type="button" className="secondary-button" disabled={busy} onClick={resetPlanDraft}>العودة إلى قائمة الباقات</button></div>
        </form>
)}

        {!planEditorOpen && <>
        <section className="plans-directory">
          <div className="section-heading compact-heading"><div><span className="eyebrow">دليل الاشتراكات</span><h2>الباقات المسجلة</h2><p>جميع الباقات الحالية وحالتها وحدودها، دون حذف السجلات عند الإيقاف.</p></div><span className="count-tag">{plans.length.toLocaleString("ar")} باقة</span></div>
          <div className="table-wrap plans-table-wrap"><table><thead><tr><th>الرمز</th><th>اسم الباقة</th><th>السعر</th><th>عمولة نقطة البيع</th><th>الحجم</th><th>الوقت</th><th>الصلاحية</th><th>المستخدمون</th><th>المجموعة</th><th>السرعة</th><th>الحالة</th><th>الإجراءات</th></tr></thead>
            <tbody>{plans.map((plan) => <tr key={plan.id}><td><span className="plan-code">{plan.code}</span></td><td><strong>{plan.name}</strong></td><td>{Number(plan.price).toLocaleString("en-US")} ريال</td><td>{plan.commission_type === "none" ? "بدون" : plan.commission_type === "percentage" ? `${Number(plan.commission_value)}%` : `${Number(plan.commission_value).toFixed(2)} ريال`}</td><td>{plan.data_limit_bytes === null ? "مفتوح" : `${plan.data_limit_bytes % (1024 ** 3) === 0 ? (plan.data_limit_bytes / 1024 ** 3).toFixed(2) + " GB" : (plan.data_limit_bytes / 1024 ** 2).toFixed(0) + " MB"}`}</td><td>{plan.session_time_limit_seconds === null ? "مفتوح" : `${(plan.session_time_limit_seconds / 3600).toFixed(2)} ساعة`}</td><td>{plan.validity_period_seconds === null ? "مفتوح" : `${(plan.validity_period_seconds / 86400).toFixed(2)} يوم`}</td><td>{plan.settings?.shared_users == null ? "غير محدود" : String(plan.settings.shared_users)}</td><td>{String(plan.settings?.group ?? "—")}</td><td>{plan.speed_profile || "—"}</td><td><span className={plan.is_active ? "plan-status active" : "plan-status inactive"}>{plan.is_active ? "مفعّلة" : "متوقفة"}</span></td><td>{can("plans.update") && <><button type="button" className="table-action" disabled={busy} onClick={() => editPlan(plan)}>تعديل</button><button type="button" className={plan.is_active ? "table-action danger-action" : "table-action"} disabled={busy} onClick={() => togglePlan(plan)}>{plan.is_active ? "إيقاف" : "تفعيل"}</button></>}{can("plans.delete") && !plan.is_active && <button type="button" className="table-action danger-action" disabled={busy} onClick={() => deletePlan(plan)}>حذف</button>}</td></tr>)}</tbody>
          </table>{plans.length === 0 && <div className="empty-state">لا توجد باقات مسجلة بعد. اضغط «إضافة باقة جديدة» لإنشاء أول باقة.</div>}</div>
        </section>
        </>}
      </section>
    );
  }

  async function saveCardTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingTemplateId ? !can("templates.update") : !can("templates.create")) { setError("ليست لديك صلاحية هذه العملية على تصاميم الكروت."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const payload = { ...templateDraft, width_mm: Number(templateDraft.width_mm), height_mm: Number(templateDraft.height_mm), plan_id: Number(templateDraft.plan_id), layout: templateLayoutDraft };
      if (editingTemplateId) await apiRequest<CardTemplate>(token, `/api/v1/card-templates/${editingTemplateId}`, { method: "PATCH", body: JSON.stringify({ name: payload.name, width_mm: payload.width_mm, height_mm: payload.height_mm, background_color: payload.background_color, text_color: payload.text_color, plan_id: Number(payload.plan_id), layout: payload.layout }) });
      else await apiRequest<CardTemplate>(token, "/api/v1/card-templates", { method: "POST", body: JSON.stringify(payload) });
      await loadCardTemplates(); setEditingTemplateId(null); setTemplateDraft({ code: "", name: "", width_mm: "90", height_mm: "50", background_color: "#e9f6ef", text_color: "#174c37", plan_id: "" }); setTemplateLayoutDraft({ ...DEFAULT_TEMPLATE_LAYOUT }); setNotice("تم حفظ القالب.");
    } catch (err) { setError(err instanceof Error ? err.message : "تعذر حفظ القالب"); } finally { setBusy(false); }
  }

  async function deleteCardTemplate(template: CardTemplate) {
    if (!can("templates.delete")) { setError("ليست لديك صلاحية حذف القوالب."); return; }
    if (template.is_default || !window.confirm(`حذف القالب ${template.name}؟`)) return;
    setBusy(true); setError("");
    try { await apiRequest<void>(token, `/api/v1/card-templates/${template.id}`, { method: "DELETE" }); await loadCardTemplates(); setNotice("تم حذف القالب."); }
    catch (err) { setError(err instanceof Error ? err.message : "تعذر حذف القالب"); } finally { setBusy(false); }
  }

  function renderTemplates() {
    const templateSummary = {
      defaults: cardTemplates.filter((item) => item.is_default).length,
      linked: cardTemplates.filter((item) => item.plan_id !== null && plans.some((plan) => plan.id === item.plan_id && plan.is_active)).length,
      inactiveLinks: cardTemplates.filter((item) => item.plan_id !== null && !plans.some((plan) => plan.id === item.plan_id && plan.is_active)).length,
    };
    const previewPlan = plans.find((plan) => String(plan.id) === templateDraft.plan_id);
    const previewPosition = (xKey: string, yKey: string) => ({
      position: "absolute" as const,
      left: String(templateLayoutDraft[xKey] ?? "50") + "%",
      top: String(templateLayoutDraft[yKey] ?? "50") + "%",
      transform: "translate(-50%, -50%)",
      width: "88%",
      textAlign: "center" as const,
    });
    const previewCardStyle = {
      position: "relative" as const,
      width: "100%",
      maxWidth: "520px",
      aspectRatio: `${templateDraft.width_mm}/${templateDraft.height_mm}`,
      background: templateDraft.background_color,
      color: templateDraft.text_color,
      fontFamily: String(templateLayoutDraft.font_family ?? "Arial"),
      fontSize: `${Number(templateLayoutDraft.font_size ?? 12)}px`,
      padding: `${Number(templateLayoutDraft.card_padding_mm ?? 3)}mm`,
      border: templateLayoutDraft.show_border === false ? "none" : `${Number(templateLayoutDraft.border_width ?? 1)}px solid ${String(templateLayoutDraft.border_color ?? "#667085")}`,
      borderRadius: "8px",
      overflow: "hidden" as const,
      boxSizing: "border-box" as const,
    };
    const resetTemplateDraft = () => {
      setEditingTemplateId(null);
      setTemplateDraft({ code: "", name: "", width_mm: "90", height_mm: "50", background_color: "#e9f6ef", text_color: "#174c37", plan_id: "" });
      setTemplateLayoutDraft({ ...DEFAULT_TEMPLATE_LAYOUT });
    };
    return (
      <section className="template-studio">
        <div className="section-heading template-studio-heading">
          <div><span className="eyebrow">استديو التصميم والطباعة</span><h2>تصاميم الكروت</h2><p>أنشئ قوالب متعددة، اربط كل قالب بباقة، وشاهد شكل الكرت مباشرة قبل الحفظ والطباعة.</p></div>
          <span className="count-tag">{cardTemplates.length.toLocaleString("ar")} قالب محفوظ</span>
        </div>

        <div className="template-summary-grid" aria-label="ملخص تصاميم الكروت">
          <article className="template-summary-card"><span>إجمالي القوالب</span><strong>{cardTemplates.length.toLocaleString("ar")}</strong><small>تصميم محفوظ في المكتبة</small></article>
          <article className="template-summary-card"><span>القوالب الافتراضية</span><strong>{templateSummary.defaults.toLocaleString("ar")}</strong><small>قالب محدد كافتراضي</small></article>
          <article className="template-summary-card"><span>مرتبطة بباقات مفعّلة</span><strong>{templateSummary.linked.toLocaleString("ar")}</strong><small>جاهزة للاستخدام في إنشاء الكروت</small></article>
          <article className="template-summary-card"><span>روابط تحتاج مراجعة</span><strong>{templateSummary.inactiveLinks.toLocaleString("ar")}</strong><small>مرتبطة بباقة غير مفعّلة أو غير متاحة</small></article>
        </div>
        <div className="template-studio-grid">
          {(can("templates.create") || (editingTemplateId !== null && can("templates.update"))) && (
<form className="panel template-editor-panel" onSubmit={saveCardTemplate}>
            <div className="template-editor-heading"><div><span className="eyebrow">{editingTemplateId ? "تعديل تصميم محفوظ" : "تصميم جديد"}</span><h3>{editingTemplateId ? "تحرير القالب" : "إنشاء قالب طباعة"}</h3></div><span className="template-editor-mark">✎</span></div>

            <div className="template-editor-section"><div className="plan-section-title"><span>01</span><div><h3>البيانات وربط الباقة</h3><p>اختر الباقة التي سيحملها هذا القالب تلقائياً</p></div></div><div className="form-grid">
              <label>رمز القالب<input value={templateDraft.code} onChange={(e) => setTemplateDraft({ ...templateDraft, code: e.target.value })} disabled={!!editingTemplateId} required pattern="[A-Za-z0-9_-]+" /></label>
              <label>اسم القالب<input value={templateDraft.name} onChange={(e) => setTemplateDraft({ ...templateDraft, name: e.target.value })} required minLength={2} placeholder="مثال: قالب الباقة الاقتصادية" /></label>
              <label className="template-plan-select">الباقة المرتبطة بالقالب<select value={templateDraft.plan_id} onChange={(e) => setTemplateDraft({ ...templateDraft, plan_id: e.target.value })} required><option value="">اختر الباقة</option>{plans.filter((plan) => plan.is_active).map((plan) => <option key={plan.id} value={plan.id}>{plan.name} — {plan.code}</option>)}</select></label>
            </div>{previewPlan && <div className="template-linked-plan"><strong>الباقة المرتبطة:</strong> {previewPlan.name} · {Number(previewPlan.price).toLocaleString("en-US")} ريال · {previewPlan.data_limit_bytes == null ? "رصيد مفتوح" : `${(previewPlan.data_limit_bytes / (1024 ** 2)).toFixed(0)} MB`}</div>}</div>

            <div className="template-editor-section"><div className="plan-section-title"><span>02</span><div><h3>أبعاد الكرت وألوانه</h3><p>تظهر التغييرات فوراً في المعاينة</p></div></div><div className="form-grid">
              <label>العرض (مم)<input type="number" min="25" max="300" value={templateDraft.width_mm} onChange={(e) => setTemplateDraft({ ...templateDraft, width_mm: e.target.value })} required /></label>
              <label>الارتفاع (مم)<input type="number" min="20" max="300" value={templateDraft.height_mm} onChange={(e) => setTemplateDraft({ ...templateDraft, height_mm: e.target.value })} required /></label>
              <label>لون الخلفية<input type="color" value={templateDraft.background_color} onChange={(e) => setTemplateDraft({ ...templateDraft, background_color: e.target.value })} /></label>
              <label>لون النص<input type="color" value={templateDraft.text_color} onChange={(e) => setTemplateDraft({ ...templateDraft, text_color: e.target.value })} /></label>
              <label>عنوان الكرت<input value={String(templateLayoutDraft.header_text ?? "الأسطورة نت")} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, header_text: e.target.value })} maxLength={60} /></label>
              <label>النص التعريفي<input value={String(templateLayoutDraft.footer_text ?? "بطاقة إنترنت")} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, footer_text: e.target.value })} maxLength={80} /></label>
            </div></div>

            <div className="template-editor-section"><div className="plan-section-title"><span>03</span><div><h3>العناصر الظاهرة</h3><p>حدد البيانات التي تظهر على وجه الكرت</p></div></div><div className="template-visibility-grid">
              {([["show_username","اسم المستخدم"],["show_password","كلمة المرور"],["show_serial_number","الرقم التسلسلي"],["show_plan","اسم الباقة"],["show_price","السعر"],["show_limits","الرصيد والوقت والصلاحية"],["show_border","إطار الكرت"]] as [string,string][]).map(([key,label]) => <label key={key}><input type="checkbox" checked={!!templateLayoutDraft[key]} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, [key]: e.target.checked })} />{label}</label>)}
            </div></div>

            <div className="template-editor-section"><div className="plan-section-title"><span>04</span><div><h3>الخط والإطار وتوزيع الصفحة</h3><p>ضبط شكل العناصر وعدد الكروت في الصفحة</p></div></div><div className="form-grid">
              <label>نوع الخط<select value={String(templateLayoutDraft.font_family)} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, font_family: e.target.value })}><option>Arial</option><option>Tahoma</option><option>Consolas</option><option>sans-serif</option></select></label>
              <label>حجم الخط<input type="number" min="6" max="32" value={String(templateLayoutDraft.font_size)} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, font_size: e.target.value })} /></label>
              <label>لون الإطار<input type="color" value={String(templateLayoutDraft.border_color)} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, border_color: e.target.value })} /></label>
              <label>سماكة الإطار<input type="number" min="0" max="5" step="0.5" value={String(templateLayoutDraft.border_width)} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, border_width: e.target.value })} /></label>
              <label>عدد الأعمدة<input type="number" min="1" max="5" value={String(templateLayoutDraft.columns)} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, columns: e.target.value })} /></label>
              <label>عدد الصفوف<input type="number" min="1" max="12" value={String(templateLayoutDraft.rows)} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, rows: e.target.value })} /></label>
              <label>المسافة بين الكروت (مم)<input type="number" min="0" max="20" step="0.5" value={String(templateLayoutDraft.page_gap_mm ?? "4")} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, page_gap_mm: e.target.value })} /></label>
              <label>الهامش الداخلي للكرت (مم)<input type="number" min="0" max="15" step="0.5" value={String(templateLayoutDraft.card_padding_mm ?? "3")} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, card_padding_mm: e.target.value })} /></label>
            </div></div>

            <div className="template-editor-section"><div className="plan-section-title"><span>05</span><div><h3>مواضع العناصر X و Y</h3><p>القيم كنسبة مئوية من أبعاد الكرت</p></div></div><div className="form-grid">
              {([["اسم المستخدم","username"],["كلمة المرور","password"],["اسم الباقة","plan"],["الرصيد والوقت","limits"],["الرقم التسلسلي","serial"],["السعر","price"]] as [string,string][]).map(([label,key]) => <div className="template-position-fields" key={key}><strong>{label}</strong><label>X<input type="number" min="0" max="100" value={String(templateLayoutDraft[`${key}_x`] ?? (key === "serial" ? "8" : key === "price" ? "92" : "50"))} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, [`${key}_x`]: e.target.value })} /></label><label>Y<input type="number" min="0" max="100" value={String(templateLayoutDraft[`${key}_y`] ?? (key === "plan" ? "25" : key === "limits" ? "82" : key === "username" ? "48" : key === "password" ? "65" : "90"))} onChange={(e) => setTemplateLayoutDraft({ ...templateLayoutDraft, [`${key}_y`]: e.target.value })} /></label></div>)}
            </div></div>

            <div className="form-actions template-editor-actions"><button type="submit" disabled={busy || !plans.some((plan) => plan.is_active && String(plan.id) === templateDraft.plan_id)}>{busy ? "جارٍ الحفظ..." : editingTemplateId ? "حفظ تعديلات القالب" : "حفظ القالب"}</button><button type="button" className="secondary-button" onClick={resetTemplateDraft}>قالب جديد / إلغاء</button></div>
          </form>
)}

          <aside className="template-preview-column">
            <div className="panel template-live-preview">
              <div className="template-preview-heading"><div><span className="eyebrow">معاينة مباشرة</span><h3>شكل الكرت</h3></div><span className="preview-live-dot">مباشر</span></div>
              <div className="template-preview-stage">
                <article className="template-preview-card" style={previewCardStyle}>
                  <div className="voucher-head"><strong>{String(templateLayoutDraft.header_text ?? "الأسطورة نت")}</strong><span>{String(templateLayoutDraft.footer_text ?? "بطاقة إنترنت")}</span></div>
                  {templateLayoutDraft.show_plan !== false && <div className="voucher-plan" style={previewPosition("plan_x","plan_y")}><span>الباقة</span><strong>{previewPlan?.name || "اسم الباقة"}</strong></div>}
                  {templateLayoutDraft.show_username !== false && <div className="voucher-user" style={previewPosition("username_x","username_y")}><span>اسم المستخدم</span><strong>123456789</strong></div>}
                  {templateLayoutDraft.show_password !== false && <div className="voucher-password" style={previewPosition("password_x","password_y")}><span>كلمة المرور</span><strong>••••••••</strong></div>}
                  {templateLayoutDraft.show_limits !== false && <div className="voucher-limits" style={previewPosition("limits_x","limits_y")}><span>{previewPlan?.data_limit_bytes == null ? "رصيد مفتوح" : `${(previewPlan.data_limit_bytes / (1024 ** 2)).toFixed(0)} MB`} · {previewPlan?.session_time_limit_seconds == null ? "وقت مفتوح" : `${(previewPlan.session_time_limit_seconds / 3600).toFixed(0)} ساعة`} · {previewPlan?.validity_period_seconds == null ? "صلاحية مفتوحة" : `${(previewPlan.validity_period_seconds / 86400).toFixed(0)} يوم`}</span></div>}
                  <div className="voucher-foot"><span style={previewPosition("serial_x","serial_y")}>{templateLayoutDraft.show_serial_number !== false ? "AL000001" : ""}</span><strong style={previewPosition("price_x","price_y")}>{templateLayoutDraft.show_price !== false ? `${previewPlan ? Number(previewPlan.price).toLocaleString("en-US") : "100"} ريال` : ""}</strong></div>
                </article>
              </div>
              <div className="template-preview-meta"><span>{templateDraft.width_mm} × {templateDraft.height_mm} مم</span><span>{templateLayoutDraft.columns} أعمدة × {templateLayoutDraft.rows} صفوف</span></div>
              <p className="field-hint">هذه معاينة توضيحية ببيانات تجريبية؛ بيانات الكروت الفعلية تظهر عند الطباعة.</p>
            </div>
          </aside>
        </div>

        <div className="template-gallery-heading"><div><span className="eyebrow">مكتبة التصاميم</span><h3>القوالب المحفوظة</h3><p>يمكنك فتح أي قالب للتعديل أو تعيينه قالباً افتراضياً.</p></div><span className="count-tag">{cardTemplates.length} قالب</span></div>
        <div className="template-gallery">{cardTemplates.map((item) => {
          const savedLayout = { ...DEFAULT_TEMPLATE_LAYOUT, ...item.layout } as Record<string, string | boolean>;
          return <article className="panel template-item" key={item.id}>
            <div className="template-sample" style={{ background: item.background_color, color: item.text_color, aspectRatio: `${item.width_mm}/${item.height_mm}`, border: savedLayout.show_border === false ? "none" : `${Number(savedLayout.border_width ?? 1)}px solid ${String(savedLayout.border_color ?? "#667085")}` }}><strong>{String(savedLayout.header_text ?? "الأسطورة نت")}</strong><span>{item.name}</span><small>{plans.find((plan) => plan.id === item.plan_id)?.name ?? "غير مرتبطة"}</small></div>
            <h3>{item.name} {item.is_default ? "— افتراضي" : ""}</h3><small>{item.width_mm} × {item.height_mm} مم · {item.code} · الباقة: {plans.find((plan) => plan.id === item.plan_id)?.name ?? "غير مرتبطة"}</small>
            <div className="form-actions">{can("templates.update") && <><button type="button" className="table-action" onClick={() => { setEditingTemplateId(item.id); setTemplateDraft({ code: item.code, name: item.name, width_mm: String(item.width_mm), height_mm: String(item.height_mm), background_color: item.background_color, text_color: item.text_color, plan_id: item.plan_id ? String(item.plan_id) : "" }); setTemplateLayoutDraft({ ...DEFAULT_TEMPLATE_LAYOUT, ...item.layout } as Record<string, string | boolean>); }}>تعديل</button><button type="button" className="table-action" disabled={busy || item.is_default} onClick={() => apiRequest<CardTemplate>(token, `/api/v1/card-templates/${item.id}`, { method: "PATCH", body: JSON.stringify({ is_default: true }) }).then(() => loadCardTemplates()).then(() => setNotice("تم تعيين القالب الافتراضي.")).catch((err) => setError(err instanceof Error ? err.message : "تعذر تعيين القالب الافتراضي"))}>جعله افتراضياً</button></>}{can("templates.delete") && <button type="button" className="table-action danger-action" disabled={busy || item.is_default} onClick={() => deleteCardTemplate(item)}>حذف</button>}</div>
          </article>;
        })}</div>
        {cardTemplates.length === 0 && <div className="empty-state">لا توجد قوالب محفوظة بعد. أنشئ أول قالب من المحرر.</div>}
      </section>
    );
  }

  function renderCardCreate() {
    const activePlans = plans.filter((plan) => plan.is_active);
    const availableTemplates = cardTemplates.filter((item) => item.plan_id !== null && activePlans.some((plan) => plan.id === item.plan_id));
    const selectedTemplate = availableTemplates.find((item) => item.code === printTemplate)
      ?? availableTemplates.find((item) => item.is_default)
      ?? availableTemplates[0];
    const selectedPlan = selectedTemplate ? activePlans.find((plan) => plan.id === selectedTemplate.plan_id) : undefined;
    const selectedPoint = points.find((point) => String(point.id) === selectedPosId && point.is_active);
    const compatibleBatches = cardBatches.filter((batch) =>
      batch.plan_id === selectedPlan?.id &&
      batch.point_of_sale_id === selectedPoint?.id &&
      batch.template_code === selectedTemplate?.code &&
      batch.card_type === batchDraft.cardType &&
      batch.generation_mode === batchDraft.generationMode &&
      batch.username_length === Number(batchDraft.usernameLength) &&
      batch.password_length === Number(batchDraft.passwordLength) &&
      batch.prefix === batchDraft.prefix
    );
    const chooseTemplate = (code: string) => {
      const template = availableTemplates.find((item) => item.code === code);
      setPrintTemplate(template?.code ?? "");
      if (template?.plan_id) {
        const planId = String(template.plan_id);
        setSingleDraft((current) => ({ ...current, planId }));
        setBatchDraft((current) => ({ ...current, planId }));
      }
      setError("");
    };
    const planDetails = selectedPlan ? [
      selectedPlan.data_limit_bytes == null ? "رصيد مفتوح" : `${(selectedPlan.data_limit_bytes / (1024 ** 2)).toFixed(0)} MB`,
      selectedPlan.session_time_limit_seconds == null ? "وقت مفتوح" : `${(selectedPlan.session_time_limit_seconds / 3600).toFixed(0)} ساعة`,
      selectedPlan.validity_period_seconds == null ? "صلاحية مفتوحة" : `${(selectedPlan.validity_period_seconds / 86400).toFixed(0)} يوم`,
      selectedPlan.speed_profile ? `السرعة: ${selectedPlan.speed_profile}` : "",
    ].filter(Boolean) : [];
    const canCreate = !!selectedTemplate && !!selectedPlan && !!selectedPoint && !busy;
    return (
      <section className="card-create-workspace">
        <div className="section-heading card-create-heading"><div><span className="eyebrow">إنشاء وإعداد بطاقات الإنترنت</span><h2>إضافة الكروت</h2><p>اختر القالب أولاً؛ ستُحدد الباقة المرتبطة به تلقائياً، ثم اختر نقطة البيع وطريقة إنشاء الكرت.</p></div><span className="count-tag">{cardMode === "single" ? "إنشاء كرت منفرد" : "إنشاء دفعة كروت"}</span></div>
        <div className="notice">الكروت تُنشأ وتحفظ داخل قاعدة ALOSTORA-RADIUS. ربطها واستعادتها من User Manager القديم مؤجل إلى المرحلة الأخيرة من المشروع.</div>

        <div className="card-create-steps">
          <article className={selectedTemplate ? "complete" : "pending"}><span>1</span><div><strong>قالب الطباعة</strong><small>{selectedTemplate?.name ?? "لم يتم اختيار قالب"}</small></div></article>
          <article className={selectedPlan ? "complete" : "pending"}><span>2</span><div><strong>الباقة المرتبطة</strong><small>{selectedPlan?.name ?? "تُحدد من القالب"}</small></div></article>
          <article className={selectedPoint ? "complete" : "pending"}><span>3</span><div><strong>نقطة البيع</strong><small>{selectedPoint?.name ?? "اختر نقطة البيع"}</small></div></article>
        </div>

        <div className="panel card-create-setup">
          <div className="card-create-section-heading"><span>01</span><div><h3>القالب ونقطة البيع</h3><p>مصدر الباقة هو القالب، ولا يتم اختيارها بشكل منفصل.</p></div></div>
          <div className="form-grid">
            <label>قالب الكرت
              <select value={selectedTemplate?.code ?? ""} onChange={(e) => chooseTemplate(e.target.value)} required>
                <option value="">اختر قالباً مرتبطاً بباقة مفعّلة</option>
                {availableTemplates.map((item) => <option key={item.id} value={item.code}>{item.name} — {item.code}</option>)}
              </select>
              <span className="field-hint">تظهر هنا القوالب المرتبطة بباقات مفعّلة فقط.</span>
            </label>
            <label>نقطة البيع
              <select value={selectedPosId} onChange={(e) => setSelectedPosId(e.target.value)} required>
                <option value="">اختر نقطة بيع مسجلة</option>
                {points.filter((point) => point.is_active).map((point) => <option key={point.id} value={point.id}>{point.name} — {point.code}</option>)}
              </select>
              <span className="field-hint">اختر نقطة البيع التي ستتبع لها عملية التوزيع والطباعة.</span>
            </label>
          </div>
          {selectedPlan ? <div className="card-create-plan-summary"><div><span>الباقة المحددة تلقائياً</span><strong>{selectedPlan.name}</strong><small>{selectedPlan.code} · {Number(selectedPlan.price).toLocaleString("en-US")} ريال</small></div><div className="card-plan-specs">{planDetails.map((detail) => <span key={detail}>{detail}</span>)}</div></div>
            : <div className="empty-state compact-empty">لا يوجد قالب متاح مرتبط بباقة مفعّلة. أنشئ قالباً واربطه بباقة من صفحة تصاميم الكروت أولاً.</div>}
        </div>

        <div className="mode-tabs card-create-mode-tabs">
          <button type="button" className={cardMode === "single" ? "mode-tab active" : "mode-tab"} onClick={() => { setCardMode("single"); setGeneratedCards([]); setGeneratedBatchNumber(""); setError(""); }}>كرت منفرد</button>
          <button type="button" className={cardMode === "batch" ? "mode-tab active" : "mode-tab"} onClick={() => { setCardMode("batch"); setGeneratedCards([]); setGeneratedBatchNumber(""); setError(""); }}>دفعة كروت</button>
        </div>

        {cardMode === "single" ? (
          <form className="panel card-create-form" onSubmit={createSingle}>
            <div className="card-create-section-heading"><span>02</span><div><h3>بيانات الكرت المنفرد</h3><p>أدخل اسم المستخدم وحدد طريقة بيانات الدخول.</p></div></div>
            <div className="form-grid">
              <label>اسم المستخدم<input value={singleDraft.username} onChange={(e) => setSingleDraft({ ...singleDraft, username: e.target.value })} minLength={3} maxLength={32} pattern="[A-Za-z0-9_-]+" required placeholder="أحرف إنجليزية وأرقام فقط" /></label>
              <label>نوع بيانات الدخول<select value={singleDraft.cardType} onChange={(e) => setSingleDraft({ ...singleDraft, cardType: e.target.value })}><option value="username_only">اسم مستخدم فقط</option>{can("cards.credentials") && <><option value="same_credentials">اسم المستخدم وكلمة المرور متطابقان</option><option value="separate_credentials">اسم مستخدم وكلمة مرور مختلفان</option></>}</select></label>
              {singleDraft.cardType === "separate_credentials" && <label>كلمة المرور<input type="text" value={singleDraft.password} onChange={(e) => setSingleDraft({ ...singleDraft, password: e.target.value })} minLength={4} maxLength={32} required /></label>}
              <label className="checkbox-label"><input type="checkbox" checked={singleDraft.isFree} onChange={(e) => setSingleDraft({ ...singleDraft, isFree: e.target.checked })} /> كرت مجاني / خاص بمالك الشبكة</label>
            </div>
            <div className="card-create-submit-row"><span>القالب: {selectedTemplate?.name ?? "—"} · الباقة: {selectedPlan?.name ?? "—"}</span><button type="submit" disabled={!canCreate || !singleDraft.username.trim() || (singleDraft.cardType === "separate_credentials" && singleDraft.password.length < 4)}>{busy ? "جارٍ الإنشاء..." : "إنشاء الكرت"}</button></div>
          </form>
        ) : (
          <form className="panel card-create-form" onSubmit={createBatch}>
            <div className="card-create-section-heading"><span>02</span><div><h3>إعداد دفعة الكروت</h3><p>حدد العدد وطريقة توليد بيانات الدخول.</p></div></div>
            <div className="form-grid">
              <label>عدد الكروت<input type="number" min="1" max="5000" value={batchDraft.quantity} onChange={(e) => setBatchDraft({ ...batchDraft, quantity: e.target.value })} required /></label>
              <label>نوع بيانات الدخول<select value={batchDraft.cardType} onChange={(e) => setBatchDraft({ ...batchDraft, cardType: e.target.value })}><option value="username_only">اسم مستخدم فقط</option>{can("cards.credentials") && <><option value="same_credentials">اسم المستخدم وكلمة المرور متطابقان</option><option value="separate_credentials">اسم مستخدم وكلمة مرور مختلفان</option></>}</select></label>
              <label>طريقة توليد اسم المستخدم<select value={batchDraft.generationMode} onChange={(e) => setBatchDraft({ ...batchDraft, generationMode: e.target.value })}><option value="digits">أرقام فقط</option><option value="letters">حروف فقط</option><option value="alphanumeric">أرقام وحروف</option></select></label>
              <label>طول اسم المستخدم<input type="number" min="3" max="32" value={batchDraft.usernameLength} onChange={(e) => setBatchDraft({ ...batchDraft, usernameLength: e.target.value })} required /></label>
              <label>طول كلمة المرور<input type="number" min="4" max="32" value={batchDraft.passwordLength} onChange={(e) => setBatchDraft({ ...batchDraft, passwordLength: e.target.value })} disabled={batchDraft.cardType !== "separate_credentials"} required={batchDraft.cardType === "separate_credentials"} /></label>
              <label>بادئة اسم المستخدم<input value={batchDraft.prefix} onChange={(e) => setBatchDraft({ ...batchDraft, prefix: e.target.value })} maxLength={20} pattern="[A-Za-z0-9]*" placeholder="اختياري، مثال: 777" /></label>
              <label>طريقة حفظ الدفعة
                <select value={batchDraft.batchMode} onChange={(e) => setBatchDraft({ ...batchDraft, batchMode: e.target.value as "new" | "existing" })}>
                  <option value="new">إنشاء دفعة جديدة</option>
                  <option value="existing">ربط الكروت بدفعة سابقة</option>
                </select>
              </label>
              {batchDraft.batchMode === "existing" && <label>رقم الدفعة السابقة
                <input list="compatible-card-batches" value={batchDraft.existingBatchNumber} onChange={(e) => setBatchDraft({ ...batchDraft, existingBatchNumber: e.target.value })} required placeholder="أدخل رقم الدفعة مثل BAT..." />
                <datalist id="compatible-card-batches">
                  {compatibleBatches.map((batch) => <option key={batch.batch_id} value={batch.batch_number}>{batch.quantity} كرت</option>)}
                </datalist>
                <span className="field-hint">يمكنك اختيار دفعة ظاهرة أو إدخال رقم دفعة أقدم يدوياً؛ يتحقق النظام من تطابق إعداداتها قبل الإضافة.</span>
              </label>}
              <label className="checkbox-label"><input type="checkbox" checked={batchDraft.isOnlineSale} onChange={(e) => setBatchDraft({ ...batchDraft, isOnlineSale: e.target.checked })} /> دفعة مخصصة للبيع أونلاين</label>
              <label>ملاحظة الدفعة<textarea value={batchDraft.note} onChange={(e) => setBatchDraft({ ...batchDraft, note: e.target.value })} maxLength={500} rows={2} placeholder="ملاحظة اختيارية للدفعة" /></label>
            </div>
            {batchDraft.batchMode === "existing" && compatibleBatches.length === 0 && <div className="notice">لا توجد دفعة متوافقة ضمن آخر الدفعات المحمّلة. يمكنك إدخال رقم دفعة أقدم وسيتم التحقق من توافقها قبل الحفظ.</div>}
            <div className="card-create-submit-row"><span>سيتم إنشاء {Number(batchDraft.quantity) || 0} كرت · {selectedTemplate?.name ?? "لا يوجد قالب"} · {selectedPlan?.name ?? "لا توجد باقة"}</span><button type="submit" disabled={!canCreate || (batchDraft.batchMode === "existing" && !batchDraft.existingBatchNumber.trim()) || Number(batchDraft.quantity) < 1 || Number(batchDraft.quantity) > 5000 || Number(batchDraft.usernameLength) < 3 || Number(batchDraft.usernameLength) > 32 || (batchDraft.cardType === "separate_credentials" && (Number(batchDraft.passwordLength) < 4 || Number(batchDraft.passwordLength) > 32))}>{busy ? "جارٍ حفظ الكروت..." : batchDraft.batchMode === "existing" ? "إضافة الكروت إلى الدفعة" : "إنشاء الدفعة"}</button></div>
          </form>
        )}

        {generatedCards.length > 0 && <section className="generated-panel card-generated-panel">
          <div className="section-heading compact-heading"><div><span className="eyebrow">تم إنشاء الكروت</span><h2>بيانات الدفعة الجديدة {generatedBatchNumber ? `— ${generatedBatchNumber}` : ""}</h2><p>{can("cards.credentials") ? "احفظ بيانات الدخول الآن؛ كلمات المرور لن تظهر مرة أخرى بعد مغادرة هذه الصفحة." : "تم إنشاء الكروت دون إظهار كلمات المرور؛ يتطلب عرضها صلاحية مستقلة."}</p></div><div className="form-actions"><button type="button" disabled={!selectedPrintCardIds.length || !selectedPosId} onClick={() => setPage("pos")}>متابعة الطباعة لنقطة البيع</button>{can("cards.credentials") && <button type="button" className="secondary-button" onClick={() => window.print()}>طباعة بيانات الدخول</button>}</div></div>
          <div className="table-wrap"><table><thead><tr><th>التسلسل</th><th>اسم المستخدم</th><th>كلمة المرور</th></tr></thead><tbody>{generatedCards.map((card) => <tr key={card.serial_number}><td>{card.serial_number}</td><td>{card.username}</td><td>{card.password === null ? "محجوب بالصلاحيات" : card.password || "بدون كلمة مرور"}</td></tr>)}</tbody></table></div>
        </section>}
      </section>
    );
  }

  function renderBatches() {
    const batchSummary = cardBatches.reduce((summary, batch) => ({
      quantity: summary.quantity + Number(batch.quantity || 0),
      printed: summary.printed + Number(batch.printed_count || 0),
      online: summary.online + (batch.is_online_sale ? 1 : 0),
    }), { quantity: 0, printed: 0, online: 0 });
    return (
      <section className="card-batches-workspace">
        <div className="section-heading card-batches-heading">
          <div><h2>دفعات الكروت</h2><p>سجل الدفعات المحفوظة مع الباقة والقالب ونقطة البيع ونوع البيع والملاحظات.</p></div>
          <button type="button" className="table-action" disabled={busy} onClick={() => loadCardBatches().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحديث الدفعات"))}>تحديث</button>
        </div>
        <div className="batch-summary-grid" aria-label="ملخص دفعات الكروت">
          <article className="batch-summary-card"><span>إجمالي الدفعات</span><strong>{cardBatches.length.toLocaleString("ar")}</strong><small>دفعة محفوظة</small></article>
          <article className="batch-summary-card"><span>إجمالي الكروت</span><strong>{batchSummary.quantity.toLocaleString("ar")}</strong><small>ضمن الدفعات المحمّلة</small></article>
          <article className="batch-summary-card"><span>الكروت المطبوعة</span><strong>{batchSummary.printed.toLocaleString("ar")}</strong><small>حسب سجل الطباعة</small></article>
          <article className="batch-summary-card"><span>دفعات البيع أونلاين</span><strong>{batchSummary.online.toLocaleString("ar")}</strong><small>دفعة مخصصة للبيع الإلكتروني</small></article>
        </div>
        <div className="table-wrap card-batches-table-wrap">
          <table className="card-batches-table"><thead><tr><th>رقم الدفعة</th><th>الباقة</th><th>القالب</th><th>نقطة البيع</th><th>عدد الكروت</th><th>المطبوع</th><th>نوع البيع</th><th>ملاحظة</th><th>التاريخ</th><th>الإجراء</th></tr></thead>
            <tbody>{cardBatches.map((batch) => <tr key={batch.batch_id}>
              <td>{batch.batch_number}</td><td>{batch.plan_name}</td><td>{batch.template_code || "—"}</td><td>{batch.point_of_sale_name || "لم تحدد"}</td>
              <td>{batch.quantity}</td><td>{batch.printed_count}</td><td>{batch.is_online_sale ? "أونلاين" : "عادي"}</td><td>{batch.note || "—"}</td><td>{new Date(batch.created_at).toLocaleString("ar")}</td>
              <td><button type="button" className="table-action" onClick={() => { setCardBatchFilter(batch.batch_id); setCardSearch(""); setCardStatusFilter(""); setCardPlanFilter(""); setCardFreeFilter(""); setCardOffset(0); setSelectedCardIds([]); setCardManagementTab("all"); setPage("cards"); loadCards("", 0, batch.batch_id, "", "", "").catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل كروت الدفعة")); }}>عرض الكروت</button></td>
            </tr>)}</tbody>
          </table>
          {cardBatches.length === 0 && <div className="empty-state">لا توجد دفعات كروت مسجلة بعد.</div>}
        </div>
      </section>
    );
  }

  function renderRadiusSessions() {
    const formatDateTime = (value: string | null) => value
      ? new Date(value).toLocaleString("ar", { dateStyle: "short", timeStyle: "short" })
      : "—";
    const formatDuration = (seconds: number) => {
      const safe = Math.max(0, Math.floor(seconds));
      const days = Math.floor(safe / 86400);
      const hours = Math.floor((safe % 86400) / 3600);
      const minutes = Math.floor((safe % 3600) / 60);
      return days ? `${days} يوم ${hours} س` : hours ? `${hours} س ${minutes} د` : `${minutes} د`;
    };
    const formatBytes = (bytes: number) => {
      const mb = Math.max(0, bytes) / (1024 * 1024);
      return mb >= 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${mb.toFixed(1)} MB`;
    };
    return <>
      <div className="section-heading">
        <div><h2>جلسات المستخدمين النشطة</h2><p>اتصالات المستخدمين الحالية التي سجلها نظام RADIUS الجديد من أجهزة الشبكة.</p></div>
        <button type="button" className="table-action" disabled={busy} onClick={() => loadRadiusSessions().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحديث جلسات المستخدمين"))}>تحديث الجلسات</button>
      </div>
      <div className="radius-session-summary">
        <div><span>جلسات الاتصال النشطة</span><strong>{radiusSessions.active_count.toLocaleString("ar")}</strong></div>
        <div><span>المستخدمون المتصلون (اكتف)</span><strong>{radiusSessions.active_users_count.toLocaleString("ar")}</strong></div>
        <div><span>إجمالي الجلسات المسجلة</span><strong>{radiusSessions.total_count.toLocaleString("ar")}</strong></div>
        <div><span>الجلسات المعروضة</span><strong>{radiusSessions.items.length.toLocaleString("ar")}</strong></div>
      </div>
      <p className="card-source-note">المصدر: سجل المحاسبة في قاعدة بيانات RADIUS. العدد النشط يعتمد على الجلسات التي لم يصل لها حدث إيقاف (Stop) بعد.</p>
      <div className="table-wrap radius-sessions-table-wrap">
        <table className="radius-sessions-table"><thead><tr><th>اسم المستخدم</th><th>الرقم التسلسلي</th><th>الراوتر</th><th>NAS Identifier</th><th>عنوان IP</th><th>MAC / الجهاز</th><th>بداية الجلسة</th><th>آخر تحديث</th><th>مدة الاتصال</th><th>رفع</th><th>تنزيل</th>{can("sessions.disconnect") && <th>الإجراء</th>}</tr></thead>
          <tbody>{radiusSessions.items.map((session) => <tr key={session.id}>
            <td>{session.username}</td><td>{session.serial_number}</td><td>{session.router_name}</td><td>{session.nas_identifier}</td>
            <td>{session.framed_ip_address || "—"}</td><td>{session.calling_station_id || "—"}</td>
            <td>{formatDateTime(session.started_at)}</td><td>{formatDateTime(session.last_update_at)}</td>
            <td>{formatDuration(session.session_time_seconds)}</td><td>{formatBytes(session.upload_bytes)}</td><td>{formatBytes(session.download_bytes)}</td>{can("sessions.disconnect") && <td><button type="button" className="table-action danger-action" disabled={busy} onClick={() => disconnectRadiusSession(session.id)}>فصل الجلسة</button></td>}
          </tr>)}</tbody>
        </table>
        {radiusSessions.items.length === 0 && <div className="empty-state">لا توجد جلسات مستخدمين نشطة مسجلة حالياً.</div>}
      </div>
    </>;
  }

  function renderCards() {
    const selectableCards = cards.filter((card) => card.status === "generated" && card.assigned_pos_id === null);
    return <>
      <div className="section-heading"><div><h2>{user.card_visibility !== "search_any" ? "إدارة الكروت" : "البحث عن كرت"}</h2><p>{user.card_visibility === "all" ? "عرض وإدارة جميع كروت النظام." : user.card_visibility === "assigned" ? "عرض وإدارة كروت نقاط البيع المرتبطة بحسابك." : "ابحث باسم المستخدم أو الرقم التسلسلي الكامل للوصول إلى كرت من أي نقطة بيع، ثم اعرض بياناته وجلساته."}</p></div>{user.card_visibility !== "search_any" && <span className="count-tag">200 كرت لكل صفحة</span>}</div>
      {user.card_visibility !== "search_any" && cardBatchFilter && <div className="notice">تُعرض كروت الدفعة المحددة فقط. <button type="button" className="table-action" onClick={() => { setCardBatchFilter(""); setCardOffset(0); setSelectedCardIds([]); loadCards(cardSearch, 0, "").catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل الكروت")); }}>إلغاء فلتر الدفعة</button></div>}
      {user.card_visibility !== "search_any" && <div className="card-management-tabs" role="tablist" aria-label="تصنيفات إدارة الكروت">
        <button type="button" role="tab" aria-selected={cardManagementTab === "all"} className={cardManagementTab === "all" ? "active" : ""} onClick={() => { setCardManagementTab("all"); setSelectedCardIds([]); setCardStatusFilter(""); setCardOffset(0); loadCards(cardSearch, 0, cardBatchFilter, "", cardPlanFilter, cardFreeFilter).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل جميع الكروت")); }}>{user.card_visibility === "all" ? "جميع كروت النظام" : "كروت نقاط البيع المرتبطة"}</button>
        <button type="button" role="tab" aria-selected={cardManagementTab === "expired"} className={cardManagementTab === "expired" ? "active" : ""} onClick={() => { setCardManagementTab("expired"); setSelectedCardIds([]); setCardStatusFilter("expired"); setCardOffset(0); loadCards(cardSearch, 0, cardBatchFilter, "expired", cardPlanFilter, cardFreeFilter).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل الكروت المنتهية")); }}>الكروت المنتهية</button>
        <button type="button" role="tab" aria-selected={cardManagementTab === "batches"} className={cardManagementTab === "batches" ? "active" : ""} onClick={() => { setCardManagementTab("batches"); setSelectedCardIds([]); loadCardBatches().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل دفعات الكروت")); }}>دفعات الكروت</button>
        {can("sessions.view") && <button type="button" role="tab" aria-selected={cardManagementTab === "sessions"} className={cardManagementTab === "sessions" ? "active" : ""} onClick={() => { setCardManagementTab("sessions"); setSelectedCardIds([]); loadRadiusSessions().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل جلسات المستخدمين")); }}>جلسات المستخدمين ({radiusSessions.active_count.toLocaleString("ar")})</button>}
      </div>}
      {user.card_visibility !== "search_any" && cardManagementTab === "batches" ? renderBatches() : user.card_visibility !== "search_any" && cardManagementTab === "sessions" ? renderRadiusSessions() : <>
      <p className="card-source-note">هذه القائمة تعرض الكروت المسجلة في قاعدة بيانات RADIUS. جلب كروت MikroTik مباشرة سيُضاف عند تنفيذ ربط مزامنة الراوتر. تُحدَّث أرصدة الوقت والرفع والتنزيل عند وصول رسائل محاسبة RADIUS (Start / Interim / Stop)، لذلك قد تتأخر عن الاستهلاك اللحظي بين الرسائل.</p>
      {(can("printing.create") && can("printing.credentials") && can("pos.view")) && user.card_visibility !== "search_any" && <div className="card-selection-toolbar">
        <label><input type="checkbox" disabled={selectableCards.length === 0} checked={selectableCards.length > 0 && selectableCards.every((card) => selectedCardIds.includes(card.id))} onChange={(e) => setSelectedCardIds(e.target.checked ? selectableCards.map((card) => card.id) : [])} /> تحديد الكروت المؤهلة في الصفحة الحالية</label>
        <span>تم تحديد {selectedCardIds.length} كرت من الصفحة الحالية</span>
        <button type="button" disabled={!selectedCardIds.length || busy} onClick={prepareSelectedCardsForPrinting}>تجهيز المحدد للطباعة</button>
        <button type="button" className="secondary-button" disabled={!selectedCardIds.length} onClick={() => setSelectedCardIds([])}>إلغاء التحديد</button>
      </div>}
      <div className="card-management-filters">
        <label htmlFor="card-search">بحث في الكروت<input id="card-search" value={cardSearch} onChange={(e) => { setCardSearch(e.target.value); setCardSessionHistory(null); }} onKeyDown={(e) => { if (e.key === "Enter") applyCardSearch(); }} placeholder={user.card_visibility !== "search_any" ? "اسم المستخدم أو الرقم التسلسلي" : "أدخل اسم المستخدم أو الرقم التسلسلي كاملاً"} /></label>
        <button type="button" className="table-action" disabled={busy} onClick={applyCardSearch}>بحث</button>
        {user.card_visibility !== "search_any" && <>
          <label htmlFor="card-status-filter">الحالة<select id="card-status-filter" value={cardStatusFilter} onChange={(e) => { setCardStatusFilter(e.target.value); setCardOffset(0); setSelectedCardIds([]); loadCards(cardSearch, 0, cardBatchFilter, e.target.value, cardPlanFilter, cardFreeFilter).catch((err) => setError(err instanceof Error ? err.message : "تعذر تطبيق فلتر الحالة")); }}><option value="">كل الحالات</option><option value="generated">منشأ</option><option value="allocated">مخصص لنقطة بيع</option><option value="active">متصل</option><option value="suspended">موقوف</option><option value="cancelled">ملغي</option><option value="printed_free">مجاني مطبوع</option><option value="expired">منتهي الصلاحية</option><option value="exhausted">نفد الرصيد</option></select></label>
          <label htmlFor="card-plan-filter">الباقة<select id="card-plan-filter" value={cardPlanFilter} onChange={(e) => { setCardPlanFilter(e.target.value); setCardOffset(0); setSelectedCardIds([]); loadCards(cardSearch, 0, cardBatchFilter, cardStatusFilter, e.target.value, cardFreeFilter).catch((err) => setError(err instanceof Error ? err.message : "تعذر تطبيق فلتر الباقة")); }}><option value="">كل الباقات</option>{plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}</select></label>
          <label htmlFor="card-free-filter">نوع الكرت<select id="card-free-filter" value={cardFreeFilter} onChange={(e) => { setCardFreeFilter(e.target.value); setCardOffset(0); setSelectedCardIds([]); loadCards(cardSearch, 0, cardBatchFilter, cardStatusFilter, cardPlanFilter, e.target.value).catch((err) => setError(err instanceof Error ? err.message : "تعذر تطبيق فلتر نوع الكرت")); }}><option value="">الكل</option><option value="paid">تجاري</option><option value="free">مجاني</option></select></label>
          <button type="button" className="table-action" onClick={() => { setCardSearch(""); setCardStatusFilter(""); setCardPlanFilter(""); setCardFreeFilter(""); setCardBatchFilter(""); setCardOffset(0); setSelectedCardIds([]); loadCards("", 0, "", "", "", "").catch((err) => setError(err instanceof Error ? err.message : "تعذر إعادة ضبط الفلاتر")); }}>مسح الفلاتر</button>
        </>}
      </div>
      <div className="card-results-strip">
        <div><strong>{cards.length.toLocaleString("ar")}</strong><span>نتيجة معروضة في هذه الصفحة</span></div>
        {user.card_visibility !== "search_any" && <div><strong>{(Math.floor(cardOffset / 200) + 1).toLocaleString("ar")}</strong><span>رقم الصفحة</span></div>}
        {(can("printing.create") && can("printing.credentials") && can("pos.view")) && user.card_visibility !== "search_any" && <div><strong>{selectedCardIds.length.toLocaleString("ar")}</strong><span>كرت محدد للطباعة</span></div>}
        {busy && <span className="card-results-loading">جارٍ تحديث النتائج…</span>}
      </div>
      <div className="table-wrap card-management-table-wrap"><table className="card-management-table"><thead><tr>{(can("printing.create") && can("printing.credentials") && can("pos.view")) && user.card_visibility !== "search_any" && <th>تحديد</th>}<th>الرقم التسلسلي</th><th>اسم المستخدم</th><th>نوع الدخول</th><th>الباقة</th><th>الحالة</th><th>أول استخدام</th><th>تاريخ الانتهاء</th><th>وقت الجلسات المستخدم / المتبقي</th><th>الوقت المتبقي للصلاحية</th><th>الجلسات النشطة</th><th>الاستهلاك (رفع / تنزيل)</th><th>البيانات المستهلكة / المتبقية</th><th>حد التزامن المسموح</th><th>السرعة</th><th>مجاني</th>{can("sessions.view") && <th>الجلسات</th>}{can("cards.update") && <th>الإجراءات</th>}</tr></thead><tbody>
        {cards.map((card) => {
          const snapshot = card.plan_snapshot ?? {};
          const remaining = typeof card.remaining_time_seconds === "number" ? card.remaining_time_seconds : null;
          const totalConsumedBytes = Math.max(0, Number(card.upload_bytes || 0)) + Math.max(0, Number(card.download_bytes || 0));
          const remainingDataBytes = typeof card.remaining_data_bytes === "number" ? card.remaining_data_bytes : null;
          const expiryTimestamp = card.expires_at ? Date.parse(card.expires_at) : Number.NaN;
          const sharedUsersLabel = typeof card.shared_users_limit === "number" ? String(card.shared_users_limit) : "غير محدود";
          const speed = card.speed_limit || "غير محددة";
          const formatDateTime = (value: string | null) => value
            ? new Date(value).toLocaleString("ar", { dateStyle: "short", timeStyle: "short" })
            : "—";
          const formatDuration = (seconds: number) => {
            const safe = Math.max(0, Math.floor(seconds));
            const days = Math.floor(safe / 86400);
            const hours = Math.floor((safe % 86400) / 3600);
            const minutes = Math.floor((safe % 3600) / 60);
            return days ? `${days} يوم ${hours} س` : hours ? `${hours} س ${minutes} د` : `${minutes} د`;
          };
          const validityRemainingLabel = card.status === "expired" ? "انتهت"
            : Number.isFinite(expiryTimestamp)
              ? expiryTimestamp <= Date.now() ? "انتهت" : formatDuration(Math.ceil((expiryTimestamp - Date.now()) / 1000))
              : card.expires_at ? "غير متاح"
              : typeof snapshot.validity_period_seconds === "number" && snapshot.validity_period_seconds > 0
                ? card.first_used_at ? "غير متاح" : "تبدأ بعد أول استخدام"
                : "مفتوحة";
          const formatBytes = (bytes: number) => {
            if (bytes <= 0) return "0 ميجابايت";
            const mb = bytes / (1024 * 1024);
            return mb >= 1024 ? `${(mb / 1024).toFixed(2)} جيجابايت` : `${mb.toFixed(1)} ميجابايت`;
          };
          return <tr key={card.id}>
            {(can("printing.create") && can("printing.credentials") && can("pos.view")) && user.card_visibility !== "search_any" && <td><input type="checkbox" aria-label={`تحديد ${card.username}`} disabled={card.status !== "generated" || card.assigned_pos_id !== null} checked={selectedCardIds.includes(card.id)} onChange={() => toggleSelectedCard(card.id)} /></td>}
            <td>{card.serial_number}</td><td>{card.username}</td><td>{card.card_type}</td>
            <td>{plans.find((p) => p.id === card.plan_id)?.name ?? card.plan_id}</td>
            <td>{card.status === "generated" ? "منشأ" : card.status === "allocated" ? "مخصص لنقطة بيع" : card.status === "active" ? "متصل" : card.status === "suspended" ? "موقوف" : card.status === "cancelled" ? "ملغي" : card.status === "printed_free" ? "مجاني مطبوع" : card.status === "expired" ? "منتهي الصلاحية" : card.status === "exhausted" ? "نفد الرصيد" : card.status}</td>
            <td>{formatDateTime(card.first_used_at)}</td>
            <td>{formatDateTime(card.expires_at)}</td>
            <td>{formatDuration(card.used_seconds)} / {remaining === null ? "غير محدود" : formatDuration(remaining)}</td>
            <td>{validityRemainingLabel}</td>
            <td>{card.active_sessions_count.toLocaleString("ar")}</td>
            <td>{formatBytes(card.upload_bytes)} / {formatBytes(card.download_bytes)}</td>
            <td>{formatBytes(totalConsumedBytes)} / {remainingDataBytes === null ? "غير محدود" : formatBytes(remainingDataBytes)}</td>
            <td>{sharedUsersLabel}</td>
            <td>{speed}</td><td>{card.is_free ? "نعم" : "لا"}</td>
            {can("sessions.view") && <td><button type="button" className="table-action" onClick={() => loadCardSessionHistory(card)}>عرض الجلسات</button></td>}
            {can("cards.update") && user.card_visibility !== "search_any" && <td className="actions-cell">{card.status === "suspended" ? <button type="button" className="table-action" disabled={busy} onClick={() => changeCardStatus(card, "reactivate")}>إعادة تفعيل</button> : ["generated", "allocated", "active", "printed_free"].includes(card.status) ? <button type="button" className="table-action" disabled={busy} onClick={() => changeCardStatus(card, "suspend")}>إيقاف</button> : null}{["generated", "printed_free"].includes(card.status) && !card.first_used_at && !card.assigned_pos_id && <button type="button" className="table-action danger-action" disabled={busy} onClick={() => changeCardStatus(card, "cancel")}>إلغاء</button>}</td>}
          </tr>;
        })}
      </tbody></table>{cards.length === 0 && <div className="empty-state">لا توجد كروت تطابق البحث في هذه الصفحة.</div>}</div>
      {cardSessionHistory && <section className="panel" style={{ marginTop: 16 }}>
        <div className="section-heading compact-heading">
          <div><h3>سجل جلسات الكرت</h3><p>{cardSessionHistory.username} — {cardSessionHistory.serial_number}</p></div>
          <button type="button" className="table-action" onClick={() => setCardSessionHistory(null)}>إغلاق</button>
        </div>
        <div className="pos-management-summary">
          <article><span>إجمالي الجلسات</span><strong>{cardSessionHistory.total_sessions.toLocaleString("ar")}</strong></article>
          <article><span>الجلسات النشطة</span><strong>{cardSessionHistory.active_sessions.toLocaleString("ar")}</strong></article>
        </div>
        <div className="table-wrap"><table><thead><tr><th>الراوتر</th><th>معرّف الجلسة</th><th>IP</th><th>MAC</th><th>بداية الاتصال</th><th>آخر تحديث</th><th>نهاية الاتصال</th><th>المدة</th><th>رفع</th><th>تنزيل</th></tr></thead><tbody>
          {cardSessionHistory.items.map((session) => <tr key={session.id}>
            <td>{session.router_name}</td><td>{session.acct_session_id}</td><td>{session.framed_ip_address ?? "—"}</td><td>{session.calling_station_id ?? "—"}</td>
            <td>{new Date(session.started_at).toLocaleString("ar")}</td><td>{session.last_update_at ? new Date(session.last_update_at).toLocaleString("ar") : "—"}</td>
            <td>{session.stopped_at ? new Date(session.stopped_at).toLocaleString("ar") : "نشطة"}</td>
            <td>{formatDuration(session.session_time_seconds)}</td><td>{formatBytes(session.upload_bytes)}</td><td>{formatBytes(session.download_bytes)}</td>
          </tr>)}
        </tbody></table>{cardSessionHistory.items.length === 0 && <div className="empty-state">لا توجد جلسات مسجلة لهذا الكرت.</div>}</div>
      </section>}
      {user.card_visibility !== "search_any" && <div className="pagination-controls"><button type="button" className="table-action" disabled={cardOffset === 0 || busy} onClick={() => changeCardPage(cardOffset - 200)}>السابق</button><span>الصفحة {Math.floor(cardOffset / 200) + 1}</span><button type="button" className="table-action" disabled={!hasMoreCards || busy} onClick={() => changeCardPage(cardOffset + 200)}>التالي</button></div>}
      </>}
    </>;
  }

  function renderPosManagement() {
    const activePoints = points.filter((point) => point.is_active).length;
    const inactivePoints = points.length - activePoints;
    const normalizedPosSearch = posSearch.trim().toLocaleLowerCase();
    const visiblePoints = points.filter((point) => {
      const matchesStatus = posStatusFilter === "all" || (posStatusFilter === "active" ? point.is_active : !point.is_active);
      const searchable = [point.name, point.code, point.contact_name ?? "", point.phone ?? ""].join(" ").toLocaleLowerCase();
      return matchesStatus && (!normalizedPosSearch || searchable.includes(normalizedPosSearch));
    });
    return (
      <section className="pos-management-page">
        <div className="section-heading pos-page-heading">
          <div>
            <span className="eyebrow">إدارة المخزون والتوزيع</span>
            <h2>نقاط البيع</h2>
            <p>سجّل نقاط البيع مرة واحدة، ثم اختر النقطة المسجلة عند إنشاء الكروت أو تنفيذ الطباعة.</p>
          </div>
          <span className="count-tag">{points.length.toLocaleString("ar")} نقطة بيع</span>
        </div>

        <div className="pos-management-summary">
          <article><span>إجمالي النقاط</span><strong>{points.length.toLocaleString("ar")}</strong><small>جميع النقاط المسجلة</small></article>
          <article><span>نقاط مفعّلة</span><strong>{activePoints.toLocaleString("ar")}</strong><small>متاحة للعمليات الجديدة</small></article>
          <article><span>نقاط متوقفة</span><strong>{inactivePoints.toLocaleString("ar")}</strong><small>محفوظة دون حذف سجلاتها</small></article>
        </div>

        <div className="pos-management-layout">
          {(can("pos.create") || (editingPosId !== null && can("pos.update"))) && <form className="panel pos-editor-panel" onSubmit={createPointOfSale}>
            <div className="pos-editor-heading">
              <div><span className="eyebrow">{editingPosId !== null ? "تحديث البيانات" : "نقطة بيع جديدة"}</span><h3>{editingPosId !== null ? "تعديل نقطة البيع" : "إضافة نقطة بيع"}</h3></div>
              <span className="pos-editor-icon">＋</span>
            </div>
            <div className="form-grid pos-editor-grid">
              <label>رمز نقطة البيع<input value={posDraft.code} onChange={(e) => setPosDraft({ ...posDraft, code: e.target.value })} disabled={editingPosId !== null} required minLength={2} maxLength={50} pattern="[A-Za-z0-9_-]+" placeholder="مثال: POS-01" /><span className="field-hint">أحرف إنجليزية وأرقام وشرطة فقط</span></label>
              <label>اسم نقطة البيع<input value={posDraft.name} onChange={(e) => setPosDraft({ ...posDraft, name: e.target.value })} required minLength={2} maxLength={150} placeholder="اسم المحل أو الموزع" /></label>
              <label>اسم المسؤول<input value={posDraft.contactName} onChange={(e) => setPosDraft({ ...posDraft, contactName: e.target.value })} maxLength={150} placeholder="اسم المسؤول (اختياري)" /></label>
              <label>رقم الهاتف<input value={posDraft.phone} onChange={(e) => setPosDraft({ ...posDraft, phone: e.target.value })} maxLength={40} placeholder="رقم التواصل (اختياري)" /></label>
              {user.roles.includes("owner") && <>
                <label>سقف المديونية بالريال<input type="number" min="0" step="0.01" value={posDraft.debtLimit} onChange={(e) => setPosDraft({ ...posDraft, debtLimit: e.target.value })} placeholder="اتركه فارغاً بلا سقف" /><span className="field-hint">عند بلوغ السقف تتوقف العمليات الجديدة حتى تسجيل سداد.</span></label>
                <label className="day-selector"><input type="checkbox" checked={posDraft.allowCardCreation} onChange={(e) => setPosDraft({ ...posDraft, allowCardCreation: e.target.checked })} /> السماح بإنشاء الكروت</label>
                <label className="day-selector"><input type="checkbox" checked={posDraft.allowPrinting} onChange={(e) => setPosDraft({ ...posDraft, allowPrinting: e.target.checked })} /> السماح بالطباعة</label>
              </>}
            </div>
            <div className="pos-editor-actions">
              <button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ..." : editingPosId !== null ? "حفظ التعديلات" : "إضافة نقطة البيع"}</button>
              {editingPosId !== null && <button type="button" className="secondary-button" onClick={() => { setEditingPosId(null); setPosDraft({ code: "", name: "", contactName: "", phone: "", debtLimit: "", allowCardCreation: true, allowPrinting: true }); }}>إلغاء التعديل</button>}
            </div>
          </form>}

          <section className="panel pos-directory-panel">
            <div className="pos-directory-heading">
              <div><span className="eyebrow">دليل الموزعين</span><h3>النقاط المسجلة</h3><p>يمكنك تعديل بيانات النقطة أو إيقافها وإعادة تفعيلها.</p></div>
              <span className="count-tag">{points.length.toLocaleString("ar")} سجل</span>
            </div>
            <div className="pos-directory-tools">
              <label className="pos-directory-search">بحث في النقاط<input type="search" value={posSearch} onChange={(event) => setPosSearch(event.target.value)} placeholder="اسم النقطة أو الرمز أو المسؤول أو الهاتف" /></label>
              <label className="pos-directory-filter">حالة النقطة<select value={posStatusFilter} onChange={(event) => setPosStatusFilter(event.target.value as "all" | "active" | "inactive")}><option value="all">كل الحالات</option><option value="active">المفعّلة فقط</option><option value="inactive">المتوقفة فقط</option></select></label>
              <span className="pos-directory-result">عرض {visiblePoints.length.toLocaleString("ar")} من {points.length.toLocaleString("ar")} نقطة</span>
            </div>
            <div className="table-wrap pos-directory-table">
              <table><thead><tr><th>الرمز</th><th>اسم نقطة البيع</th><th>المسؤول</th><th>رقم الهاتف</th><th>سقف المديونية</th><th>إنشاء الكروت</th><th>الطباعة</th><th>الحالة</th><th>الإجراءات</th></tr></thead>
                <tbody>{visiblePoints.map((point) => (
                  <tr key={point.id}>
                    <td><span className="pos-code">{point.code}</span></td>
                    <td><strong>{point.name}</strong></td>
                    <td>{point.contact_name || "—"}</td>
                    <td>{point.phone || "—"}</td>
                    <td>{point.debt_limit === null ? "بلا سقف" : Number(point.debt_limit).toLocaleString("en-US", { minimumFractionDigits: 2 }) + " ريال"}</td>
                    <td><span className={point.allow_card_creation ? "pos-status active" : "pos-status inactive"}>{point.allow_card_creation ? "مسموح" : "موقوف"}</span></td>
                    <td><span className={point.allow_printing ? "pos-status active" : "pos-status inactive"}>{point.allow_printing ? "مسموح" : "موقوف"}</span></td>
                    <td><span className={point.is_active ? "pos-status active" : "pos-status inactive"}>{point.is_active ? "مفعّلة" : "متوقفة"}</span></td>
                    <td className="actions-cell">
                      {can("pos.update") ? <>
                        <button type="button" className="table-action" disabled={busy} onClick={() => { setEditingPosId(point.id); setPosDraft({ code: point.code, name: point.name, contactName: point.contact_name || "", phone: point.phone || "", debtLimit: point.debt_limit === null ? "" : String(point.debt_limit), allowCardCreation: point.allow_card_creation, allowPrinting: point.allow_printing }); }}>تعديل</button>
                        {user.roles.includes("owner") && <>
                          <button type="button" className="table-action" disabled={busy} onClick={() => togglePointOperation(point, "allow_card_creation")}>{point.allow_card_creation ? "إيقاف الإنشاء" : "السماح بالإنشاء"}</button>
                          <button type="button" className="table-action" disabled={busy} onClick={() => togglePointOperation(point, "allow_printing")}>{point.allow_printing ? "إيقاف الطباعة" : "السماح بالطباعة"}</button>
                          <button type="button" className={point.is_active ? "table-action danger-action" : "table-action"} disabled={busy} onClick={() => togglePointOfSale(point)}>{point.is_active ? "إيقاف الحساب" : "تفعيل الحساب"}</button>
                        </>}
                      </> : <span className="field-hint">عرض فقط</span>}
                    </td>
                  </tr>
                ))}</tbody>
              </table>
              {visiblePoints.length === 0 && <div className="empty-state">{points.length === 0 ? "لا توجد نقاط بيع مسجلة بعد. أضف أول نقطة بيع من النموذج." : "لا توجد نقاط تطابق البحث أو الحالة المحددة."}</div>}
            </div>
            <div className="pos-directory-note"><span>معلومة</span> إيقاف نقطة البيع يمنع استخدامها في عمليات الطباعة الجديدة، مع الاحتفاظ بسجلها وحركاتها السابقة.</div>
          </section>
        </div>
      </section>
    );
  }

  function renderPos() {
    const selectedTemplate = cardTemplates.find((item) => item.code === printTemplate);
    const selectedLayout = selectedTemplate?.layout ?? {};
    const layoutPosition = (xKey: string, yKey: string) =>
      selectedLayout[xKey] === undefined || selectedLayout[yKey] === undefined
        ? undefined
        : { position: "absolute" as const, left: String(selectedLayout[xKey]) + "%", top: String(selectedLayout[yKey]) + "%", transform: "translate(-50%, -50%)", width: "88%" };
    const printableCards = cards.filter((card) => card.status === "generated" && card.assigned_pos_id === null);
    const selectedPoint = points.find((point) => String(point.id) === selectedPosId);
    const atDebtLimit = selectedPoint?.debt_limit !== null && selectedPoint?.debt_limit !== undefined &&
      posAccount !== null && posAccount !== undefined &&
      Number(posAccount.balance_due) >= Number(selectedPoint.debt_limit);
    const cardsPerPage = Math.max(1, Math.min(60, Number(selectedLayout.columns ?? 2) * Number(selectedLayout.rows ?? 5)));
    return (
      <>
        <div className="section-heading">
          <div><h2>الطباعة والدفعات</h2><p>اختر نقطة بيع مسجلة مسبقاً، وحدد الكروت ثم سجل الطباعة أو أعد طباعة دفعة سابقة.</p></div>
        </div>

        <div className="pos-toolbar">
          <label>اختر نقطة البيع
            <select value={selectedPosId} onChange={(e) => {
              const id = e.target.value;
              setPrintPreviewCards([]);
              setSelectedPosId(id);
              Promise.all([loadPosInventory(id), loadPrintHistory(id), ...(can("finance.view") ? [loadPosAccount(id)] : [])]).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل بيانات نقطة البيع"));
            }}>
              <option value="">-- اختر نقطة بيع --</option>
              {points.map((point) => <option key={point.id} value={point.id}>{point.name} — {point.code}{point.is_active ? "" : " (متوقفة)"}</option>)}
            </select>
          </label>
          {selectedPoint && user.roles.includes("owner") && <button type="button" className="table-action" disabled={busy} onClick={() => togglePointOfSale(selectedPoint)}>{selectedPoint.is_active ? "إيقاف النقطة" : "تفعيل النقطة"}</button>}
        </div>

        {selectedPosId && selectedPoint && !selectedPoint.allow_printing && (
          <div className="notice">الطباعة متوقفة لهذه النقطة بقرار من الإدارة. يمكنك مراجعة السجلات، لكن لن تُقبل أي عملية طباعة جديدة.</div>
        )}
        {selectedPosId && atDebtLimit && (
          <div className="notice">وصلت نقطة البيع إلى سقف المديونية. أوقف النظام الطباعة حتى تسجيل سداد يخفض الرصيد المستحق.</div>
        )}
        {selectedPosId && selectedPoint && !selectedPoint.allow_card_creation && (
          <div className="notice">إنشاء الكروت متوقف لهذه النقطة بقرار من الإدارة.</div>
        )}
        {selectedPosId && posInventory && (
          <div className="pos-stats">
            <div><span>الكروت المخصصة</span><strong>{posInventory.allocated_cards}</strong></div>
            <div><span>الكروت المستخدمة</span><strong>{posInventory.used_cards}</strong></div>
            <div><span>الكروت الموقوفة</span><strong>{posInventory.suspended_cards}</strong></div>
            <div><span>القيمة التجارية المطبوعة</span><strong>{Number(posInventory.commercial_printed_value).toLocaleString("en-US")}</strong></div>
            <div><span>الكروت المجانية المطبوعة</span><strong>{posInventory.free_cards_printed}</strong></div>
          </div>
        )}

        {can("finance.view") && selectedPosId && posAccount && (
          <section className="pos-account-section">
            <div className="section-heading compact-heading pos-account-heading"><div><span className="eyebrow">المتابعة المالية</span><h2>الحساب المالي لنقطة البيع</h2><p>الرصيد يُحدّث تلقائياً عند تخصيص الكروت التجارية، ولا تُحتسب إعادة الطباعة أو الكروت المجانية.</p></div><span className="pos-account-point">{selectedPoint?.name ?? "نقطة البيع المحددة"}</span></div>
            <div className="pos-stats account-stats pos-finance-summary">
              <div><span>إجمالي المديونية</span><strong>{Number(posAccount.total_debit).toLocaleString("en-US", { minimumFractionDigits: 2 })} ريال</strong></div>
              <div><span>إجمالي السداد والخصومات</span><strong>{Number(posAccount.total_credit).toLocaleString("en-US", { minimumFractionDigits: 2 })} ريال</strong></div>
              <div><span>الرصيد المستحق</span><strong>{Number(posAccount.balance_due).toLocaleString("en-US", { minimumFractionDigits: 2 })} ريال</strong></div>
              <div><span>سقف المديونية</span><strong>{selectedPoint?.debt_limit === null || selectedPoint?.debt_limit === undefined ? "غير محدد" : Number(selectedPoint.debt_limit).toLocaleString("en-US", { minimumFractionDigits: 2 }) + " ريال"}</strong></div>
              <div><span>المتاح قبل السقف</span><strong>{selectedPoint?.debt_limit === null || selectedPoint?.debt_limit === undefined ? "غير محدود" : Math.max(0, Number(selectedPoint.debt_limit) - Number(posAccount.balance_due)).toLocaleString("en-US", { minimumFractionDigits: 2 }) + " ريال"}</strong></div>
            </div>
            {can("finance.create") && <form className="panel form-grid account-entry-form" onSubmit={createAccountEntry}>
              <label>نوع الحركة<select value={accountDraft.entryType} onChange={(e) => setAccountDraft({ ...accountDraft, entryType: e.target.value, direction: e.target.value === "payment" || e.target.value === "commission" || e.target.value === "return" ? "credit" : accountDraft.direction })}>
                <option value="payment">سداد من نقطة البيع</option><option value="commission">عمولة مستحقة للنقطة</option><option value="return">مرتجع / خصم</option><option value="adjustment">تسوية يدوية</option>
              </select></label>
              <label>اتجاه الحركة<select value={accountDraft.direction} onChange={(e) => setAccountDraft({ ...accountDraft, direction: e.target.value as "debit" | "credit" })}><option value="credit">يخصم من المديونية (دائن)</option><option value="debit">يضاف للمديونية (مدين)</option></select></label>
              <label>المبلغ بالريال<input type="number" min="0.01" step="0.01" value={accountDraft.amount} onChange={(e) => setAccountDraft({ ...accountDraft, amount: e.target.value })} required /></label>
              <label>البيان<input value={accountDraft.description} onChange={(e) => setAccountDraft({ ...accountDraft, description: e.target.value })} maxLength={500} placeholder="مثال: سداد نقدي" /></label>
              <label>رقم مرجعي (اختياري)<input value={accountDraft.reference} onChange={(e) => setAccountDraft({ ...accountDraft, reference: e.target.value })} maxLength={120} /></label>
              <div className="form-actions"><button type="submit" disabled={busy || !accountDraft.amount || Number(accountDraft.amount) <= 0}>{busy ? "جارٍ التسجيل..." : "تسجيل الحركة"}</button></div>
            </form>}
            <div className="section-heading compact-heading"><div><h2>كشف الحساب</h2><p>آخر 100 حركة مالية، مرتبة من الأحدث إلى الأقدم.</p></div><span className="count-tag">{posEntries.length} حركة</span></div>
            <div className="table-wrap pos-account-table"><table><thead><tr><th>التاريخ</th><th>نوع الحركة</th><th>البيان</th><th>مدين</th><th>دائن</th><th>الموظف</th><th>المرجع</th></tr></thead><tbody>
              {posEntries.map((entry) => <tr key={entry.id}><td>{new Date(entry.created_at).toLocaleString("ar")}</td><td>{({ card_delivery: "تسليم كروت", payment: "سداد", commission: "عمولة", return: "مرتجع", adjustment: "تسوية" } as Record<string, string>)[entry.entry_type] ?? entry.entry_type}</td><td>{entry.description || "—"}</td><td className={entry.direction === "debit" ? "finance-amount debit" : "finance-amount"}>{entry.direction === "debit" ? Number(entry.amount).toFixed(2) : "—"}</td><td className={entry.direction === "credit" ? "finance-amount credit" : "finance-amount"}>{entry.direction === "credit" ? Number(entry.amount).toFixed(2) : "—"}</td><td>{entry.created_by || "—"}</td><td>{entry.reference || "—"}</td></tr>)}
            </tbody></table>{posEntries.length === 0 && <div className="empty-state">لا توجد حركات مالية مسجلة لهذه النقطة.</div>}</div>
          </section>
        )}

        {selectedPosId && (
          <>
            <div className="section-heading compact-heading"><div><h2>الكروت الجاهزة للتخصيص</h2><p>حدد الكروت المنشأة وغير المخصصة. عند التسجيل تُرحّل القيمة التجارية مرة واحدة فقط.</p></div><span className="count-tag">{printableCards.length} كرت</span></div>
            <div className="card-search">
              <label htmlFor="pos-card-search">بحث عن كرت</label>
              <input id="pos-card-search" value={cardSearch} onChange={(e) => { setCardSearch(e.target.value); setCardOffset(0); loadCards(e.target.value, 0).catch((err) => setError(err instanceof Error ? err.message : "تعذر البحث")); }} placeholder={user.card_visibility === "search_any" ? "أدخل اسم المستخدم أو الرقم التسلسلي كاملاً" : "اسم المستخدم أو الرقم التسلسلي"} />
              <button type="button" className="table-action" onClick={() => loadCards(cardSearch, cardOffset).catch((err) => setError(err instanceof Error ? err.message : "تعذر التحديث"))}>تحديث</button>
            </div>
            <div className="table-wrap">
              <table><thead><tr><th>اختيار</th><th>الرقم التسلسلي</th><th>اسم المستخدم</th><th>الباقة</th><th>القيمة</th><th>التصنيف</th></tr></thead>
                <tbody>{printableCards.map((card) => <tr key={card.id}>
                  <td><input type="checkbox" aria-label={`اختيار الكرت ${card.username}`} checked={selectedPrintCardIds.includes(card.id)} onChange={() => togglePrintCard(card.id)} /></td>
                  <td>{card.serial_number}</td><td>{card.username}</td>
                  <td>{plans.find((plan) => plan.id === card.plan_id)?.name ?? card.plan_id}</td>
                  <td>{card.is_free ? "0" : Number(card.price_snapshot).toLocaleString("en-US")}</td>
                  <td>{card.is_free ? "مجاني" : "تجاري"}</td>
                </tr>)}</tbody>
              </table>
              {printableCards.length === 0 && <div className="empty-state">لا توجد كروت جاهزة في هذه الصفحة من نتائج البحث.</div>}
            </div>
            <div className="pagination-controls">
              <button type="button" className="table-action" disabled={cardOffset === 0 || busy} onClick={() => changeCardPage(cardOffset - 200)}>السابق</button>
              <span>صفحة {Math.floor(cardOffset / 200) + 1}</span>
              <button type="button" className="table-action" disabled={!hasMoreCards || busy} onClick={() => changeCardPage(cardOffset + 200)}>التالي</button>
            </div>
            <div className="panel pos-print-panel">
              <div className="print-mode-section">
                <h3>طريقة الطباعة</h3>
                <div className="print-mode-grid">
                  <button type="button" className={printMode === "default" ? "print-mode-option active" : "print-mode-option"} onClick={() => { setPrintMode("default"); setPrintOptions((current) => ({ ...current, sequential: false })); setPrintImportSummary(""); }}>الطباعة الافتراضية<small>طباعة الكروت المحددة بالشكل المعتاد</small></button>
                  <button type="button" className={printMode === "sequential" ? "print-mode-option active" : "print-mode-option"} onClick={() => { setPrintMode("sequential"); setPrintOptions((current) => ({ ...current, sequential: true })); setPrintImportSummary(""); }}>الطباعة المتسلسلة<small>ترتيب القسائم حسب تسلسل الاختيار</small></button>
                  <button type="button" className={printMode === "file" ? "print-mode-option active" : "print-mode-option"} onClick={() => setPrintMode("file")}>من ملف استيراد<small>تحديد الكروت من ملف CSV أو TXT</small></button>
                  <button type="button" className={printMode === "single" ? "print-mode-option active" : "print-mode-option"} onClick={() => { setPrintMode("single"); setSelectedPrintCardIds((current) => current.slice(0, 1)); setPrintOptions((current) => ({ ...current, sequential: false })); setPrintImportSummary(""); }}>طباعة كرت واحد<small>يسمح بتحديد كرت واحد فقط</small></button>
                </div>
                {printMode === "file" && <label className="print-file-picker">استيراد قائمة أسماء المستخدمين أو الأرقام التسلسلية<input type="file" accept=".csv,.txt,text/csv,text/plain" onChange={importPrintSelection} /><small>العمود الأول فقط، وتتم المطابقة مع الكروت الظاهرة في نتائج الصفحة المحمّلة.</small></label>}
                {printImportSummary && <div className="notice print-import-summary">{printImportSummary}</div>}
                <div className="print-selection-tools"><span>المحدد: {selectedPrintCardIds.length} كرت</span><div><button type="button" className="table-action" onClick={() => setSelectedPrintCardIds(printMode === "single" ? (printableCards[0] ? [printableCards[0].id] : []) : printableCards.slice(0, 5000).map((card) => card.id))} disabled={printableCards.length === 0}>تحديد الكروت الظاهرة</button><button type="button" className="table-action" onClick={() => setSelectedPrintCardIds([])} disabled={!selectedPrintCardIds.length}>إلغاء التحديد</button></div></div>
              </div>
              <label>قالب الطباعة
                <select value={printTemplate} onChange={(e) => setPrintTemplate(e.target.value)}>
                  {cardTemplates.map((item) => <option key={item.id} value={item.code}>{item.name}</option>)}
                </select>
              </label>
              <div className="plan-form-section">
                <h3>خيارات الطباعة</h3>
                <div className="day-selector">
                  <label><input type="checkbox" checked={printOptions.show_username} onChange={(e) => setPrintOptions({ ...printOptions, show_username: e.target.checked })} /> إظهار اسم المستخدم</label>
                  <label><input type="checkbox" checked={printOptions.show_password} onChange={(e) => setPrintOptions({ ...printOptions, show_password: e.target.checked })} /> إظهار كلمة المرور</label>
                  <label><input type="checkbox" checked={printOptions.show_serial_number} onChange={(e) => setPrintOptions({ ...printOptions, show_serial_number: e.target.checked })} /> إظهار الرقم التسلسلي</label>
                  <label><input type="checkbox" checked={printOptions.show_plan} onChange={(e) => setPrintOptions({ ...printOptions, show_plan: e.target.checked })} /> إظهار اسم الباقة</label>
                  <label><input type="checkbox" checked={printOptions.show_price} onChange={(e) => setPrintOptions({ ...printOptions, show_price: e.target.checked })} /> إظهار السعر</label>
                  <label><input type="checkbox" checked={printOptions.show_limits} onChange={(e) => setPrintOptions({ ...printOptions, show_limits: e.target.checked })} /> إظهار الرصيد والوقت والصلاحية</label>
                  <label><input type="checkbox" checked={printOptions.sequential} onChange={(e) => setPrintOptions({ ...printOptions, sequential: e.target.checked })} /> ترتيب متسلسل</label>
                </div>
              </div>
              <div className="pos-print-summary">تم اختيار {selectedPrintCardIds.length} كرت. الكروت المجانية تظهر في القسائم ولا تدخل في قيمة نقطة البيع.</div>
              <button type="button" disabled={busy || selectedPrintCardIds.length === 0 || !selectedPoint?.is_active || !selectedPoint?.allow_printing || atDebtLimit || !can("printing.create") || !can("printing.credentials") || !can("templates.view")} onClick={printSelectedCards}>{busy ? "جارٍ التسجيل..." : "تسجيل دفعة الطباعة وتخصيص الكروت"}</button>
            </div>
            {printPreviewCards.length > 0 && (
              <section className="voucher-print-preview">
                <div className="voucher-toolbar">
                  <div><strong>معاينة القسائم</strong><span>كلمات المرور تظهر في هذه المعاينة فقط ولا تظهر في سجل الكروت.</span></div>
                  <div>
                    <button type="button" onClick={() => window.print()}>طباعة القسائم</button>
                    <button type="button" className="secondary-button" onClick={() => setPrintPreviewCards([])}>إغلاق المعاينة</button>
                  </div>
                </div>
                <div className={printOptions.sequential ? "voucher-grid sequential-vouchers" : "voucher-grid"} style={selectedTemplate ? { gridTemplateColumns: `repeat(${Math.max(1, Math.min(5, Number(selectedLayout.columns ?? 2)))}, minmax(0, 1fr))`, gap: `${Number(selectedLayout.page_gap_mm ?? 4)}mm` } : undefined}>
                  {printPreviewCards.map((card, index) => (
                    <article className={`voucher-card ${printTemplate}`} key={card.card_id} style={selectedTemplate ? { position: "relative", background: selectedTemplate.background_color, color: selectedTemplate.text_color, aspectRatio: `${selectedTemplate.width_mm}/${selectedTemplate.height_mm}`, minHeight: `${selectedTemplate.height_mm}mm`, fontFamily: String(selectedLayout.font_family ?? "Arial"), fontSize: `${Number(selectedLayout.font_size ?? 12)}px`, padding: `${Number(selectedLayout.card_padding_mm ?? 3)}mm`, border: selectedLayout.show_border === false ? "none" : `${Number(selectedLayout.border_width ?? 1)}px solid ${String(selectedLayout.border_color ?? "#b9d9c8")}`, breakAfter: (index + 1) % cardsPerPage === 0 && index < printPreviewCards.length - 1 ? "page" : undefined } : undefined}>
                      <div className="voucher-head"><strong>{String(selectedLayout.header_text ?? "الأسطورة نت")}</strong><span>{String(selectedLayout.footer_text ?? (card.is_free ? "كرت مجاني" : "بطاقة إنترنت"))}</span></div>
                      {printOptions.show_plan && selectedLayout.show_plan !== false && <div className="voucher-plan" style={layoutPosition("plan_x", "plan_y")}><span>الباقة</span><strong>{card.plan_name}</strong></div>}
                      {printOptions.show_username && selectedLayout.show_username !== false && <div className="voucher-user" style={layoutPosition("username_x", "username_y")}><span>اسم المستخدم</span><strong>{card.username}</strong></div>}
                      {printOptions.show_password && selectedLayout.show_password !== false && <div className="voucher-password" style={layoutPosition("password_x", "password_y")}><span>كلمة المرور</span><strong>{card.password || "بدون كلمة مرور"}</strong></div>}
                      {printOptions.show_limits && selectedLayout.show_limits !== false && <div className="voucher-limits" style={layoutPosition("limits_x", "limits_y")}><span>{card.data_limit_bytes == null ? "رصيد مفتوح" : (Number(card.data_limit_bytes) / (1024 ** 2)).toFixed(0) + " MB"} · {card.session_time_limit_seconds == null ? "وقت مفتوح" : (Number(card.session_time_limit_seconds) / 3600).toFixed(0) + " ساعة"} · {card.validity_period_seconds == null ? "صلاحية مفتوحة" : (Number(card.validity_period_seconds) / 86400).toFixed(0) + " يوم"}</span></div>}
                      <div className="voucher-foot"><span style={layoutPosition("serial_x", "serial_y")}>{printOptions.show_serial_number && selectedLayout.show_serial_number !== false ? card.serial_number : ""}</span><strong style={layoutPosition("price_x", "price_y")}>{printOptions.show_price && selectedLayout.show_price !== false ? (card.is_free ? "مجاني" : Number(card.price_snapshot).toLocaleString("en-US") + " ريال") : ""}</strong></div>
                    </article>
                  ))}
                </div>
              </section>
            )}
            <div className="section-heading compact-heading"><div><h2>سجل عمليات الطباعة</h2><p>إعادة الطباعة لا تضيف قيمة تجارية جديدة.</p></div><span className="count-tag">{printHistory.length} عملية</span></div>
            <div className="table-wrap">
              <table><thead><tr><th>التاريخ</th><th>القالب</th><th>عدد الكروت</th><th>النوع</th><th>الإجراء</th></tr></thead>
                <tbody>{printHistory.map((job) => <tr key={job.id}>
                  <td>{new Date(job.created_at).toLocaleString("ar")}</td><td>{job.template_code || "افتراضي"}</td><td>{job.card_count}</td><td>{job.is_reprint ? "إعادة طباعة" : "طباعة أصلية"}</td>
                  <td>{can("printing.reprint") && can("printing.credentials") && <button type="button" className="table-action" disabled={busy || !selectedPoint?.is_active || !selectedPoint?.allow_printing || atDebtLimit} onClick={() => reprintJob(job)}>إعادة طباعة</button>}</td>
                </tr>)}</tbody>
              </table>
              {printHistory.length === 0 && <div className="empty-state">لا توجد عمليات طباعة لهذه النقطة.</div>}
            </div>
          </>
        )}
        {points.length === 0 && <div className="empty-state">أنشئ أول نقطة بيع للبدء.</div>}
      </>
    );
  }

  function renderReports() {
    const totals = posReport?.totals ?? {
      opening_balance: 0, delivered_value: 0, other_debits: 0, commissions: 0,
      payments: 0, returns: 0, other_credits: 0, period_debit: 0, period_credit: 0, closing_balance: 0,
    };
    const money = (value: number | undefined) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return (
      <>
        <div className="section-heading">
          <div><h2>التقارير الشاملة</h2><p>تقارير الكروت والاستهلاك والجلسات والدفعات والطباعة والحسابات حسب الفترة.</p></div>
        </div>
        <form className="panel form-grid report-period-filter" onSubmit={(event) => { event.preventDefault(); setBusy(true); setError(""); loadReportData().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل التقرير")).finally(() => setBusy(false)); }}>
          <label>من تاريخ<input type="date" value={reportFrom} max={reportTo} onChange={(event) => setReportFrom(event.target.value)} required /></label>
          <label>إلى تاريخ<input type="date" value={reportTo} min={reportFrom} onChange={(event) => setReportTo(event.target.value)} required /></label>
          <div className="form-actions"><button type="submit" disabled={busy}>{busy ? "جارٍ إعداد التقرير..." : "عرض التقرير"}</button></div>
        </form>
        <div className="report-period-indicator" aria-live="polite">
          <span className="report-period-mark" aria-hidden="true">◷</span>
          <div><span>الفترة المحددة للتقرير</span><strong>{new Date(reportFrom + "T00:00:00").toLocaleDateString("ar")} — {new Date(reportTo + "T00:00:00").toLocaleDateString("ar")}</strong></div>
        </div>
        <div className="report-tabs" role="tablist" aria-label="أقسام التقارير">
          {can("cards.view") && <button type="button" className={reportTab === "cards" ? "active" : ""} onClick={() => setReportTab("cards")}>الكروت</button>}
          {can("sessions.view") && <button type="button" className={reportTab === "usage" ? "active" : ""} onClick={() => setReportTab("usage")}>الاستهلاك والوقت</button>}
          {can("cards.view") && <button type="button" className={reportTab === "batches" ? "active" : ""} onClick={() => setReportTab("batches")}>دفعات الكروت</button>}
          {can("printing.view") && <button type="button" className={reportTab === "printing" ? "active" : ""} onClick={() => setReportTab("printing")}>عمليات الطباعة</button>}
          {can("finance.view") && <button type="button" className={reportTab === "finance" ? "active" : ""} onClick={() => setReportTab("finance")}>نقاط البيع والحسابات</button>}
        </div>
        {reportTab === "cards" && can("cards.view") && (
          <section className="report-section">
            <div className="stats-grid">
              <article className="stat-card"><span>إجمالي الكروت</span><strong>{(cardsReport?.total_cards ?? 0).toLocaleString("ar")}</strong></article>
              <article className="stat-card"><span>القيمة الاسمية للكروت المنشأة</span><strong>{money(cardsReport?.total_value)} ريال</strong></article>
              <article className="stat-card"><span>إجمالي الرفع</span><strong>{formatBytes(cardsReport?.upload_bytes ?? 0)}</strong></article>
              <article className="stat-card"><span>إجمالي التنزيل</span><strong>{formatBytes(cardsReport?.download_bytes ?? 0)}</strong></article>
            </div>
            <div className="report-split">
              <div className="panel"><h3>توزيع الكروت حسب الحالة</h3><div className="report-list">{(cardsReport?.by_status ?? []).map((item) => <div key={item.status}><span>{item.status}</span><strong>{item.count.toLocaleString("ar")}</strong></div>)}</div></div>
              <div className="panel"><h3>توزيع الكروت حسب الباقة</h3><div className="report-list">{(cardsReport?.by_plan ?? []).map((item) => <div key={item.plan_name}><span>{item.plan_name}</span><strong>{item.count.toLocaleString("ar")}</strong></div>)}</div></div>
            </div>
          </section>
        )}
        {reportTab === "usage" && can("sessions.view") && (
          <section className="report-section">
            <div className="stats-grid">
              <article className="stat-card"><span>إجمالي الجلسات</span><strong>{(sessionsReport?.total_sessions ?? 0).toLocaleString("ar")}</strong></article>
              <article className="stat-card"><span>المستخدمون دون تكرار</span><strong>{(sessionsReport?.unique_users ?? 0).toLocaleString("ar")}</strong></article>
              <article className="stat-card"><span>الجلسات النشطة الآن</span><strong>{(sessionsReport?.active_sessions ?? 0).toLocaleString("ar")}</strong></article>
              <article className="stat-card"><span>مدة الاتصال المسجلة</span><strong>{formatDuration(sessionsReport?.session_seconds ?? 0)}</strong></article>
              <article className="stat-card"><span>إجمالي الرفع</span><strong>{formatBytes(sessionsReport?.upload_bytes ?? 0)}</strong></article>
              <article className="stat-card"><span>إجمالي التنزيل</span><strong>{formatBytes(sessionsReport?.download_bytes ?? 0)}</strong></article>
            </div>
            <div className="panel"><h3>الجلسات حسب الراوتر</h3><div className="report-list">{(sessionsReport?.by_router ?? []).map((item) => <div key={item.router_name}><span>{item.router_name}</span><strong>{item.sessions.toLocaleString("ar")}</strong></div>)}</div></div>
          </section>
        )}
        {reportTab === "batches" && can("cards.view") && (
          <section className="panel report-section"><div className="section-heading"><h3>تقرير دفعات الكروت</h3><span className="count-tag">{batchesReport?.total_batches ?? 0} دفعة · {batchesReport?.total_cards ?? 0} كرت</span></div>
            <div className="table-wrap"><table><thead><tr><th>رقم الدفعة</th><th>التاريخ</th><th>الباقة</th><th>نقطة البيع</th><th>الكمية المطلوبة</th><th>الكروت المنشأة</th><th>نوع البيع</th><th>ملاحظة</th></tr></thead><tbody>
              {(batchesReport?.items ?? []).map((item) => <tr key={item.batch_id}><td>{item.batch_number}</td><td>{new Date(item.created_at).toLocaleString("ar")}</td><td>{item.plan_name}</td><td>{item.point_of_sale_name ?? "—"}</td><td>{item.quantity}</td><td>{item.generated_cards}</td><td>{item.is_online_sale ? "أونلاين" : "عادي"}</td><td>{item.note || "—"}</td></tr>)}
              {(batchesReport?.items.length ?? 0) === 0 && <tr><td colSpan={8} className="empty-state">لا توجد دفعات خلال الفترة المحددة.</td></tr>}
            </tbody></table></div>
          </section>
        )}
        {reportTab === "printing" && can("printing.view") && (
          <section className="panel report-section"><div className="stats-grid">
            <article className="stat-card"><span>عمليات الطباعة</span><strong>{(printingReport?.total_jobs ?? 0).toLocaleString("ar")}</strong></article>
            <article className="stat-card"><span>الكروت المطبوعة</span><strong>{(printingReport?.total_cards_printed ?? 0).toLocaleString("ar")}</strong></article>
            <article className="stat-card"><span>عمليات إعادة الطباعة</span><strong>{(printingReport?.reprint_jobs ?? 0).toLocaleString("ar")}</strong></article>
          </div><div className="table-wrap"><table><thead><tr><th>التاريخ</th><th>نقطة البيع</th><th>عدد الكروت</th><th>نوع العملية</th><th>القالب</th></tr></thead><tbody>
            {(printingReport?.items ?? []).map((item) => <tr key={item.id}><td>{new Date(item.created_at).toLocaleString("ar")}</td><td>{item.point_of_sale_name}</td><td>{item.card_count}</td><td>{item.is_reprint ? "إعادة طباعة" : "طباعة"}</td><td>{item.template_code ?? "—"}</td></tr>)}
            {(printingReport?.items.length ?? 0) === 0 && <tr><td colSpan={5} className="empty-state">لا توجد عمليات طباعة خلال الفترة المحددة.</td></tr>}
          </tbody></table></div></section>
        )}
        {reportTab === "finance" && can("finance.view") && posReport && (

          <>
            <div className="report-actions">
              <button type="button" disabled={busy} onClick={() => downloadProtectedFile(`/api/v1/reports/points-of-sale/export.xlsx?date_from=${encodeURIComponent(reportFrom)}&date_to=${encodeURIComponent(reportTo)}`, `pos-report-${reportFrom}-${reportTo}.xlsx`).catch((err) => setError(err instanceof Error ? err.message : "تعذر تنزيل Excel"))}>تنزيل التقرير Excel</button>
              <button type="button" className="secondary-button" onClick={() => window.print()}>طباعة التقرير / حفظ PDF</button>
            </div>
            <div className="report-print-area">
            <div className="stats-grid">
              <article className="stat-card"><span>رصيد افتتاحي</span><strong>{money(totals?.opening_balance)} ريال</strong></article>
              <article className="stat-card"><span>قيمة الكروت المسلّمة</span><strong>{money(totals?.delivered_value)} ريال</strong></article>
              <article className="stat-card"><span>عمولات نقاط البيع</span><strong>{money(totals?.commissions)} ريال</strong></article>
              <article className="stat-card"><span>إجمالي السدادات</span><strong>{money(totals?.payments)} ريال</strong></article>
              <article className="stat-card"><span>رصيد نهاية الفترة</span><strong>{money(totals?.closing_balance)} ريال</strong></article>
            </div>
            <div className="section-heading compact-heading"><div><h2>تفاصيل كل نقطة بيع</h2><p>الرصيد الختامي = الرصيد الافتتاحي + المدين خلال الفترة − الدائن خلال الفترة.</p></div></div>
            <div className="table-wrap">
              <table><thead><tr><th>نقطة البيع</th><th>رصيد افتتاحي</th><th>تسليم كروت</th><th>مدين آخر</th><th>العمولات</th><th>السدادات</th><th>المرتجعات</th><th>دائن آخر</th><th>رصيد ختامي</th></tr></thead>
                <tbody>{posReport.points.map((row) => <tr key={row.point_of_sale_id}>
                  <td>{row.point_of_sale_name}</td><td>{money(row.opening_balance)}</td><td>{money(row.delivered_value)}</td><td>{money(row.other_debits)}</td><td>{money(row.commissions)}</td><td>{money(row.payments)}</td><td>{money(row.returns)}</td><td>{money(row.other_credits)}</td><td><strong>{money(row.closing_balance)}</strong></td>
                </tr>)}</tbody>
                <tfoot><tr><th>الإجمالي</th><th>{money(totals.opening_balance)}</th><th>{money(totals.delivered_value)}</th><th>{money(totals.other_debits)}</th><th>{money(totals.commissions)}</th><th>{money(totals.payments)}</th><th>{money(totals.returns)}</th><th>{money(totals.other_credits)}</th><th>{money(totals.closing_balance)}</th></tr></tfoot>
              </table>
              {posReport.points.length === 0 && <div className="empty-state">لا توجد نقاط بيع مسجلة حتى الآن.</div>}
            </div>
            </div>
            <div className="section-heading compact-heading">
              <div><h2>كشف حساب تفصيلي لنقطة البيع</h2><p>يعرض كل حركة بالترتيب مع الرصيد المتراكم بعد كل حركة.</p></div>
            </div>
            <div className="panel statement-controls">
              <label>نقطة البيع
                <select value={statementPointId} onChange={(event) => {
                  const id = event.target.value;
                  setStatementPointId(id);
                  setBusy(true);
                  loadPosStatement(id).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل كشف الحساب")).finally(() => setBusy(false));
                }}>
                  <option value="">اختر نقطة بيع</option>
                  {points.map((point) => <option key={point.id} value={point.id}>{point.name}</option>)}
                </select>
              </label>
              <div className="report-actions">
                <button type="button" disabled={busy || !statementPointId || !posStatement} onClick={() => downloadProtectedFile(`/api/v1/reports/points-of-sale/${statementPointId}/statement/export.xlsx?date_from=${encodeURIComponent(reportFrom)}&date_to=${encodeURIComponent(reportTo)}`, `pos-${statementPointId}-statement-${reportFrom}-${reportTo}.xlsx`).catch((err) => setError(err instanceof Error ? err.message : "تعذر تنزيل كشف الحساب"))}>تنزيل كشف الحساب Excel</button>
                <button type="button" className="secondary-button" disabled={!posStatement} onClick={() => window.print()}>طباعة الكشف / حفظ PDF</button>
              </div>
            </div>
            {posStatement && (
              <div className="statement-print-area">
                <div className="statement-heading"><h3>كشف حساب: {posStatement.point_of_sale_name}</h3><span>الفترة: {posStatement.date_from} — {posStatement.date_to}</span></div>
                <div className="stats-grid">
                  <article className="stat-card"><span>الرصيد الافتتاحي</span><strong>{money(posStatement.opening_balance)} ريال</strong></article>
                  <article className="stat-card"><span>إجمالي المدين</span><strong>{money(posStatement.total_debit)} ريال</strong></article>
                  <article className="stat-card"><span>إجمالي الدائن</span><strong>{money(posStatement.total_credit)} ريال</strong></article>
                  <article className="stat-card"><span>الرصيد الختامي</span><strong>{money(posStatement.closing_balance)} ريال</strong></article>
                </div>
                <div className="table-wrap">
                  <table><thead><tr><th>التاريخ والوقت</th><th>نوع الحركة</th><th>البيان</th><th>المرجع</th><th>المستخدم</th><th>مدين</th><th>دائن</th><th>الرصيد المتراكم</th></tr></thead>
                    <tbody>{posStatement.entries.map((entry) => <tr key={entry.id}>
                      <td>{new Date(entry.created_at).toLocaleString("ar")}</td><td>{entry.entry_type}</td><td>{entry.description || "—"}</td><td>{entry.reference || "—"}</td><td>{entry.created_by || "—"}</td><td>{money(entry.debit)}</td><td>{money(entry.credit)}</td><td><strong>{money(entry.running_balance)}</strong></td>
                    </tr>)}</tbody>
                  </table>
                  {posStatement.entries.length === 0 && <div className="empty-state">لا توجد حركات مالية لهذه النقطة خلال الفترة المحددة.</div>}
                </div>
              </div>
            )}
          </>
        )}
      </>
    );
  }

  function renderRouters() {
    return (
      <>
        <div className="section-heading">
          <div><h2>إدارة أجهزة MikroTik</h2><p>سجل الراوترات ومعرّفات NAS. تُحفظ كلمات المرور والأسرار مشفرة ولا تظهر في قائمة الراوترات.</p></div>
        </div>
        <div className="notice">أدخل عنوان مصدر RADIUS الذي سيظهر به الراوتر أمام خادم RADIUS. بيانات العملاء النشطة متاحة داخلياً لخدمة FreeRADIUS؛ لم يتم بعد تشغيل خادم FreeRADIUS أو الاتصال بإدارة RouterOS.</div>
        {(can("routers.create") || (editingRouterId !== null && can("routers.update"))) && (
<form className="panel form-grid" onSubmit={createRouter}>
          <div className="section-heading"><div><h3>{editingRouterId !== null ? "تعديل بيانات الراوتر" : "إضافة راوتر جديد"}</h3><p>{editingRouterId !== null ? "تعديل بيانات الاتصال والعنوان دون إعادة إدخال الأسرار." : "سجّل بيانات الراوتر ومعرّف NAS."}</p></div></div>
          <label>اسم الراوتر<input value={routerDraft.name} onChange={(e) => setRouterDraft({ ...routerDraft, name: e.target.value })} required minLength={2} maxLength={120} /></label>
          <label>NAS Identifier<input value={routerDraft.nasIdentifier} onChange={(e) => setRouterDraft({ ...routerDraft, nasIdentifier: e.target.value })} required maxLength={150} readOnly={editingRouterId !== null} placeholder="مثال: router-aden-01" /><small className="field-hint">يجب أن يطابق اسم الهوية في MikroTik: /system identity. لا يتغير أثناء التعديل الحالي.</small></label>
          <label>عنوان الإدارة / IP<input value={routerDraft.managementHost} onChange={(e) => setRouterDraft({ ...routerDraft, managementHost: e.target.value })} required maxLength={255} placeholder="مثال: 192.168.88.1" /></label>
          <label>عنوان RADIUS للراوتر أو CIDR<input value={routerDraft.radiusClientAddress} onChange={(e) => setRouterDraft({ ...routerDraft, radiusClientAddress: e.target.value })} maxLength={255} placeholder="مثال: 192.168.88.1 أو 192.168.88.0/24" /><small className="field-hint">عنوان مصدر حزم RADIUS كما يراه الخادم، وقد يختلف عن عنوان إدارة API. إذا تركته فارغاً فلن يُحمّل الراوتر كعميل RADIUS.</small></label>
          <label>منفذ MikroTik API<input type="number" min="1" max="65535" value={routerDraft.apiPort} onChange={(e) => setRouterDraft({ ...routerDraft, apiPort: e.target.value })} required /><small className="field-hint">الافتراضي 8729 لاتصال API المشفر TLS. استخدم 8728 فقط داخل شبكة إدارة موثوقة ومعزولة.</small></label>
          {editingRouterId === null && <>
            <label>اسم مستخدم API (اختياري)<input value={routerDraft.apiUsername} onChange={(e) => setRouterDraft({ ...routerDraft, apiUsername: e.target.value })} maxLength={120} /></label>
            <label>كلمة مرور API (اختياري)<input type="password" autoComplete="new-password" value={routerDraft.apiSecret} onChange={(e) => setRouterDraft({ ...routerDraft, apiSecret: e.target.value })} minLength={8} maxLength={500} /></label>
            <label>RADIUS Shared Secret<input type="password" autoComplete="new-password" value={routerDraft.radiusSecret} onChange={(e) => setRouterDraft({ ...routerDraft, radiusSecret: e.target.value })} required minLength={8} maxLength={500} /><small className="field-hint">استخدم القيمة نفسها في إعداد /radius على MikroTik؛ لن تظهر مرة أخرى بعد الحفظ.</small></label>
          </>}
          <label>إصدار RouterOS<input value={routerDraft.routerosVersion} onChange={(e) => setRouterDraft({ ...routerDraft, routerosVersion: e.target.value })} maxLength={30} placeholder="مثال: 7.x أو 6.x" /></label>
          <div className="form-actions"><button type="submit" disabled={busy || (editingRouterId === null && !!routerDraft.apiUsername !== !!routerDraft.apiSecret)}>{busy ? "جارٍ الحفظ..." : editingRouterId !== null ? "حفظ التعديلات" : "حفظ الراوتر"}</button>{editingRouterId !== null && <button type="button" className="secondary-button" disabled={busy} onClick={resetRouterDraft}>إلغاء التعديل</button>}</div>
          {editingRouterId === null && !!routerDraft.apiUsername !== !!routerDraft.apiSecret && <div className="field-hint">أدخل اسم مستخدم API وكلمة مروره معاً، أو اتركهما فارغين.</div>}
        </form>
)}
        {user.roles.includes("owner") && (
<section className="panel form-grid">
          <div className="section-heading"><div><h2>فحص كرت واحد من User Manager</h2><p>بحث تشخيصي بالاسم الدقيق؛ لا ينشئ كرتاً ولا يستورده ولا يغيّر بيانات المصدر.</p></div></div>
          <label>جهاز User Manager
            <select value={inspectRouterId} onChange={(event) => { const nextId = event.target.value; setInspectRouterId(nextId); setUserManagerUserInspect(null); setUserManagerPreviews(null); setUserManagerPreviewRuns([]); setSelectedPreviewRunId(""); if (nextId) loadUserManagerPreviewRuns(Number(nextId)).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل سجل المعاينات")); }}>
              <option value="">اختر الراوتر المسجل</option>
              {routers.filter((item) => item.is_active && item.api_username).map((item) => (
                <option key={item.id} value={item.id}>{item.name} — {item.management_host}:{item.api_port}</option>
              ))}
            </select>
          </label>
          <label>اسم المستخدم / رقم الكرت
            <input value={inspectUsername} onChange={(event) => { setInspectUsername(event.target.value); setUserManagerUserInspect(null); }} maxLength={120} placeholder="أدخل اسم كرت واحد كما هو في User Manager" />
          </label>
          <div className="form-actions">
            <button type="button" disabled={inspectingUser || !inspectRouterId || !inspectUsername.trim()} onClick={inspectRouterUser}>{inspectingUser ? "جارٍ فحص الكرت..." : "فحص الكرت"}</button>
          </div>
          {userManagerUserInspect && (
            <div className="notice">
              {userManagerUserInspect.found && userManagerUserInspect.user ? (
                <>
                  <strong>الكرت موجود في User Manager</strong>
                  <div>اسم المستخدم: {userManagerUserInspect.user.username}</div>
                  <div>معرّف المصدر: {userManagerUserInspect.user.external_id || "غير متاح"}</div>
                  <div>العميل: {userManagerUserInspect.user.customer || "غير متاح"}</div>
                  <div>البروفايل الفعلي: {userManagerUserInspect.user.actual_profile || "غير متاح"}</div>
                  <div>معطّل: {userManagerUserInspect.user.disabled ?? "غير متاح"}</div>
                  <div>المستخدمون المشتركون: {userManagerUserInspect.user.shared_users || "غير متاح"}</div>
                  <div className="notice">
                    <strong>استخدام الكرت حتى الآن</strong>
                    <div>وقت الاستخدام: {userManagerUserInspect.user.usage.uptime_used ?? "لم يعرضه المصدر"}</div>
                    <div>التنزيل: {userManagerUserInspect.user.usage.download_used_bytes === null ? "لم يعرضه المصدر" : `${userManagerUserInspect.user.usage.download_used_bytes} بايت`}</div>
                    <div>الرفع: {userManagerUserInspect.user.usage.upload_used_bytes === null ? "لم يعرضه المصدر" : `${userManagerUserInspect.user.usage.upload_used_bytes} بايت`}</div>
                    <div>آخر ظهور: {userManagerUserInspect.user.usage.last_seen || "لم يعرضه المصدر"}</div>
                    <div>الجلسات النشطة: {userManagerUserInspect.user.usage.active_sessions ?? "لم يعرضه المصدر"}</div>
                    <small className="field-hint">القيم غير الظاهرة تبقى مجهولة ولا نفترض أنها صفر؛ العدادات بوحدات المصدر الأصلية.</small>
                  </div>
                  {userManagerUserInspect.user.profile && (
                    <div className="notice">
                      <strong>تفاصيل البروفايل: {userManagerUserInspect.user.profile.name}</strong>
                      <div>الصلاحية: {userManagerUserInspect.user.profile.validity || "غير محدد"}</div>
                      <div>بداية الصلاحية: {userManagerUserInspect.user.profile["starts-when"] || "غير محدد"}</div>
                      <div>السعر الأصلي في المصدر: {userManagerUserInspect.user.profile.price || "غير محدد"}</div>
                      {userManagerUserInspect.user.profile.comment && <div>ملاحظات: {userManagerUserInspect.user.profile.comment}</div>}
                    </div>
                  )}
                  <strong>القيود المرتبطة ({userManagerUserInspect.user.limitations.length})</strong>
                  {userManagerUserInspect.user.limitations.map((limitation) => (
                    <div className="notice" key={limitation.name}>
                      <strong>{limitation.name}</strong>
                      <div>وقت الاستخدام: {limitation["uptime-limit"] || "غير محدد"}</div>
                      <div>التنزيل: {limitation["download-limit"] || "غير محدد"}</div>
                      <div>الرفع: {limitation["upload-limit"] || "غير محدد"}</div>
                      <div>إجمالي النقل: {limitation["transfer-limit"] || "غير محدد"}</div>
                      <div>سرعة التنزيل: {limitation["rate-limit-rx"] || "غير محدد"}</div>
                      <div>سرعة الرفع: {limitation["rate-limit-tx"] || "غير محدد"}</div>
                    </div>
                  ))}
                  {userManagerUserInspect.user.warnings.map((warning) => <div className="field-hint" key={warning}>{warning}</div>)}
                </>
              ) : <strong>لم يتم العثور على الكرت بهذا الاسم.</strong>}
              <small className="field-hint">قراءة فقط · لم تُقرأ كلمة المرور · لم يتم الاستيراد. القيم المعروضة هي كما أعادها المصدر ولا تُحوّل إلى وحدات النظام الجديد بعد.</small>
              {userManagerUserInspect.found && (
                <div className="form-actions">
                  <button type="button" disabled={savingUserPreview || !inspectRouterId || !inspectUsername.trim()} onClick={saveUserManagerPreview}>
                    {savingUserPreview ? "جارٍ حفظ المعاينة..." : "حفظ معاينة آمنة"}
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
)}
        {(userManagerPreviewRuns.length > 0 || loadingPreviewRuns) && (
          <section className="panel um-probe-panel">
            <div className="section-heading">
              <div><h2>سجل عمليات المعاينة</h2><p>اختر عملية سابقة لعرض الكروت التي حُفظت فيها.</p></div>
              <button type="button" className="table-action" disabled={loadingPreviewRuns || !inspectRouterId} onClick={() => loadUserManagerPreviewRuns(Number(inspectRouterId), selectedPreviewRunId)}>تحديث السجل</button>
            </div>
            <label>عملية المعاينة
              <select value={selectedPreviewRunId} disabled={loadingPreviewRuns} onChange={(event) => selectUserManagerPreviewRun(event.target.value)}>
                <option value="">اختر عملية</option>
                {userManagerPreviewRuns.map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.created_at ? new Date(run.created_at).toLocaleString("ar") : run.id} — {run.preview_count} معاينة
                  </option>
                ))}
              </select>
            </label>
            {loadingPreviewRuns && <small className="field-hint">جارٍ تحميل سجل المعاينات...</small>}
          </section>
        )}
        {userManagerPreviews && (
          <section className="panel um-probe-panel">
            <div className="section-heading">
              <div><h2>المعاينة المحفوظة</h2><p>{userManagerPreviews.run?.created_at ? new Date(userManagerPreviews.run.created_at).toLocaleString("ar") : "نتائج محفوظة للمراجعة قبل أي استيراد."}</p></div>
              <span className="count-tag">{userManagerPreviews.total} سجل</span>
            </div>
            <div className="um-preview-counts">
              {[
                { key: "new", label: "جديد" },
                { key: "already_linked", label: "مرتبط مسبقاً" },
                { key: "username_conflict", label: "تعارض اسم المستخدم" },
                { key: "duplicate_in_batch", label: "مكرر في المعاينة" },
                { key: "invalid", label: "بيانات غير مكتملة" },
              ].map((entry) => (
                <div className="um-preview-count" key={entry.key}>
                  <strong>{userManagerPreviews.classification_counts?.[entry.key] ?? 0}</strong>
                  <span>{entry.label}</span>
                </div>
              ))}
            </div>
            {userManagerPreviews.items.map((preview) => (
              <div className="notice" key={preview.id}>
                <strong>{preview.username || "اسم غير متاح"}</strong>
                <div>تصنيف السجل: {{
                  new: "جديد",
                  already_linked: "مرتبط مسبقاً",
                  username_conflict: "تعارض اسم المستخدم",
                  duplicate_in_batch: "مكرر داخل المعاينة",
                  invalid: "بيانات غير مكتملة",
                }[preview.classification] || preview.classification}</div>
                <div>البروفايل الأصلي: {preview.source_profile_id || "غير متاح"}</div>
                <div>حالة بيانات الدخول: {preview.credential_state}</div>
                <div>نوع بيانات الدخول: {preview.credential_mode || "غير محدد"}</div>
                <div>معرّف المصدر: {preview.external_user_id}</div>
                {preview.issues.length > 0 && <div>ملاحظات: {preview.issues.join("، ")}</div>}
              </div>
            ))}
            <div className="form-actions">
              <button type="button" className="secondary-button" disabled={loadingPreviewRuns || userManagerPreviews.offset <= 0} onClick={() => changeUserManagerPreviewPage(userManagerPreviews.offset - userManagerPreviews.limit)}>السابق</button>
              <span className="field-hint">عرض {userManagerPreviews.total === 0 ? 0 : userManagerPreviews.offset + 1}–{Math.min(userManagerPreviews.offset + userManagerPreviews.items.length, userManagerPreviews.total)} من {userManagerPreviews.total}</span>
              <button type="button" className="secondary-button" disabled={loadingPreviewRuns || userManagerPreviews.offset + userManagerPreviews.items.length >= userManagerPreviews.total} onClick={() => changeUserManagerPreviewPage(userManagerPreviews.offset + userManagerPreviews.limit)}>التالي</button>
            </div>
            <small className="field-hint">حالة المعاينة: قراءة فقط · الاستيراد: متوقف · قراءة كلمات المرور: لم تتم.</small>
          </section>
        )}
        <div className="router-summary-grid" aria-label="ملخص الراوترات">
          <div className="router-summary-card"><span>إجمالي الراوترات</span><strong>{routers.length.toLocaleString("ar")}</strong><small>كل الأجهزة المسجلة</small></div>
          <div className="router-summary-card"><span>أجهزة مفعّلة</span><strong>{routers.filter((router) => router.is_active).length.toLocaleString("ar")}</strong><small>حالتها مفعّلة في النظام</small></div>
          <div className="router-summary-card"><span>أجهزة متوقفة</span><strong>{routers.filter((router) => !router.is_active).length.toLocaleString("ar")}</strong><small>يمكن مراجعتها من الجدول</small></div>
          <div className="router-summary-card"><span>عملاء RADIUS محددون</span><strong>{routers.filter((router) => !!router.radius_client_address).length.toLocaleString("ar")}</strong><small>لديها عنوان مصدر RADIUS</small></div>
        </div>
        <div className="section-heading compact-heading"><div><h2>الراوترات المسجلة</h2><p>لا تعرض هذه القائمة أي كلمة مرور أو RADIUS secret.</p></div><span className="count-tag">{routers.length} راوتر</span></div>
        <div className="table-wrap">
          <table><thead><tr><th>الاسم</th><th>NAS Identifier</th><th>عنوان الإدارة</th><th>عنوان RADIUS</th><th>API Port</th><th>الإصدار</th><th>آخر ظهور</th><th>الحالة</th><th>الإجراء</th></tr></thead>
            <tbody>{routers.map((router) => <tr key={router.id}>
              <td>{router.name}</td><td>{router.nas_identifier}</td><td>{router.management_host}</td><td>{router.radius_client_address || "غير محدد"}</td><td>{router.api_port}</td>
              <td>{router.routeros_version || "غير محدد"}</td><td>{router.last_seen_at ? new Date(router.last_seen_at).toLocaleString("ar") : "لم يتصل بعد"}</td>
              <td>{router.is_active ? "مفعل" : "متوقف"}</td>
              <td className="actions-cell">
                {can("routers.update") && <button type="button" className="table-action" disabled={busy || probingRouterId !== null || testingRouterConnectionId !== null} onClick={() => beginEditRouter(router)}>تعديل</button>}
                {can("routers.update") && <button type="button" className="table-action" disabled={busy || probingRouterId !== null || testingRouterConnectionId !== null || !router.api_username || !router.is_active} onClick={() => testRouterConnection(router)}>{testingRouterConnectionId === router.id ? "جارٍ فحص API..." : "فحص اتصال API"}</button>}
                {user.roles.includes("owner") && <button type="button" className="table-action" disabled={busy || probingRouterId !== null || testingRouterConnectionId !== null || !router.api_username} onClick={() => testRouterUserManager(router)}>{probingRouterId === router.id ? "جارٍ الفحص..." : "فحص User Manager"}</button>}
                {can("routers.update") && <button type="button" className="table-action" disabled={busy || probingRouterId !== null || testingRouterConnectionId !== null} onClick={() => toggleRouter(router)}>{router.is_active ? "تعطيل" : "تفعيل"}</button>}
                {can("routers.delete") && <button type="button" className="table-action" title={router.is_active ? "أوقف الراوتر أولاً" : "حذف الراوتر"} disabled={busy || probingRouterId !== null || testingRouterConnectionId !== null || router.is_active} onClick={() => deleteRouter(router)}>حذف</button>}
              </td>
            </tr>)}</tbody>
          </table>
          {routers.length === 0 && <div className="empty-state">لا توجد راوترات مسجلة. أضف أول راوتر من النموذج أعلاه.</div>}
        </div>
        {routerConnectionProbe && (
          <section className="panel um-probe-panel">
            <div className="section-heading">
              <div><h2>نتيجة اتصال RouterOS API</h2><p>{routerConnectionProbe.router_name} · {routerConnectionProbe.identity || "هوية غير متاحة"} · {routerConnectionProbe.version || "إصدار غير معروف"}</p></div>
              <span className="count-tag">{routerConnectionProbe.connected ? "متصل" : "غير متصل"}</span>
            </div>
            <div className="pos-metrics">
              <div><span>اللوحة</span><strong>{routerConnectionProbe.board_name || "غير متاح"}</strong></div>
              <div><span>المعمارية</span><strong>{routerConnectionProbe.architecture_name || "غير متاح"}</strong></div>
              <div><span>مدة التشغيل</span><strong>{routerConnectionProbe.uptime || "غير متاح"}</strong></div>
              <div><span>استخدام المعالج</span><strong>{routerConnectionProbe.cpu_load ? routerConnectionProbe.cpu_load + "%" : "غير متاح"}</strong></div>
              <div><span>التشفير</span><strong>{routerConnectionProbe.secure ? "TLS مفعل" : "اتصال غير مشفر"}</strong></div>
            </div>
            {routerConnectionProbe.warnings.length > 0 && <div className="notice">{routerConnectionProbe.warnings.map((warning) => <div key={warning}>• {warning}</div>)}</div>}
            <small className="field-hint">الفحص يقرأ هوية النظام ومعلومات الموارد فقط؛ لا يغيّر إعدادات الراوتر ولا يفحص User Manager.</small>
          </section>
        )}
        {user.roles.includes("owner") && userManagerProbe && (
          <section className="panel um-probe-panel">
            <div className="section-heading">
              <div><h2>نتيجة فحص User Manager</h2><p>{userManagerProbe.router_name} · {userManagerProbe.identity || "هوية غير متاحة"} · {userManagerProbe.routeros_version || "إصدار غير معروف"}</p></div>
              <span className="count-tag">{userManagerProbe.user_manager_available ? "الخدمة متاحة" : "الخدمة غير مؤكدة"}</span>
            </div>
            <div className="pos-metrics">
              {Object.entries(userManagerProbe.resources).map(([key, value]) => (
                <div key={key}><span>{({ users: "الكروت", profiles: "البروفايلات", limitations: "القيود", profile_limitations: "ربط البروفايلات", sessions: "الجلسات", customers: "العملاء" } as Record<string, string>)[key] || key}</span><strong>{value.available && value.count !== null ? value.count.toLocaleString("ar") : "غير متاح"}</strong></div>
              ))}
            </div>
            {(userManagerProbe.warnings.length > 0) && <div className="notice">{userManagerProbe.warnings.map((warning) => <div key={warning}>• {warning}</div>)}</div>}
            <small className="field-hint">الفحص قراءة فقط؛ لم يتم تنزيل كلمات مرور أو تعديل أي سجل في User Manager.</small>
          </section>
        )}
      </>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">أ</div>
        <div className="brand-copy"><strong>الأسطورة RADIUS</strong><span>إدارة الشبكة والكروت</span></div>
        <div className="side-label">القائمة الرئيسية</div>
        <nav>
          <button className={page === "overview" ? "nav-item active" : "nav-item"} onClick={() => setPage("overview")}>لوحة المعلومات</button>
          {user.roles.includes("owner") && <button className={page === "admins" ? "nav-item active" : "nav-item"} onClick={() => setPage("admins")}>حسابات الإدارة والصلاحيات</button>}

          {(can("plans.view") || can("routers.view") || can("reports.view") || can("finance.view")) && <div className="nav-group">
            <button type="button" className={openNavGroup === "system" ? "nav-group-toggle expanded" : "nav-group-toggle"} aria-expanded={openNavGroup === "system"} onClick={() => setOpenNavGroup((current) => current === "system" ? null : "system")}>
              <span>إدارة النظام</span><span className="nav-chevron" aria-hidden="true">⌄</span>
            </button>
            {openNavGroup === "system" && <div className="nav-group-items">
              {can("plans.view") && <button className={page === "plans" ? "nav-sub active" : "nav-sub"} onClick={() => setPage("plans")}>إدارة الباقات</button>}
              {can("routers.view") && <button className={page === "routers" ? "nav-sub active" : "nav-sub"} onClick={() => setPage("routers")}>الراوترات</button>}
              {(can("reports.view") || can("finance.view")) && <button className={page === "reports" ? "nav-sub active" : "nav-sub"} onClick={() => setPage("reports")}>التقارير</button>}
            </div>}
          </div>}
          {(can("cards.create") || can("cards.view") || can("templates.view")) && <div className="nav-group">
            <button type="button" className={openNavGroup === "cards" ? "nav-group-toggle expanded" : "nav-group-toggle"} aria-expanded={openNavGroup === "cards"} onClick={() => setOpenNavGroup((current) => current === "cards" ? null : "cards")}>
              <span>إدارة الكروت</span><span className="nav-chevron" aria-hidden="true">⌄</span>
            </button>
            {openNavGroup === "cards" && <div className="nav-group-items">
              {can("cards.create") && <button className={page === "card-create" ? "nav-sub active" : "nav-sub"} onClick={() => setPage("card-create")}>إضافة الكروت</button>}
              {can("cards.view") && <button className={page === "cards" ? "nav-sub active" : "nav-sub"} onClick={() => setPage("cards")}>إدارة الكروت</button>}
              {can("cards.view") && user.card_visibility !== "search_any" && <button className={page === "batches" ? "nav-sub active" : "nav-sub"} onClick={() => setPage("batches")}>دفعات الكروت</button>}
              {can("templates.view") && <button className={page === "templates" ? "nav-sub active" : "nav-sub"} onClick={() => setPage("templates")}>تصاميم الكروت</button>}
            </div>}
          </div>}
          {can("pos.view") && <button className={page === "pos-management" ? "nav-item active" : "nav-item"} onClick={() => setPage("pos-management")}>نقاط البيع</button>}
          {(can("printing.view") || can("printing.create") || can("printing.reprint")) && can("cards.view") && can("pos.view") && <div className="nav-group">
            <button type="button" className={openNavGroup === "printing" ? "nav-group-toggle expanded" : "nav-group-toggle"} aria-expanded={openNavGroup === "printing"} onClick={() => setOpenNavGroup((current) => current === "printing" ? null : "printing")}>
              <span>الطباعة</span><span className="nav-chevron" aria-hidden="true">⌄</span>
            </button>
            {openNavGroup === "printing" && <div className="nav-group-items">
              <button className={page === "pos" ? "nav-sub active" : "nav-sub"} onClick={() => setPage("pos")}>الطباعة والدفعات</button>
            </div>}
          </div>}
          {can("audit.view") && <button className={page === "audit" ? "nav-item active" : "nav-item"} onClick={() => setPage("audit")}>سجل عمليات النظام</button>}
          {user.roles.includes("owner") && <button className={page === "settings" ? "nav-item active" : "nav-item"} onClick={() => setPage("settings")}>الإعدادات والصيانة</button>}
        </nav>
        <div className="sidebar-foot">ALOSTORA-RADIUS · 0.4.0</div>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div><span className="eyebrow">مركز إدارة الشبكة</span><h1>{page === "overview" ? "لوحة التحكم" : page === "plans" ? "إدارة الباقات" : page === "cards" ? "إدارة الكروت" : page === "card-create" ? "إضافة الكروت" : page === "pos" ? "الطباعة والدفعات" : page === "pos-management" ? "إدارة نقاط البيع" : page === "batches" ? "دفعات الكروت" : page === "reports" ? "التقارير" : page === "templates" ? "استديو تصميم الكروت" : page === "admins" ? "حسابات الإدارة والصلاحيات" : page === "audit" ? "سجل عمليات النظام" : page === "settings" ? "الإعدادات والصيانة" : "إدارة أجهزة MikroTik"}</h1></div>
          <div className="topbar-actions"><div className="environment"><span className="status-dot" /> بيئة التطوير</div><div className="user-chip">{user.display_name}</div><button className="logout-button" onClick={onLogout}>تسجيل الخروج</button></div>
        </header>
        {error && <div className="notice error-notice" role="alert">{error}</div>}
        {notice && <div className="notice success-notice" role="status">{notice}</div>}
        {page === "settings" && user.roles.includes("owner") ? renderSystemSettings() : page === "audit" && can("audit.view") ? renderAuditLogs() : page === "admins" && user.roles.includes("owner") ? renderAdmins() : page === "overview" ? renderOverview() : page === "plans" && can("plans.view") ? renderPlans() : page === "cards" && (can("cards.view") || (cardManagementTab === "sessions" && can("sessions.view"))) ? renderCards() : page === "card-create" && can("cards.create") && can("templates.view") && can("plans.view") && can("pos.view") ? renderCardCreate() : page === "pos" && (can("printing.view") || can("printing.create") || can("printing.reprint")) && can("cards.view") && can("pos.view") ? renderPos() : page === "pos-management" && can("pos.view") ? renderPosManagement() : page === "batches" && can("cards.view") ? renderBatches() : page === "reports" && (can("reports.view") || can("finance.view")) ? renderReports() : page === "templates" && can("templates.view") ? renderTemplates() : page === "routers" && can("routers.view") ? renderRouters() : renderOverview()}
        <footer>© شبكة الأسطورة نت · ALOSTORA-RADIUS</footer>
      </section>
    </main>
  );
}

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checking, setChecking] = useState(false);

  async function login(username: string, password: string) {
    const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error("اسم المستخدم أو كلمة المرور غير صحيحة");
      throw new Error("تعذر الاتصال بالخادم. تحقق من تشغيل الخدمات وإعداد المفتاح السري.");
    }
    const data = await response.json();
    setToken(data.access_token as string);
  }

  useEffect(() => {
    if (!token) { setUser(null); return; }
    let active = true;
    setChecking(true);
    fetch(`${API_BASE}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => {
        if (!response.ok) throw new Error("انتهت جلسة الدخول");
        return response.json();
      })
      .then((data: CurrentUser) => { if (active) setUser(data); })
      .catch(() => { if (active) { setToken(null); setUser(null); } })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [token]);

  if (!token) return <LoginScreen onLogin={login} />;
  if (checking || !user) return <main className="loading-screen">جارٍ تحميل لوحة التحكم...</main>;
  return <Dashboard user={user} token={token} onLogout={() => { setToken(null); setUser(null); }} />;
}

export default App;
