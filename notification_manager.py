import pywhatkit as pwk
import requests
import time
import os
from datetime import datetime, timedelta
from pathlib import Path


class MailNotificationManager:
    """Telegram veya WhatsApp üzerinden mail bildirimleri gönderir"""
    
    def __init__(self, platform="telegram", phone_number=None, telegram_token=None, 
                 telegram_chat_id=None, throttle_seconds=300, enabled=True):
        """
        Args:
            platform (str): Bildirim platformu ("telegram" veya "whatsapp")
            phone_number (str): WhatsApp telefon numarası (örn: "+905378284599")
            telegram_token (str): Telegram bot token
            telegram_chat_id (str): Telegram chat ID
            throttle_seconds (int): Bildirimler arası minimum bekleme süresi (saniye)
            enabled (bool): Bildirim sistemi aktif mi?
        """
        self.platform = platform.lower()
        self.phone_number = phone_number
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.throttle_seconds = throttle_seconds
        self.enabled = enabled
        self.last_notification_time = None
        
        if self.enabled:
            if self.platform == "telegram":
                print(f"✅ Telegram bildirimleri aktif: Chat ID {telegram_chat_id}")
                print(f"⏱️  Throttle süresi: {throttle_seconds} saniye ({throttle_seconds//60} dakika)")
            elif self.platform == "whatsapp":
                print(f"✅ WhatsApp bildirimleri aktif: {phone_number}")
                print(f"⏱️  Throttle süresi: {throttle_seconds} saniye ({throttle_seconds//60} dakika)")
        else:
            print("⚠️  Bildirimler devre dışı")
    
    def should_send_notification(self):
        """Bildirim gönderilmeli mi? (Throttle kontrolü)"""
        if not self.enabled:
            return False
        
        if self.last_notification_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_notification_time).total_seconds()
        
        if elapsed < self.throttle_seconds:
            remaining = int(self.throttle_seconds - elapsed)
            print(f"⏳ Throttle aktif, bildirim atlandı (kalan: {remaining} saniye)")
            return False
        
        return True
    
    def format_mail_summary(self, mail_data, source):
        """
        Mail verisini WhatsApp mesajı formatına çevir
        
        Args:
            mail_data (dict): Mail bilgileri (subject, from, body, date)
            source (str): Bildirim kaynağı (örn: "Yapı Kredi Takip")
        
        Returns:
            str: Formatlanmış mesaj
        """
        subject = mail_data.get('subject', 'Konu yok')[:100]
        from_addr = mail_data.get('from', 'Bilinmeyen')[:100]
        body = mail_data.get('body', '')[:100]
        date = mail_data.get('date', '')
        
        # Özet mesajı oluştur
        message = f"""🔔 YENİ MAİL ALINDI

📌 Kaynak: {source}
👤 Gönderen: {from_addr}
📩 Konu: {subject}
📅 Tarih: {date}

📄 Özet:
{body}..."""
        
        # Ek dosya bilgisi ekle
        attachments = mail_data.get('attachments', [])
        if attachments:
            attachment_names = [att.get('filename', 'Unknown') for att in attachments]
            message += f"\n\n📎 Ekler: {', '.join(attachment_names[:3])}"
            if len(attachment_names) > 3:
                message += f" (+{len(attachment_names) - 3} daha)"
        
        return message
    
    def send_telegram_message(self, message, image_path=None):
        """
        Telegram üzerinden mesaj gönder
        
        Args:
            message (str): Gönderilecek mesaj
            image_path (str): Görsel dosya yolu (opsiyonel)
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            if image_path and os.path.exists(image_path):
                # Görsel ile mesaj gönder
                print(f"   📎 Görsel eki: {os.path.basename(image_path)}")
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendPhoto"
                
                with open(image_path, 'rb') as photo:
                    files = {'photo': photo}
                    data = {
                        'chat_id': self.telegram_chat_id,
                        'caption': message
                    }
                    response = requests.post(url, files=files, data=data, timeout=30)
                
                if response.status_code == 200:
                    print("   ✅ Görsel ve mesaj gönderildi!")
                    return True
                else:
                    print(f"   ⚠️ Görsel gönderilemedi (HTTP {response.status_code}), sadece metin gönderiliyor...")
                    # Görsel gönderilemezse sadece mesaj gönder
                    return self.send_telegram_message(message, image_path=None)
            else:
                # Sadece metin mesaj gönder
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                data = {
                    'chat_id': self.telegram_chat_id,
                    'text': message
                }
                response = requests.post(url, json=data, timeout=30)
                
                if response.status_code == 200:
                    print("   ✅ Mesaj gönderildi!")
                    return True
                else:
                    print(f"   ✗ Mesaj gönderilemedi (HTTP {response.status_code})")
                    print(f"   Yanıt: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"   ✗ Telegram mesajı gönderilemedi: {e}")
            return False
    
    def send_notification(self, mail_data, source, attachment_paths=None):
        """
        Telegram veya WhatsApp bildirimi gönder
        
        Args:
            mail_data (dict): Mail bilgileri
            source (str): Bildirim kaynağı
            attachment_paths (list): Gönderilecek ek dosya yolları (görseller)
        
        Returns:
            bool: Başarılı ise True
        """
        # Throttle kontrolü
        if not self.should_send_notification():
            return False
        
        try:
            # Mesajı formatla
            message = self.format_mail_summary(mail_data, source)
            
            # Platform seçimi
            if self.platform == "telegram":
                print(f"\n📱 Telegram bildirimi gönderiliyor...")
                print(f"   💬 Chat ID: {self.telegram_chat_id}")
                print(f"   📌 Kaynak: {source}")
                
                # Görsel ek var mı?
                image_to_send = None
                if attachment_paths:
                    # İlk görsel eki bul
                    for path in attachment_paths:
                        if path and os.path.exists(path):
                            # Görsel dosyası mı kontrol et
                            ext = os.path.splitext(path)[1].lower()
                            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                                image_to_send = path
                                break
                
                # Telegram mesajı gönder
                success = self.send_telegram_message(message, image_to_send)
                
                if success:
                    self.last_notification_time = datetime.now()
                    return True
                else:
                    return False
                    
            elif self.platform == "whatsapp":
                print(f"\n📱 WhatsApp bildirimi gönderiliyor...")
                print(f"   📞 Numara: {self.phone_number}")
                print(f"   📌 Kaynak: {source}")
                
                # Görsel ek var mı?
                image_to_send = None
                if attachment_paths:
                    # İlk görsel eki bul
                    for path in attachment_paths:
                        if path and os.path.exists(path):
                            # Görsel dosyası mı kontrol et
                            ext = os.path.splitext(path)[1].lower()
                            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                                image_to_send = path
                                break
                
                # WhatsApp mesajı gönder - ÇALIŞAN KOD (send_message.py'den)
                if image_to_send:
                    print(f"   📎 Görsel eki: {os.path.basename(image_to_send)}")
                    try:
                        # Görsel ile mesaj gönder
                        pwk.sendwhats_image(
                            self.phone_number,
                            image_to_send,
                            message,
                            wait_time=10,  # send_message.py'deki çalışan değer
                            tab_close=True  # send_message.py'deki çalışan değer
                        )
                        print("   ✅ Görsel ve mesaj gönderildi!")
                    except Exception as e:
                        print(f"   ⚠️ Görsel gönderilemedi ({e}), sadece metin gönderiliyor...")
                        # Görsel gönderilemezse sadece mesaj gönder
                        try:
                            pwk.sendwhatmsg_instantly(
                                self.phone_number,
                                message,
                                wait_time=10,  # send_message.py'deki çalışan değer
                                tab_close=True  # send_message.py'deki çalışan değer
                            )
                            print("   ✅ Mesaj gönderildi!")
                        except Exception as e2:
                            print(f"   ✗ Mesaj da gönderilemedi: {e2}")
                            return False
                else:
                    # Sadece metin mesaj gönder - send_message.py'deki AYNI KOD
                    try:
                        print("   ⏳ WhatsApp Web açılıyor ve mesaj gönderiliyor...")
                        pwk.sendwhatmsg_instantly(
                            self.phone_number,
                            message,
                            wait_time=10,  # send_message.py'deki çalışan değer
                            tab_close=True  # send_message.py'deki çalışan değer  
                        )
                        print("   ✅ Mesaj gönderildi!")
                    except Exception as e:
                        print(f"   ✗ Mesaj gönderilemedi: {e}")
                        return False
                
                # Son bildirim zamanını güncelle
                self.last_notification_time = datetime.now()
                return True
            
            else:
                print(f"   ✗ Bilinmeyen platform: {self.platform}")
                return False
            
        except KeyboardInterrupt:
            # Kullanıcı Ctrl+C bastıysa, bunu yukarı fırlat
            print("\n   ⚠️ Bildirim iptal edildi (Ctrl+C)")
            raise
        except Exception as e:
            print(f"   ✗ Bildirim gönderilemedi: {e}")
            print(f"   ℹ️  Program çalışmaya devam ediyor...")
            # Exception'ı yakalayıp thread'in devam etmesini sağla
            return False
    
    def test_notification(self):
        """Test bildirimi gönder"""
        test_mail = {
            "subject": "Test Mail",
            "from": "test@example.com",
            "body": f"Bu bir test mesajıdır. {self.platform.title()} bildirim sistemi çalışıyor!",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return self.send_notification(test_mail, "Test Modu")


def main():
    """Test fonksiyonu"""
    print("="*70)
    print("📬 BİLDİRİM SİSTEMİ TEST")
    print("="*70)
    
    # Test için bilgiler
    TELEGRAM_TOKEN = "8360884606:AAH1vfYva_AWC0G53Hz4ZKfSMe7RvEghgVY"
    TELEGRAM_CHAT_ID = "5837188708"
    
    # Telegram Notification manager oluştur
    print("\n🔹 TELEGRAM TEST")
    manager = MailNotificationManager(
        platform="telegram",
        telegram_token=TELEGRAM_TOKEN,
        telegram_chat_id=TELEGRAM_CHAT_ID,
        throttle_seconds=60,  # Test için 1 dakika
        enabled=True
    )
    
    # Test bildirimi gönder
    print("\nTest bildirimi gönderiliyor...\n")
    success = manager.test_notification()
    
    if success:
        print("\n🎉 Telegram test başarılı!")
    else:
        print("\n⚠️ Telegram test başarısız veya throttle aktif")


if __name__ == "__main__":
    main()

