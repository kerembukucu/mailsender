import imaplib
import email
from email.header import decode_header
import time
import os
import json
from datetime import datetime
from pathlib import Path
from notification_manager import MailNotificationManager

class ReplyTracker:
    """Gönderilen mailleri izler ve yanıtları yakalar"""
    
    def __init__(self, imap_server, email_address, password, check_interval=30, 
                 platform="telegram", telegram_token=None, telegram_chat_id=None, 
                 whatsapp_phone=None, throttle_seconds=300):
        """
        Args:
            imap_server (str): IMAP sunucu adresi
            email_address (str): Email adresi
            password (str): Email şifresi veya uygulama şifresi
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
        
        # Takip edilen mail'lerin Message-ID'leri ve konuları
        self.tracked_emails = {}  # {message_id: {"subject": "...", "to": "...", "date": "..."}}
        self.found_replies = set()  # Bulunan yanıtların ID'leri
        
        # Klasörler
        self.sent_folder = "[Gmail]/Sent Mail"  # Gmail için
        self.inbox_folder = "INBOX"
        
        # Yanıtları kaydet klasörü
        self.replies_folder = "tracked_replies"
        Path(self.replies_folder).mkdir(parents=True, exist_ok=True)
        
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
    
    def find_sent_folder(self):
        """Gönderilen mailler klasörünü bul"""
        # Tüm klasörleri listele
        try:
            status, folders = self.mail.list()
            if status != "OK":
                return None
            
            # Olası sent klasör isimleri
            possible_names = [
                "[Gmail]/G&APY-nderilmi&AV8- Postalar",  # Türkçe: Gönderilmiş Postalar (encoded)
                "[Gmail]/Sent Mail",
                "[Gmail]/G&APY-nderilmi&AV8- &ANY-&AVY-eler",  # Türkçe encoded alternatif
                "[Gmail]/Gönderilmiş Öğeler",
                "[Gmail]/Gönderilmiş Postalar",
                "[Gmail]/Gönderilen",
                "Sent",
                "INBOX.Sent",
                "Sent Items",
                "Sent Messages"
            ]
            
            # Önce bilinen isimleri dene
            for folder_name in possible_names:
                # Tırnak ile dene
                try:
                    status, response = self.mail.select(f'"{folder_name}"')
                    if status == "OK":
                        print(f"✓ Gönderilen mailler klasörü bulundu: {folder_name}")
                        return folder_name
                except:
                    pass
                
                # Tırnak olmadan dene
                try:
                    status, response = self.mail.select(folder_name)
                    if status == "OK":
                        print(f"✓ Gönderilen mailler klasörü bulundu: {folder_name}")
                        # Close yapmıyoruz - list_sent_emails tekrar select yapacak
                        return folder_name
                except Exception as e:
                    # Debug için hatayı görelim
                    if folder_name == "[Gmail]/G&APY-nderilmi&AV8- Postalar":
                        print(f"  Deneme hatası: {e}")
                    pass
            
            # Tüm klasörlerde "Sent", "Gönder", "G&" içerenleri ara
            for folder in folders:
                folder_str = folder.decode('utf-8', errors='ignore')
                folder_name = folder_str.split('"')[-2] if '"' in folder_str else ""
                
                if any(keyword in folder_name.lower() for keyword in ['sent', 'gönder', 'g&']):
                    try:
                        status, _ = self.mail.select(folder_name)
                        if status == "OK":
                            print(f"✓ Gönderilen mailler klasörü bulundu: {folder_name}")
                            # Close yapmıyoruz - list_sent_emails tekrar select yapacak
                            return folder_name
                    except:
                        pass
            
            return None
            
        except Exception as e:
            print(f"Klasör arama hatası: {e}")
            return None
    
    def select_folder(self, folder_name):
        """Klasörü seç (özel karakterler için farklı yöntemler dene)"""
        # Tırnak ile dene
        try:
            status, _ = self.mail.select(f'"{folder_name}"')
            if status == "OK":
                return True
        except:
            pass
        
        # Tırnak olmadan dene
        try:
            status, _ = self.mail.select(folder_name)
            if status == "OK":
                return True
        except:
            pass
        
        return False
    
    def list_sent_emails(self, limit=20):
        """Gönderilen mailleri listele"""
        try:
            # Önce sent klasörünü bul ve seç
            if not self.sent_folder or self.sent_folder == "[Gmail]/Sent Mail":
                found_folder = self.find_sent_folder()
                if found_folder:
                    self.sent_folder = found_folder
                    # find_sent_folder içinde zaten select başarılı oldu, tekrar seçmeye gerek yok
                else:
                    print("✗ Gönderilen mailler klasörü bulunamadı")
                    print("\nMevcut klasörler:")
                    status, folders = self.mail.list()
                    if status == "OK":
                        for folder in folders[:20]:  # İlk 20 klasörü göster
                            print(f"  {folder.decode('utf-8', errors='ignore')}")
                    return []
            else:
                # Klasör zaten biliniyorsa tekrar seç
                if not self.select_folder(self.sent_folder):
                    print(f"✗ Klasör seçilemedi: {self.sent_folder}")
                    return []
            
            # Tüm mailleri al (en yeni başta)
            status, messages = self.mail.search(None, 'ALL')
            
            if status != "OK":
                return []
            
            email_ids = messages[0].split()
            email_ids = email_ids[-limit:]  # Son N mail
            email_ids.reverse()  # En yeni önce
            
            sent_emails = []
            
            for idx, email_id in enumerate(email_ids, 1):
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        message_id = msg.get("Message-ID", "")
                        subject = self.decode_header_value(msg["Subject"])
                        to_address = msg.get("To", "")
                        date = msg.get("Date", "")
                        
                        sent_emails.append({
                            "index": idx,
                            "message_id": message_id,
                            "subject": subject,
                            "to": to_address,
                            "date": date,
                            "email_id": email_id
                        })
            
            return sent_emails
            
        except Exception as e:
            print(f"✗ Gönderilen mailler listelenemedi: {e}")
            return []
    
    def display_sent_emails(self, sent_emails):
        """Gönderilen mailleri ekrana yazdır"""
        print("\n" + "="*70)
        print("📤 SON GÖNDERİLEN MAİLLER")
        print("="*70)
        
        for email_data in sent_emails:
            print(f"\n[{email_data['index']}] {email_data['subject']}")
            print(f"    Kime: {email_data['to']}")
            print(f"    Tarih: {email_data['date']}")
        
        print("\n" + "="*70 + "\n")
    
    def select_emails_to_track(self, sent_emails):
        """Kullanıcıdan takip edilecek mailleri seç"""
        self.display_sent_emails(sent_emails)
        
        print("Takip etmek istediğiniz mail numaralarını virgülle ayırarak girin")
        print("Örnek: 1,3,5 veya tümünü takip etmek için 'all' yazın")
        print("Çıkmak için 'q' yazın\n")
        
        user_input = input("Seçiminiz: ").strip().lower()
        
        if user_input == 'q':
            return False
        
        if user_input == 'all':
            selected_indices = [e['index'] for e in sent_emails]
        else:
            try:
                selected_indices = [int(x.strip()) for x in user_input.split(',')]
            except:
                print("✗ Geçersiz giriş!")
                return False
        
        # Seçilen mailleri tracked_emails'e ekle
        for email_data in sent_emails:
            if email_data['index'] in selected_indices:
                message_id = email_data['message_id']
                self.tracked_emails[message_id] = {
                    "subject": email_data['subject'],
                    "to": email_data['to'],
                    "date": email_data['date']
                }
        
        print(f"\n✅ {len(selected_indices)} mail takibe alındı!")
        print("\nTakip edilen mailler:")
        for msg_id, data in self.tracked_emails.items():
            print(f"  • {data['subject']}")
        
        return True
    
    def check_for_replies(self):
        """Takip edilen maillere gelen yanıtları kontrol et"""
        try:
            # INBOX'ı seç
            if not self.select_folder(self.inbox_folder):
                print(f"✗ INBOX seçilemedi")
                return []
            
            # Tüm mailleri al
            status, messages = self.mail.search(None, 'ALL')
            
            if status != "OK":
                return []
            
            email_ids = messages[0].split()
            new_replies = []
            
            for email_id in email_ids:
                # Bu mail ID'sini daha önce işledik mi?
                if email_id in self.found_replies:
                    continue
                
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # In-Reply-To header'ını kontrol et
                        in_reply_to = msg.get("In-Reply-To", "")
                        references = msg.get("References", "")
                        
                        # Bu mail, takip ettiğimiz maillerden birine yanıt mı?
                        is_reply = False
                        replied_to = None
                        
                        for tracked_msg_id in self.tracked_emails.keys():
                            if tracked_msg_id in in_reply_to or tracked_msg_id in references:
                                is_reply = True
                                replied_to = tracked_msg_id
                                break
                        
                        if is_reply:
                            # Yanıt bulundu!
                            subject = self.decode_header_value(msg["Subject"])
                            from_address = msg.get("From", "")
                            date = msg.get("Date", "")
                            body = self.get_email_body(msg)
                            
                            reply_data = {
                                "email_id": email_id,
                                "replied_to_message_id": replied_to,
                                "replied_to_subject": self.tracked_emails[replied_to]['subject'],
                                "subject": subject,
                                "from": from_address,
                                "date": date,
                                "body": body,
                                "msg": msg
                            }
                            
                            new_replies.append(reply_data)
                            self.found_replies.add(email_id)
            
            return new_replies
            
        except Exception as e:
            print(f"✗ Yanıt kontrol hatası: {e}")
            return []
    
    def save_reply(self, reply_data):
        """Yanıt mailini kaydet"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            email_id_str = reply_data['email_id'].decode() if isinstance(reply_data['email_id'], bytes) else str(reply_data['email_id'])
            
            # JSON formatında kaydet
            json_filename = f"{timestamp}_reply_{email_id_str}.json"
            json_path = os.path.join(self.replies_folder, json_filename)
            
            email_json = {
                "id": email_id_str,
                "replied_to_message_id": reply_data['replied_to_message_id'],
                "replied_to_subject": reply_data['replied_to_subject'],
                "subject": reply_data['subject'],
                "from": reply_data['from'],
                "date": reply_data['date'],
                "body": reply_data['body'],
                "saved_at": datetime.now().isoformat()
            }
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(email_json, f, ensure_ascii=False, indent=2)
            
            # .eml formatında da kaydet
            eml_filename = f"{timestamp}_reply_{email_id_str}.eml"
            eml_path = os.path.join(self.replies_folder, eml_filename)
            with open(eml_path, "wb") as f:
                f.write(reply_data['msg'].as_bytes())
            
            return json_path, eml_path
            
        except Exception as e:
            print(f"✗ Yanıt kaydetme hatası: {e}")
            return None, None
    
    def display_reply(self, reply_data):
        """Yanıtı ekrana yazdır"""
        print("\n" + "🎉"*35)
        print("🔔 YANITLANMIŞ MAİL BULUNDU!")
        print("🎉"*35)
        print(f"\n📧 Orijinal Mail: {reply_data['replied_to_subject']}")
        print("-" * 70)
        print(f"📩 Yanıt Konusu: {reply_data['subject']}")
        print(f"👤 Yanıtlayan: {reply_data['from']}")
        print(f"📅 Tarih: {reply_data['date']}")
        print(f"\n💬 İçerik:\n{reply_data['body'][:300]}...")
        print("\n" + "="*70 + "\n")
    
    def start_tracking(self):
        """Mail takibini başlat"""
        print("\n" + "="*70)
        print("📬 YANITLANMA TAKİP SİSTEMİ")
        print("="*70)
        print("Gmail'den gönderdiğiniz maillere gelen yanıtları takip eder")
        print("="*70 + "\n")
        
        if not self.connect():
            return
        
        try:
            # Önce gönderilen mailleri listele
            print("📤 Gönderilen mailler getiriliyor...\n")
            sent_emails = self.list_sent_emails(limit=20)
            
            if not sent_emails:
                print("✗ Gönderilen mail bulunamadı!")
                return
            
            # Kullanıcıdan takip edilecek mailleri seç
            if not self.select_emails_to_track(sent_emails):
                print("\n👋 Çıkılıyor...")
                return
            
            # Şimdi sürekli yanıt kontrolü yap
            print(f"\n🔍 Yanıt kontrolü başlatıldı...")
            print(f"⏰ Kontrol aralığı: {self.check_interval} saniye")
            print(f"📂 Yanıtlar kaydedilecek: {self.replies_folder}/")
            print(f"🔄 Durdurmak için Ctrl+C\n")
            
            while True:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] Yanıtlar kontrol ediliyor...")
                
                replies = self.check_for_replies()
                
                if replies:
                    for reply in replies:
                        self.display_reply(reply)
                        
                        # Yanıtı kaydet
                        print("💾 Yanıt kaydediliyor...")
                        json_path, eml_path = self.save_reply(reply)
                        if json_path:
                            print(f"✅ Yanıt kaydedildi:")
                            print(f"   📄 JSON: {json_path}")
                            print(f"   📧 EML: {eml_path}\n")
                        
                        # WhatsApp bildirimi gönder
                        if self.notification_manager:
                            mail_data = {
                                "subject": reply['subject'],
                                "from": reply['from'],
                                "body": reply['body'],
                                "date": reply['date']
                            }
                            
                            source = f"Yanıt Takip - {reply['replied_to_subject'][:30]}..."
                            
                            # EML dosyasını attachment olarak ekle
                            attachment_paths = [eml_path] if eml_path and os.path.exists(eml_path) else None
                            
                            self.notification_manager.send_notification(
                                mail_data=mail_data,
                                source=source,
                                attachment_paths=attachment_paths
                            )
                else:
                    print("📭 Yeni yanıt yok")
                
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
    
    tracker = ReplyTracker(
        imap_server=IMAP_SERVER,
        email_address=EMAIL_ADDRESS,
        password=PASSWORD,
        check_interval=CHECK_INTERVAL,
        whatsapp_phone=WHATSAPP_PHONE
    )
    
    tracker.start_tracking()


if __name__ == "__main__":
    main()

