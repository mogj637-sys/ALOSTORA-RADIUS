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
  api_port: number;
  api_username: string | null;
  routeros_version: string | null;
  is_active: boolean;
  last_seen_at: string | null;
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
  { title: "التقارير", detail: "المبيعات والاستخدام والأرشفة", icon: "▥", page: "overview" as const },
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
  const [page, setPage] = useState<"overview" | "plans" | "cards" | "pos" | "routers">("overview");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [routers, setRouters] = useState<RouterRecord[]>([]);
  const [routerDraft, setRouterDraft] = useState({ name: "", nasIdentifier: "", managementHost: "", apiPort: "8728", apiUsername: "", apiSecret: "", radiusSecret: "", routerosVersion: "" });
  const [cards, setCards] = useState<Card[]>([]);
  const [generatedCards, setGeneratedCards] = useState<GeneratedCard[]>([]);
  const [editingPlanId, setEditingPlanId] = useState<number | null>(null);
  const [cardSearch, setCardSearch] = useState("");
  const [points, setPoints] = useState<PointOfSale[]>([]);
  const [selectedPosId, setSelectedPosId] = useState("");
  const [posInventory, setPosInventory] = useState<PosInventory | null>(null);
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
    code: "", name: "", price: "", dataGb: "", timeHours: "", validityDays: "", speedProfile: "",
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
          api_port: Number(routerDraft.apiPort),
          api_username: routerDraft.apiUsername || null,
          api_secret: routerDraft.apiSecret || null,
          radius_secret: routerDraft.radiusSecret,
          routeros_version: routerDraft.routerosVersion || null,
        }),
      });
      setRouterDraft({ name: "", nasIdentifier: "", managementHost: "", apiPort: "8728", apiUsername: "", apiSecret: "", radiusSecret: "", routerosVersion: "" });
      await loadRouters();
      setNotice("تم تسجيل الراوتر وحفظ أسراره مشفرة.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تسجيل الراوتر");
    } finally { setBusy(false); }
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

  async function loadCards(search = cardSearch) {
    const params = new URLSearchParams({ offset: "0", limit: "200" });
    if (search.trim()) params.set("search", search.trim());
    const result = await apiRequest<Card[]>(token, `/api/v1/cards?${params.toString()}`);
    setCards(result);
  }

  async function loadPosInventory(pointId: string) {
    if (!pointId) { setPosInventory(null); return; }
    const result = await apiRequest<PosInventory>(token, `/api/v1/points-of-sale/${pointId}/inventory`);
    setPosInventory(result);
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
    await Promise.all([loadPosInventory(current), loadPrintHistory(current)]);
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
      await Promise.all([loadPosInventory(String(point.id)), loadPrintHistory(String(point.id))]);
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
    setSelectedPrintCardIds((current) =>
      current.includes(cardId) ? current.filter((id) => id !== cardId) : [...current, cardId]
    );
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
      await Promise.all([loadCards(), loadPosInventory(selectedPosId), loadPrintHistory(selectedPosId)]);
      setNotice(`تم تسجيل طباعة ${result.card_count} كرت: ${result.commercial_card_count} تجاري و${result.free_card_count} مجاني. القيمة التجارية: ${Number(result.total_amount).toFixed(2)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تنفيذ الطباعة");
    } finally { setBusy(false); }
  }

  useEffect(() => {
    if (page !== "pos") setPrintPreviewCards([]);
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
        data_limit_bytes: numberOrNull(planDraft.dataGb, 1024 ** 3),
        session_time_limit_seconds: numberOrNull(planDraft.timeHours, 3600),
        validity_period_seconds: numberOrNull(planDraft.validityDays, 86400),
        speed_profile: planDraft.speedProfile || null,
      };
      await apiRequest<Plan>(token, editingPlanId ? `/api/v1/plans/${editingPlanId}` : "/api/v1/plans", {
        method: editingPlanId ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      setPlanDraft({ code: "", name: "", price: "", dataGb: "", timeHours: "", validityDays: "", speedProfile: "" });
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

  async function reprintPrintJob(job: PrintJobHistory) {
    if (!selectedPosId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<PrintJobResult>(token, "/api/v1/print-jobs", {
        method: "POST",
        body: JSON.stringify({
          idempotency_key: `reprint-${crypto.randomUUID()}`,
          point_of_sale_id: Number(selectedPosId),
          card_ids: job.cards.map((card) => card.card_id),
          template_code: job.template_code || printTemplate,
          is_reprint: true,
        }),
      });
      setPrintTemplate(result.template_code || printTemplate);
      setPrintPreviewCards(result.items);
      await Promise.all([loadPosInventory(selectedPosId), loadPrintHistory(selectedPosId)]);
      setNotice(`تم تجهيز نسخة إعادة طباعة من ${result.card_count} كرت. لم تتم إضافة قيمة جديدة للمخزون.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذرت إعادة الطباعة");
    } finally { setBusy(false); }
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
          <label>الحجم بالجيجابايت <span className="field-hint">اتركه فارغاً ليكون مفتوحاً</span><input type="number" min="0.001" step="0.001" value={planDraft.dataGb} onChange={(e) => setPlanDraft({ ...planDraft, dataGb: e.target.value })} /></label>
          <label>وقت الاستخدام بالساعات <span className="field-hint">اتركه فارغاً ليكون مفتوحاً</span><input type="number" min="0.01" step="0.01" value={planDraft.timeHours} onChange={(e) => setPlanDraft({ ...planDraft, timeHours: e.target.value })} /></label>
          <label>الصلاحية بالأيام <span className="field-hint">تبدأ من أول دخول</span><input type="number" min="0.01" step="0.01" value={planDraft.validityDays} onChange={(e) => setPlanDraft({ ...planDraft, validityDays: e.target.value })} /></label>
          <label>اسم السرعة<input value={planDraft.speedProfile} onChange={(e) => setPlanDraft({ ...planDraft, speedProfile: e.target.value })} placeholder="مثال: 2M (اختياري)" /></label>
          <div className="form-actions"><button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ..." : editingPlanId ? "حفظ التعديلات" : "إنشاء الباقة"}</button>{editingPlanId !== null && <button type="button" className="secondary-button" onClick={() => { setEditingPlanId(null); setPlanDraft({ code: "", name: "", price: "", dataGb: "", timeHours: "", validityDays: "", speedProfile: "" }); setNotice(""); }}>إلغاء التعديل</button>}</div>
        </form>
        <div className="section-heading compact-heading"><div><h2>الباقات المسجلة</h2></div><span className="count-tag">{plans.length} باقة</span></div>
        <div className="table-wrap"><table><thead><tr><th>الرمز</th><th>اسم الباقة</th><th>السعر</th><th>الحجم</th><th>الوقت</th><th>الصلاحية</th><th>الحالة</th><th>الإجراءات</th></tr></thead>
          <tbody>{plans.map((plan) => <tr key={plan.id}><td>{plan.code}</td><td>{plan.name}</td><td>{Number(plan.price).toLocaleString("en-US")}</td><td>{plan.data_limit_bytes === null ? "مفتوح" : `${(plan.data_limit_bytes / 1024 ** 3).toFixed(2)} GB`}</td><td>{plan.session_time_limit_seconds === null ? "مفتوح" : `${(plan.session_time_limit_seconds / 3600).toFixed(2)} ساعة`}</td><td>{plan.validity_period_seconds === null ? "مفتوح" : `${(plan.validity_period_seconds / 86400).toFixed(2)} يوم`}</td><td>{plan.is_active ? "مفعلة" : "متوقفة"}</td><td><button type="button" className="table-action" onClick={() => editPlan(plan)}>تعديل</button><button type="button" className="table-action" disabled={busy} onClick={() => togglePlan(plan)}>{plan.is_active ? "إيقاف" : "تفعيل"}</button></td></tr>)}</tbody>
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
        <div className="section-heading compact-heading"><div><h2>سجل الكروت</h2><p>ابحث باسم المستخدم أو الرقم التسلسلي، ثم أوقف الكرت أو أعد تفعيله أو ألغِ الكرت غير المستخدم.</p></div><span className="count-tag">حتى 50 نتيجة</span></div>
        <div className="card-search"><label htmlFor="card-search">بحث في الكروت</label><input id="card-search" value={cardSearch} onChange={(e) => { setCardSearch(e.target.value); loadCards(e.target.value).catch((err) => setError(err instanceof Error ? err.message : "تعذر البحث")); }} placeholder="اسم المستخدم أو الرقم التسلسلي" /></div>
        <div className="table-wrap"><table><thead><tr><th>الرقم التسلسلي</th><th>اسم المستخدم</th><th>نوع الدخول</th><th>الباقة</th><th>الحالة</th><th>مجاني</th><th>الإجراءات</th></tr></thead><tbody>{cards.map((card) => <tr key={card.id}><td>{card.serial_number}</td><td>{card.username}</td><td>{card.card_type}</td><td>{plans.find((p) => p.id === card.plan_id)?.name ?? card.plan_id}</td><td>{card.status === "generated" ? "منشأ" : card.status === "suspended" ? "موقوف" : card.status === "cancelled" ? "ملغي" : card.status === "printed_free" ? "مجاني مطبوع" : card.status}</td><td>{card.is_free ? "نعم" : "لا"}</td><td className="actions-cell">{card.status === "suspended" ? <button type="button" className="table-action" disabled={busy} onClick={() => changeCardStatus(card, "reactivate")}>إعادة تفعيل</button> : ["generated", "allocated", "active"].includes(card.status) ? <button type="button" className="table-action" disabled={busy} onClick={() => changeCardStatus(card, "suspend")}>إيقاف</button> : null}{card.status === "generated" && <button type="button" className="table-action danger-action" disabled={busy} onClick={() => changeCardStatus(card, "cancel")}>إلغاء</button>}</td></tr>)}</tbody></table>{cards.length === 0 && <div className="empty-state">لا توجد كروت تطابق البحث.</div>}</div>
      </>
    );
  }

  function renderRouters() {
    return (
      <>
        <div className="section-heading">
          <div><h2>إدارة أجهزة MikroTik</h2><p>سجل الراوترات ومعرّفات NAS. تُحفظ كلمات المرور والأسرار مشفرة ولا تظهر في قائمة الراوترات.</p></div>
        </div>
        <div className="notice">تنبيه: هذه المرحلة تسجل إعدادات الراوتر وأسراره فقط. الاتصال الفعلي بـ RouterOS وإعداد FreeRADIUS لم يُفعّلا بعد.</div>
        <form className="panel form-grid" onSubmit={createRouter}>
          <label>اسم الراوتر<input value={routerDraft.name} onChange={(e) => setRouterDraft({ ...routerDraft, name: e.target.value })} required minLength={2} maxLength={120} /></label>
          <label>NAS Identifier<input value={routerDraft.nasIdentifier} onChange={(e) => setRouterDraft({ ...routerDraft, nasIdentifier: e.target.value })} required maxLength={150} placeholder="مثال: router-aden-01" /></label>
          <label>عنوان الإدارة / IP<input value={routerDraft.managementHost} onChange={(e) => setRouterDraft({ ...routerDraft, managementHost: e.target.value })} required maxLength={255} placeholder="مثال: 192.168.88.1" /></label>
          <label>منفذ MikroTik API<input type="number" min="1" max="65535" value={routerDraft.apiPort} onChange={(e) => setRouterDraft({ ...routerDraft, apiPort: e.target.value })} required /></label>
          <label>اسم مستخدم API (اختياري)<input value={routerDraft.apiUsername} onChange={(e) => setRouterDraft({ ...routerDraft, apiUsername: e.target.value })} maxLength={120} /></label>
          <label>كلمة مرور API (اختياري)<input type="password" autoComplete="new-password" value={routerDraft.apiSecret} onChange={(e) => setRouterDraft({ ...routerDraft, apiSecret: e.target.value })} minLength={8} maxLength={500} /></label>
          <label>RADIUS Shared Secret<input type="password" autoComplete="new-password" value={routerDraft.radiusSecret} onChange={(e) => setRouterDraft({ ...routerDraft, radiusSecret: e.target.value })} required minLength={8} maxLength={500} /></label>
          <label>إصدار RouterOS<input value={routerDraft.routerosVersion} onChange={(e) => setRouterDraft({ ...routerDraft, routerosVersion: e.target.value })} maxLength={30} placeholder="مثال: 7.x أو 6.x" /></label>
          <div className="form-actions"><button type="submit" disabled={busy || (!!routerDraft.apiUsername !== !!routerDraft.apiSecret)}>{busy ? "جارٍ الحفظ..." : "حفظ الراوتر"}</button></div>
          {!!routerDraft.apiUsername !== !!routerDraft.apiSecret && <div className="field-hint">أدخل اسم مستخدم API وكلمة مروره معاً، أو اتركهما فارغين.</div>}
        </form>
        <div className="section-heading compact-heading"><div><h2>الراوترات المسجلة</h2><p>لا تعرض هذه القائمة أي كلمة مرور أو RADIUS secret.</p></div><span className="count-tag">{routers.length} راوتر</span></div>
        <div className="table-wrap">
          <table><thead><tr><th>الاسم</th><th>NAS Identifier</th><th>عنوان الإدارة</th><th>API Port</th><th>الإصدار</th><th>آخر ظهور</th><th>الحالة</th><th>الإجراء</th></tr></thead>
            <tbody>{routers.map((router) => <tr key={router.id}>
              <td>{router.name}</td><td>{router.nas_identifier}</td><td>{router.management_host}</td><td>{router.api_port}</td>
              <td>{router.routeros_version || "غير محدد"}</td><td>{router.last_seen_at ? new Date(router.last_seen_at).toLocaleString("ar") : "لم يتصل بعد"}</td>
              <td>{router.is_active ? "مفعل" : "متوقف"}</td>
              <td><button type="button" className="table-action" disabled={busy} onClick={() => toggleRouter(router)}>{router.is_active ? "تعطيل" : "تفعيل"}</button></td>
            </tr>)}</tbody>
          </table>
          {routers.length === 0 && <div className="empty-state">لا توجد راوترات مسجلة. أضف أول راوتر من النموذج أعلاه.</div>}
        </div>
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
        </nav>
        <div className="sidebar-foot">ALOSTORA-RADIUS · 0.4.0</div>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div><span className="eyebrow">مركز إدارة الشبكة</span><h1>{page === "overview" ? "لوحة التحكم" : page === "plans" ? "إدارة الباقات" : page === "cards" ? "إدارة الكروت" : page === "pos" ? "نقاط البيع والطباعة" : "إدارة أجهزة MikroTik"}</h1></div>
          <div className="topbar-actions"><div className="environment"><span className="status-dot" /> بيئة التطوير</div><div className="user-chip">{user.display_name}</div><button className="logout-button" onClick={onLogout}>تسجيل الخروج</button></div>
        </header>
        {error && <div className="notice error-notice" role="alert">{error}</div>}
        {notice && <div className="notice success-notice" role="status">{notice}</div>}
        {page === "overview" ? renderOverview() : page === "plans" ? renderPlans() : page === "cards" ? renderCards() : page === "pos" ? renderPos() : renderRouters()}
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
