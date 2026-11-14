const modules = [
  { title: "الكروت", detail: "إنشاء وإدارة كروت الإنترنت", icon: "▤" },
  { title: "الباقات والسرعات", detail: "إعداد حدود الوقت والحجم والسرعة", icon: "◷" },
  { title: "أجهزة MikroTik", detail: "إدارة الراوترات والاتصال", icon: "⌁" },
  { title: "نقاط البيع", detail: "المخزون والطباعة والعمولات", icon: "▣" },
  { title: "جلسات RADIUS", detail: "المصادقة والاستهلاك والجلسات", icon: "◉" },
  { title: "التقارير", detail: "المبيعات والاستخدام والأرشفة", icon: "▥" },
];

function App() {
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
        <div className="sidebar-foot">ALOSTORA-RADIUS · 0.1.0</div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">مركز إدارة الشبكة</span>
            <h1>لوحة التحكم</h1>
          </div>
          <div className="environment"><span className="status-dot" /> بيئة التطوير</div>
        </header>

        <section className="welcome-card" id="overview">
          <div>
            <span className="welcome-kicker">مرحباً بك في</span>
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

export default App;