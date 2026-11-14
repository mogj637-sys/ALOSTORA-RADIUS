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
3. انسخ `.env.example` إلى `.env` وعدّل كلمات المرور والمفتاح السري محلياً.
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

## أوامر مفيدة
- عرض الخدمات: `docker compose ps`
- عرض السجلات: `docker compose logs -f api`
- عرض سجلات الواجهة: `docker compose logs -f web`
- إيقاف الخدمات مع الاحتفاظ بالبيانات: `docker compose down`
- إيقاف الخدمات وحذف بيانات قاعدة التطوير نهائياً: `docker compose down -v`
- تشغيل الاختبارات محلياً من مجلد backend بعد تثبيت `requirements-dev.txt`: `pytest -q`

## تنبيهات
- لا ترفع ملف `.env` إلى GitHub.
- كلمة المرور الافتراضية في Compose مخصصة للتطوير المحلي فقط؛ غيّرها قبل الاستخدام.
- لا توصل راوتر إنتاج أو RADIUS حقيقي قبل إضافة المصادقة وإدارة الأسرار وقواعد الشبكة والاختبارات.
- مخطط قاعدة البيانات الأولي يطبق تلقائياً عبر Alembic عند بدء API.
- FreeRADIUS لم يُضف إلى Compose بعد؛ سيضاف بعد تصميم مخطط المصادقة والمحاسبة واختباره.
- لم يتم التحقق من تشغيل الحاويات على جهازك بعد؛ هذا الدليل يصف الملفات المضافة للمستودع.
