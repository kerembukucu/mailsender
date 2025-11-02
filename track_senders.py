import imaplib
import email
from email.header import decode_header
import time
import os
import json
from datetime import datetime
from pathlib import Path
from notification_manager import MailNotificationManager

class SenderTracker:
    """Belirli göndericilerden gelen mailleri yakalar"""
    
    def __init__(self, imap_server, email_address, password, check_interval=30, 
                 platform="telegram", telegram_token=None, telegram_chat_id=None, 
                 whatsapp_phone=None, throttle_seconds=300):
        """
        Args:
            imap_server (str): IMAP sunucu adresi
            email_address (str): Email adresi
            password (str): Email şifresi
            check_interval (int): Kontrol aralığı (saniye)
            platform (str): Bildirim platformu ("telegram" veya "whatsapp")
            telegram_token (str): Telegram bot token
            telegram_chat_id (str): Telegram chat ID
            whatsapp_phone (str): WhatsApp bildirim telefon numarası
            throttle_seconds (int): Bildirimler arası minimum bekleme süresi
        """
        self.imap_server = imap_server
        self.email_address = email_address
        self.password = password
        self.check_interval = check_interval
        self.mail = None
        
        # Takip edilen göndericiler
        self.tracked_senders = {}  # {email: {"name": "...", "added_at": "..."}}
        self.processed_email_ids = set()  # İşlenmiş mail ID'leri
        
        # Kayıt klasörü
        self.save_folder = "tracked_sender_mails"
        Path(self.save_folder).mkdir(parents=True, exist_ok=True)
        
        # Takip listesini yükle
        self.load_tracked_senders()
        
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
    
    def load_tracked_senders(self):
        """Daha önce kaydedilmiş takip listesini yükle"""
        tracker_file = "tracked_senders.json"
        if os.path.exists(tracker_file):
            try:
                with open(tracker_file, "r", encoding="utf-8") as f:
                    self.tracked_senders = json.load(f)
                print(f"✓ {len(self.tracked_senders)} gönderici takip listesinden yüklendi")
            except:
                pass
    
    def save_tracked_senders(self):
        """Takip listesini kaydet"""
        tracker_file = "tracked_senders.json"
        try:
            with open(tracker_file, "w", encoding="utf-8") as f:
                json.dump(self.tracked_senders, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"✗ Takip listesi kaydedilemedi: {e}")
    
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
    
    def decode_header_value(self, value):
        """Header değerini decode et"""
        if value is None:
            return ""
        
        decoded_parts = decode_header(value)
        result = ""
        
        for content, encoding in decoded_parts:
            if isinstance(content, bytes):
                try:
                    result += content.decode(encoding or 'utf-8')
                except:
                    result += content.decode('utf-8', errors='ignore')
            else:
                result += str(content)
        
        return result
    
    def extract_email_address(self, from_field):
        """From alanından email adresini çıkar"""
        # Örnek: "Ali Veli <ali@example.com>" -> "ali@example.com"
        if "<" in from_field and ">" in from_field:
            return from_field.split("<")[1].split(">")[0].strip().lower()
        return from_field.strip().lower()
    
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
    
    def list_inbox_emails(self, limit=30):
        """INBOX'taki son mailleri listele"""
        try:
            self.mail.select("INBOX")
            
            # Son N maili al
            status, messages = self.mail.search(None, 'ALL')
            
            if status != "OK":
                return []
            
            email_ids = messages[0].split()
            email_ids = email_ids[-limit:]  # Son N mail
            email_ids.reverse()  # En yeni önce
            
            inbox_emails = []
            
            for idx, email_id in enumerate(email_ids, 1):
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject = self.decode_header_value(msg["Subject"])
                        from_field = msg.get("From", "")
                        date = msg.get("Date", "")
                        
                        inbox_emails.append({
                            "index": idx,
                            "subject": subject,
                            "from": from_field,
                            "from_email": self.extract_email_address(from_field),
                            "date": date,
                            "email_id": email_id
                        })
            
            return inbox_emails
            
        except Exception as e:
            print(f"✗ INBOX listelenemedi: {e}")
            return []
    
    def display_inbox_emails(self, inbox_emails):
        """INBOX maillerini ekrana yazdır"""
        print("\n" + "="*70)
        print("📥 GELEN KUTUSU - SON MAİLLER")
        print("="*70)
        
        for email_data in inbox_emails:
            # Takip ediliyor mu kontrolü
            tracking_marker = "🔔" if email_data['from_email'] in self.tracked_senders else "  "
            
            print(f"\n{tracking_marker}[{email_data['index']}] {email_data['subject'][:60]}")
            print(f"    Gönderen: {email_data['from'][:60]}")
            print(f"    Tarih: {email_data['date']}")
        
        print("\n" + "="*70)
        print("🔔 = Bu gönderici zaten takip ediliyor")
        print("="*70 + "\n")
    
    def select_senders_to_track(self, inbox_emails):
        """Kullanıcıdan takip edilecek göndericileri seç"""
        self.display_inbox_emails(inbox_emails)
        
        print("Takip etmek istediğiniz mail numaralarını virgülle ayırarak girin")
        print("Örnek: 1,3,5")
        print("Çıkmak için 'q', takip listesini görmek için 'list' yazın\n")
        
        user_input = input("Seçiminiz: ").strip().lower()
        
        if user_input == 'q':
            return False
        
        if user_input == 'list':
            self.show_tracked_senders()
            return self.select_senders_to_track(inbox_emails)
        
        try:
            selected_indices = [int(x.strip()) for x in user_input.split(',')]
        except:
            print("✗ Geçersiz giriş!")
            return False
        
        # Seçilen göndericileri takip listesine ekle
        added_count = 0
        for email_data in inbox_emails:
            if email_data['index'] in selected_indices:
                sender_email = email_data['from_email']
                
                if sender_email not in self.tracked_senders:
                    self.tracked_senders[sender_email] = {
                        "name": email_data['from'],
                        "added_at": datetime.now().isoformat(),
                        "sample_subject": email_data['subject']
                    }
                    added_count += 1
                    print(f"✅ Eklendi: {email_data['from']}")
                else:
                    print(f"ℹ️  Zaten takipte: {email_data['from']}")
        
        if added_count > 0:
            self.save_tracked_senders()
            print(f"\n🎉 {added_count} yeni gönderici takibe alındı!")
        
        return True
    
    def show_tracked_senders(self):
        """Takip edilen göndericileri göster"""
        print("\n" + "="*70)
        print("🔔 TAKİP EDİLEN GÖNDERİCİLER")
        print("="*70)
        
        if not self.tracked_senders:
            print("Henüz kimse takip edilmiyor.")
        else:
            for idx, (sender_email, data) in enumerate(self.tracked_senders.items(), 1):
                print(f"\n[{idx}] {data['name']}")
                print(f"    Email: {sender_email}")
                print(f"    Eklenme: {data['added_at']}")
        
        print("\n" + "="*70 + "\n")
    
    def save_email_to_file(self, email_data, msg, sender_email):
        """Maili dosyaya kaydet"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            email_id_str = email_data['id'].decode() if isinstance(email_data['id'], bytes) else str(email_data['id'])
            
            # Güvenli dosya adı için gönderici email'ini temizle
            safe_sender = sender_email.replace("@", "_at_").replace(".", "_")
            
            # JSON formatında kaydet
            json_filename = f"{timestamp}_{safe_sender}_{email_id_str}.json"
            json_path = os.path.join(self.save_folder, json_filename)
            
            # Ek dosya bilgilerini topla
            attachments = []
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_disposition() == "attachment":
                        filename = part.get_filename()
                        if filename:
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
                "sender_email": sender_email,
                "sender_name": self.tracked_senders[sender_email]['name'],
                "subject": email_data["subject"],
                "from": email_data["from"],
                "date": email_data["date"],
                "body": email_data["body"],
                "attachments": attachments,
                "saved_at": datetime.now().isoformat()
            }
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(email_json, f, ensure_ascii=False, indent=2)
            
            # .eml formatında da kaydet
            eml_filename = f"{timestamp}_{safe_sender}_{email_id_str}.eml"
            eml_path = os.path.join(self.save_folder, eml_filename)
            with open(eml_path, "wb") as f:
                f.write(msg.as_bytes())
            
            return json_path, eml_path
            
        except Exception as e:
            print(f"✗ Mail kaydetme hatası: {e}")
            return None, None
    
    def check_new_emails(self, skip_existing=False):
        """Takip edilen göndericilerden gelen yeni mailleri kontrol et"""
        try:
            self.mail.select("INBOX")
            
            # Tüm mailleri al
            status, messages = self.mail.search(None, 'ALL')
            
            if status != "OK":
                return []
            
            email_ids = messages[0].split()
            
            if skip_existing:
                # İlk çalıştırmada tüm mevcut mailleri işlenmiş olarak işaretle
                for email_id in email_ids:
                    self.processed_email_ids.add(email_id)
                print(f"ℹ️  {len(email_ids)} mevcut mail atlandı. Sadece yeni gelenler gösterilecek.")
                return []
            
            # Sadece daha önce işlenmemiş mailleri kontrol et
            new_email_ids = [eid for eid in email_ids if eid not in self.processed_email_ids]
            
            if not new_email_ids:
                return []
            
            triggered_emails = []
            
            for email_id in new_email_ids:
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        from_field = msg.get("From", "")
                        sender_email = self.extract_email_address(from_field)
                        
                        # Bu gönderici takip ediliyor mu?
                        if sender_email in self.tracked_senders:
                            subject = self.decode_header_value(msg["Subject"])
                            date = msg.get("Date", "")
                            body = self.get_email_body(msg)
                            
                            email_data = {
                                "id": email_id,
                                "subject": subject,
                                "from": from_field,
                                "date": date,
                                "body": body
                            }
                            
                            triggered_emails.append({
                                "email_data": email_data,
                                "msg": msg,
                                "sender_email": sender_email
                            })
                
                # Bu mail ID'sini işlenmiş olarak işaretle
                self.processed_email_ids.add(email_id)
            
            return triggered_emails
            
        except Exception as e:
            print(f"✗ Mail kontrol hatası: {e}")
            return []
    
    def display_triggered_email(self, trigger_info):
        """Tetiklenen maili ekrana yazdır"""
        email_data = trigger_info['email_data']
        sender_email = trigger_info['sender_email']
        sender_name = self.tracked_senders[sender_email]['name']
        
        print("\n" + "🎉"*35)
        print("🔔 TAKİP EDİLEN GÖNDERİCİDEN MAİL GELDİ!")
        print("🎉"*35)
        print(f"\n👤 Gönderici: {sender_name}")
        print(f"📧 Email: {sender_email}")
        print("-" * 70)
        print(f"📩 Konu: {email_data['subject']}")
        print(f"📅 Tarih: {email_data['date']}")
        print(f"\n💬 İçerik:\n{email_data['body'][:300]}...")
        print("\n" + "="*70 + "\n")
    
    def start_tracking(self):
        """Gönderici takibini başlat"""
        print("\n" + "="*70)
        print("📬 GÖNDERİCİ TAKİP SİSTEMİ")
        print("="*70)
        print("Seçtiğiniz göndericilerden gelen mailleri otomatik yakalar")
        print("="*70 + "\n")
        
        if not self.connect():
            return
        
        try:
            # Mevcut takip listesini göster
            if self.tracked_senders:
                self.show_tracked_senders()
                print("Yeni gönderici eklemek için devam edin veya 'start' yazıp dinlemeye başlayın")
                choice = input("\nYeni gönderici ekle (y), dinlemeye başla (start), çık (q): ").strip().lower()
                
                if choice == 'q':
                    print("\n👋 Çıkılıyor...")
                    return
                elif choice == 'start':
                    pass  # Direkt dinlemeye başla
                else:
                    # Inbox'tan mail listele
                    print("\n📥 INBOX'tan son mailler getiriliyor...\n")
                    inbox_emails = self.list_inbox_emails(limit=30)
                    
                    if not inbox_emails:
                        print("✗ Mail bulunamadı!")
                        return
                    
                    if not self.select_senders_to_track(inbox_emails):
                        print("\n👋 Çıkılıyor...")
                        return
            else:
                # İlk kez kullanılıyor, inbox'tan seç
                print("📥 INBOX'tan son mailler getiriliyor...\n")
                inbox_emails = self.list_inbox_emails(limit=30)
                
                if not inbox_emails:
                    print("✗ Mail bulunamadı!")
                    return
                
                if not self.select_senders_to_track(inbox_emails):
                    print("\n👋 Çıkılıyor...")
                    return
            
            # Şimdi dinlemeye başla
            print(f"\n🔍 Mail dinleme başlatıldı...")
            print(f"⏰ Kontrol aralığı: {self.check_interval} saniye")
            print(f"📂 Mailler kaydedilecek: {self.save_folder}/")
            print(f"🔄 Durdurmak için Ctrl+C\n")
            
            # İlk çalıştırmada mevcut mailleri atla
            print("Mevcut mailler kontrol ediliyor...")
            self.check_new_emails(skip_existing=True)
            print("✅ Hazır! Takip edilen göndericilerden gelecek yeni mailler yakalanacak.\n")
            
            while True:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] Mail kontrol ediliyor...")
                
                triggered = self.check_new_emails()
                
                if triggered:
                    for trigger_info in triggered:
                        self.display_triggered_email(trigger_info)
                        
                        # Maili kaydet
                        print("💾 Mail kaydediliyor...")
                        json_path, eml_path = self.save_email_to_file(
                            trigger_info['email_data'],
                            trigger_info['msg'],
                            trigger_info['sender_email']
                        )
                        if json_path:
                            print(f"✅ Mail kaydedildi:")
                            print(f"   📄 JSON: {json_path}")
                            print(f"   📧 EML: {eml_path}\n")
                        
                        # WhatsApp bildirimi gönder
                        if self.notification_manager:
                            sender_email = trigger_info['sender_email']
                            sender_name = self.tracked_senders.get(sender_email, {}).get('name', sender_email)
                            
                            # Ek dosya yollarını topla
                            attachment_paths = []
                            msg = trigger_info['msg']
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_disposition() == "attachment":
                                        filename = part.get_filename()
                                        if filename:
                                            attachment_path = os.path.join(self.save_folder, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
                                            if os.path.exists(attachment_path):
                                                attachment_paths.append(attachment_path)
                            
                            source = f"Gönderici Takip - {sender_name[:40]}"
                            
                            self.notification_manager.send_notification(
                                mail_data=trigger_info['email_data'],
                                source=source,
                                attachment_paths=attachment_paths if attachment_paths else None
                            )
                else:
                    print("📭 Yeni mail yok")
                
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹ Takip durduruldu")
        finally:
            self.disconnect()


def main():
    """Ana fonksiyon"""
    
    # =====================================
    # BURAYA KENDİ BİLGİLERİNİZİ GİRİN
    # =====================================
    
    IMAP_SERVER = "imap.gmail.com"
    EMAIL_ADDRESS = "krmbkc42@gmail.com"
    PASSWORD = "einz nuea scrs aozj"
    CHECK_INTERVAL = 15  # 15 saniyede bir kontrol
    
    # WhatsApp bildirimi (None ise bildirim gönderilmez)
    WHATSAPP_PHONE = "+905378284599"  # Kendi numaranız
    # WHATSAPP_PHONE = None  # Bildirimi kapatmak için
    
    # =====================================
    
    tracker = SenderTracker(
        imap_server=IMAP_SERVER,
        email_address=EMAIL_ADDRESS,
        password=PASSWORD,
        check_interval=CHECK_INTERVAL,
        whatsapp_phone=WHATSAPP_PHONE
    )
    
    tracker.start_tracking()


if __name__ == "__main__":
    main()

