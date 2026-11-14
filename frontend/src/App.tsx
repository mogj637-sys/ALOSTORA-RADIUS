import { FormEvent, useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";

type CurrentUser = {
  id: number;
  username: string;
  display_name: string;
  roles: string[];
};

const modules = [
  { title: "الكروت", detail: "إنشاء وإدارة كروت الإنترنت", icon: "▤" },
  { title: "الباقات والسرعات", detail: "إعداد حدود الوقت والحجم والسرعة", icon: "◷" },
  { title: "أجهزة MikroTik", detail: "إدارة الراوترات والاتصال", icon: "⌁" },
  { title: "نقاط البيع", detail: "المخزون والطباعة والعمولات", icon: "▣" },
  { title: "جلسات RADIUS", detail: "المصادقة والاستهلاك والجلسات", icon: "◉" },
  { title: "التقارير", detail: "المبيعات والاستخدام والأرشفة", icon: "▥" },
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
          <div>
            <strong>الأسطورة RADIUS</strong>
            <span>إدارة الشبكة والكروت</span>
          </div>
        </div>
        <span className="eyebrow">مرحباً بعودتك</span>
        <h1>تسجيل دخول المشرف</h1>
        <p className="login-description">أدخل بيانات حساب الإدارة للوصول إلى لوحة التحكم.</p>
        <form onSubmit={submit} className="login-form">
          <label htmlFor="username">اسم المستخدم</label>
          <input
            id="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
          <label htmlFor="password">كلمة المرور</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          {error && <div className="login-error" role="alert">{error}</div>}
          <button type="submit" disabled={busy}>
            {busy ? "جارٍ التحقق..." : "دخول إلى النظام"}
          </button>
        </form>
        <div className="login-foot">نظام إدارة شبكة الأسطورة نت</div>
      </section>
    </main>
  );
}

function Dashboard({ user, onLogout }: { user: CurrentUser; onLogout: () => void }) {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">أ</div>
        <div className="brand-copy">
          <strong>الأسطورة RADIUS</strong>
          <span>إدارة الشبكة والكروت</span>
        </div>
        <div className="side-label">القائمة الرئيسية</div>
        <nav>
          <a className="nav-item active" href="#overview">نظرة عامة</a>
          <a className="nav-item" href="#modules">وحدات النظام</a>
        </nav>
        <div className="sidebar-foot">ALOSTORA-RADIUS · 0.3.0</div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">مركز إدارة الشبكة</span>
            <h1>لوحة التحكم</h1>
          </div>
          <div className="topbar-actions">
            <div className="environment"><span className="status-dot" /> بيئة التطوير</div>
            <div className="user-chip">{user.display_name}</div>
            <button className="logout-button" onClick={onLogout}>تسجيل الخروج</button>
          </div>
        </header>

        <section className="welcome-card" id="overview">
          <div>
            <span className="welcome-kicker">مرحباً بك، {user.display_name}</span>
            <h2>نظام الأسطورة لإدارة RADIUS</h2>
            <p>منصة موحدة لإدارة الكروت والباقات والراوترات ونقاط البيع.</p>
          </div>
          <div className="welcome-symbol">A</div>
        </section>

        <div className="section-heading" id="modules">
          <div>
            <h2>وحدات النظام</h2>
            <p>سيتم تفعيل الوحدات تدريجياً بعد بناء خدماتها واختبارها.</p>
          </div>
          <span className="phase-tag">مرحلة التأسيس</span>
        </div>

        <div className="module-grid">
          {modules.map((item) => (
            <article className="module-card" key={item.title}>
              <div className="module-icon">{item.icon}</div>
              <h3>{item.title}</h3>
              <p>{item.detail}</p>
              <span className="module-state">قيد التطوير</span>
            </article>
          ))}
        </div>

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
      throw new Error("تعذر الاتصال بالخادم. تحقق من تشغيل الخدمات.");
    }
    const data = await response.json();
    setToken(data.access_token as string);
  }

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    let active = true;
    setChecking(true);
    fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("انتهت جلسة الدخول");
        return response.json();
      })
      .then((data: CurrentUser) => {
        if (active) setUser(data);
      })
      .catch(() => {
        if (active) {
          setToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  if (!token) return <LoginScreen onLogin={login} />;
  if (checking || !user) {
    return <main className="loading-screen">جارٍ تحميل لوحة التحكم...</main>;
  }
  return <Dashboard user={user} onLogout={() => { setToken(null); setUser(null); }} />;
}

export default App;
