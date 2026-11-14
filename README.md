# ALOSTORA-RADIUS
## نظام إدارة شبكة الأسطورة نت باستخدام RADIUS

مشروع مستقل لإدارة كروت الإنترنت والباقات وجلسات RADIUS وأجهزة MikroTik ونقاط البيع والعمولات والطباعة والتقارير والأرشفة.

> هذه المنظومة ليست واجهة لـ MikroTik User Manager. تعتمد على FreeRADIUS وPostgreSQL وخدمات خلفية مستقلة.

## النطاق المستهدف
- حتى 40,000 كرت محفوظ.
- هدف أولي يصل إلى 400–500 اتصال متزامن، ويجب إثباته باختبارات تحميل قبل الإنتاج.
- دعم MikroTik RouterOS v6 وv7.
- لوحة إدارة عربية RTL وصفحة استعلام آمنة للعملاء.

## البنية التقنية المبدئية
- FreeRADIUS: المصادقة والمحاسبة وعمليات Disconnect/CoA عند دعمها.
- PostgreSQL: البيانات التشغيلية والتاريخية.
- Backend API: Python وFastAPI.
- ORM والترحيلات: SQLAlchemy وAlembic.
- واجهة الإدارة: React وTypeScript وVite.
- تشغيل التطوير والخدمات: Docker Compose.

هذه اختيارات تأسيسية قابلة للمراجعة أثناء التنفيذ، ولا تعني أن الأداء أو التوافق قد تم إثباتهما بعد.

## حالة التطوير الحالية
- [x] توثيق المتطلبات والمعمارية وقرارات دورة حياة الكرت.
- [x] بيئة تطوير Docker Compose وPostgreSQL مع ترحيلات Alembic.
- [x] Backend FastAPI وربط قاعدة البيانات ونقاط فحص الصحة.
- [x] تسجيل دخول المشرفين برمز JWT والأدوار الأساسية.
- [x] إدارة الباقات: إنشاء وتعديل وتفعيل وإيقاف.
- [x] إنشاء الكروت منفردة أو دفعات، ودعم أنماط بيانات الدخول الثلاثة.
- [x] البحث في الكروت وإيقافها وإعادة تفعيلها وإلغاء الكروت غير المخصصة.
- [x] تشفير بيانات اعتماد الكروت وعدم إرجاع كلمات المرور في قوائم الكروت.
- [x] إدارة نقاط البيع وملخص الكروت والقيمة التجارية المطبوعة.
- [x] عمليات الطباعة مع منع التكرار وإعادة الطباعة دون احتساب مالي إضافي.
- [x] استثناء الكروت المجانية من تخصيص المخزون والقيمة التجارية.
- [x] معاينة القسائم في المتصفح وسجل عمليات الطباعة مع إخفاء كلمات المرور من سجل العمليات.
- [x] سجل الراوترات ودعم حفظ أسرار MikroTik/RADIUS مشفرة بمفتاح منفصل.
- [x] نواة API داخلية لمصادقة RADIUS عبر PAP/CHAP ومحاسبة Start/Interim/Stop مع منع تكرار الحزم واحتساب الرفع والتنزيل ووقت الاتصال.
- [x] خصائص RADIUS لحد الوقت والحجم والاتصال الواحد، مع حجز مصادقة مؤقت ومنع الجلسات المتزامنة.
- [x] FreeRADIUS Docker service مع rlm_rest وقائمة NAS ديناميكية وفحص إعدادات الحاوية في CI.
- [x] اختبارات تكامل PostgreSQL لمصادقة RADIUS والمحاسبة والحدود الأساسية.
- [x] اختبارات تكامل PostgreSQL وبناء الواجهة عبر GitHub Actions.
- [ ] إدارة التحصيلات النقدية والديون والعمولات والتسويات.
- [ ] اختبار Access-Accept/Reject وAccounting من راوتر MikroTik فعلياً بعد إعداد NAS-Identifier وعنوان مصدر RADIUS.
- [ ] ربط MikroTik RouterOS v6/v7 فعلياً واختبار الاتصال والإدارة.
- [x] إضافة Disconnect-Request اختياري عند تجاوز الحدود أو إيقاف الكرت، ويظل معطلاً افتراضياً حتى تفعيل استقبال RADIUS على الراوتر.
- [ ] اختبار Disconnect-ACK/NAK على RouterOS v6/v7 فعلياً.
- [ ] إدارة الصلاحيات التفصيلية من الواجهة.
- [ ] صفحة استعلام العميل والتقارير.
- [ ] الأرشفة والنسخ الاحتياطي والاستعادة.
- [ ] اختبارات الحمل والأمان والتوافق على أجهزة راوتر فعلية.

## قواعد العمل
- تبدأ صلاحية الكرت عند أول استخدام ناجح، ثم تنقضي المدة بصورة متواصلة حتى لو لم يكن العميل متصلاً.
- يُخصم رصيد وقت الاستخدام أثناء الاتصال الفعلي فقط.
- الاستهلاك الحجمي هو مجموع التحميل والرفع.
- يسمح باتصال نشط واحد للكرت.
- الطباعة الموجهة لنقطة بيع تسجل تخصيص الكروت/تحميلها على تلك النقطة مرة واحدة؛ إعادة طباعة نسخة لا تكرر الحركة.
- لا تُرسل قيمة صفر للحد المفتوح؛ تُستخدم قيمة NULL/غياب الحد.
- الكروت المجانية لا تدخل في المبيعات أو العمولات التجارية.
- كل عملية مالية أو مخزنية يجب أن تكون قابلة للتتبع.
- لا يُعلن عن نجاح ميزة RADIUS أو السرعة أو الفصل إلا بعد اختبارها فعلياً.

## تشغيل بيئة التطوير
راجع [دليل التطوير](docs/DEVELOPMENT.md) و[دليل المصادقة](docs/AUTHENTICATION.md).

باختصار:
1. انسخ المستودع.
2. انسخ `.env.example` إلى `.env` وعدّل القيم المحلية.
3. نفّذ `docker compose up --build -d`.
4. افتح الواجهة: http://localhost:5173
5. فحص API: http://localhost:8000/health

## الأنظمة المستهدفة
التصميم يستهدف Linux وWindows 10 وWindows 11. خدمات التطبيق وقاعدة البيانات تُشغّل بالحاويات. FreeRADIUS خدمة Linux-first وستعمل داخل حاوية Linux/WSL2 على Windows. يجب التحقق من متطلبات Docker/WSL2 الفعلية على إصدار Windows 10 المستخدم قبل اعتماد دعمه.

لا تضع كلمات مرور أو RADIUS secrets أو بيانات راوترات حقيقية في المستودع.


## FreeRADIUS container

Docker Compose now includes a FreeRADIUS 3 service listening on UDP 1812 (authentication) and UDP 1813 (accounting). It loads active RADIUS clients from the protected API when the container starts.

Before starting the stack, add a private internal key to `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the result as `RADIUS_INTERNAL_API_KEY`. Keep it identical for the API and FreeRADIUS containers. After registering a router in the dashboard, enter its RADIUS client IP/CIDR, NAS Identifier and shared secret, then reload the client list:

```bash
docker compose restart freeradius
```

The first integration uses the REST-backed authorization/accounting endpoints. CoA/Disconnect and automatic client-list refresh are not implemented yet, and the service still needs end-to-end validation against a real MikroTik router.
