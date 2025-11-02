import smtplib
import ssl
from email.message import EmailMessage

# E-posta gönderen ve alan bilgileri
gonderen_email = "krmbkc42@gmail.com"  # Sizin e-posta adresiniz
alici_email = "krmbkc42@gmail.com"    # Alıcının e-posta adresi
sifre = "einz nuea scrs aozj"

mesaj = EmailMessage()
mesaj['Subject'] = "Python ile Gönderilen E-posta"
mesaj['From'] = gonderen_email
mesaj['To'] = alici_email
mesaj.set_content("Bu, Python smtplib modülü kullanılarak gönderilmiş bir test e-postasıdır.")

# Güvenli SSL bağlantısı oluşturma
context = ssl.create_default_context()

try:
    # SMTP sunucusuna bağlanma (Gmail için)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(gonderen_email, sifre)  # Hesabınıza giriş yapma
        server.send_message(mesaj)           # E-postayı gönderme
    
    print("E-posta başarıyla gönderildi!")

except Exception as e:
    print(f"Bir hata oluştu: {e}")