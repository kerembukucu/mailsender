# 🚀 Birleşik Mail Takip Sistemi

Tüm mail takip sistemlerini tek bir yerden yöneten merkezi sistem.

## 📋 İçindekiler

- [Kurulum](#kurulum)
- [Hızlı Başlangıç](#hızlı-başlangıç)
- [Config Dosyası](#config-dosyası)
- [Kullanım Senaryoları](#kullanım-senaryoları)

---

## 🔧 Kurulum

```bash
cd /Users/xevin/Desktop/projeler/mailsender
pip install -r requirements.txt
```

---

## ⚡ Hızlı Başlangıç

### 1. Config Dosyasını Düzenleyin

Örnek config dosyasını kopyalayın ve kendi bilgilerinizle doldurun:

```bash
cp mail_tracking_config.example.json mail_tracking_config.json
```

Ardından `mail_tracking_config.json` dosyasını açın ve email bilgilerinizi girin:

```json
{
  "email_settings": {
    "imap_server": "imap.gmail.com",
    "email_address": "sizin_email@gmail.com",
    "password": "gmail_uygulama_sifreniz",
    "check_interval": 30
  },
  "whatsapp_settings": {
    "phone_number": "+90XXXXXXXXXX",
    "enabled": true
  }
}
```

### 2. Anahtar Kelime Ekleyin

Config'te `keyword_tracking` bölümüne anahtar kelimeler ekleyin:

```json
"keyword_tracking": {
  "enabled": true,
  "keywords": ["yapı kredi", "banka", "ödeme"]
}
```

### 3. Sistemi Çalıştırın

```bash
python run.py
```

🎉 Sistem şimdi çalışıyor! Tüm tetiklenen mailler WhatsApp'a gönderilecek.

---

## 📄 Config Dosyası Yapısı

### Email Ayarları
```json
"email_settings": {
  "imap_server": "imap.gmail.com",
  "email_address": "email@gmail.com",
  "password": "uygulama_sifresi",
  "check_interval": 30  // Her 30 saniyede kontrol
}
```

### WhatsApp Ayarları
```json
"whatsapp_settings": {
  "phone_number": "+905378284599",
  "enabled": true,  // false yaparsanız bildirim gitmez
  "throttle_seconds": 300  // 5 dakikada max 1 bildirim
}
```

### Anahtar Kelime Takibi
```json
"keyword_tracking": {
  "enabled": true,
  "keywords": ["yapı kredi", "banka"],
  "save_folder": "tracked_keyword_mails"
}
```

### Gönderici Takibi
```json
"sender_tracking": {
  "enabled": true,
  "tracked_senders": {
    "ali@example.com": {
      "name": "Ali Veli <ali@example.com>",
      "added_at": "2025-11-01T20:00:00"
    }
  }
}
```

### Yanıt Takibi
```json
"reply_tracking": {
  "enabled": true,
  "tracked_message_ids": {
    "<message-id@gmail.com>": {
      "subject": "İş Teklifi",
      "to": "firma@example.com",
      "date": "2025-11-01T15:30:00"
    }
  }
}
```

---

## 🎯 Kullanım Senaryoları

### Senaryo 1: Sadece Anahtar Kelime Takibi

**1. Config dosyasını düzenleyin:**
```json
{
  "keyword_tracking": {
    "enabled": true,
    "keywords": ["yapı kredi", "fatura", "ödeme"]
  },
  "sender_tracking": {"enabled": false},
  "reply_tracking": {"enabled": false}
}
```

**2. Çalıştırın:**
```bash
python run.py
```

✅ Sadece anahtar kelimeleri içeren mailler izlenecek.

---

### Senaryo 2: Belirli Göndericileri Takip Et

**Yöntem 1: Helper Script Kullan**

```bash
python add_sender.py
```

Ekranda çıkan talimatlara göre gönderici ekleyin.

**Yöntem 2: Manuel Config Düzenleme**

```json
"sender_tracking": {
  "enabled": true,
  "tracked_senders": {
    "ali@example.com": {
      "name": "Ali Veli",
      "added_at": "2025-11-01T20:00:00"
    },
    "ayse@example.com": {
      "name": "Ayşe Yılmaz",
      "added_at": "2025-11-01T20:05:00"
    }
  }
}
```

**3. Çalıştırın:**
```bash
python run.py
```

✅ Ali ve Ayşe'den gelen her mail WhatsApp'a bildirim olarak gelecek.

---

### Senaryo 3: Gönderilen Maillerin Yanıtlarını Takip Et

**Yöntem 1: Helper Script Kullan**

```bash
python add_reply_tracking.py
```

**Yöntem 2: İnteraktif Mod (Önerilen)**

```bash
python track_replies.py
```

Bu mod:
- Son gönderdiğiniz 20 maili gösterir
- Hangi mail(ler)e yanıt beklendiğini seçmenizi sağlar
- Otomatik olarak takip listesine ekler

**3. Çalıştırın:**
```bash
python run.py
```

✅ Seçtiğiniz mail(ler)e gelen yanıtlar WhatsApp'a bildirim olarak gelecek.

---

### Senaryo 4: HEPSİ BİRDEN! 🔥

```json
{
  "keyword_tracking": {"enabled": true, "keywords": ["yapı kredi"]},
  "sender_tracking": {"enabled": true, "tracked_senders": {...}},
  "reply_tracking": {"enabled": true, "tracked_message_ids": {...}}
}
```

```bash
python run.py
```

✅ Tüm sistemler aynı anda çalışır, hepsi WhatsApp bildirimi gönderir!

---

## 🛠️ Helper Script'ler

### Gönderici Ekle
```bash
python add_sender.py
```

### Yanıt Takibi Ekle
```bash
python add_reply_tracking.py
```

---

## 📱 WhatsApp Bildirimi Formatı

```
🔔 YENİ MAİL ALINDI

📌 Kaynak: Yapı Kredi Takip
👤 Gönderen: yapikredi@example.com
📩 Konu: Ödeme Hatırlatması
📅 Tarih: 2025-11-01 20:30:00

📄 Özet:
Sayın müşterimiz, ödemenizin son tarihi yaklaşıyor...

📎 Ekler: fatura.pdf
```

---

## ⚙️ Gelişmiş Ayarlar

### Spam Önleme

WhatsApp'a çok fazla bildirim gitmemesi için:

```json
"whatsapp_settings": {
  "throttle_seconds": 300  // 5 dakikada max 1 bildirim
}
```

### Kontrol Aralığı

Mail kontrolü sıklığını ayarlayın:

```json
"email_settings": {
  "check_interval": 30  // 30 saniye (önerilen: 15-60 arası)
}
```

---

## 🐛 Sorun Giderme

### WhatsApp Bildirimi Gitmiyor

1. `pywhatkit` kurulu mu?
   ```bash
   pip install pywhatkit
   ```

2. Config'te `enabled: true` mu?
   ```json
   "whatsapp_settings": {"enabled": true}
   ```

3. Telefon numarası doğru formatta mı?
   ```json
   "phone_number": "+905378284599"  // + ile başlamalı
   ```

### Config Yüklenemiyor

```bash
# Config dosyasını kontrol edin
cat mail_tracking_config.json

# JSON formatı doğru mu test edin
python -m json.tool mail_tracking_config.json
```

### Mailler Yakalanmıyor

1. Email ayarları doğru mu?
2. Gmail uygulama şifresi mi kullanılıyor? (normal şifre değil)
3. Anahtar kelimeler/göndericiler doğru yazılmış mı?

---

## 📚 Ek Kaynaklar

- Tek tek sistem kullanımı için orijinal README'lere bakın
- `receieveit.py` - Anahtar kelime takibi
- `track_replies.py` - Yanıt takibi
- `track_senders.py` - Gönderici takibi

---

## 🎉 Örnek Tam Konfigürasyon

```json
{
  "email_settings": {
    "imap_server": "imap.gmail.com",
    "email_address": "your_email@gmail.com",
    "password": "your_app_password_here",
    "check_interval": 30
  },
  "whatsapp_settings": {
    "phone_number": "+90XXXXXXXXXX",
    "enabled": true,
    "throttle_seconds": 300
  },
  "keyword_tracking": {
    "enabled": true,
    "keywords": ["yapı kredi", "yapıkredi", "banka", "ödeme"],
    "save_folder": "tracked_keyword_mails"
  },
  "sender_tracking": {
    "enabled": true,
    "tracked_senders": {
      "ali@example.com": {
        "name": "Ali Veli <ali@example.com>",
        "added_at": "2025-11-01T20:00:00"
      }
    },
    "save_folder": "tracked_sender_mails"
  },
  "reply_tracking": {
    "enabled": false,
    "tracked_message_ids": {},
    "save_folder": "tracked_replies"
  }
}
```

Bu config ile `python run.py` çalıştırdığınızda:
- ✅ Yapı Kredi, banka, ödeme içeren mailler yakalanır
- ✅ Ali Veli'den gelen mailler yakalanır
- ✅ Hepsi WhatsApp'a bildirim olarak gelir
- ✅ 5 dakikada en fazla 1 bildirim (spam önleme)

---

**Hazırsınız! 🚀 İyi kullanımlar!**

