# نواة المصادقة والمحاسبة الداخلية لـ RADIUS

## واجهات داخلية

هذه الواجهات مخصصة لاتصال FreeRADIUS بخدمة API داخل شبكة Docker، وليست واجهات عامة للعملاء. يجب إرسال الترويسة `X-Radius-Internal-Key` مع كل طلب. المفتاح:

- يُضبط في `RADIUS_INTERNAL_API_KEY`.
- يجب أن يكون عشوائياً بطول 32 محرفاً على الأقل.
- يُشارك فقط بين خدمة FreeRADIUS وخدمة API.
- لا يُستخدم مكان RADIUS shared secret الخاص بكل راوتر.

### المصادقة

`POST /internal/radius/authorize`

الطلب يحتوي `nas_identifier` و`username`، ويدعم طريقتي PAP عبر `password` وCHAP عبر `chap_password_hex` و`chap_challenge_hex`. يمكن أن يحتوي أيضاً عنوان IP وMAC للعميل. دعم CHAP مهم لأن HotSpot في MikroTik يستخدم CHAP افتراضياً.

عند القبول تعيد الخدمة خصائص مثل:

- `Port-Limit = 1`: اتصال واحد.
- `Acct-Interim-Interval = 60`: تحديث محاسبة كل 60 ثانية.
- `Session-Timeout`: المتبقي من وقت الاستخدام أو الصلاحية، أيهما أقرب.
- `Mikrotik-Total-Limit`: المتبقي من مجموع التحميل والرفع.
- `Mikrotik-Rate-Limit`: ملف السرعة المسجل في الباقة عند وجوده.

يبدأ عداد الصلاحية عند أول مصادقة ناجحة. وتُنشأ فترة حجز مؤقتة قصيرة لمنع قبول طلب دخول ثانٍ قبل وصول Accounting-Start.

### المحاسبة

`POST /internal/radius/accounting`

يدعم `Start` و`Interim-Update` و`Stop`. يتضمن الطلب NAS identifier واسم المستخدم ومعرّف الجلسة والوقت التراكمي وعدادات الرفع والتنزيل. يدعم `input_gigawords` و`output_gigawords` لتجاوز حد 32-bit.

- تُحفظ جلسات كل راوتر بمعرّف جلسة مستقل.
- تُحسب فروقات العدادات التراكمية، ولا تُجمع الحزمة المكررة مرتين.
- `input_octets` يسجل كرفع و`output_octets` كتنزيل.
- وقت الاستخدام يضاف من `session_time_seconds` أثناء الاتصال، وليس من وقت إنشاء الكرت.
- إذا انتهى الوقت أو الحجم، تعيد الخدمة `disconnect_required=true` كي ينفذ محول RADIUS الفصل.
- يمكن استقبال Interim/Stop لجلسة قائمة حتى بعد تعطيل الراوتر من السجل، بينما يُمنع بدء جلسة جديدة منه.

## حدود التنفيذ الحالية

أُضيفت خدمة FreeRADIUS إلى Docker Compose مع إعداد `rlm_rest`، وتُحمّل قائمة NAS النشطة عند بدء الحاوية من `/internal/radius/clients`. يلزم إعادة تشغيل الحاوية بعد إضافة راوتر أو تغيير عنوانه/مفتاحه حتى يعاد توليد clients.conf. أُضيف فحص بناء للإعداد، لكن لا يزال اختبار حزم RADIUS من راوتر MikroTik حقيقي وCoA/Disconnect فعلياً مطلوباً قبل اعتبار التكامل جاهزاً للإنتاج.

## اختبار محلي

يجب إعداد `RADIUS_INTERNAL_API_KEY` في `.env` قبل تشغيل API. استخدم قيمة عشوائية لا تقل عن 32 محرفاً. لا تضع المفتاح أو كلمات مرور الكروت في سجلات أو مستودع Git.


## عناوين الراوتر

- `management_host` هو عنوان إدارة RouterOS API.
- `radius_client_address` هو عنوان المصدر أو CIDR الذي تظهر منه حزم RADIUS القادمة من الراوتر، ويُستخدم لتوليد تعريف NAS في FreeRADIUS. لا تفترض أنه يساوي عنوان الإدارة.
- `nas_identifier` يجب أن يطابق قيمة NAS-Identifier التي يرسلها الراوتر. توثيق MikroTik يذكر أن NAS-Identifier الافتراضي هو اسم هوية الراوتر (/system/identity).

بعد تسجيل راوتر جديد أو تغيير بياناته، أعد تحميل قائمة العملاء بإعادة تشغيل خدمة RADIUS:

`docker compose restart freeradius`

## HotSpot وطرق الدخول

يدعم محول المصادقة PAP وCHAP. في CHAP يرسل FreeRADIUS قيم CHAP-Password وCHAP-Challenge بصيغة hex إلى API ليتم التحقق منها مقابل كلمة مرور الكرت المشفرة. لا يحتاج المستخدم إلى تغيير HotSpot من CHAP الافتراضي. لا يدعم هذا الإصدار MS-CHAP.
