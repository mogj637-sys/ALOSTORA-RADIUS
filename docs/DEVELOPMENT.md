# دليل تشغيل بيئة التطوير

## المتطلبات
- Git.
- Docker Desktop مع Linux containers على Windows 11.
- Docker Compose v2 (مضمن مع Docker Desktop).
- على Linux: Docker Engine وDocker Compose plugin.
- على Windows 10: يلزم إصدار مدعوم ومتوافق مع WSL2 ومتطلبات Docker Desktop؛ وإلا استخدم Linux VM أو خادماً Linux.

## تشغيل أولي على Windows 11
1. استنسخ المستودع:
   `git clone https://github.com/mogj637-sys/ALOSTORA-RADIUS.git`
2. ادخل مجلد المشروع.
3. انسخ `.env.example` إلى `.env` وعدّل كلمات المرور والمفتاح السري محلياً. أنشئ مفتاحاً عشوائياً عبر `python -c "import secrets; print(secrets.token_urlsafe(48))"` وضع الناتج في `APP_SECRET_KEY`. وأنشئ مفتاح تشفير الكروت عبر `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` وضعه في `CREDENTIAL_ENCRYPTION_KEY`. وأنشئ مفتاحاً مستقلاً آخر بالطريقة نفسها وضعه في `ROUTER_SECRET_ENCRYPTION_KEY` لحماية أسرار الراوترات. ثم أنشئ مفتاحاً داخلياً عشوائياً عبر `python -c "import secrets; print(secrets.token_urlsafe(48))"` وضعه في `RADIUS_INTERNAL_API_KEY` لربط FreeRADIUS الداخلي بواجهة API. لا تستخدم المفتاح نفسه لأكثر من غرض.
4. شغّل الخدمات:
   `docker compose up --build -d`
5. انتظر اكتمال بناء الحاويات وترحيلات قاعدة البيانات التي تعمل قبل تشغيل API.
6. افتح لوحة التحكم:
   `http://localhost:5173`
7. فحص API:
   `http://localhost:8000/health`
8. فحص جاهزية قاعدة البيانات:
   `http://localhost:8000/health/ready`
9. توثيق API:
   `http://localhost:8000/docs`
10. أنشئ حساب المدير الأول كما هو موضح في [دليل المصادقة](AUTHENTICATION.md).
11. افتح الواجهة وسجّل الدخول ببيانات المدير الذي أنشأته.

## أوامر مفيدة
- عرض الخدمات: `docker compose ps`
- عرض السجلات: `docker compose logs -f api`
- عرض سجلات الواجهة: `docker compose logs -f web`
- إيقاف الخدمات مع الاحتفاظ بالبيانات: `docker compose down`
- إيقاف الخدمات وحذف بيانات قاعدة التطوير نهائياً: `docker compose down -v`
- تشغيل الاختبارات محلياً من مجلد backend بعد تثبيت `requirements-dev.txt`: `pytest -q`

## تنبيهات
- لا ترفع ملف `.env` إلى GitHub.
- احتفظ بنسخة احتياطية آمنة من `CREDENTIAL_ENCRYPTION_KEY` و`ROUTER_SECRET_ENCRYPTION_KEY`؛ فقدانهما يمنع فك تشفير بيانات الكروت وأسرار الراوترات المخزنة.
- كلمة المرور الافتراضية في Compose مخصصة للتطوير المحلي فقط؛ غيّرها قبل الاستخدام.
- لا توصل راوتر إنتاج في أول تجربة. استخدم راوتر اختبار أو نافذة صيانة، واسمح فقط بعنوان الراوتر في جدار الحماية.
- مخطط قاعدة البيانات يطبق تلقائياً عبر Alembic عند بدء API.
- FreeRADIUS يعمل كخدمة Docker على UDP 1812 للمصادقة وUDP 1813 للمحاسبة. راجع [دليل ربط MikroTik الفعلي](MIKROTIK_RADIUS_INTEGRATION.md).
- اختبارات CI تحققت من تكامل UDP داخل بيئة Docker؛ لا يعني ذلك أن راوتر MikroTik فعلياً تم اختباره أو أن الإعداد جاهز للإنتاج.
