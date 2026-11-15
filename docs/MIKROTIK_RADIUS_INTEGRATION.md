# ربط MikroTik مع ALOSTORA-RADIUS (تجربة فعلية أولى)

هذا الدليل لتجربة **HotSpot RADIUS** على راوتر RouterOS v6 أو v7 باستخدام راوتر اختبار أولاً. لا تطبّق الإعدادات على راوتر إنتاج قبل أخذ نسخة احتياطية وتحديد نافذة اختبار.

## ما الذي يعمل حالياً؟

- FreeRADIUS 3.2.10 يستقبل UDP 1812 للمصادقة وUDP 1813 للمحاسبة.
- FreeRADIUS يحمّل NAS clients من API عند بدء الحاوية.
- اختبار CI يرسل Access-Request بصيغة CHAP وكلمة مرور خاطئة، ثم Accounting Start وInterim-Update وStop، ويتحقق من وصول النتائج إلى PostgreSQL.
- لم يتم بعد إثبات الاتصال من جهاز MikroTik فعلي.
- CoA/Disconnect غير مفعّل افتراضياً، ولا تفعّل استقبال رسائله في أول تجربة.
- اختبار السرعة الفعلية وتغيير السرعة والفصل الفوري من لوحة النظام مرحلة منفصلة لاحقة.

## 1. جهّز مسار الشبكة

استخدم عناوين ثابتة أو VPN بين الراوتر والخادم. مثال توضيحي فقط:

| العنصر | مثال |
|---|---|
| عنوان خادم ALOSTORA الذي يصل إليه الراوتر | `192.168.10.20` |
| عنوان المصدر الذي يخرج منه الراوتر إلى RADIUS | `192.168.10.1` |
| NAS-Identifier / هوية الراوتر | `ALOSTORA-NAS-01` |
| منفذ المصادقة | UDP 1812 |
| منفذ المحاسبة | UDP 1813 |

استبدل العناوين والأسماء بقيم شبكتك. إذا كان هناك NAT بين الراوتر والخادم، سجّل في النظام عنوان المصدر الذي يراه الخادم بعد NAT، لا عنواناً داخلياً غير ظاهر له.

### إذا كان الخادم على Windows 11

- استخدم عنوان LAN ثابتاً لجهاز Windows، وليس `localhost` أو `127.0.0.1`.
- يجب أن تكون حاوية FreeRADIUS قادرة على استقبال UDP 1812 و1813 من الراوتر.
- اسمح في Windows Firewall بهذين المنفذين **من عنوان الراوتر المحدد فقط**. مثال PowerShell كمسؤول، بعد استبدال العنوان:

```powershell
New-NetFirewallRule -DisplayName "ALOSTORA RADIUS Auth" -Direction Inbound -Protocol UDP -LocalPort 1812 -RemoteAddress 192.168.10.1 -Action Allow
New-NetFirewallRule -DisplayName "ALOSTORA RADIUS Accounting" -Direction Inbound -Protocol UDP -LocalPort 1813 -RemoteAddress 192.168.10.1 -Action Allow
```

لا تفتح UDP 1812/1813 على الإنترنت العام. في Linux طبّق القاعدة نفسها باستخدام جدار الحماية الموجود لديك.

## 2. أضف الراوتر في لوحة ALOSTORA

من إدارة الراوترات أضف سجلاً جديداً بهذه القيم:

- **الاسم:** اسم واضح للراوتر.
- **NAS Identifier:** نفس قيمة هوية RouterOS التي ستضبطها في الخطوة التالية، حرفياً.
- **Management Host:** عنوان الإدارة الذي تستخدمه للوصول إلى الراوتر.
- **RADIUS Client Address:** عنوان IP المصدر الذي سيستخدمه الراوتر لإرسال RADIUS، ويفضّل عنواناً واحداً بصيغة `192.168.10.1/32`.
- **RouterOS Version:** إصدار v6 أو v7 الفعلي.
- **RADIUS Shared Secret:** سر عشوائي قوي، 16 حرفاً أو أكثر، ويكون نفسه في النظام والراوتر. لا تستخدم سرّاً منشوراً أو كلمة مرور لوحة الإدارة.

لا تضع السر في مستودع Git أو ترسله في محادثة عامة. خزّنه في مدير كلمات مرور.

بعد حفظ الراوتر، أعد تشغيل FreeRADIUS كي يعيد تحميل قائمة NAS من API:

```bash
docker compose restart freeradius
docker compose logs --tail=80 freeradius
```

تحقق أن الخدمة بدأت دون أخطاء في قراءة ملف العملاء أو فحص الإعداد.

## 3. اضبط هوية RADIUS على MikroTik

افتح Terminal في WinBox أو SSH، وخذ نسخة احتياطية أولاً:

```routeros
/export file=before-alostora-radius
/system backup save name=before-alostora-radius
```

عيّن هوية الراوتر لتطابق NAS Identifier المسجل في لوحة النظام:

```routeros
/system identity set name="ALOSTORA-NAS-01"
```

أضف خادم RADIUS. نفّذ الأمر مرة واحدة فقط؛ افحص `/radius print` أولاً لتجنب تكرار السجل:

