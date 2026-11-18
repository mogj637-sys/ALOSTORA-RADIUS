import { FormEvent, useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";

type CurrentUser = {
  id: number;
  username: string;
  display_name: string;
  roles: string[];
};

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
  is_active: boolean;
};

type Card = {
  id: string;
  serial_number: string;
  username: string;
  card_type: string;
  status: string;
  is_free: boolean;
  plan_id: number;
  price_snapshot: number;
  assigned_pos_id: number | null;
  first_used_at: string | null;
  expires_at: string | null;
};

type GeneratedCard = {
  serial_number: string;
  username: string;
  password: string;
};

type RouterRecord = {
  id: number;
  name: string;
  nas_identifier: string;
  management_host: string;
  radius_client_address: string | null;
  api_port: number;
  api_use_ssl: boolean;
  api_username: string | null;
  routeros_version: string | null;
  is_active: boolean;
  last_seen_at: string | null;
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

type PrintJobHistory = {
  id: string;
  template_code: string | null;
  card_count: number;
  is_reprint: boolean;
  created_at: string;
  cards: { card_id: string; serial_number: string; username: string; is_free: boolean }[];
};

type PrintJobResult = {
  id: string;
  template_code: string | null;
  card_count: number;
  commercial_card_count: number;
  free_card_count: number;
  total_amount: number;
  is_reprint: boolean;
  items: { card_id: string; serial_number: string; username: string; password: string; is_free: boolean; price_snapshot: number }[];
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
  { title: "الكروت", detail: "إنشاء وإدارة كروت الإنترنت", icon: "▤", page: "cards" as const },
  { title: "الباقات والسرعات", detail: "إعداد حدود الوقت والحجم والسرعة", icon: "◷", page: "plans" as const },
  { title: "أجهزة MikroTik", detail: "تسجيل الراوترات وإعداد بيانات الاتصال", icon: "⌁", page: "routers" as const },
  { title: "نقاط البيع", detail: "المخزون وتخصيص الكروت بالطباعة", icon: "▣", page: "pos" as const },
  { title: "جلسات RADIUS", detail: "المصادقة والاستهلاك والجلسات", icon: "◉", page: "overview" as const },
  { title: "التقارير", detail: "المبيعات والاستخدام والأرشفة", icon: "▥", page: "reports" as const },
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

function Dashboard({ user, token, onLogout }: { user: CurrentUser; token: string; onLogout: () => void }) {
  const [page, setPage] = useState<"overview" | "plans" | "cards" | "pos" | "routers" | "reports">("overview");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [routers, setRouters] = useState<RouterRecord[]>([]);
  const [userManagerProbe, setUserManagerProbe] = useState<UserManagerProbe | null>(null);
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
  const [routerDraft, setRouterDraft] = useState({ name: "", nasIdentifier: "", managementHost: "", radiusClientAddress: "", apiPort: "8729", apiUseSsl: true, apiUsername: "", apiSecret: "", radiusSecret: "", routerosVersion: "" });
  const [cards, setCards] = useState<Card[]>([]);
  const [generatedCards, setGeneratedCards] = useState<GeneratedCard[]>([]);
  const [editingPlanId, setEditingPlanId] = useState<number | null>(null);
  const [cardSearch, setCardSearch] = useState("");
  const [cardOffset, setCardOffset] = useState(0);
  const [hasMoreCards, setHasMoreCards] = useState(false);
  const [points, setPoints] = useState<PointOfSale[]>([]);
  const [selectedPosId, setSelectedPosId] = useState("");
  const [posInventory, setPosInventory] = useState<PosInventory | null>(null);
  const [posAccount, setPosAccount] = useState<PosAccountSummary | null>(null);
  const [posEntries, setPosEntries] = useState<PosAccountEntry[]>([]);
  const [posReport, setPosReport] = useState<PosReport | null>(null);
  const [statementPointId, setStatementPointId] = useState("");
  const [posStatement, setPosStatement] = useState<PosStatement | null>(null);
  const [reportFrom, setReportFrom] = useState(() => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10));
  const [reportTo, setReportTo] = useState(() => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10));
  const [accountDraft, setAccountDraft] = useState({ amount: "", entryType: "payment", direction: "credit" as "debit" | "credit", description: "", reference: "" });
  const [printHistory, setPrintHistory] = useState<PrintJobHistory[]>([]);
  const [posDraft, setPosDraft] = useState({ code: "", name: "", contactName: "", phone: "" });
  const [selectedPrintCardIds, setSelectedPrintCardIds] = useState<string[]>([]);
  const [printPreviewCards, setPrintPreviewCards] = useState<PrintJobResult["items"]>([]);
  const [printTemplate, setPrintTemplate] = useState("classic-green");
  const [cardMode, setCardMode] = useState<"batch" | "single">("batch");
  const [singleDraft, setSingleDraft] = useState({ planId: "", username: "", cardType: "username_only", password: "", isFree: false });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [planDraft, setPlanDraft] = useState({
    code: "", name: "", price: "", commissionType: "none" as "none" | "fixed" | "percentage", commissionValue: "", dataGb: "", timeHours: "", validityDays: "", speedProfile: "",
  });
  const [batchDraft, setBatchDraft] = useState({
    planId: "", quantity: "100", cardType: "separate_credentials",
    generationMode: "digits", usernameLength: "8", passwordLength: "10", prefix: "",
  });

  async function loadPlans() {
    const result = await apiRequest<Plan[]>(token, "/api/v1/plans?include_inactive=true");
    setPlans(result);
    const firstActive = result.find((plan) => plan.is_active);
    if (firstActive) {
      if (!batchDraft.planId) setBatchDraft((current) => ({ ...current, planId: String(firstActive.id) }));
      if (!singleDraft.planId) setSingleDraft((current) => ({ ...current, planId: String(firstActive.id) }));
    }
  }

  async function loadRouters() {
    const result = await apiRequest<RouterRecord[]>(token, "/api/v1/routers?include_inactive=true");
    setRouters(result);
  }

  async function createRouter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<RouterRecord>(token, "/api/v1/routers", {
        method: "POST",
        body: JSON.stringify({
          name: routerDraft.name,
          nas_identifier: routerDraft.nasIdentifier,
          management_host: routerDraft.managementHost,
          radius_client_address: routerDraft.radiusClientAddress || null,
          api_port: Number(routerDraft.apiPort),
          api_use_ssl: routerDraft.apiUseSsl,
          api_username: routerDraft.apiUsername || null,
          api_secret: routerDraft.apiSecret || null,
          radius_secret: routerDraft.radiusSecret,
          routeros_version: routerDraft.routerosVersion || null,
        }),
      });
      setRouterDraft({ name: "", nasIdentifier: "", managementHost: "", radiusClientAddress: "", apiPort: "8729", apiUseSsl: true, apiUsername: "", apiSecret: "", radiusSecret: "", routerosVersion: "" });
      await loadRouters();
      setNotice("تم تسجيل الراوتر وحفظ أسراره مشفرة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تسجيل الراوتر");
    } finally { setBusy(false); }
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

  async function loadCards(search = cardSearch, offset = cardOffset) {
    const params = new URLSearchParams({ offset: String(offset), limit: "200" });
    if (search.trim()) params.set("search", search.trim());
    const result = await apiRequest<Card[]>(token, `/api/v1/cards?${params.toString()}`);
    setCards(result);
    setHasMoreCards(result.length === 200);
  }

  function changeCardPage(nextOffset: number) {
    const safeOffset = Math.max(0, nextOffset);
    setCardOffset(safeOffset);
    loadCards(cardSearch, safeOffset).catch((err) =>
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
    const [report, availablePoints] = await Promise.all([
      apiRequest<PosReport>(token, `/api/v1/reports/points-of-sale?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}`),
      apiRequest<PointOfSale[]>(token, "/api/v1/points-of-sale?include_inactive=true"),
    ]);
    setPosReport(report);
    setPoints(availablePoints);
    const currentPoint = statementPointId && availablePoints.some((point) => String(point.id) === statementPointId)
      ? statementPointId
      : String(availablePoints[0]?.id ?? "");
    setStatementPointId(currentPoint);
    if (currentPoint) await loadPosStatement(currentPoint, from, to);
    else setPosStatement(null);
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
    await Promise.all([loadPosInventory(current), loadPrintHistory(current), loadPosAccount(current)]);
  }

  async function createPointOfSale(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const point = await apiRequest<PointOfSale>(token, "/api/v1/points-of-sale", {
        method: "POST",
        body: JSON.stringify({
          code: posDraft.code,
          name: posDraft.name,
          contact_name: posDraft.contactName || null,
          phone: posDraft.phone || null,
        }),
      });
      setPosDraft({ code: "", name: "", contactName: "", phone: "" });
      await loadPointsOfSale();
      setSelectedPosId(String(point.id));
      await Promise.all([loadPosInventory(String(point.id)), loadPrintHistory(String(point.id)), loadPosAccount(String(point.id))]);
      setNotice("تم إنشاء نقطة البيع بنجاح.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء نقطة البيع");
    } finally { setBusy(false); }
  }

  async function togglePointOfSale(point: PointOfSale) {
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

  function togglePrintCard(cardId: string) {
    setSelectedPrintCardIds((current) => {
      if (current.includes(cardId)) return current.filter((id) => id !== cardId);
      if (current.length >= 5000) {
        setError("الحد الأقصى لعملية الطباعة الواحدة هو 5000 كرت.");
        return current;
      }
      return [...current, cardId];
    });
  }

  async function reprintJob(job: PrintJobHistory) {
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
        }),
      });
      setPrintTemplate(job.template_code ?? "classic-green");
      setPrintPreviewCards(result.items);
      await loadPrintHistory(selectedPosId);
      setNotice(`تم تسجيل إعادة طباعة ${result.card_count} كرت دون إضافة قيمة تجارية جديدة.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذرت إعادة الطباعة");
    } finally { setBusy(false); }
  }

  async function printSelectedCards() {
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
        }),
      });
      setSelectedPrintCardIds([]);
      setPrintTemplate(result.template_code || printTemplate);
      setPrintPreviewCards(result.items);
      await Promise.all([loadCards(), loadPosInventory(selectedPosId), loadPrintHistory(selectedPosId), loadPosAccount(selectedPosId)]);
      setNotice(`تم تسجيل طباعة ${result.card_count} كرت: ${result.commercial_card_count} تجاري و${result.free_card_count} مجاني. القيمة التجارية: ${Number(result.total_amount).toFixed(2)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تنفيذ الطباعة");
    } finally { setBusy(false); }
  }

  useEffect(() => {
    if (page !== "pos") setPrintPreviewCards([]);
    if (page === "reports") {
      setError("");
      loadReportData().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل التقارير المالية"));
    }
    if (page === "plans" || page === "cards" || page === "pos" || page === "routers") {
      setError("");
      Promise.all([
        loadPlans(),
        page === "cards" || page === "pos" ? loadCards() : Promise.resolve(),
        page === "pos" ? loadPointsOfSale() : Promise.resolve(),
        page === "routers" ? loadRouters() : Promise.resolve(),
      ]).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل البيانات"));
    }
    // Data is refreshed when the selected section changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, token]);

  async function createPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
        data_limit_bytes: numberOrNull(planDraft.dataGb, 1024 ** 3),
        session_time_limit_seconds: numberOrNull(planDraft.timeHours, 3600),
        validity_period_seconds: numberOrNull(planDraft.validityDays, 86400),
        speed_profile: planDraft.speedProfile || null,
      };
      await apiRequest<Plan>(token, editingPlanId ? `/api/v1/plans/${editingPlanId}` : "/api/v1/plans", {
        method: editingPlanId ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      setPlanDraft({ code: "", name: "", price: "", commissionType: "none", commissionValue: "", dataGb: "", timeHours: "", validityDays: "", speedProfile: "" });
      const wasEditing = editingPlanId !== null;
      setEditingPlanId(null);
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
    setPlanDraft({
      code: plan.code,
      name: plan.name,
      price: String(plan.price),
      commissionType: plan.commission_type,
      commissionValue: plan.commission_type === "none" ? "" : String(plan.commission_value),
      dataGb: plan.data_limit_bytes === null ? "" : String(plan.data_limit_bytes / 1024 ** 3),
      timeHours: plan.session_time_limit_seconds === null ? "" : String(plan.session_time_limit_seconds / 3600),
      validityDays: plan.validity_period_seconds === null ? "" : String(plan.validity_period_seconds / 86400),
      speedProfile: plan.speed_profile ?? "",
    });
    setError("");
    setNotice("أنت تعدّل بيانات الباقة المحددة.");
  }

  async function togglePlan(plan: Plan) {
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

  async function changeCardStatus(card: Card, action: "suspend" | "reactivate" | "cancel") {
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
    setBusy(true); setError(""); setNotice(""); setGeneratedCards([]);
    try {
      const result = await apiRequest<{ serial_number: string; username: string; password: string }> (token, "/api/v1/cards/single", {
        method: "POST",
        body: JSON.stringify({
          plan_id: Number(singleDraft.planId || plans[0]?.id),
          username: singleDraft.username,
          card_type: singleDraft.cardType,
          password: singleDraft.cardType === "separate_credentials" ? singleDraft.password : null,
          is_free: singleDraft.isFree,
        }),
      });
      setGeneratedCards([{ serial_number: result.serial_number, username: result.username, password: result.password }]);
      await loadCards();
      setNotice("تم إنشاء الكرت. احفظ بيانات الدخول الآن؛ لن تظهر كلمة المرور مرة أخرى.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء الكرت");
    } finally {
      setBusy(false);
    }
  }

  async function createBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice(""); setGeneratedCards([]);
    try {
      const result = await apiRequest<{ created_count: number; cards: GeneratedCard[] }>(token, "/api/v1/cards/batch", {
        method: "POST",
        body: JSON.stringify({
          plan_id: Number(batchDraft.planId),
          quantity: Number(batchDraft.quantity),
          card_type: batchDraft.cardType,
          generation_mode: batchDraft.generationMode,
          username_length: Number(batchDraft.usernameLength),
          password_length: Number(batchDraft.passwordLength),
          prefix: batchDraft.prefix,
        }),
      });
      setGeneratedCards(result.cards);
      await loadCards();
      setNotice(`تم إنشاء ${result.created_count} كرت. احفظ بيانات الدخول الآن؛ لن تظهر كلمات المرور مرة أخرى.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء الدفعة");
    } finally {
      setBusy(false);
    }
  }

  function renderOverview() {
    return (
      <>
        <section className="welcome-card" id="overview">
          <div>
            <span className="welcome-kicker">مرحباً بك، {user.display_name}</span>
            <h2>نظام الأسطورة لإدارة RADIUS</h2>
            <p>منصة موحدة لإدارة الكروت والباقات والراوترات ونقاط البيع.</p>
          </div>
          <div className="welcome-symbol">A</div>
        </section>
        <div className="section-heading">
          <div><h2>وحدات النظام</h2><p>اختر إحدى الوحدات التي بدأ تشغيلها.</p></div>
          <span className="phase-tag">مرحلة التأسيس</span>
        </div>
        <div className="module-grid">
          {modules.map((item) => (
            <button className="module-card module-card-button" key={item.title} onClick={() => setPage(item.page)}>
              <div className="module-icon">{item.icon}</div>
              <h3>{item.title}</h3>
              <p>{item.detail}</p>
              <span className={item.page === "overview" ? "module-state" : "module-state active-state"}>
                {item.page === "overview" ? "قيد التطوير" : "متاح الآن"}
              </span>
            </button>
          ))}
        </div>
      </>
    );
  }

  function renderPlans() {
    return (
      <>
        <div className="section-heading"><div><h2>إدارة الباقات</h2><p>حدد السعر وحدود الاستخدام والصلاحية والسرعة، ويمكنك تعديل الباقة أو إيقافها دون حذفها.</p></div></div>
        <form className="panel form-grid" onSubmit={createPlan}>
          <label>رمز الباقة<input value={planDraft.code} onChange={(e) => setPlanDraft({ ...planDraft, code: e.target.value })} required /></label>
          <label>اسم الباقة<input value={planDraft.name} onChange={(e) => setPlanDraft({ ...planDraft, name: e.target.value })} required /></label>
          <label>السعر<input type="number" min="0" step="0.01" value={planDraft.price} onChange={(e) => setPlanDraft({ ...planDraft, price: e.target.value })} required /></label>
          <label>نوع العمولة<select value={planDraft.commissionType} onChange={(e) => setPlanDraft({ ...planDraft, commissionType: e.target.value as "none" | "fixed" | "percentage", commissionValue: e.target.value === "none" ? "" : planDraft.commissionValue })}><option value="none">بدون عمولة</option><option value="percentage">نسبة مئوية</option><option value="fixed">مبلغ ثابت لكل كرت</option></select></label>
          {planDraft.commissionType !== "none" && <label>{planDraft.commissionType === "percentage" ? "نسبة العمولة (%)" : "العمولة لكل كرت (ريال)"}<input type="number" min="0" max={planDraft.commissionType === "percentage" ? "100" : planDraft.price || undefined} step="0.01" value={planDraft.commissionValue} onChange={(e) => setPlanDraft({ ...planDraft, commissionValue: e.target.value })} required /></label>}
          <label>الحجم بالجيجابايت <span className="field-hint">اتركه فارغاً ليكون مفتوحاً</span><input type="number" min="0.001" step="0.001" value={planDraft.dataGb} onChange={(e) => setPlanDraft({ ...planDraft, dataGb: e.target.value })} /></label>
          <label>وقت الاستخدام بالساعات <span className="field-hint">اتركه فارغاً ليكون مفتوحاً</span><input type="number" min="0.01" step="0.01" value={planDraft.timeHours} onChange={(e) => setPlanDraft({ ...planDraft, timeHours: e.target.value })} /></label>
          <label>الصلاحية بالأيام <span className="field-hint">تبدأ من أول دخول</span><input type="number" min="0.01" step="0.01" value={planDraft.validityDays} onChange={(e) => setPlanDraft({ ...planDraft, validityDays: e.target.value })} /></label>
          <label>اسم السرعة<input value={planDraft.speedProfile} onChange={(e) => setPlanDraft({ ...planDraft, speedProfile: e.target.value })} placeholder="مثال: 2M (اختياري)" /></label>
          <div className="form-actions"><button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ..." : editingPlanId ? "حفظ التعديلات" : "إنشاء الباقة"}</button>{editingPlanId !== null && <button type="button" className="secondary-button" onClick={() => { setEditingPlanId(null); setPlanDraft({ code: "", name: "", price: "", commissionType: "none", commissionValue: "", dataGb: "", timeHours: "", validityDays: "", speedProfile: "" }); setNotice(""); }}>إلغاء التعديل</button>}</div>
        </form>
        <div className="section-heading compact-heading"><div><h2>الباقات المسجلة</h2></div><span className="count-tag">{plans.length} باقة</span></div>
        <div className="table-wrap"><table><thead><tr><th>الرمز</th><th>اسم الباقة</th><th>السعر</th><th>عمولة نقطة البيع</th><th>الحجم</th><th>الوقت</th><th>الصلاحية</th><th>الحالة</th><th>الإجراءات</th></tr></thead>
          <tbody>{plans.map((plan) => <tr key={plan.id}><td>{plan.code}</td><td>{plan.name}</td><td>{Number(plan.price).toLocaleString("en-US")}</td><td>{plan.commission_type === "none" ? "بدون" : plan.commission_type === "percentage" ? `${Number(plan.commission_value)}%` : `${Number(plan.commission_value).toFixed(2)} ريال`}</td><td>{plan.data_limit_bytes === null ? "مفتوح" : `${(plan.data_limit_bytes / 1024 ** 3).toFixed(2)} GB`}</td><td>{plan.session_time_limit_seconds === null ? "مفتوح" : `${(plan.session_time_limit_seconds / 3600).toFixed(2)} ساعة`}</td><td>{plan.validity_period_seconds === null ? "مفتوح" : `${(plan.validity_period_seconds / 86400).toFixed(2)} يوم`}</td><td>{plan.is_active ? "مفعلة" : "متوقفة"}</td><td><button type="button" className="table-action" onClick={() => editPlan(plan)}>تعديل</button><button type="button" className="table-action" disabled={busy} onClick={() => togglePlan(plan)}>{plan.is_active ? "إيقاف" : "تفعيل"}</button></td></tr>)}</tbody>
        </table>{plans.length === 0 && <div className="empty-state">لا توجد باقات بعد. أنشئ أول باقة من النموذج أعلاه.</div>}</div>
      </>
    );
  }

  function renderCards() {
    return (
      <>
        <div className="section-heading"><div><h2>إدارة الكروت</h2><p>أنشئ كرتاً منفرداً أو دفعة كروت وفق نوع بيانات الدخول.</p></div></div>
        <div className="mode-tabs">
          <button type="button" className={cardMode === "single" ? "mode-tab active" : "mode-tab"} onClick={() => { setCardMode("single"); setGeneratedCards([]); }}>كرت منفرد</button>
          <button type="button" className={cardMode === "batch" ? "mode-tab active" : "mode-tab"} onClick={() => { setCardMode("batch"); setGeneratedCards([]); }}>دفعة كروت</button>
        </div>
        {plans.filter((plan) => plan.is_active).length === 0 ? <div className="empty-state">لا توجد باقات مفعلة. فعّل باقة من قسم الباقات أولاً.</div> : cardMode === "single" ? (
          <form className="panel form-grid" onSubmit={createSingle}>
            <label>الباقة<select value={singleDraft.planId || (plans[0] ? String(plans[0].id) : "")} onChange={(e) => setSingleDraft({ ...singleDraft, planId: e.target.value })}>{plans.filter((plan) => plan.is_active).map((plan) => <option value={plan.id} key={plan.id}>{plan.name} — {plan.code}</option>)}</select></label>
            <label>اسم المستخدم<input value={singleDraft.username} onChange={(e) => setSingleDraft({ ...singleDraft, username: e.target.value })} minLength={3} maxLength={32} required /></label>
            <label>نوع بيانات الدخول<select value={singleDraft.cardType} onChange={(e) => setSingleDraft({ ...singleDraft, cardType: e.target.value })}><option value="username_only">اسم مستخدم فقط</option><option value="same_credentials">اسم المستخدم وكلمة المرور متطابقان</option><option value="separate_credentials">اسم مستخدم وكلمة مرور مختلفان</option></select></label>
            {singleDraft.cardType === "separate_credentials" && <label>كلمة المرور<input type="text" value={singleDraft.password} onChange={(e) => setSingleDraft({ ...singleDraft, password: e.target.value })} minLength={4} maxLength={32} required /></label>}
            <label className="checkbox-label"><input type="checkbox" checked={singleDraft.isFree} onChange={(e) => setSingleDraft({ ...singleDraft, isFree: e.target.checked })} /> كرت مجاني / خاص بمالك الشبكة</label>
            <div className="form-actions"><button type="submit" disabled={busy || !singleDraft.planId}>{busy ? "جارٍ الإنشاء..." : "إنشاء الكرت"}</button></div>
          </form>
        ) : (
          <form className="panel form-grid" onSubmit={createBatch}>
            <label>الباقة<select value={batchDraft.planId} onChange={(e) => setBatchDraft({ ...batchDraft, planId: e.target.value })}>{plans.filter((plan) => plan.is_active).map((plan) => <option value={plan.id} key={plan.id}>{plan.name} — {plan.code}</option>)}</select></label>
            <label>عدد الكروت<input type="number" min="1" max="5000" value={batchDraft.quantity} onChange={(e) => setBatchDraft({ ...batchDraft, quantity: e.target.value })} required /></label>
            <label>نوع بيانات الدخول<select value={batchDraft.cardType} onChange={(e) => setBatchDraft({ ...batchDraft, cardType: e.target.value })}><option value="username_only">اسم مستخدم فقط</option><option value="same_credentials">اسم المستخدم وكلمة المرور متطابقان</option><option value="separate_credentials">اسم مستخدم وكلمة مرور مختلفان</option></select></label>
            <label>طريقة توليد اسم المستخدم<select value={batchDraft.generationMode} onChange={(e) => setBatchDraft({ ...batchDraft, generationMode: e.target.value })}><option value="digits">أرقام فقط</option><option value="letters">حروف فقط</option><option value="alphanumeric">أرقام وحروف</option></select></label>
            <label>طول اسم المستخدم<input type="number" min="3" max="32" value={batchDraft.usernameLength} onChange={(e) => setBatchDraft({ ...batchDraft, usernameLength: e.target.value })} /></label>
            <label>طول كلمة المرور<input type="number" min="4" max="32" value={batchDraft.passwordLength} onChange={(e) => setBatchDraft({ ...batchDraft, passwordLength: e.target.value })} disabled={batchDraft.cardType !== "separate_credentials"} /></label>
            <label>بادئة اختيارية<input value={batchDraft.prefix} onChange={(e) => setBatchDraft({ ...batchDraft, prefix: e.target.value })} placeholder="مثال: 777" /></label>
            <div className="form-actions"><button type="submit" disabled={busy || !batchDraft.planId}>{busy ? "جارٍ إنشاء الكروت..." : "إنشاء الدفعة"}</button></div>
          </form>
        )}
        {generatedCards.length > 0 && (
          <section className="generated-panel">
            <div className="section-heading compact-heading"><div><h2>بيانات الدفعة الجديدة</h2><p>كلمات المرور تظهر الآن فقط. احفظ الجدول أو اطبعه قبل مغادرة الصفحة.</p></div><button type="button" className="secondary-button" onClick={() => window.print()}>طباعة الصفحة</button></div>
            <div className="table-wrap"><table><thead><tr><th>التسلسل</th><th>اسم المستخدم</th><th>كلمة المرور</th></tr></thead><tbody>{generatedCards.map((card) => <tr key={card.serial_number}><td>{card.serial_number}</td><td>{card.username}</td><td>{card.password || "بدون كلمة مرور"}</td></tr>)}</tbody></table></div>
          </section>
        )}
        <div className="section-heading compact-heading"><div><h2>سجل الكروت</h2><p>ابحث باسم المستخدم أو الرقم التسلسلي، ثم أوقف الكرت أو أعد تفعيله أو ألغِ الكرت غير المستخدم.</p></div><span className="count-tag">200 كرت لكل صفحة</span></div>
        <div className="card-search"><label htmlFor="card-search">بحث في الكروت</label><input id="card-search" value={cardSearch} onChange={(e) => { setCardSearch(e.target.value); setCardOffset(0); loadCards(e.target.value, 0).catch((err) => setError(err instanceof Error ? err.message : "تعذر البحث")); }} placeholder="اسم المستخدم أو الرقم التسلسلي" /></div>
        <div className="table-wrap"><table><thead><tr><th>الرقم التسلسلي</th><th>اسم المستخدم</th><th>نوع الدخول</th><th>الباقة</th><th>الحالة</th><th>مجاني</th><th>الإجراءات</th></tr></thead><tbody>{cards.map((card) => <tr key={card.id}><td>{card.serial_number}</td><td>{card.username}</td><td>{card.card_type}</td><td>{plans.find((p) => p.id === card.plan_id)?.name ?? card.plan_id}</td><td>{card.status === "generated" ? "منشأ" : card.status === "allocated" ? "مخصص لنقطة بيع" : card.status === "active" ? "متصل" : card.status === "suspended" ? "موقوف" : card.status === "cancelled" ? "ملغي" : card.status === "printed_free" ? "مجاني مطبوع" : card.status === "expired" ? "منتهي الصلاحية" : card.status === "exhausted" ? "نفد الرصيد" : card.status}</td><td>{card.is_free ? "نعم" : "لا"}</td><td className="actions-cell">{card.status === "suspended" ? <button type="button" className="table-action" disabled={busy} onClick={() => changeCardStatus(card, "reactivate")}>إعادة تفعيل</button> : ["generated", "allocated", "active", "printed_free"].includes(card.status) ? <button type="button" className="table-action" disabled={busy} onClick={() => changeCardStatus(card, "suspend")}>إيقاف</button> : null}{["generated", "printed_free"].includes(card.status) && !card.first_used_at && !card.assigned_pos_id && <button type="button" className="table-action danger-action" disabled={busy} onClick={() => changeCardStatus(card, "cancel")}>إلغاء</button>}</td></tr>)}</tbody></table>{cards.length === 0 && <div className="empty-state">لا توجد كروت تطابق البحث في هذه الصفحة.</div>}</div>
        <div className="pagination-controls">
          <button type="button" className="table-action" disabled={cardOffset === 0 || busy} onClick={() => changeCardPage(cardOffset - 200)}>السابق</button>
          <span>الصفحة {Math.floor(cardOffset / 200) + 1}</span>
          <button type="button" className="table-action" disabled={!hasMoreCards || busy} onClick={() => changeCardPage(cardOffset + 200)}>التالي</button>
        </div>
      </>
    );
  }

  function renderPos() {
    const printableCards = cards.filter((card) => card.status === "generated" && card.assigned_pos_id === null);
    const selectedPoint = points.find((point) => String(point.id) === selectedPosId);
    return (
      <>
        <div className="section-heading">
          <div><h2>نقاط البيع والطباعة</h2><p>أنشئ نقاط البيع، راجع قيمة الكروت المطبوعة، وسجل الطباعة أو أعد طباعة دفعة سابقة.</p></div>
        </div>
        <form className="panel form-grid" onSubmit={createPointOfSale}>
          <label>رمز نقطة البيع<input value={posDraft.code} onChange={(e) => setPosDraft({ ...posDraft, code: e.target.value })} required minLength={2} maxLength={50} /></label>
          <label>اسم نقطة البيع<input value={posDraft.name} onChange={(e) => setPosDraft({ ...posDraft, name: e.target.value })} required minLength={2} maxLength={150} /></label>
          <label>اسم المسؤول<input value={posDraft.contactName} onChange={(e) => setPosDraft({ ...posDraft, contactName: e.target.value })} /></label>
          <label>رقم الهاتف<input value={posDraft.phone} onChange={(e) => setPosDraft({ ...posDraft, phone: e.target.value })} /></label>
          <div className="form-actions"><button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ..." : "إضافة نقطة بيع"}</button></div>
        </form>

        <div className="pos-toolbar">
          <label>اختر نقطة البيع
            <select value={selectedPosId} onChange={(e) => {
              const id = e.target.value;
              setSelectedPrintCardIds([]);
              setPrintPreviewCards([]);
              setSelectedPosId(id);
              Promise.all([loadPosInventory(id), loadPrintHistory(id), loadPosAccount(id)]).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل بيانات نقطة البيع"));
            }}>
              <option value="">-- اختر نقطة بيع --</option>
              {points.map((point) => <option key={point.id} value={point.id}>{point.name} — {point.code}{point.is_active ? "" : " (متوقفة)"}</option>)}
            </select>
          </label>
          {selectedPoint && <button type="button" className="table-action" disabled={busy} onClick={() => togglePointOfSale(selectedPoint)}>{selectedPoint.is_active ? "إيقاف النقطة" : "تفعيل النقطة"}</button>}
        </div>

        {selectedPosId && posInventory && (
          <div className="pos-stats">
            <div><span>الكروت المخصصة</span><strong>{posInventory.allocated_cards}</strong></div>
            <div><span>الكروت المستخدمة</span><strong>{posInventory.used_cards}</strong></div>
            <div><span>الكروت الموقوفة</span><strong>{posInventory.suspended_cards}</strong></div>
            <div><span>القيمة التجارية المطبوعة</span><strong>{Number(posInventory.commercial_printed_value).toLocaleString("en-US")}</strong></div>
            <div><span>الكروت المجانية المطبوعة</span><strong>{posInventory.free_cards_printed}</strong></div>
          </div>
        )}

        {selectedPosId && posAccount && (
          <section className="pos-account-section">
            <div className="section-heading compact-heading"><div><h2>الحساب المالي لنقطة البيع</h2><p>الرصيد يُحدّث تلقائياً عند تخصيص الكروت التجارية، ولا تُحتسب إعادة الطباعة أو الكروت المجانية.</p></div></div>
            <div className="pos-stats account-stats">
              <div><span>إجمالي المديونية</span><strong>{Number(posAccount.total_debit).toLocaleString("en-US", { minimumFractionDigits: 2 })} ريال</strong></div>
              <div><span>إجمالي السداد والخصومات</span><strong>{Number(posAccount.total_credit).toLocaleString("en-US", { minimumFractionDigits: 2 })} ريال</strong></div>
              <div><span>الرصيد المستحق</span><strong>{Number(posAccount.balance_due).toLocaleString("en-US", { minimumFractionDigits: 2 })} ريال</strong></div>
            </div>
            <form className="panel form-grid account-entry-form" onSubmit={createAccountEntry}>
              <label>نوع الحركة<select value={accountDraft.entryType} onChange={(e) => setAccountDraft({ ...accountDraft, entryType: e.target.value, direction: e.target.value === "payment" || e.target.value === "commission" || e.target.value === "return" ? "credit" : accountDraft.direction })}>
                <option value="payment">سداد من نقطة البيع</option><option value="commission">عمولة مستحقة للنقطة</option><option value="return">مرتجع / خصم</option><option value="adjustment">تسوية يدوية</option>
              </select></label>
              <label>اتجاه الحركة<select value={accountDraft.direction} onChange={(e) => setAccountDraft({ ...accountDraft, direction: e.target.value as "debit" | "credit" })}><option value="credit">يخصم من المديونية (دائن)</option><option value="debit">يضاف للمديونية (مدين)</option></select></label>
              <label>المبلغ بالريال<input type="number" min="0.01" step="0.01" value={accountDraft.amount} onChange={(e) => setAccountDraft({ ...accountDraft, amount: e.target.value })} required /></label>
              <label>البيان<input value={accountDraft.description} onChange={(e) => setAccountDraft({ ...accountDraft, description: e.target.value })} maxLength={500} placeholder="مثال: سداد نقدي" /></label>
              <label>رقم مرجعي (اختياري)<input value={accountDraft.reference} onChange={(e) => setAccountDraft({ ...accountDraft, reference: e.target.value })} maxLength={120} /></label>
              <div className="form-actions"><button type="submit" disabled={busy || !accountDraft.amount || Number(accountDraft.amount) <= 0}>{busy ? "جارٍ التسجيل..." : "تسجيل الحركة"}</button></div>
            </form>
            <div className="section-heading compact-heading"><div><h2>كشف الحساب</h2><p>آخر 100 حركة مالية، مرتبة من الأحدث إلى الأقدم.</p></div><span className="count-tag">{posEntries.length} حركة</span></div>
            <div className="table-wrap"><table><thead><tr><th>التاريخ</th><th>نوع الحركة</th><th>البيان</th><th>مدين</th><th>دائن</th><th>الموظف</th><th>المرجع</th></tr></thead><tbody>
              {posEntries.map((entry) => <tr key={entry.id}><td>{new Date(entry.created_at).toLocaleString("ar")}</td><td>{({ card_delivery: "تسليم كروت", payment: "سداد", commission: "عمولة", return: "مرتجع", adjustment: "تسوية" } as Record<string, string>)[entry.entry_type] ?? entry.entry_type}</td><td>{entry.description || "—"}</td><td>{entry.direction === "debit" ? Number(entry.amount).toFixed(2) : "—"}</td><td>{entry.direction === "credit" ? Number(entry.amount).toFixed(2) : "—"}</td><td>{entry.created_by || "—"}</td><td>{entry.reference || "—"}</td></tr>)}
            </tbody></table>{posEntries.length === 0 && <div className="empty-state">لا توجد حركات مالية مسجلة لهذه النقطة.</div>}</div>
          </section>
        )}

        {selectedPosId && (
          <>
            <div className="section-heading compact-heading"><div><h2>الكروت الجاهزة للتخصيص</h2><p>حدد الكروت المنشأة وغير المخصصة. عند التسجيل تُرحّل القيمة التجارية مرة واحدة فقط.</p></div><span className="count-tag">{printableCards.length} كرت</span></div>
            <div className="card-search">
              <label htmlFor="pos-card-search">بحث عن كرت</label>
              <input id="pos-card-search" value={cardSearch} onChange={(e) => { setCardSearch(e.target.value); setCardOffset(0); loadCards(e.target.value, 0).catch((err) => setError(err instanceof Error ? err.message : "تعذر البحث")); }} placeholder="اسم المستخدم أو الرقم التسلسلي" />
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
              <label>قالب الطباعة
                <select value={printTemplate} onChange={(e) => setPrintTemplate(e.target.value)}>
                  <option value="classic-green">القالب الأخضر</option>
                  <option value="classic-blue">القالب الأزرق</option>
                  <option value="compact">القالب المختصر</option>
                </select>
              </label>
              <div className="pos-print-summary">تم اختيار {selectedPrintCardIds.length} كرت. الكروت المجانية تظهر في القسائم ولا تدخل في قيمة نقطة البيع.</div>
              <button type="button" disabled={busy || selectedPrintCardIds.length === 0 || !selectedPoint?.is_active} onClick={printSelectedCards}>{busy ? "جارٍ التسجيل..." : "تسجيل دفعة الطباعة وتخصيص الكروت"}</button>
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
                <div className="voucher-grid">
                  {printPreviewCards.map((card) => (
                    <article className={`voucher-card ${printTemplate}`} key={card.card_id}>
                      <div className="voucher-head"><strong>الأسطورة نت</strong><span>{card.is_free ? "كرت مجاني" : "بطاقة إنترنت"}</span></div>
                      <div className="voucher-user"><span>اسم المستخدم</span><strong>{card.username}</strong></div>
                      <div className="voucher-password"><span>كلمة المرور</span><strong>{card.password || "بدون كلمة مرور"}</strong></div>
                      <div className="voucher-foot"><span>{card.serial_number}</span><strong>{card.is_free ? "مجاني" : `${Number(card.price_snapshot).toLocaleString("en-US")} ريال`}</strong></div>
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
                  <td><button type="button" className="table-action" disabled={busy || !selectedPoint?.is_active} onClick={() => reprintJob(job)}>إعادة طباعة</button></td>
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
          <div><h2>تقارير نقاط البيع</h2><p>ملخص التسليمات والعمولات والسدادات والأرصدة خلال الفترة المحددة.</p></div>
          <span className="count-tag">{posReport?.point_count ?? 0} نقطة بيع</span>
        </div>
        <form className="panel form-grid" onSubmit={(event) => { event.preventDefault(); setBusy(true); setError(""); loadReportData().catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل التقرير")).finally(() => setBusy(false)); }}>
          <label>من تاريخ<input type="date" value={reportFrom} max={reportTo} onChange={(event) => setReportFrom(event.target.value)} required /></label>
          <label>إلى تاريخ<input type="date" value={reportTo} min={reportFrom} onChange={(event) => setReportTo(event.target.value)} required /></label>
          <div className="form-actions"><button type="submit" disabled={busy}>{busy ? "جارٍ إعداد التقرير..." : "عرض التقرير"}</button></div>
        </form>
        {posReport && (
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
        <form className="panel form-grid" onSubmit={createRouter}>
          <label>اسم الراوتر<input value={routerDraft.name} onChange={(e) => setRouterDraft({ ...routerDraft, name: e.target.value })} required minLength={2} maxLength={120} /></label>
          <label>NAS Identifier<input value={routerDraft.nasIdentifier} onChange={(e) => setRouterDraft({ ...routerDraft, nasIdentifier: e.target.value })} required maxLength={150} placeholder="مثال: router-aden-01" /><small className="field-hint">يجب أن يطابق اسم الهوية في MikroTik: /system identity.</small></label>
          <label>عنوان الإدارة / IP<input value={routerDraft.managementHost} onChange={(e) => setRouterDraft({ ...routerDraft, managementHost: e.target.value })} required maxLength={255} placeholder="مثال: 192.168.88.1" /></label>
          <label>عنوان RADIUS للراوتر أو CIDR<input value={routerDraft.radiusClientAddress} onChange={(e) => setRouterDraft({ ...routerDraft, radiusClientAddress: e.target.value })} maxLength={255} placeholder="مثال: 192.168.88.1 أو 192.168.88.0/24" /><small className="field-hint">عنوان مصدر حزم RADIUS كما يراه الخادم، وقد يختلف عن عنوان إدارة API. إذا تركته فارغاً فلن يُحمّل الراوتر كعميل RADIUS.</small></label>
          <label>منفذ MikroTik API<input type="number" min="1" max="65535" value={routerDraft.apiPort} onChange={(e) => setRouterDraft({ ...routerDraft, apiPort: e.target.value })} required /><small className="field-hint">المنفذ حسب إعداد /ip service في الراوتر؛ يمكن تغيير منفذ API-SSL من إعدادات MikroTik.</small></label>
          <label className="inline-check"><input type="checkbox" checked={routerDraft.apiUseSsl} onChange={(e) => setRouterDraft({ ...routerDraft, apiUseSsl: e.target.checked })} /> استخدام API-SSL (TLS) والتحقق من شهادة الراوتر</label>
          <small className="field-hint">اتركه مفعلاً لحماية اتصال API. عند إيقافه لا تُشفّر القناة ويستخدم الموصل challenge-response القديم بدلاً من إرسال كلمة المرور الصريحة؛ قد لا يعمل ذلك مع RouterOS 6.43+، لذا يُفضّل تفعيل API-SSL.</small>
          <label>اسم مستخدم API (اختياري)<input value={routerDraft.apiUsername} onChange={(e) => setRouterDraft({ ...routerDraft, apiUsername: e.target.value })} maxLength={120} /></label>
          <label>كلمة مرور API (اختياري)<input type="password" autoComplete="new-password" value={routerDraft.apiSecret} onChange={(e) => setRouterDraft({ ...routerDraft, apiSecret: e.target.value })} minLength={8} maxLength={500} /></label>
          <label>RADIUS Shared Secret<input type="password" autoComplete="new-password" value={routerDraft.radiusSecret} onChange={(e) => setRouterDraft({ ...routerDraft, radiusSecret: e.target.value })} required minLength={8} maxLength={500} /><small className="field-hint">استخدم القيمة نفسها في إعداد /radius على MikroTik؛ لن تظهر مرة أخرى بعد الحفظ.</small></label>
          <label>إصدار RouterOS<input value={routerDraft.routerosVersion} onChange={(e) => setRouterDraft({ ...routerDraft, routerosVersion: e.target.value })} maxLength={30} placeholder="مثال: 7.x أو 6.x" /></label>
          <div className="form-actions"><button type="submit" disabled={busy || (!!routerDraft.apiUsername !== !!routerDraft.apiSecret)}>{busy ? "جارٍ الحفظ..." : "حفظ الراوتر"}</button></div>
          {!!routerDraft.apiUsername !== !!routerDraft.apiSecret && <div className="field-hint">أدخل اسم مستخدم API وكلمة مروره معاً، أو اتركهما فارغين.</div>}
        </form>
        <section className="panel form-grid">
          <div className="section-heading"><div><h2>فحص كرت واحد من User Manager</h2><p>بحث تشخيصي بالاسم الدقيق؛ لا ينشئ كرتاً ولا يستورده ولا يغيّر بيانات المصدر.</p></div></div>
          <label>جهاز User Manager
            <select value={inspectRouterId} onChange={(event) => { const nextId = event.target.value; setInspectRouterId(nextId); setUserManagerUserInspect(null); setUserManagerPreviews(null); setUserManagerPreviewRuns([]); setSelectedPreviewRunId(""); if (nextId) loadUserManagerPreviewRuns(Number(nextId)).catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل سجل المعاينات")); }}>
              <option value="">اختر الراوتر المسجل</option>
              {routers.filter((item) => item.is_active && item.api_username).map((item) => (
                <option key={item.id} value={item.id}>{item.name} — {item.management_host}:{item.api_port} ({item.api_use_ssl ? "TLS" : "غير مشفر"})</option>
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
            {userManagerPreviews.items.map((preview) => (
              <div className="notice" key={preview.id}>
                <strong>{preview.username || "اسم غير متاح"}</strong>
                <div>تصنيف السجل: {preview.classification}</div>
                <div>البروفايل الأصلي: {preview.source_profile_id || "غير متاح"}</div>
                <div>حالة بيانات الدخول: {preview.credential_state}</div>
                <div>نوع بيانات الدخول: {preview.credential_mode}</div>
                <div>معرّف المصدر: {preview.external_user_id}</div>
                {preview.issues.length > 0 && <div>ملاحظات: {preview.issues.join("، ")}</div>}
              </div>
            ))}
            <small className="field-hint">حالة المعاينة: قراءة فقط · الاستيراد: متوقف · قراءة كلمات المرور: لم تتم.</small>
          </section>
        )}
        <div className="section-heading compact-heading"><div><h2>الراوترات المسجلة</h2><p>لا تعرض هذه القائمة أي كلمة مرور أو RADIUS secret.</p></div><span className="count-tag">{routers.length} راوتر</span></div>
        <div className="table-wrap">
          <table><thead><tr><th>الاسم</th><th>NAS Identifier</th><th>عنوان الإدارة</th><th>عنوان RADIUS</th><th>API Port / TLS</th><th>الإصدار</th><th>آخر ظهور</th><th>الحالة</th><th>الإجراء</th></tr></thead>
            <tbody>{routers.map((router) => <tr key={router.id}>
              <td>{router.name}</td><td>{router.nas_identifier}</td><td>{router.management_host}</td><td>{router.radius_client_address || "غير محدد"}</td><td>{router.api_port} / {router.api_use_ssl ? "TLS" : "غير مشفر"}</td>
              <td>{router.routeros_version || "غير محدد"}</td><td>{router.last_seen_at ? new Date(router.last_seen_at).toLocaleString("ar") : "لم يتصل بعد"}</td>
              <td>{router.is_active ? "مفعل" : "متوقف"}</td>
              <td className="actions-cell">
                <button type="button" className="table-action" disabled={busy || probingRouterId !== null || !router.api_username} onClick={() => testRouterUserManager(router)}>{probingRouterId === router.id ? "جارٍ الفحص..." : "فحص User Manager"}</button>
                <button type="button" className="table-action" disabled={busy || probingRouterId !== null} onClick={() => toggleRouter(router)}>{router.is_active ? "تعطيل" : "تفعيل"}</button>
              </td>
            </tr>)}</tbody>
          </table>
          {routers.length === 0 && <div className="empty-state">لا توجد راوترات مسجلة. أضف أول راوتر من النموذج أعلاه.</div>}
        </div>
        {userManagerProbe && (
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
          <button className={page === "overview" ? "nav-item active" : "nav-item"} onClick={() => setPage("overview")}>نظرة عامة</button>
          <button className={page === "plans" ? "nav-item active" : "nav-item"} onClick={() => setPage("plans")}>الباقات</button>
          <button className={page === "cards" ? "nav-item active" : "nav-item"} onClick={() => setPage("cards")}>الكروت</button>
          <button className={page === "pos" ? "nav-item active" : "nav-item"} onClick={() => setPage("pos")}>نقاط البيع والطباعة</button>
          <button className={page === "routers" ? "nav-item active" : "nav-item"} onClick={() => setPage("routers")}>أجهزة MikroTik</button>
          <button className={page === "reports" ? "nav-item active" : "nav-item"} onClick={() => setPage("reports")}>التقارير المالية</button>
        </nav>
        <div className="sidebar-foot">ALOSTORA-RADIUS · 0.4.0</div>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div><span className="eyebrow">مركز إدارة الشبكة</span><h1>{page === "overview" ? "لوحة التحكم" : page === "plans" ? "إدارة الباقات" : page === "cards" ? "إدارة الكروت" : page === "pos" ? "نقاط البيع والطباعة" : page === "reports" ? "التقارير المالية" : "إدارة أجهزة MikroTik"}</h1></div>
          <div className="topbar-actions"><div className="environment"><span className="status-dot" /> بيئة التطوير</div><div className="user-chip">{user.display_name}</div><button className="logout-button" onClick={onLogout}>تسجيل الخروج</button></div>
        </header>
        {error && <div className="notice error-notice" role="alert">{error}</div>}
        {notice && <div className="notice success-notice" role="status">{notice}</div>}
        {page === "overview" ? renderOverview() : page === "plans" ? renderPlans() : page === "cards" ? renderCards() : page === "pos" ? renderPos() : page === "reports" ? renderReports() : renderRouters()}
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
