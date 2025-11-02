import imaplib
import email
from email.header import decode_header
import time
import os
import json
from datetime import datetime
from pathlib import Path
from notification_manager import MailNotificationManager

class MailReceiver:
    """Mail alıcı sınıfı - IMAP protokolü ile mail sunucusuna bağlanır"""
    
    def __init__(self, imap_server, email_address, password, check_interval=60, 
                 trigger_keywords=None, save_folder="saved_emails", 
                 platform="telegram", telegram_token=None, telegram_chat_id=None, 
                 whatsapp_phone=None, throttle_seconds=300):
        """
        Args:
            imap_server (str): IMAP sunucu adresi (örn: imap.gmail.com)
            email_address (str): Email adresi
            password (str): Email şifresi veya uygulama şifresi
            check_interval (int): Mail kontrol aralığı (saniye)
            trigger_keywords (list): Tetiklenecek anahtar kelimeler (örn: ["yapı kredi", "banka"])
            save_folder (str): Tetiklenen maillerin kaydedileceği klasör
            platform (str): Bildirim platformu ("telegram" veya "whatsapp")
            telegram_token (str): Telegram bot token
            telegram_chat_id (str): Telegram chat ID
            whatsapp_phone (str): WhatsApp bildirim telefon numarası (örn: "+905378284599")
            throttle_seconds (int): Bildirimler arası minimum bekleme süresi
        """
        self.imap_server = imap_server
        self.email_address = email_address
        self.password = password
        self.check_interval = check_interval
        self.mail = None
        self.processed_email_ids = set()  # İşlenmiş mail ID'lerini tut
        self.trigger_keywords = [kw.lower() for kw in trigger_keywords] if trigger_keywords else []
        self.save_folder = save_folder
        
        # Klasörü oluştur
        if self.trigger_keywords:
            Path(self.save_folder).mkdir(parents=True, exist_ok=True)
        
        # Bildirim yöneticisi (Telegram veya WhatsApp)
        self.notification_manager = None
        if platform == "telegram" and telegram_token and telegram_chat_id:
            self.notification_manager = MailNotificationManager(
                platform="telegram",
                telegram_token=telegram_token,
                telegram_chat_id=telegram_chat_id,
                throttle_seconds=throttle_seconds,
                enabled=True
            )
        elif platform == "whatsapp" and whatsapp_phone:
            self.notification_manager = MailNotificationManager(
                platform="whatsapp",
                phone_number=whatsapp_phone,
                throttle_seconds=throttle_seconds,
                enabled=True
            )
    
    def connect(self):
        """Mail sunucusuna bağlan"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_address, self.password)
            print(f"✓ {self.email_address} adresine başarıyla bağlanıldı")
            return True
        except Exception as e:
            print(f"✗ Bağlantı hatası: {e}")
            return False
    
    def disconnect(self):
        """Mail sunucusundan ayrıl"""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
                print("✓ Bağlantı kapatıldı")
            except:
                pass
    
    def decode_email_subject(self, subject):
        """Email başlığını decode et"""
        if subject is None:
            return ""
        
        decoded_parts = decode_header(subject)
        subject_text = ""
        
        for content, encoding in decoded_parts:
            if isinstance(content, bytes):
                try:
                    subject_text += content.decode(encoding or 'utf-8')
                except:
                    subject_text += content.decode('utf-8', errors='ignore')
            else:
                subject_text += str(content)
        
        return subject_text
    
    def get_email_body(self, msg):
        """Email içeriğini al"""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode()
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode()
            except:
                pass
        
        return body
    
    def check_trigger(self, subject, body, from_address):
        """Mailde trigger kelimeleri kontrol et"""
        if not self.trigger_keywords:
            return False
        
        # Kontrol edilecek tüm metni birleştir ve küçük harfe çevir
        full_text = f"{subject} {body} {from_address}".lower()
        
        # Herhangi bir trigger kelime geçiyor mu?
        for keyword in self.trigger_keywords:
            if keyword in full_text:
                return True
        
        return False
    
    def save_email_to_file(self, email_data, msg):
        """Maili dosyaya kaydet"""
        try:
            # Dosya adı için güvenli tarih formatı
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            email_id_str = email_data['id'].decode() if isinstance(email_data['id'], bytes) else str(email_data['id'])
            
            # JSON formatında kaydet
            json_filename = f"{timestamp}_email_{email_id_str}.json"
            json_path = os.path.join(self.save_folder, json_filename)
            
            # Ek dosya bilgilerini topla
            attachments = []
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_disposition() == "attachment":
                        filename = part.get_filename()
                        if filename:
                            # Ek dosyayı kaydet
                            attachment_path = os.path.join(self.save_folder, f"{timestamp}_{filename}")
                            try:
                                with open(attachment_path, "wb") as f:
                                    f.write(part.get_payload(decode=True))
                                attachments.append({
                                    "filename": filename,
                                    "saved_as": attachment_path
                                })
                            except:
                                attachments.append({
                                    "filename": filename,
                                    "error": "Kaydedilemedi"
                                })
            
            # JSON verisi
            email_json = {
                "id": email_id_str,
                "subject": email_data["subject"],
                "from": email_data["from"],
                "date": email_data["date"],
                "body": email_data["body"],
                "attachments": attachments,
                "saved_at": datetime.now().isoformat()
            }
            
            # JSON dosyasını kaydet
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(email_json, f, ensure_ascii=False, indent=2)
            
            # .eml formatında da kaydet (orijinal mail)
            eml_filename = f"{timestamp}_email_{email_id_str}.eml"
            eml_path = os.path.join(self.save_folder, eml_filename)
            with open(eml_path, "wb") as f:
                f.write(msg.as_bytes())
            
            return json_path, eml_path
            
        except Exception as e:
            print(f"✗ Mail kaydetme hatası: {e}")
            return None, None
    
    def process_email(self, email_id, msg):
        """Gelen maili işle"""
        # Email bilgilerini al
        subject = self.decode_email_subject(msg["Subject"])
        from_address = msg.get("From")
        date = msg.get("Date")
        body = self.get_email_body(msg)
        
        # Trigger kontrolü
        is_triggered = self.check_trigger(subject, body, from_address)
        
        print("\n" + "="*50)
        if is_triggered:
            print(f"🚨 TETİKLENDİ! YENİ MAİL GELDİ!")
        else:
            print(f"📧 YENİ MAİL GELDİ!")
        print("="*50)
        print(f"Tarih: {date}")
        print(f"Gönderen: {from_address}")
        print(f"Konu: {subject}")
        print(f"İçerik:\n{body[:200]}...")  # İlk 200 karakter
        print("="*50 + "\n")
        
        # Ekleri kontrol et
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    filename = part.get_filename()
                    if filename:
                        print(f"📎 Ek dosya: {filename}")
        
        email_data = {
            "id": email_id,
            "subject": subject,
            "from": from_address,
            "date": date,
            "body": body
        }
        
        # Eğer tetiklendiyse maili kaydet
        if is_triggered:
            print(f"💾 Mail kaydediliyor...")
            json_path, eml_path = self.save_email_to_file(email_data, msg)
            if json_path:
                print(f"✅ Mail kaydedildi:")
                print(f"   📄 JSON: {json_path}")
                print(f"   📧 EML: {eml_path}")
            
            # WhatsApp bildirimi gönder
            if self.notification_manager:
                # Ek dosya yollarını topla
                attachment_paths = []
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            filename = part.get_filename()
                            if filename:
                                attachment_path = os.path.join(self.save_folder, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
                                if os.path.exists(attachment_path):
                                    attachment_paths.append(attachment_path)
                
                # Bildirim kaynağı belirle
                source = "Anahtar Kelime Takip"
                if self.trigger_keywords:
                    source = f"Anahtar Kelime Takip ({', '.join(self.trigger_keywords[:2])})"
                
                self.notification_manager.send_notification(
                    mail_data=email_data,
                    source=source,
                    attachment_paths=attachment_paths if attachment_paths else None
                )
            
            print("="*50 + "\n")
        
        return email_data
    
    def check_new_emails(self, skip_existing=False):
        """Yeni mailleri kontrol et"""
        try:
            # INBOX'ı seç
            self.mail.select("INBOX")
            
            # Okunmamış mailleri ara
            status, messages = self.mail.search(None, 'UNSEEN')
            
            if status != "OK":
                print("Mail arama hatası")
                return []
            
            email_ids = messages[0].split()
            
            if skip_existing:
                # İlk çalıştırmada mevcut tüm okunmamış mailleri işlenmiş olarak işaretle
                for email_id in email_ids:
                    self.processed_email_ids.add(email_id)
                print(f"ℹ️  {len(email_ids)} mevcut okunmamış mail atlandı. Sadece yeni gelenler gösterilecek.")
                return []
            
            # Sadece daha önce işlenmemiş mailleri al
            new_email_ids = [eid for eid in email_ids if eid not in self.processed_email_ids]
            
            if not new_email_ids:
                return []
            
            print(f"🔔 {len(new_email_ids)} yeni mail bulundu!")
            
            new_emails = []
            
            for email_id in new_email_ids:
                # Mail içeriğini al
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                
                # Email mesajını parse et
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        email_data = self.process_email(email_id, msg)
                        new_emails.append(email_data)
                        
                        # Bu mail ID'sini işlenmiş olarak işaretle
                        self.processed_email_ids.add(email_id)
            
            return new_emails
            
        except Exception as e:
            print(f"✗ Mail kontrol hatası: {e}")
            return []
    
    def start_listening(self):
        """Mail dinlemeyi başlat - sürekli yeni mailleri kontrol et"""
        print(f"📬 Mail dinleme başlatıldı...")
        print(f"⏰ Kontrol aralığı: {self.check_interval} saniye")
        print(f"🔄 Ctrl+C ile durdurun\n")
        
        if not self.connect():
            return
        
        try:
            # İlk çalıştırmada mevcut okunmamış mailleri atla
            print("🔍 Mevcut okunmamış mailler kontrol ediliyor...")
            self.check_new_emails(skip_existing=True)
            print("✅ Hazır! Şimdi sadece yeni gelen mailler gösterilecek.\n")
            
            while True:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] Mail kontrol ediliyor...")
                
                new_emails = self.check_new_emails()
                
                if not new_emails:
                    print("📭 Yeni mail yok")
                
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹ Mail dinleme durduruldu")
        finally:
            self.disconnect()


def main():
    """Ana fonksiyon - Yapı Kredi takibi ile örnek"""
    
    # =====================================
    # BURAYA KENDİ BİLGİLERİNİZİ GİRİN
    # =====================================
    
    # Gmail için örnek ayarlar:
    IMAP_SERVER = "imap.gmail.com"  # Gmail için
    # Outlook için: "outlook.office365.com"
    # Yahoo için: "imap.mail.yahoo.com"
    
    EMAIL_ADDRESS = "krmbkc42@gmail.com"  # Kendi email adresiniz
    PASSWORD = "einz nuea scrs aozj"  # Gmail için uygulama şifresi gerekir
    
    CHECK_INTERVAL = 10  # 10 saniyede bir kontrol et
    
    # Tetiklenecek anahtar kelimeler
    TRIGGER_KEYWORDS = ["yapı kredi", "yapıkredi"]
    
    # Maillerin kaydedileceği klasör
    SAVE_FOLDER = "yapi_kredi_mails"
    
    # WhatsApp bildirimi (None ise bildirim gönderilmez)
    WHATSAPP_PHONE = "+905378284599"  # Kendi numaranız
    # WHATSAPP_PHONE = None  # Bildirimi kapatmak için
    
    # =====================================
    
    print("=" * 60)
    print("📧 MAİL DİNLEYİCİ - YAPI KREDİ MAİL YAKALAYICI")
    print("=" * 60)
    print(f"📂 Kaydedilecek klasör: {SAVE_FOLDER}")
    print(f"🔑 Tetikleyici kelimeler: {', '.join(TRIGGER_KEYWORDS)}")
    if WHATSAPP_PHONE:
        print(f"📱 WhatsApp bildirimi: {WHATSAPP_PHONE}")
    print("=" * 60 + "\n")
    
    # Mail alıcıyı oluştur
    receiver = MailReceiver(
        imap_server=IMAP_SERVER,
        email_address=EMAIL_ADDRESS,
        password=PASSWORD,
        check_interval=CHECK_INTERVAL,
        trigger_keywords=TRIGGER_KEYWORDS,
        save_folder=SAVE_FOLDER,
        whatsapp_phone=WHATSAPP_PHONE
    )
    
    # Dinlemeyi başlat
    receiver.start_listening()


if __name__ == "__main__":
    main()

