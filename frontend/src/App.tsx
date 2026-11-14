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
  { title: "أجهزة MikroTik", detail: "إدارة الراوترات والاتصال", icon: "⌁", page: "overview" as const },
  { title: "نقاط البيع", detail: "المخزون والطباعة والعمولات", icon: "▣", page: "overview" as const },
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
  const [page, setPage] = useState<"overview" | "plans" | "cards">("overview");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [generatedCards, setGeneratedCards] = useState<GeneratedCard[]>([]);
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
    const result = await apiRequest<Plan[]>(token, "/api/v1/plans");
    setPlans(result);
    if (!batchDraft.planId && result.length) {
      setBatchDraft((current) => ({ ...current, planId: String(result[0].id) }));
    }
  }

  async function loadCards() {
    const result = await apiRequest<Card[]>(token, "/api/v1/cards?offset=0&limit=50");
    setCards(result);
  }

  useEffect(() => {
    if (page === "plans" || page === "cards") {
      setError("");
      Promise.all([loadPlans(), page === "cards" ? loadCards() : Promise.resolve()])
        .catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل البيانات"));
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
      await apiRequest<Plan>(token, "/api/v1/plans", {
        method: "POST",
        body: JSON.stringify({
          code: planDraft.code,
          name: planDraft.name,
          price: Number(planDraft.price),
          data_limit_bytes: numberOrNull(planDraft.dataGb, 1024 ** 3),
          session_time_limit_seconds: numberOrNull(planDraft.timeHours, 3600),
          validity_period_seconds: numberOrNull(planDraft.validityDays, 86400),
          speed_profile: planDraft.speedProfile || null,
        }),
      });
      setPlanDraft({ code: "", name: "", price: "", dataGb: "", timeHours: "", validityDays: "", speedProfile: "" });
      await loadPlans();
      setNotice("تم إنشاء الباقة بنجاح.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر إنشاء الباقة");
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
        <div className="section-heading"><div><h2>إدارة الباقات</h2><p>حدد السعر وحدود الاستخدام والصلاحية والسرعة.</p></div></div>
        <form className="panel form-grid" onSubmit={createPlan}>
          <label>رمز الباقة<input value={planDraft.code} onChange={(e) => setPlanDraft({ ...planDraft, code: e.target.value })} required /></label>
          <label>اسم الباقة<input value={planDraft.name} onChange={(e) => setPlanDraft({ ...planDraft, name: e.target.value })} required /></label>
          <label>السعر<input type="number" min="0" step="0.01" value={planDraft.price} onChange={(e) => setPlanDraft({ ...planDraft, price: e.target.value })} required /></label>
          <label>الحجم بالجيجابايت <span className="field-hint">اتركه فارغاً ليكون مفتوحاً</span><input type="number" min="0.001" step="0.001" value={planDraft.dataGb} onChange={(e) => setPlanDraft({ ...planDraft, dataGb: e.target.value })} /></label>
          <label>وقت الاستخدام بالساعات <span className="field-hint">اتركه فارغاً ليكون مفتوحاً</span><input type="number" min="0.01" step="0.01" value={planDraft.timeHours} onChange={(e) => setPlanDraft({ ...planDraft, timeHours: e.target.value })} /></label>
          <label>الصلاحية بالأيام <span className="field-hint">تبدأ من أول دخول</span><input type="number" min="0.01" step="0.01" value={planDraft.validityDays} onChange={(e) => setPlanDraft({ ...planDraft, validityDays: e.target.value })} /></label>
          <label>اسم السرعة<input value={planDraft.speedProfile} onChange={(e) => setPlanDraft({ ...planDraft, speedProfile: e.target.value })} placeholder="مثال: 2M (اختياري)" /></label>
          <div className="form-actions"><button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ..." : "حفظ الباقة"}</button></div>
        </form>
        <div className="section-heading compact-heading"><div><h2>الباقات المسجلة</h2></div><span className="count-tag">{plans.length} باقة</span></div>
        <div className="table-wrap"><table><thead><tr><th>الرمز</th><th>اسم الباقة</th><th>السعر</th><th>الحجم</th><th>الوقت</th><th>الصلاحية</th><th>الحالة</th></tr></thead>
          <tbody>{plans.map((plan) => <tr key={plan.id}><td>{plan.code}</td><td>{plan.name}</td><td>{Number(plan.price).toLocaleString("en-US")}</td><td>{plan.data_limit_bytes === null ? "مفتوح" : `${(plan.data_limit_bytes / 1024 ** 3).toFixed(2)} GB`}</td><td>{plan.session_time_limit_seconds === null ? "مفتوح" : `${(plan.session_time_limit_seconds / 3600).toFixed(2)} ساعة`}</td><td>{plan.validity_period_seconds === null ? "مفتوح" : `${(plan.validity_period_seconds / 86400).toFixed(2)} يوم`}</td><td>{plan.is_active ? "مفعلة" : "متوقفة"}</td></tr>)}</tbody>
        </table>{plans.length === 0 && <div className="empty-state">لا توجد باقات بعد. أنشئ أول باقة من النموذج أعلاه.</div>}</div>
      </>
    );
  }

  function renderCards() {
    return (
      <>
        <div className="section-heading"><div><h2>إنشاء دفعة كروت</h2><p>أنشئ كروتاً بأسماء مولدة وكلمات مرور وفق نوع الدخول.</p></div></div>
        {plans.length === 0 ? <div className="empty-state">يجب إنشاء باقة أولاً من قسم الباقات.</div> : (
          <form className="panel form-grid" onSubmit={createBatch}>
            <label>الباقة<select value={batchDraft.planId} onChange={(e) => setBatchDraft({ ...batchDraft, planId: e.target.value })}>{plans.map((plan) => <option value={plan.id} key={plan.id}>{plan.name} — {plan.code}</option>)}</select></label>
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
        <div className="section-heading compact-heading"><div><h2>آخر الكروت المنشأة</h2></div><span className="count-tag">آخر 50</span></div>
        <div className="table-wrap"><table><thead><tr><th>الرقم التسلسلي</th><th>اسم المستخدم</th><th>نوع الدخول</th><th>الباقة</th><th>الحالة</th><th>مجاني</th></tr></thead><tbody>{cards.map((card) => <tr key={card.id}><td>{card.serial_number}</td><td>{card.username}</td><td>{card.card_type}</td><td>{plans.find((p) => p.id === card.plan_id)?.name ?? card.plan_id}</td><td>{card.status}</td><td>{card.is_free ? "نعم" : "لا"}</td></tr>)}</tbody></table>{cards.length === 0 && <div className="empty-state">لا توجد كروت منشأة بعد.</div>}</div>
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
        </nav>
        <div className="sidebar-foot">ALOSTORA-RADIUS · 0.4.0</div>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div><span className="eyebrow">مركز إدارة الشبكة</span><h1>{page === "overview" ? "لوحة التحكم" : page === "plans" ? "إدارة الباقات" : "إدارة الكروت"}</h1></div>
          <div className="topbar-actions"><div className="environment"><span className="status-dot" /> بيئة التطوير</div><div className="user-chip">{user.display_name}</div><button className="logout-button" onClick={onLogout}>تسجيل الخروج</button></div>
        </header>
        {error && <div className="notice error-notice" role="alert">{error}</div>}
        {notice && <div className="notice success-notice" role="status">{notice}</div>}
        {page === "overview" ? renderOverview() : page === "plans" ? renderPlans() : renderCards()}
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
