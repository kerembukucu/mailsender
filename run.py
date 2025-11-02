import threading
import time
import json
import os
from receieveit import MailReceiver
from track_replies import ReplyTracker
from track_senders import SenderTracker


class ConfigManager:
    """Merkezi config yöneticisi"""
    
    def __init__(self, config_file="mail_tracking_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Config dosyasını yükle"""
        if not os.path.exists(self.config_file):
            print(f"⚠️  Config dosyası bulunamadı: {self.config_file}")
            print("   Varsayılan config oluşturuluyor...")
            return self.create_default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"✓ Config yüklendi: {self.config_file}")
            return config
        except Exception as e:
            print(f"✗ Config yükleme hatası: {e}")
            return self.create_default_config()
    
    def save_config(self):
        """Config dosyasını kaydet"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"✓ Config kaydedildi: {self.config_file}")
        except Exception as e:
            print(f"✗ Config kaydetme hatası: {e}")
    
    def create_default_config(self):
        """Varsayılan config oluştur"""
        return {
            "email_settings": {
                "imap_server": "imap.gmail.com",
                "email_address": "",
                "password": "",
                "check_interval": 30
            },
            "notification_settings": {
                "platform": "telegram",
                "throttle_seconds": 300,
                "telegram": {
                    "bot_token": "",
                    "chat_id": "",
                    "enabled": False
                },
                "whatsapp": {
                    "phone_number": "",
                    "enabled": False
                }
            },
            "keyword_tracking": {
                "enabled": False,
                "keywords": [],
                "save_folder": "tracked_keyword_mails"
            },
            "sender_tracking": {
                "enabled": False,
                "tracked_senders": {},
                "save_folder": "tracked_sender_mails"
            },
            "reply_tracking": {
                "enabled": False,
                "tracked_message_ids": {},
                "save_folder": "tracked_replies"
            }
        }
    
    def add_sender(self, email, name, sample_subject=""):
        """Takip edilecek gönderici ekle"""
        from datetime import datetime
        
        if "sender_tracking" not in self.config:
            self.config["sender_tracking"] = {"enabled": True, "tracked_senders": {}, "save_folder": "tracked_sender_mails"}
        
        self.config["sender_tracking"]["tracked_senders"][email] = {
            "name": name,
            "added_at": datetime.now().isoformat(),
            "sample_subject": sample_subject
        }
        self.config["sender_tracking"]["enabled"] = True
        self.save_config()
        print(f"✓ Gönderici eklendi: {name} ({email})")
    
    def add_reply_tracking(self, message_id, subject, to, date):
        """Takip edilecek mail yanıtı ekle"""
        from datetime import datetime
        
        if "reply_tracking" not in self.config:
            self.config["reply_tracking"] = {"enabled": True, "tracked_message_ids": {}, "save_folder": "tracked_replies"}
        
        self.config["reply_tracking"]["tracked_message_ids"][message_id] = {
            "subject": subject,
            "to": to,
            "date": date,
            "added_at": datetime.now().isoformat()
        }
        self.config["reply_tracking"]["enabled"] = True
        self.save_config()
        print(f"✓ Yanıt takibi eklendi: {subject}")


class UnifiedMailTracker:
    """Tüm mail takip sistemlerini birleştirir ve yönetir"""
    
    def __init__(self, config_manager):
        """
        Args:
            config_manager (ConfigManager): Config yöneticisi
        """
        self.config_manager = config_manager
        self.config = config_manager.config
        self.threads = []
        self.running = False
    
    def start_keyword_tracker(self):
        """Anahtar kelime takip sistemini başlat (receieveit.py)"""
        try:
            print("\n🔑 Anahtar Kelime Takip Sistemi başlatılıyor...")
            
            keyword_config = self.config.get('keyword_tracking', {})
            email_settings = self.config.get('email_settings', {})
            notification_settings = self.config.get('notification_settings', {})
            
            keywords = keyword_config.get('keywords', [])
            if not keywords:
                print("   ⚠️  Anahtar kelime tanımlanmamış, atlanıyor...")
                return
            
            # Platform seçimine göre parametreleri hazırla
            platform = notification_settings.get('platform', 'telegram')
            telegram_settings = notification_settings.get('telegram', {})
            whatsapp_settings = notification_settings.get('whatsapp', {})
            
            receiver = MailReceiver(
                imap_server=email_settings.get('imap_server'),
                email_address=email_settings.get('email_address'),
                password=email_settings.get('password'),
                check_interval=email_settings.get('check_interval', 30),
                trigger_keywords=keywords,
                save_folder=keyword_config.get('save_folder', 'tracked_keyword_mails'),
                platform=platform,
                telegram_token=telegram_settings.get('bot_token') if platform == 'telegram' and telegram_settings.get('enabled') else None,
                telegram_chat_id=telegram_settings.get('chat_id') if platform == 'telegram' and telegram_settings.get('enabled') else None,
                whatsapp_phone=whatsapp_settings.get('phone_number') if platform == 'whatsapp' and whatsapp_settings.get('enabled') else None,
                throttle_seconds=notification_settings.get('throttle_seconds', 300)
            )
            
            receiver.start_listening()
            
        except KeyboardInterrupt:
            print("\n   ⚠️ Anahtar Kelime Takip durduruldu (Ctrl+C)")
            self.running = False
            raise  # Ana loop'a fırlat
        except SystemExit:
            print("\n   ⚠️ Thread sonlandı (WhatsApp gönderimi sonrası normal)")
            # Bu normal - tab_close=True kullandığımızda olabilir
            # Thread'i yeniden başlat
            print("   🔄 Sistem yeniden başlatılıyor...")
            time.sleep(2)
            if self.running:
                self.start_keyword_tracker()  # Kendini yeniden başlat
        except Exception as e:
            print(f"✗ Anahtar Kelime Takip hatası: {e}")
            print("   ℹ️  Diğer sistemler çalışmaya devam edecek...")
            import traceback
            traceback.print_exc()
    
    def start_reply_tracker_auto(self):
        """Yanıt takip sistemini otomatik başlat (config'ten)"""
        try:
            print("\n💬 Yanıt Takip Sistemi başlatılıyor...")
            
            reply_config = self.config.get('reply_tracking', {})
            email_settings = self.config.get('email_settings', {})
            notification_settings = self.config.get('notification_settings', {})
            
            tracked_message_ids = reply_config.get('tracked_message_ids', {})
            if not tracked_message_ids:
                print("   ⚠️  Takip edilen mail bulunamadı, atlanıyor...")
                print("   💡 Config dosyasına mail ekleyin veya interaktif mod kullanın:")
                print("      python track_replies.py")
                return
            
            # Platform seçimine göre parametreleri hazırla
            platform = notification_settings.get('platform', 'telegram')
            telegram_settings = notification_settings.get('telegram', {})
            whatsapp_settings = notification_settings.get('whatsapp', {})
            
            tracker = ReplyTracker(
                imap_server=email_settings.get('imap_server'),
                email_address=email_settings.get('email_address'),
                password=email_settings.get('password'),
                check_interval=email_settings.get('check_interval', 30),
                platform=platform,
                telegram_token=telegram_settings.get('bot_token') if platform == 'telegram' and telegram_settings.get('enabled') else None,
                telegram_chat_id=telegram_settings.get('chat_id') if platform == 'telegram' and telegram_settings.get('enabled') else None,
                whatsapp_phone=whatsapp_settings.get('phone_number') if platform == 'whatsapp' and whatsapp_settings.get('enabled') else None,
                throttle_seconds=notification_settings.get('throttle_seconds', 300)
            )
            
            # Config'ten tracked emails'leri yükle
            tracker.tracked_emails = tracked_message_ids
            
            # Bağlan
            if not tracker.connect():
                return
            
            print(f"   ✓ {len(tracked_message_ids)} mail takip ediliyor:")
            for msg_id, data in tracked_message_ids.items():
                print(f"     • {data.get('subject', 'No subject')}")
            
            # Yanıt kontrolü loop'u
            while self.running:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{timestamp}] Yanıtlar kontrol ediliyor...")
                
                replies = tracker.check_for_replies()
                
                if replies:
                    for reply in replies:
                        tracker.display_reply(reply)
                        
                        # Yanıtı kaydet
                        print("💾 Yanıt kaydediliyor...")
                        json_path, eml_path = tracker.save_reply(reply)
                        if json_path:
                            print(f"✅ Yanıt kaydedildi:")
                            print(f"   📄 JSON: {json_path}")
                            print(f"   📧 EML: {eml_path}\n")
                        
                        # WhatsApp bildirimi
                        if tracker.notification_manager:
                            mail_data = {
                                "subject": reply['subject'],
                                "from": reply['from'],
                                "body": reply['body'],
                                "date": reply['date']
                            }
                            source = f"Yanıt Takip - {reply['replied_to_subject'][:30]}..."
                            tracker.notification_manager.send_notification(
                                mail_data=mail_data,
                                source=source,
                                attachment_paths=[eml_path] if eml_path and os.path.exists(eml_path) else None
                            )
                else:
                    print("📭 Yeni yanıt yok")
                
                time.sleep(email_settings.get('check_interval', 30))
            
            tracker.disconnect()
            
        except Exception as e:
            print(f"✗ Yanıt Takip hatası: {e}")
    
    def start_sender_tracker_auto(self):
        """Gönderici takip sistemini otomatik başlat (config'ten)"""
        try:
            print("\n👤 Gönderici Takip Sistemi başlatılıyor...")
            
            sender_config = self.config.get('sender_tracking', {})
            email_settings = self.config.get('email_settings', {})
            notification_settings = self.config.get('notification_settings', {})
            
            tracked_senders = sender_config.get('tracked_senders', {})
            if not tracked_senders:
                print("   ⚠️  Takip edilen gönderici bulunamadı, atlanıyor...")
                print("   💡 Config dosyasına gönderici ekleyin veya interaktif mod kullanın:")
                print("      python track_senders.py")
                return
            
            # Platform seçimine göre parametreleri hazırla
            platform = notification_settings.get('platform', 'telegram')
            telegram_settings = notification_settings.get('telegram', {})
            whatsapp_settings = notification_settings.get('whatsapp', {})
            
            tracker = SenderTracker(
                imap_server=email_settings.get('imap_server'),
                email_address=email_settings.get('email_address'),
                password=email_settings.get('password'),
                check_interval=email_settings.get('check_interval', 30),
                platform=platform,
                telegram_token=telegram_settings.get('bot_token') if platform == 'telegram' and telegram_settings.get('enabled') else None,
                telegram_chat_id=telegram_settings.get('chat_id') if platform == 'telegram' and telegram_settings.get('enabled') else None,
                whatsapp_phone=whatsapp_settings.get('phone_number') if platform == 'whatsapp' and whatsapp_settings.get('enabled') else None,
                throttle_seconds=notification_settings.get('throttle_seconds', 300)
            )
            
            # Config'ten tracked senders'ları yükle
            tracker.tracked_senders = tracked_senders
            
            # Bağlan
            if not tracker.connect():
                return
            
            print(f"   ✓ {len(tracked_senders)} gönderici takip ediliyor:")
            for email, data in tracked_senders.items():
                print(f"     • {data.get('name', email)}")
            
            # İlk çalıştırmada mevcut mailleri atla
            print("\n   Mevcut mailler kontrol ediliyor...")
            tracker.check_new_emails(skip_existing=True)
            print("   ✅ Hazır! Takip edilen göndericilerden gelecek yeni mailler yakalanacak.")
            
            # Mail kontrolü loop'u
            while self.running:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{timestamp}] Mail kontrol ediliyor...")
                
                triggered = tracker.check_new_emails()
                
                if triggered:
                    for trigger_info in triggered:
                        tracker.display_triggered_email(trigger_info)
                        
                        # Maili kaydet
                        print("💾 Mail kaydediliyor...")
                        json_path, eml_path = tracker.save_email_to_file(
                            trigger_info['email_data'],
                            trigger_info['msg'],
                            trigger_info['sender_email']
                        )
                        if json_path:
                            print(f"✅ Mail kaydedildi:")
                            print(f"   📄 JSON: {json_path}")
                            print(f"   📧 EML: {eml_path}\n")
                        
                        # WhatsApp bildirimi
                        if tracker.notification_manager:
                            sender_email = trigger_info['sender_email']
                            sender_name = tracker.tracked_senders.get(sender_email, {}).get('name', sender_email)
                            
                            # Ek dosya yolları
                            attachment_paths = []
                            msg = trigger_info['msg']
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_disposition() == "attachment":
                                        filename = part.get_filename()
                                        if filename:
                                            from datetime import datetime
                                            attachment_path = os.path.join(tracker.save_folder, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
                                            if os.path.exists(attachment_path):
                                                attachment_paths.append(attachment_path)
                            
                            source = f"Gönderici Takip - {sender_name[:40]}"
                            tracker.notification_manager.send_notification(
                                mail_data=trigger_info['email_data'],
                                source=source,
                                attachment_paths=attachment_paths if attachment_paths else None
                            )
                else:
                    print("📭 Yeni mail yok")
                
                time.sleep(email_settings.get('check_interval', 30))
            
            tracker.disconnect()
            
        except Exception as e:
            print(f"✗ Gönderici Takip hatası: {e}")
    
    def start_all(self):
        """Tüm etkin takip sistemlerini başlat"""
        self.running = True
        
        print("="*70)
        print("🚀 BİRLEŞİK MAİL TAKİP SİSTEMİ")
        print("="*70)
        print(f"📧 Email: {self.config['email_settings'].get('email_address')}")
        
        # Bildirim platformu bilgisi
        notification_settings = self.config.get('notification_settings', {})
        platform = notification_settings.get('platform', 'telegram')
        if platform == 'telegram':
            telegram = notification_settings.get('telegram', {})
            print(f"📱 Bildirim: Telegram (Chat ID: {telegram.get('chat_id', 'Yok')}) {'✓' if telegram.get('enabled') else '✗'}")
        elif platform == 'whatsapp':
            whatsapp = notification_settings.get('whatsapp', {})
            print(f"📱 Bildirim: WhatsApp ({whatsapp.get('phone_number', 'Yok')}) {'✓' if whatsapp.get('enabled') else '✗'}")
        else:
            print(f"📱 Bildirim: Devre dışı")
        
        print(f"⏰ Kontrol aralığı: {self.config['email_settings'].get('check_interval', 30)} saniye")
        print("="*70 + "\n")
        
        # Anahtar kelime takibi
        if self.config.get('keyword_tracking', {}).get('enabled'):
            thread = threading.Thread(
                target=self.start_keyword_tracker,
                daemon=True,
                name="KeywordTracker"
            )
            thread.start()
            self.threads.append(thread)
            time.sleep(2)
        
        # Yanıt takibi (otomatik)
        if self.config.get('reply_tracking', {}).get('enabled'):
            thread = threading.Thread(
                target=self.start_reply_tracker_auto,
                daemon=True,
                name="ReplyTracker"
            )
            thread.start()
            self.threads.append(thread)
            time.sleep(2)
        
        # Gönderici takibi (otomatik)
        if self.config.get('sender_tracking', {}).get('enabled'):
            thread = threading.Thread(
                target=self.start_sender_tracker_auto,
                daemon=True,
                name="SenderTracker"
            )
            thread.start()
            self.threads.append(thread)
            time.sleep(2)
        
        # Ana thread'i canlı tut
        try:
            print("\n✅ Sistemler çalışıyor...")
            print("🔄 Durdurmak için Ctrl+C basın\n")
            
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n⏹ Tüm sistemler durduruluyor...")
            self.running = False
        
        # Thread'lerin bitmesini bekle
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        print("✓ Tüm sistemler durduruldu")


def main():
    """Ana fonksiyon - Config'ten tüm takip sistemlerini başlat"""
    
    # Config yöneticisini oluştur
    config_manager = ConfigManager("mail_tracking_config.json")
    
    # Birleşik takip sistemini başlat
    tracker = UnifiedMailTracker(config_manager)
    tracker.start_all()


if __name__ == "__main__":
    main()
