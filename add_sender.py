"""
Takip edilecek gönderici ekle
Config dosyasına yeni gönderici eklemek için bu script'i kullanın
"""
import sys
from run import ConfigManager


def main():
    """Gönderici ekle"""
    
    print("="*70)
    print("👤 GÖNDERİCİ EKLE - Config'e yeni gönderici ekleyin")
    print("="*70 + "\n")
    
    # Config yükle
    config_manager = ConfigManager()
    
    # Kullanıcıdan bilgi al
    print("Takip edilecek göndericinin bilgilerini girin:\n")
    
    email = input("📧 Email adresi: ").strip()
    if not email:
        print("✗ Email adresi boş olamaz!")
        return
    
    name = input("👤 İsim (örn: Ali Veli <ali@example.com>): ").strip()
    if not name:
        name = email
    
    sample_subject = input("📩 Örnek konu (opsiyonel): ").strip()
    
    # Config'e ekle
    config_manager.add_sender(email, name, sample_subject)
    
    print(f"\n✅ Başarılı! Gönderici config'e eklendi.")
    print(f"📂 Config dosyası: {config_manager.config_file}")
    print(f"\n🚀 Şimdi run.py'yi çalıştırabilirsiniz:")
    print(f"   python run.py")


if __name__ == "__main__":
    main()

