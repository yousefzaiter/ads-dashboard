# Syncing Data to Production Server

هذا الدليل يشرح كيفية نقل البيانات المحلية (المشاريع والـ .env) إلى السيرفر.

## البيانات المطلوبة نسخها

### 1. clients.json (تكوين المشاريع)
يحتوي على:
- تعريف المشاريع الثلاثة
- تكوين الحسابات على كل منصة
- معرفات العملاء

**الملفات الحالية:**
```json
3 مشاريع:
├── Grass (قراس)
│   ├── Google Ads: 2221677009
│   ├── Meta: act_579554746963968
│   ├── Snap: 3b43a935-f7d1-49f9-b6f6-a088433e2a09
│   └── TikTok: 7238520801270448130
├── لمسة حرير
│   ├── Google Ads: 5975503292
│   ├── Meta: act_6142338646041704
│   ├── Snap: 8b16188a-6b0f-4a0e-a610-1da0b09fee7d
│   └── TikTok: (empty)
└── كوناي
    ├── Google Ads: 1010563403
    ├── Meta: (empty)
    ├── Snap: eaaf9e64-b163-4393-b6d6-f2b631a11560
    └── TikTok: (empty)
```

### 2. .env (بيانات الاعتماد)
يحتوي على:
- Snap tokens (OAuth)
- Meta tokens
- Google Ads tokens
- TikTok tokens (pending)

**الحالة الحالية:**
- ✅ Snap: Fresh access token
- ✅ Meta: 59 days valid
- ✅ Google: Active
- ⚠️ TikTok: Pending

---

## خيارات النسخ

### الخيار 1: استخدام Scripts المتاحة (الأسهل)

#### نسخ المشاريع فقط:
```bash
./sync_clients.sh <server-hostname> <username>
# مثال:
./sync_clients.sh ads.example.com ubuntu
```

#### نسخ بيانات الاعتماد فقط:
```bash
./sync_env.sh <server-hostname> <username>
# مثال:
./sync_env.sh ads.example.com ubuntu
```

#### نسخ الاثنين معاً:
```bash
# نسخ clients.json
./sync_clients.sh ads.example.com ubuntu

# ثم نسخ .env
./sync_env.sh ads.example.com ubuntu

# أو استخدم script مرة واحدة:
./sync_all.sh ads.example.com ubuntu
```

### الخيار 2: النسخ اليدوي عبر SCP

```bash
# نسخ clients.json
scp clients.json user@server:/opt/ads-dashboard/

# نسخ .env
scp .env user@server:/opt/ads-dashboard/

# تحقق من التثبيت
ssh user@server "ls -la /opt/ads-dashboard/clients.json /opt/ads-dashboard/.env"
```

### الخيار 3: SSH مباشر

```bash
# الاتصال بالسيرفر
ssh user@server

# الدخول للمجلد
cd /opt/ads-dashboard

# نسخ المحتوى من المجلد المحلي
# (سيحتاج لـ copy-paste أو استخدام scp)
```

---

## خطوات Deployment الكاملة

```bash
# 1️⃣ من الجهاز المحلي

# تأكد من وجود البيانات
ls -la clients.json .env

# نسخ الملفات إلى السيرفر
./sync_clients.sh your-server.com your-username
./sync_env.sh your-server.com your-username

# 2️⃣ على السيرفر

# تحقق من الملفات
ssh your-username@your-server.com
cd /opt/ads-dashboard
ls -la clients.json .env

# تحقق من صحة الـ JSON
python3 -c "import json; json.load(open('clients.json')); print('✅ clients.json valid')"
python3 -c "import os; print('✅ .env exists' if os.path.exists('.env') else '❌ .env missing')"

# 3️⃣ أعد تشغيل التطبيق

# قتل العملية السابقة
pkill -f "streamlit run dashboard.py"
sleep 2

# مسح الـ cache
rm -rf ~/.streamlit/cache*

# بدء جديد
nohup streamlit run dashboard.py --logger.level=info &

# تحقق من التشغيل
ps aux | grep streamlit
```

---

## التحقق من الـ Sync

### تحقق من clients.json:
```bash
ssh user@server "python3 -c \"import json; data = json.load(open('/opt/ads-dashboard/clients.json')); print('Projects:', [p['name'] for p in data['projects']])\""
```

**النتيجة المتوقعة:**
```
Projects: ['Grass', 'لمسة حرير', 'كوناي']
```

### تحقق من .env:
```bash
ssh user@server "grep '^SNAP_ACCESS_TOKEN\|^META_ACCESS_TOKEN' /opt/ads-dashboard/.env | cut -c1-50"
```

**النتيجة المتوقعة:**
```
SNAP_ACCESS_TOKEN=hCgwKCjE3NzcyNTE2MTk...
META_ACCESS_TOKEN=EAAeVfs3ARaYBRb7Men...
```

---

## الملفات المطلوبة محليًا

✅ موجودة:
- `clients.json` - تكوين المشاريع
- `.env` - بيانات الاعتماد
- `sync_clients.sh` - script لنسخ المشاريع
- `sync_env.sh` - script لنسخ بيانات الاعتماد

---

## ملاحظات أمان مهمة

⚠️ **لا تقم بـ commit الملفات التالية إلى git:**
- `.env` - يحتوي على tokens سرية
- `clients.json` - قد يحتوي على معلومات حساسة

✅ **استخدم الـ scripts بدلاً من ذلك:**
- `sync_env.sh` - نسخ آمن عبر SCP
- `sync_clients.sh` - نسخ آمن عبر SCP

---

## الحالة الحالية

### المشاريع المُعدّة:
- ✅ Grass (قراس)
- ✅ لمسة حرير
- ✅ كوناي

### المنصات المُفعّلة:
- ✅ Google Ads (3 مشاريع)
- ✅ Meta (2 مشروع)
- ✅ Snap (3 مشاريع)
- ⚠️ TikTok (1 مشروع فقط)

### Tokens:
- ✅ Snap: Fresh (just refreshed)
- ✅ Meta: 59 days valid
- ✅ Google: Active
- ⚠️ TikTok: Pending

---

## استكشاف الأخطاء

### إذا لم تظهر المشاريع على الداشبورد:
```bash
# تحقق من ملف clients.json
ssh user@server "python3 -m json.tool /opt/ads-dashboard/clients.json | head -20"

# تحقق من صرح Streamlit
ssh user@server "tail -50 /var/log/ads-dashboard/streamlit.log | grep -i 'clients\|project'"
```

### إذا أظهرت الداشبورد أخطاء في الـ Token:
```bash
# تحقق من بيانات الاعتماد
ssh user@server "grep 'SNAP_ACCESS_TOKEN\|META_ACCESS_TOKEN' /opt/ads-dashboard/.env"

# أعد تشغيل Streamlit
ssh user@server "pkill -f streamlit; sleep 2; cd /opt/ads-dashboard && nohup streamlit run dashboard.py &"
```

