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
- `Mikrotik-Total-Limit` مع `Mikrotik-Total-Limit-Gigawords` عند الحاجة: المتبقي من مجموع التحميل والرفع، بما يدعم الحدود الأكبر من 4 GiB.
- `Mikrotik-Rate-Limit`: ملف السرعة المسجل في الباقة عند وجوده.

يبدأ عداد الصلاحية عند أول مصادقة ناجحة. وتُنشأ فترة حجز مؤقتة قصيرة لمنع قبول طلب دخول ثانٍ قبل وصول Accounting-Start.

### المحاسبة

`POST /internal/radius/accounting`

يدعم `Start` و`Interim-Update` و`Stop`. يتضمن الطلب NAS identifier واسم المستخدم ومعرّف الجلسة والوقت التراكمي وعدادات الرفع والتنزيل. يدعم `input_gigawords` و`output_gigawords` لتجاوز حد 32-bit.

- تُحفظ جلسات كل راوتر بمعرّف جلسة مستقل.
- تُحسب فروقات العدادات التراكمية، ولا تُجمع الحزمة المكررة مرتين.
- تُحفظ عدادات `input_octets` و`output_octets` منفصلة، ويُجمع الاثنان لحساب استهلاك الحجم. تسمية اتجاه الرفع/التنزيل تحتاج تحققاً على HotSpot فعلياً قبل اعتماد تقارير الاتجاه.
- وقت الاستخدام يضاف من `session_time_seconds` أثناء الاتصال، وليس من وقت إنشاء الكرت.
- إذا انتهى الوقت أو الحجم، تعيد الخدمة `disconnect_required=true`. هذا حالياً مؤشر داخلي؛ إرسال Disconnect/CoA آلياً لم يُنفّذ بعد. يرسل Access-Accept أيضاً حدود `Session-Timeout` و`Mikrotik-Total-Limit` ليطبق الراوتر الحدود المدعومة لديه.
- يمكن استقبال Interim/Stop لجلسة قائمة حتى بعد تعطيل الراوتر من السجل، بينما يُمنع بدء جلسة جديدة منه.

## حدود التنفيذ الحالية

أُضيفت خدمة FreeRADIUS إلى Docker Compose مع إعداد `rlm_rest`، وتُحمّل قائمة NAS المسجلة ذات العناوين المحددة عند بدء الحاوية من `/internal/radius/clients`. تبقى الراوترات المعطلة ضمن clients.conf حتى يمكنها إرسال Accounting-Stop للجلسات القائمة، لكن API ترفض مصادقتها وبدء جلسات جديدة. يلزم إعادة تشغيل الحاوية بعد إضافة راوتر أو تغيير عنوانه/مفتاحه حتى يعاد توليد clients.conf. أُضيف فحص بناء للإعداد، لكن لا يزال اختبار حزم RADIUS من راوتر MikroTik حقيقي وCoA/Disconnect فعلياً مطلوباً قبل اعتبار التكامل جاهزاً للإنتاج.

## إعداد MikroTik HotSpot بعد تشغيل FreeRADIUS

هذه أوامر نموذجية؛ استبدل العناوين والأسماء والقيم بما سجلته في لوحة النظام:

```routeros
/system identity set name="nas-aden-01"
/radius add service=hotspot address=RADIUS_SERVER_IP authentication-port=1812 accounting-port=1813 secret="SAME_RADIUS_SHARED_SECRET" src-address=ROUTER_RADIUS_SOURCE_IP
/ip hotspot profile set [find] use-radius=yes radius-accounting=yes radius-interim-update=received
```

- يجب أن يطابق اسم الهوية قيمة `nas_identifier` المسجلة.
- يجب أن يطابق `ROUTER_RADIUS_SOURCE_IP` العنوان أو الشبكة المسجلة في `radius_client_address`.
- استخدم نفس `RADIUS_SHARED_SECRET` الذي أدخلته عند تسجيل الراوتر.
- HotSpot يستخدم CHAP افتراضياً، ومحولنا يدعم CHAP وPAP؛ لا تغيّر طريقة الدخول إلى PAP لمجرد استخدام RADIUS.
- `radius-interim-update=received` مهم حتى يحترم HotSpot قيمة `Acct-Interim-Interval` المرسلة من الخادم.
- بعد التأكد من وصول خادم RADIUS إلى الراوتر، فعّل استقبال Disconnect-Message على MikroTik:
  `/radius incoming set accept=yes port=1700`
- ثم غيّر `RADIUS_COA_ENABLED=true` في `.env` وأعد تشغيل خدمة API.
- يرسل النظام Disconnect-Request عند تجاوز حدود الوقت/الحجم أو عند إيقاف كرت متصل. المنفذ الافتراضي في RouterOS هو 1700، ويُستخدم نفس RADIUS shared secret.
- إذا كان `radius_client_address` عنواناً مفرداً، يستخدمه النظام كوجهة Disconnect؛ وإذا كان CIDR يستخدم `management_host`. في حال وجود NAT أو جدار ناري، يجب السماح بوصول UDP إلى المنفذ 1700.
- إذا بقي `RADIUS_COA_ENABLED=false` فلن يرسل النظام Disconnect تلقائياً، لكنه سيبقي نتيجة المحاسبة معلّمة بأن الفصل مطلوب.

مرجع MikroTik الرسمي: https://manual.mikrotik.com/docs/authentication-authorization-accounting/radius/

## اختبار محلي

يجب إعداد `RADIUS_INTERNAL_API_KEY` في `.env` قبل تشغيل API. استخدم قيمة عشوائية لا تقل عن 32 محرفاً. لا تضع المفتاح أو كلمات مرور الكروت في سجلات أو مستودع Git.


## عناوين الراوتر

- `management_host` هو عنوان إدارة RouterOS API.
- `radius_client_address` هو عنوان المصدر أو CIDR الذي تظهر منه حزم RADIUS القادمة من الراوتر، ويُستخدم لتوليد تعريف NAS في FreeRADIUS. لا تفترض أنه يساوي عنوان الإدارة.
- `nas_identifier` يجب أن يطابق قيمة NAS-Identifier التي يرسلها الراوتر. توثيق MikroTik يذكر أن NAS-Identifier الافتراضي هو اسم هوية الراوتر (/system/identity).

بعد تسجيل راوتر جديد أو تغيير عنوانه أو المفتاح المشترك، أعد تحميل قائمة العملاء بإعادة تشغيل خدمة RADIUS:

`docker compose restart freeradius`

## HotSpot وطرق الدخول

يدعم محول المصادقة PAP وCHAP. في CHAP يرسل FreeRADIUS قيم CHAP-Password وCHAP-Challenge بصيغة hex إلى API ليتم التحقق منها مقابل كلمة مرور الكرت المشفرة. لا يحتاج المستخدم إلى تغيير HotSpot من CHAP الافتراضي. لا يدعم هذا الإصدار MS-CHAP.


## ملاحظة إعداد HotSpot

حتى يرسل الراوتر تحديثات Interim وفق الفترة التي يطلبها RADIUS، يجب ضبط `radius-interim-update=received` في HotSpot Server Profile. إذا لم يُضبط ذلك، قد لا يحترم HotSpot قيمة `Acct-Interim-Interval` القادمة من Access-Accept.
