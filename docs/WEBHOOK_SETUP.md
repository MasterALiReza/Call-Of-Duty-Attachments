# راهنمای Webhook در OX_LOADOUT Attachments Bot

## 📋 پیش‌نیازها

برای استفاده از حالت Webhook، موارد زیر را آماده کنید:

| نیازمندی | توضیحات |
|----------|---------| 
| **دامنه (Domain)** | یک دامنه معتبر مثل `bot.example.com` |
| **گواهی SSL** | HTTPS الزامی است (Let's Encrypt رایگان) |
| **پورت باز** | یکی از پورت‌های `443`, `80`, `88`, `8443` |
| **IP ثابت** | سرور با IP ثابت (VPS/Cloud) |

---

## 🔧 تنظیمات `.env`

متغیرهای زیر را در فایل `.env` تنظیم کنید:

```env
# ----------------------------------------------------------------------------
# Webhook Configuration (Optional - Default is Polling)
# ----------------------------------------------------------------------------

# Bot running mode: "polling" or "webhook"
BOT_MODE=polling

# Webhook settings (only needed if BOT_MODE=webhook)
# WEBHOOK_URL=https://your-domain.com
# WEBHOOK_PORT=8443
# WEBHOOK_PATH=/webhook

# SSL Certificate paths (for self-signed certificates only)
# Leave empty if using reverse proxy with SSL (recommended)
# WEBHOOK_CERT_PATH=
# WEBHOOK_KEY_PATH=

# Secret token for webhook security (auto-generated if empty)
# WEBHOOK_SECRET_TOKEN=
```

### توضیح متغیرها:

| متغیر | مقدار پیش‌فرض | توضیحات |
|-------|--------------|---------| 
| `BOT_MODE` | `polling` | حالت اجرا: `polling` یا `webhook` |
| `WEBHOOK_URL` | - | آدرس کامل سرور **بدون مسیر** (مثال: `https://bot.example.com`) |
| `WEBHOOK_PORT` | `8443` | پورت داخلی بات |
| `WEBHOOK_PATH` | `/webhook` | مسیر endpoint |
| `WEBHOOK_SECRET_TOKEN` | auto | توکن امنیتی (توصیه: خالی بگذارید تا خودکار تولید شود) |
| `WEBHOOK_CERT_PATH` | - | مسیر certificate (فقط برای self-signed) |
| `WEBHOOK_KEY_PATH` | - | مسیر private key (فقط برای self-signed) |

> [!IMPORTANT]
> `WEBHOOK_URL` باید فقط دامنه باشد **بدون** مسیر `/webhook`  
> ❌ اشتباه: `https://bot.example.com/webhook`  
> ✅ درست: `https://bot.example.com`

---

## 🚀 روش‌های راه‌اندازی

### روش ۱: با Reverse Proxy (توصیه شده)

این روش ایمن‌ترین و ساده‌ترین روش است. Nginx مسئول SSL است و بات داخلی HTTP ساده ارائه می‌دهد.

#### Nginx Configuration:

```nginx
server {
    listen 443 ssl;
    server_name bot.example.com;
    
    ssl_certificate /etc/letsencrypt/live/bot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.example.com/privkey.pem;
    
    location /webhook {
        proxy_pass http://127.0.0.1:8443/webhook;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### تنظیمات `.env`:
```env
BOT_MODE=webhook
WEBHOOK_URL=https://bot.example.com
WEBHOOK_PORT=8443
WEBHOOK_PATH=/webhook
# SSL paths خالی بمانند چون Nginx هندل می‌کند
```

---

### روش ۲: SSL مستقیم (Self-Signed)

برای سرورهایی که Reverse Proxy ندارند:

```bash
# ساخت گواهی self-signed
openssl req -newkey rsa:2048 -sha256 -nodes \
    -keyout webhook_key.pem \
    -x509 -days 3650 \
    -out webhook_cert.pem \
    -subj "/CN=YOUR_SERVER_IP"
```

#### تنظیمات `.env`:
```env
BOT_MODE=webhook
WEBHOOK_URL=https://YOUR_SERVER_IP:8443
WEBHOOK_PORT=8443
WEBHOOK_PATH=/webhook
WEBHOOK_CERT_PATH=./webhook_cert.pem
WEBHOOK_KEY_PATH=./webhook_key.pem
```

---

## 🔄 سوئیچ سریع بین حالت‌ها

### Linux/macOS:
```bash
# فعال‌سازی Webhook
sed -i 's/BOT_MODE=polling/BOT_MODE=webhook/' .env

# برگشت به Polling
sed -i 's/BOT_MODE=webhook/BOT_MODE=polling/' .env
```

### PowerShell (Windows):
```powershell
# فعال‌سازی Webhook
(Get-Content .env) -replace 'BOT_MODE=polling', 'BOT_MODE=webhook' | Set-Content .env

# برگشت به Polling
(Get-Content .env) -replace 'BOT_MODE=webhook', 'BOT_MODE=polling' | Set-Content .env
```

---

## ✅ تست و عیب‌یابی

### بررسی وضعیت Webhook:

```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

### پاسخ موفق:
```json
{
  "ok": true,
  "result": {
    "url": "https://bot.example.com/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40
  }
}
```

### حذف Webhook (برگشت به Polling):

```bash
curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"
```

یا کافی است در `.env` مقدار `BOT_MODE=polling` تنظیم شود - بات خودکار webhook را آزاد می‌کند.

---

## 🔒 نکات امنیتی

> [!IMPORTANT]
> - **توکن بات را هرگز در URL قرار ندهید** - از `WEBHOOK_SECRET_TOKEN` استفاده کنید
> - **HTTPS الزامی است** - تلگرام HTTP را قبول نمی‌کند
> - **پورت‌های مجاز**: فقط `443`, `80`, `88`, `8443`
> - **یک بات = یک حالت** - نمی‌توان همزمان Polling و Webhook داشت

---

## ⚡ Fallback خودکار

اگر Webhook به هر دلیلی fail شود (مثلاً `WEBHOOK_URL` تنظیم نشده)، بات به صورت خودکار به Polling برمی‌گردد. این رفتار در لاگ‌ها قابل مشاهده است:

```
❌ WEBHOOK_URL is required for webhook mode!
⬅️  Falling back to polling mode...
🔄 Starting bot in POLLING mode...
```

---

## 📊 مقایسه عملکرد

| معیار | Polling | Webhook |
|-------|---------|---------| 
| تأخیر پاسخ | 0.5-2 ثانیه | <100ms |
| مصرف CPU | بالاتر | کمتر |
| مصرف پهنای باند | بیشتر | کمتر |
| پیچیدگی | ساده | نیاز به SSL |
| مناسب برای | توسعه/تست | پروداکشن |

---

**آخرین بروزرسانی**: مارس ۲۰۲۶
