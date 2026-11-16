# تشغيل تجربة ALOSTORA-RADIUS على Windows

هذا الدليل يشغّل نسخة تطوير محلية على نفس الكمبيوتر. لا يحتاج إلى Linux مستقل، لكنه يحتاج Docker Desktop مع Linux containers وWSL2 عندما يكون ذلك مطلوباً من إصدار Windows لديك.

## قبل البدء

1. ثبّت Git for Windows وDocker Desktop.
2. شغّل Docker Desktop وانتظر حتى تصبح حالة المحرك **Engine running**.
3. افتح PowerShell.
4. نزّل فرع التجربة:

~~~powershell
git clone --branch feature/user-manager-sync https://github.com/mogj637-sys/ALOSTORA-RADIUS.git
~~~

5. ادخل مجلد المشروع:

~~~powershell
cd ALOSTORA-RADIUS
~~~

## تشغيل تلقائي

نفّذ في PowerShell:

~~~powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\start-windows.ps1
~~~

يقوم البرنامج المساعد بما يلي:
- يتأكد من أن Docker يعمل.
- ينشئ ملف .env محلياً بمفاتيح عشوائية إذا لم يكن موجوداً، ولا يستبدل ملفاً موجوداً.
- يبني خدمات PostgreSQL وAPI وواجهة الويب وFreeRADIUS.
- ينتظر فحص جاهزية API وقاعدة البيانات.
- لا يفتح منافذ لوحة التحكم وAPI إلا على localhost وفق إعداد Docker Compose الحالي.

## إنشاء حساب المدير

بعد نجاح التشغيل، نفّذ:

~~~powershell
docker compose exec api python -m app.scripts.create_admin --username admin --display-name "مدير النظام"
~~~

اختر كلمة مرور قوية من 12 حرفاً على الأقل عند طلبها. لا توجد كلمة مرور افتراضية.

## فتح البرنامج

- لوحة الإدارة: http://localhost:5173
- فحص API: http://localhost:8000/health
- توثيق API: http://localhost:8000/docs

## الإيقاف

لإيقاف الخدمات مع الاحتفاظ ببيانات التجربة:

~~~powershell
docker compose down
~~~

لحذف قاعدة بيانات التجربة وكل بياناتها نهائياً:

~~~powershell
docker compose down -v
~~~

## حدود هذه التجربة

- هذه نسخة تطوير/اختبار وليست إصدار إنتاج أو ملف تثبيت نهائي.
- ابدأ ببيانات تجريبية فقط.
- لا تدخل أسرار الراوتر الحقيقي أو بيانات كروتك الحقيقية.
- لا تربط راوتر إنتاج ولا تغيّر إعدادات RADIUS عليه.
- اختبار FreeRADIUS داخل Docker لا يثبت بعد التوافق مع MikroTik فعلي.
- قارئ User Manager v6 الجماعي غير معتمد حتى الآن؛ لا تعتبر هذه النسخة جاهزة لاستيراد الكروت القديمة.
- لا تشارك ملف .env؛ يحتوي مفاتيح وأسراراً محلية.

إذا تعذر تشغيل Docker Desktop على نسخة Windows لديك، أرسل نص رسالة الخطأ فقط بعد حذف أي أسرار أو كلمات مرور منها.
