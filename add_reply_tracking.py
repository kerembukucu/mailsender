"""
Yanıt takibi ekle
Config dosyasına yanıt takibi eklemek için bu script'i kullanın
"""
import sys
from run import ConfigManager


def main():
    """Yanıt takibi ekle"""
    
    print("="*70)
    print("💬 YANIT TAKİBİ EKLE - Config'e yanıt takibi ekleyin")
    print("="*70 + "\n")
    
    # Config yükle
    config_manager = ConfigManager()
    
    print("ℹ️  Yanıt takibi eklemek için gönderdiğiniz mailin Message-ID'sine ihtiyacınız var.")
    print("   Message-ID'yi bulmak için:")
    print("   1. Gmail'de gönderdiğiniz maili açın")
    print("   2. 'Show original' veya 'Orijinali göster' tıklayın")
    print("   3. 'Message-ID' alanını kopyalayın")
    print("   Örnek: <CABcdefg123456@mail.gmail.com>\n")
    
    print("Takip edilecek mailin bilgilerini girin:\n")
    
    message_id = input("🔑 Message-ID: ").strip()
    if not message_id:
        print("✗ Message-ID boş olamaz!")
        return
    
    subject = input("📩 Mail konusu: ").strip()
    if not subject:
        subject = "Konu belirtilmedi"
    
    to = input("📧 Gönderilen kişi: ").strip()
    if not to:
        to = "Belirtilmedi"
    
    from datetime import datetime
    date = datetime.now().isoformat()
    
    # Config'e ekle
    config_manager.add_reply_tracking(message_id, subject, to, date)
    
    print(f"\n✅ Başarılı! Yanıt takibi config'e eklendi.")
    print(f"📂 Config dosyası: {config_manager.config_file}")
    print(f"\n🚀 Şimdi run.py'yi çalıştırabilirsiniz:")
    print(f"   python run.py")
    print(f"\n💡 İpucu: track_replies.py ile interaktif olarak da seçim yapabilirsiniz:")
    print(f"   python track_replies.py")


if __name__ == "__main__":
    main()