```routeros
/radius add service=hotspot address=192.168.10.20 src-address=192.168.10.1 authentication-port=1812 accounting-port=1813 secret="REPLACE_WITH_THE_SAME_SHARED_SECRET" timeout=1s
```

- `address`: عنوان خادم ALOSTORA الذي يمكن للراوتر الوصول إليه.
- `src-address`: عنوان الراوتر الذي سجلته في حقل RADIUS Client Address.
- `secret`: نفس السر المحفوظ في لوحة النظام.
- إذا كان الراوتر لا يملك هذا العنوان أو يستخدم مساراً مختلفاً، لا تنسخ المثال كما هو؛ اختر عنوان المصدر الصحيح أولاً.

اعرض السجل:

```routeros
/radius print detail
```

## 4. فعّل RADIUS على ملف HotSpot الصحيح

اعرف اسم ملف HotSpot Profile المستخدم:

```routeros
/ip hotspot print detail
/ip hotspot profile print detail
```

ابحث عن قيمة `profile` في خادم HotSpot، ثم عدّل ذلك الملف فقط. المثال التالي يفترض أن اسمه `hsprof1`:

```routeros
/ip hotspot profile set [find where name="hsprof1"] use-radius=yes radius-accounting=yes radius-interim-update=1m
```

لا تستخدم `[find]` دون تحديد الملف إذا كان الراوتر يحتوي على أكثر من HotSpot أو أكثر من Profile.

يُرسل الراوتر تحديث محاسبة دورياً كل دقيقة في هذا المثال. يمكن تعديل الفترة لاحقاً بعد قياس الحمل وجودة الاتصال.

## 5. أنشئ كرت اختبار

1. من لوحة ALOSTORA أنشئ باقة اختبار صغيرة.
2. أنشئ كرتاً واحداً ببيانات دخول معروفة.
3. تأكد أن اسم المستخدم غير موجود كحساب محلي في `/ip hotspot user`، لأن RouterOS قد يستخدم قاعدة المستخدمين المحلية قبل RADIUS.
4. سجّل اسم المستخدم وكلمة المرور محلياً لاختبار الدخول فقط.
5. افتح صفحة HotSpot من جهاز عميل متصل بالراوتر، وسجّل الدخول بالكرت.

ملف HotSpot الافتراضي يستخدم عادة `http-chap`، والنظام يدعم مسار CHAP الذي اختبرناه في FreeRADIUS. لا تغيّر طريقة تسجيل الدخول أو إعدادات الصفحة في أول تجربة إلا عند وجود سبب واضح.

## 6. راقب نتيجة الاتصال

على MikroTik:

```routeros
/radius print
/radius monitor 0
/ip hotspot active print detail
/log print
```

استخدم رقم سجل RADIUS الصحيح الظاهر في `/radius print` بدلاً من `0` إذا كان مختلفاً.

على جهاز الخادم:

```bash
docker compose logs -f freeradius
docker compose logs -f api
```

النتيجة المطلوبة:

- كلمة مرور صحيحة: قبول المصادقة.
- كلمة مرور خاطئة: رفض المصادقة.
- بعد الدخول: ظهور Accounting Start.
- أثناء الاتصال: ظهور Interim-Update وتزايد عدادات الرفع والتنزيل.
- بعد الخروج: ظهور Accounting Stop وإغلاق الجلسة.

إذا لم يعمل الاتصال، افحص بالترتيب: عنوان المصدر، NAS-Identifier، السر المشترك، مسار الشبكة، جدار الحماية، ثم سجلات FreeRADIUS وAPI. ارتفاع `timeouts` يعني غالباً عدم وصول الرد؛ وارتفاع `bad-replies` قد يشير إلى عدم تطابق السر أو مشكلة في الرد.

## 7. التراجع الآمن

لإيقاف استخدام RADIUS في ملف HotSpot وإرجاع المصادقة المحلية مؤقتاً:

```routeros
/ip hotspot profile set [find where name="hsprof1"] use-radius=no
```

احذف سجل RADIUS الذي أضفته فقط بعد تحديد رقمه من `/radius print`:

```routeros
/radius remove <RADIUS_ENTRY_NUMBER>
```

لا تحذف سجلات RADIUS الأخرى الموجودة مسبقاً.

## حدود هذه المرحلة

- هذا الدليل يجهّز اختبار HotSpot RADIUS فقط؛ لا يعني أن جميع خدمات RouterOS (مثل PPPoE) تم ربطها.
- لا تفعّل `/radius incoming set accept=yes` الآن. استقبال Disconnect/CoA غير داخل اختبار HotSpot الأول، ويحتاج إعداداً واختباراً منفصلين.
- لا نعلن نجاح الاختبار الفعلي حتى نرى طلباً من الراوتر الحقيقي وسجلات قبول ومحاسبة متطابقة في النظام.
- لا تعتمد النظام على شبكة إنتاج قبل اختبار حدود الوقت والحجم، الجلسات المتزامنة، انقطاع الشبكة، إعادة تشغيل الراوتر، واستعادة قاعدة البيانات.

## مراجع MikroTik الرسمية

- [RADIUS - RouterOS](https://manual.mikrotik.com/docs/authentication-authorization-accounting/radius/)
- [HotSpot - RouterOS](https://help.mikrotik.com/docs/spaces/ROS/pages/56459266/HotSpot%2B-%2BCaptive%2Bportal)
